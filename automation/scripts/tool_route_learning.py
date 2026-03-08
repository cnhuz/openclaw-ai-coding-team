#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from lockfile import acquire, release


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_iso(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def load_attempts(root: Path, lookback_days: int) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    cutoff = datetime.now().astimezone().timestamp() - lookback_days * 86400
    result: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                continue
            attempted_at = parse_iso(item.get("attempted_at"))
            if attempted_at < cutoff:
                continue
            result.append(item)
    return result


def sort_tools(counter: dict[str, int]) -> list[str]:
    return [tool_id for tool_id, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def weighted_quality(item: dict[str, Any]) -> int:
    quality = item.get("quality")
    if quality == "strong":
        return 4
    if quality == "medium":
        return 3
    if quality == "weak":
        return 2
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn per-site tool preferences from recorded attempts.")
    parser.add_argument("--site-profiles", default="data/research/site_profiles.json")
    parser.add_argument("--attempts-root", default="data/research/tool_attempts")
    parser.add_argument("--lock", default="data/research/_state/research.lock")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    site_profiles_path = Path(args.site_profiles).expanduser()
    attempts_root = Path(args.attempts_root).expanduser()
    lock_path = Path(args.lock).expanduser()

    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire research lock: {lock_path}")

    try:
        payload = load_json(site_profiles_path, {"schemaVersion": 1, "updatedAt": None, "sites": [], "settings": {}})
        sites = payload.get("sites")
        if not isinstance(sites, list):
            sites = []
            payload["sites"] = sites
        attempts = load_attempts(attempts_root, args.lookback_days)

        success_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        failure_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        quality_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        frontier_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        failure_kind_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        latest_attempt: dict[str, dict[str, Any]] = {}
        latest_success: dict[str, dict[str, Any]] = {}

        for item in attempts:
            site_id = item.get("site_id")
            tool_id = item.get("tool_id")
            if not isinstance(site_id, str) or not site_id or not isinstance(tool_id, str) or not tool_id:
                continue
            outcome = item.get("outcome")
            weight = weighted_quality(item)
            target_kind = item.get("target_kind")
            if outcome == "success":
                success_counter[site_id][tool_id] += weight
                quality_counter[site_id][tool_id] += weight
                if isinstance(target_kind, str) and target_kind:
                    frontier_counter[site_id][target_kind] += weight
                existing_success = latest_success.get(site_id)
                if existing_success is None or parse_iso(item.get("attempted_at")) >= parse_iso(existing_success.get("attempted_at")):
                    latest_success[site_id] = item
            elif outcome == "partial":
                success_counter[site_id][tool_id] += max(weight - 1, 1)
                quality_counter[site_id][tool_id] += max(weight - 1, 1)
                if isinstance(target_kind, str) and target_kind:
                    frontier_counter[site_id][target_kind] += max(weight - 1, 1)
            elif outcome == "failure":
                failure_counter[site_id][tool_id] += 1
                failure_kind = item.get("failure_kind")
                if isinstance(failure_kind, str) and failure_kind:
                    failure_kind_counter[site_id][failure_kind] += 1
            existing_attempt = latest_attempt.get(site_id)
            if existing_attempt is None or parse_iso(item.get("attempted_at")) >= parse_iso(existing_attempt.get("attempted_at")):
                latest_attempt[site_id] = item

        updated_sites = 0
        for site in sites:
            if not isinstance(site, dict):
                continue
            site_id = site.get("site_id")
            if not isinstance(site_id, str) or not site_id:
                continue

            learning = site.get("learning")
            if not isinstance(learning, dict):
                learning = {}
                site["learning"] = learning

            site_success = success_counter.get(site_id, {})
            site_failure = failure_counter.get(site_id, {})
            site_quality = quality_counter.get(site_id, {})
            site_frontier = frontier_counter.get(site_id, {})
            site_failure_kind = failure_kind_counter.get(site_id, {})
            learning["success_by_tool"] = dict(sorted(site_success.items()))
            learning["failure_by_tool"] = dict(sorted(site_failure.items()))
            learning["quality_by_tool"] = dict(sorted(site_quality.items()))
            learning["failure_by_kind"] = dict(sorted(site_failure_kind.items()))
            learning["preferred_frontier_kinds"] = sort_tools(site_frontier)
            learning["learned_preferred_tools"] = [
                tool_id
                for tool_id, _ in sorted(
                    site_success.items(),
                    key=lambda item: (-(item[1] - site_failure.get(item[0], 0)), -site_quality.get(item[0], 0), item[0]),
                )
            ]
            learning["learned_avoid_tools"] = [
                tool_id
                for tool_id, count in sorted(site_failure.items(), key=lambda item: (-item[1], item[0]))
                if count >= 2 and site_success.get(tool_id, 0) == 0
            ]

            success_item = latest_success.get(site_id)
            if success_item is not None:
                learning["last_successful_tool"] = success_item.get("tool_id")
            attempt_item = latest_attempt.get(site_id)
            if attempt_item is not None:
                learning["last_failure_kind"] = attempt_item.get("failure_kind") if attempt_item.get("outcome") == "failure" else None
                learning["last_seen_at"] = attempt_item.get("attempted_at")
            if site_failure_kind.get("login-required", 0) >= 2:
                site["access"] = "login-required"
            elif site_failure_kind.get("blocked", 0) + site_failure_kind.get("captcha", 0) >= 2 and site.get("access") == "public":
                site["access"] = "partial"
            if site_failure_kind.get("js-heavy", 0) >= 2 or site_failure_kind.get("render-failed", 0) >= 2:
                site["js_heavy"] = True
            updated_sites += 1

        payload["updatedAt"] = now_iso()
        site_profiles_path.parent.mkdir(parents=True, exist_ok=True)
        site_profiles_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        release(lock_path)

    if args.format == "md":
        lines = [
            "# tool_route_learning",
            "",
            f"- updated_sites: {updated_sites}",
            f"- attempts_considered: {len(attempts)}",
        ]
        print("\n".join(lines) + "\n", end="")
        return 0

    print(
        json.dumps(
            {
                "ok": True,
                "site_profiles_path": str(site_profiles_path),
                "updated_sites": updated_sites,
                "attempts_considered": len(attempts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

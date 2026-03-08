#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lockfile import acquire, release


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def normalize_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "site"


def derive_site_id(label: str, domains: list[str]) -> str:
    if domains:
        primary = domains[0].replace("www.", "")
        primary = re.sub(r"[^a-z0-9]+", "-", primary.lower()).strip("-")
        if primary:
            return primary
    return slugify(label)


def ensure_learning(entry: dict[str, Any]) -> None:
    learning = entry.get("learning")
    if not isinstance(learning, dict):
        learning = {}
        entry["learning"] = learning
    for key, default in {
        "success_by_tool": {},
        "failure_by_tool": {},
        "quality_by_tool": {},
        "failure_by_kind": {},
        "learned_preferred_tools": [],
        "learned_avoid_tools": [],
        "preferred_frontier_kinds": [],
        "last_successful_tool": None,
        "last_failure_kind": None,
        "last_seen_at": None,
    }.items():
        if key not in learning:
            learning[key] = default


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a research site profile.")
    parser.add_argument("--path", default="data/research/site_profiles.json")
    parser.add_argument("--lock", default="data/research/_state/research.lock")
    parser.add_argument("--site-id")
    parser.add_argument("--label", required=True)
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--channel", default="public-web")
    parser.add_argument("--access", choices=["public", "partial", "login-required"], default="public")
    parser.add_argument("--status", default="active")
    parser.add_argument("--js-heavy", action="store_true")
    parser.add_argument("--topic-tag", action="append", default=[])
    parser.add_argument("--preferred-tool", action="append", default=[])
    parser.add_argument("--fallback-tool", action="append", default=[])
    parser.add_argument("--hot-page", action="append", default=[])
    parser.add_argument("--feed-url", action="append", default=[])
    parser.add_argument("--quality-signal", action="append", default=[])
    parser.add_argument("--discovery-query", action="append", default=[])
    parser.add_argument("--reason", default="")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    lock_path = Path(args.lock).expanduser()
    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire research lock: {lock_path}")

    try:
        payload = load_json(path, {"schemaVersion": 1, "updatedAt": None, "sites": [], "settings": {}})
        sites = payload.get("sites")
        if not isinstance(sites, list):
            sites = []
            payload["sites"] = sites

        domains = normalize_list(args.domain)
        site_id = args.site_id or derive_site_id(args.label, domains)
        target: dict[str, Any] | None = None
        for item in sites:
            if not isinstance(item, dict):
                continue
            if item.get("site_id") == site_id:
                target = item
                break
            existing_domains = item.get("domains")
            if isinstance(existing_domains, list) and set(domains) & {d for d in existing_domains if isinstance(d, str)}:
                target = item
                break

        if target is None:
            target = {
                "site_id": site_id,
                "label": args.label.strip(),
                "domains": [],
                "channel": args.channel,
                "access": args.access,
                "js_heavy": args.js_heavy,
                "topic_tags": [],
                "preferred_tools": [],
                "fallback_tools": [],
                "hot_pages": [],
                "feed_urls": [],
                "quality_signals": [],
                "discovery_queries": [],
                "learning": {},
            }
            sites.append(target)

        target["site_id"] = site_id
        target["label"] = args.label.strip()
        target["channel"] = args.channel.strip() or "public-web"
        target["access"] = args.access
        target["status"] = args.status.strip() or "active"
        target["js_heavy"] = bool(args.js_heavy or target.get("js_heavy"))
        target["domains"] = normalize_list([*normalize_list(target.get("domains") if isinstance(target.get("domains"), list) else []), *domains])
        target["topic_tags"] = normalize_list([*normalize_list(target.get("topic_tags") if isinstance(target.get("topic_tags"), list) else []), *args.topic_tag])
        target["preferred_tools"] = normalize_list([*normalize_list(target.get("preferred_tools") if isinstance(target.get("preferred_tools"), list) else []), *args.preferred_tool])
        target["fallback_tools"] = normalize_list([*normalize_list(target.get("fallback_tools") if isinstance(target.get("fallback_tools"), list) else []), *args.fallback_tool])
        target["hot_pages"] = normalize_list([*normalize_list(target.get("hot_pages") if isinstance(target.get("hot_pages"), list) else []), *args.hot_page])
        target["feed_urls"] = normalize_list([*normalize_list(target.get("feed_urls") if isinstance(target.get("feed_urls"), list) else []), *args.feed_url])
        target["quality_signals"] = normalize_list([*normalize_list(target.get("quality_signals") if isinstance(target.get("quality_signals"), list) else []), *args.quality_signal])
        target["discovery_queries"] = normalize_list([*normalize_list(target.get("discovery_queries") if isinstance(target.get("discovery_queries"), list) else []), *args.discovery_query])
        if args.reason:
            notes = target.get("notes")
            if not isinstance(notes, list):
                notes = []
                target["notes"] = notes
            notes.append(args.reason.strip())
        ensure_learning(target)

        payload["updatedAt"] = now_iso()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        release(lock_path)

    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "site_id": site_id,
                "domains": domains,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

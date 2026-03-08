#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
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


def candidate_id(slug: str, capability_gap: str) -> str:
    basis = slug or capability_gap
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10].upper()
    return f"SKILL-{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a skill candidate entry.")
    parser.add_argument("--path", default="data/skills/catalog.json")
    parser.add_argument("--lock", default="data/skills/catalog.lock")
    parser.add_argument("--candidate-id")
    parser.add_argument("--slug", default="")
    parser.add_argument("--name", default="")
    parser.add_argument("--source-type", choices=["clawhub", "openclaw-bundled", "git", "manual"], required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--registry", default="")
    parser.add_argument("--capability-gap", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--site-id", action="append", default=[])
    parser.add_argument("--tool-id", action="append", default=[])
    parser.add_argument("--topic-id", action="append", default=[])
    parser.add_argument("--install-method", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--homepage", default="")
    parser.add_argument("--risk", choices=["low", "medium", "high", "unknown"], default="unknown")
    parser.add_argument("--review-status", choices=["pending", "reviewed", "approved", "rejected"], default="pending")
    parser.add_argument("--status", choices=["candidate", "approved", "installed", "rejected"], default="candidate")
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    lock_path = Path(args.lock).expanduser()
    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire skill catalog lock: {lock_path}")

    try:
        payload = load_json(path, {"schemaVersion": 1, "updatedAt": None, "candidates": []})
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            candidates = []
            payload["candidates"] = candidates

        slug = args.slug.strip()
        entry_id = args.candidate_id or candidate_id(slug, args.capability_gap.strip())
        target: dict[str, Any] | None = None
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if item.get("candidate_id") == entry_id:
                target = item
                break
            if slug and item.get("slug") == slug:
                target = item
                break

        if target is None:
            target = {
                "candidate_id": entry_id,
                "created_at": now_iso(),
                "notes": [],
            }
            candidates.append(target)

        target["candidate_id"] = entry_id
        target["slug"] = slug
        target["name"] = args.name.strip() or slug
        target["source_type"] = args.source_type
        target["source_url"] = args.source_url.strip()
        target["registry"] = args.registry.strip()
        target["capability_gap"] = args.capability_gap.strip()
        target["reason"] = args.reason.strip()
        target["query"] = args.query.strip()
        target["site_ids"] = normalize_list(args.site_id)
        target["tool_ids"] = normalize_list(args.tool_id)
        target["topic_ids"] = normalize_list(args.topic_id)
        target["install_method"] = args.install_method.strip()
        target["version"] = args.version.strip()
        target["homepage"] = args.homepage.strip()
        target["risk"] = args.risk
        target["review_status"] = args.review_status
        target["status"] = args.status
        target["updated_at"] = now_iso()

        notes = target.get("notes")
        if not isinstance(notes, list):
            notes = []
            target["notes"] = notes
        notes.extend(normalize_list(args.note))

        payload["updatedAt"] = now_iso()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        release(lock_path)

    print(json.dumps({"ok": True, "path": str(path), "candidate_id": entry_id, "status": args.status}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

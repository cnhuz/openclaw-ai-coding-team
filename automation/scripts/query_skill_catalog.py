#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def parse_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    status_order = {"approved": 0, "candidate": 1, "installed": 2, "rejected": 3}
    status = item.get("status")
    if isinstance(status, str):
        return (status_order.get(status, 9), str(item.get("updated_at", "")))
    return (9, "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the skill candidate catalog.")
    parser.add_argument("--path", default="data/skills/catalog.json")
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--review-status", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    payload = load_json(Path(args.path).expanduser(), {"candidates": []})
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        candidates = []

    status_filter = set(args.status)
    review_filter = set(args.review_status)
    filtered: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if status_filter:
            status = item.get("status")
            if not isinstance(status, str) or status not in status_filter:
                continue
        if review_filter:
            review_status = item.get("review_status")
            if not isinstance(review_status, str) or review_status not in review_filter:
                continue
        filtered.append(item)

    filtered.sort(key=parse_sort_key, reverse=False)
    filtered = filtered[: args.limit]

    if args.format == "md":
        lines = ["# skill_catalog", ""]
        if not filtered:
            lines.append("- no candidates")
        for item in filtered:
            lines.append(
                f"- `{item.get('candidate_id', '-')}` | status={item.get('status', '-')} | review={item.get('review_status', '-')} | "
                f"slug={item.get('slug', '-') or '-'} | gap={item.get('capability_gap', '-')}"
            )
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps({"ok": True, "count": len(filtered), "candidates": filtered}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

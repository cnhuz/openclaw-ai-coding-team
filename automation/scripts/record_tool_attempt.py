#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one exploration tool attempt record.")
    parser.add_argument("--attempts-root", default="data/research/tool_attempts")
    parser.add_argument("--attempted-at")
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--site-label", default="")
    parser.add_argument("--domain", default="")
    parser.add_argument("--tool-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--topic-id", action="append", default=[])
    parser.add_argument("--source-id", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--target-kind", choices=["hot_page", "feed", "query", "article", "post", "timeline", "unknown"], default="unknown")
    parser.add_argument("--outcome", choices=["success", "failure", "partial", "skipped"], required=True)
    parser.add_argument("--failure-kind", default="")
    parser.add_argument("--quality", choices=["none", "weak", "medium", "strong"], default="none")
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args()

    attempted_at = args.attempted_at or now_iso()
    entry: dict[str, Any] = {
        "attempted_at": attempted_at,
        "site_id": args.site_id.strip(),
        "site_label": args.site_label.strip() or args.site_id.strip(),
        "domain": args.domain.strip(),
        "tool_id": args.tool_id.strip(),
        "stage": args.stage.strip(),
        "topic_ids": normalize_list(args.topic_id),
        "source_id": args.source_id.strip(),
        "url": args.url.strip(),
        "query": args.query.strip(),
        "target_kind": args.target_kind,
        "outcome": args.outcome,
        "failure_kind": args.failure_kind.strip(),
        "quality": args.quality,
        "notes": normalize_list(args.note),
    }

    attempts_root = Path(args.attempts_root).expanduser()
    attempts_root.mkdir(parents=True, exist_ok=True)
    path = attempts_root / f"{attempted_at[:10]}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(json.dumps({"ok": True, "path": str(path), "tool_id": entry["tool_id"], "outcome": entry["outcome"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


STATUS_ORDER = {
    "ready_review": 0,
    "candidate": 1,
    "watchlist": 2,
    "promoted": 3,
    "rejected": 4,
}


def parse_iso(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def render_md(path: Path, rows: list[dict[str, Any]]) -> str:
    lines = [
        "# research_opportunity_query",
        "",
        f"- path: `{path}`",
        f"- count: {len(rows)}",
    ]
    if not rows:
        lines.extend(["", "- no opportunities matched"])
        return "\n".join(lines) + "\n"

    for row in rows:
        lines.extend(
            [
                "",
                f"## {row.get('opportunity_id', '<missing-id>')} | {row.get('title', '<missing-title>')}",
                f"- status: {row.get('status', 'unknown')}",
                f"- priority: {row.get('priority', 'unknown')}",
                f"- score: {row.get('score', 'unknown')}",
                f"- recommended_action: {row.get('recommended_action', 'unknown')}",
                f"- topic_ids: {', '.join(normalize_list(row.get('topic_ids'))) or 'none'}",
                f"- signal_count: {row.get('signal_count', 0)}",
                f"- source_diversity: {row.get('source_diversity', 0)}",
                f"- card_path: {row.get('card_path') or 'none'}",
                f"- task_id: {row.get('task_id') or 'none'}",
                f"- summary: {row.get('summary', 'none')}",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Query data/research/opportunities.json")
    parser.add_argument("--path", default="data/research/opportunities.json")
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--topic-id", action="append", default=[])
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--format", choices=["json", "md"], default="md")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    payload = load_payload(path)
    opportunities = payload.get("opportunities")
    if not isinstance(opportunities, list):
        raise SystemExit("opportunities must be a list")

    rows: list[dict[str, Any]] = []
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        if args.status and item.get("status") not in args.status:
            continue
        if float(item.get("score", 0) or 0) < args.min_score:
            continue
        topic_ids = normalize_list(item.get("topic_ids"))
        if args.topic_id and not set(args.topic_id).intersection(topic_ids):
            continue
        rows.append(item)

    rows.sort(
        key=lambda item: (
            STATUS_ORDER.get(str(item.get("status")), 99),
            -float(item.get("score", 0) or 0),
            -parse_iso(item.get("updated_at")),
            str(item.get("opportunity_id", "")),
        )
    )

    if args.limit is not None:
        rows = rows[: args.limit]

    if args.format == "json":
        print(json.dumps({"ok": True, "path": str(path), "count": len(rows), "opportunities": rows}, ensure_ascii=False, indent=2))
        return 0

    print(render_md(path, rows), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

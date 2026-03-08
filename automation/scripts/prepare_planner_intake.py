#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from query_task_registry import PRIORITY_ORDER, parse_dt
from update_task_registry import load_registry


TARGET_STATES = {"Intake", "Replan"}


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def find_latest_handoff(handoffs_dir: Path, task_id: str, next_owner: str) -> str | None:
    matches = []
    suffix = f"-to-{next_owner}.md"
    for path in handoffs_dir.rglob("*.md"):
        if path.name in {"README.md", "TEMPLATE.md"}:
            continue
        if task_id not in path.name:
            continue
        if suffix in path.name or task_id in path.name:
            matches.append(path)
    if not matches:
        return None
    matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0])


def select_tasks(tasks: list[dict[str, Any]], owner: str, states: set[str], limit: int | None) -> list[dict[str, Any]]:
    rows = [
        item
        for item in tasks
        if isinstance(item, dict)
        and item.get("owner") == owner
        and item.get("state") in states
    ]
    rows.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(item.get("priority"), 99),
            -parse_dt(item.get("updated_at")),
            str(item.get("task_id", "")),
        )
    )
    return rows[:limit] if limit is not None else rows


def build_packet(task: dict[str, Any], latest_handoff: str | None, opportunity_card: str | None) -> str:
    evidence = normalize_list(task.get("evidence_pointer"))
    notes = normalize_list(task.get("notes"))
    tags = normalize_list(task.get("tags"))
    breakpoint_value = task.get("breakpoint")
    breakpoint_lines: list[str] = []
    if isinstance(breakpoint_value, dict):
        next_items = normalize_list(breakpoint_value.get("next"))
        design_notes = normalize_list(breakpoint_value.get("design_notes"))
        pending = normalize_list(breakpoint_value.get("pending_confirmation"))
        if next_items:
            breakpoint_lines.append("## Breakpoint Next")
            breakpoint_lines.extend(f"- {item}" for item in next_items)
        if design_notes:
            breakpoint_lines.append("")
            breakpoint_lines.append("## Breakpoint Design Notes")
            breakpoint_lines.extend(f"- {item}" for item in design_notes)
        if pending:
            breakpoint_lines.append("")
            breakpoint_lines.append("## Pending Confirmation")
            breakpoint_lines.extend(f"- {item}" for item in pending)

    lines = [
        "# Planner Intake Packet",
        "",
        f"- task_id: {task.get('task_id', 'unknown')}",
        f"- title: {task.get('title', 'unknown')}",
        f"- state: {task.get('state', 'unknown')}",
        f"- owner: {task.get('owner', 'unknown')}",
        f"- priority: {task.get('priority', 'unknown')}",
        f"- updated_at: {task.get('updated_at', 'unknown')}",
        f"- latest_handoff: {latest_handoff or 'none'}",
        f"- opportunity_card: {opportunity_card or 'none'}",
        "",
        "## Next Step",
        task.get("next_step", "none"),
        "",
        "## Evidence",
    ]
    lines.extend(f"- {item}" for item in evidence or ["none"])
    if tags:
        lines.extend(["", "## Tags", *[f"- {item}" for item in tags]])
    if notes:
        lines.extend(["", "## Notes", *[f"- {item}" for item in notes]])
    if breakpoint_lines:
        lines.extend(["", *breakpoint_lines])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one planner intake packet from the captain task registry.")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--handoffs-dir", required=True)
    parser.add_argument("--owner", default="aic-planner")
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--packet-dir", default="intake")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    registry_path = Path(args.registry_path).expanduser()
    handoffs_dir = Path(args.handoffs_dir).expanduser()
    packet_dir = Path(args.packet_dir).expanduser()
    registry = load_registry(registry_path)
    tasks = registry.get("tasks", [])
    if not isinstance(tasks, list):
        raise SystemExit("registry.tasks must be a list")

    states = set(args.state) if args.state else set(TARGET_STATES)
    selected = select_tasks([item for item in tasks if isinstance(item, dict)], args.owner, states, args.limit)
    if not selected:
        result = {"ok": True, "count": 0, "items": []}
        if args.format == "md":
            print("# planner_intake\n\n- no tasks matched\n", end="")
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    items: list[dict[str, Any]] = []
    packet_dir.mkdir(parents=True, exist_ok=True)
    for task in selected:
        task_id = str(task.get("task_id"))
        evidence = normalize_list(task.get("evidence_pointer"))
        opportunity_card = next((item for item in evidence if "opportunity-cards" in item and item.endswith(".md")), None)
        latest_handoff = find_latest_handoff(handoffs_dir, task_id, args.owner)
        packet_path = packet_dir / f"{task_id}.md"
        packet_path.write_text(build_packet(task, latest_handoff, opportunity_card), encoding="utf-8")
        items.append(
            {
                "task_id": task_id,
                "title": task.get("title"),
                "state": task.get("state"),
                "priority": task.get("priority"),
                "updated_at": task.get("updated_at"),
                "latest_handoff": latest_handoff,
                "opportunity_card": opportunity_card,
                "packet_path": str(packet_path),
                "evidence": evidence,
            }
        )

    result = {"ok": True, "count": len(items), "items": items}
    if args.format == "md":
        lines = ["# planner_intake", "", f"- count: {len(items)}"]
        for item in items:
            lines.extend(
                [
                    "",
                    f"## {item['task_id']} | {item['title']}",
                    f"- state: {item['state']}",
                    f"- priority: {item['priority']}",
                    f"- updated_at: {item['updated_at']}",
                    f"- packet_path: {item['packet_path']}",
                    f"- latest_handoff: {item['latest_handoff'] or 'none'}",
                    f"- opportunity_card: {item['opportunity_card'] or 'none'}",
                ]
            )
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

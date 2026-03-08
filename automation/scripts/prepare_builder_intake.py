#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from execution_target import load_execution_target
from prepare_planner_intake import find_latest_handoff, normalize_list, select_tasks
from update_task_registry import load_registry


TARGET_STATES = {"Building", "Rework"}


def build_packet(task: dict[str, Any], latest_handoff: str | None, execution_target: dict[str, Any]) -> str:
    evidence = normalize_list(task.get("evidence_pointer"))
    acceptance = normalize_list(task.get("acceptance"))
    notes = normalize_list(task.get("notes"))

    lines = [
        "# Builder Intake Packet",
        "",
        f"- task_id: {task.get('task_id', 'unknown')}",
        f"- title: {task.get('title', 'unknown')}",
        f"- state: {task.get('state', 'unknown')}",
        f"- owner: {task.get('owner', 'unknown')}",
        f"- priority: {task.get('priority', 'unknown')}",
        f"- updated_at: {task.get('updated_at', 'unknown')}",
        f"- latest_handoff: {latest_handoff or 'none'}",
        f"- repo_root: {execution_target['repo_root']}",
        f"- default_branch: {execution_target['default_branch']}",
        f"- build_entrypoint: {execution_target['build_entrypoint'] or 'none'}",
        f"- release_mode: {execution_target['release_mode']}",
        "",
        "## Next Step",
        task.get("next_step", "none"),
        "",
        "## Acceptance",
    ]
    lines.extend(f"- {item}" for item in acceptance or ["none"])
    lines.extend(["", "## Evidence"])
    lines.extend(f"- {item}" for item in evidence or ["none"])
    lines.extend(["", "## Suggested Local Checks"])
    lines.extend(f"- {item}" for item in execution_target["test_commands"] or ["none"])
    if notes:
        lines.extend(["", "## Notes"])
        lines.extend(f"- {item}" for item in notes)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one builder intake packet from the captain task registry.")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--handoffs-dir", required=True)
    parser.add_argument("--execution-target-path", required=True)
    parser.add_argument("--owner", default="aic-builder")
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--packet-dir", default="intake")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    registry = load_registry(Path(args.registry_path).expanduser())
    tasks = registry.get("tasks", [])
    if not isinstance(tasks, list):
        raise SystemExit("registry.tasks must be a list")

    execution_target = load_execution_target(Path(args.execution_target_path).expanduser())
    states = set(args.state) if args.state else set(TARGET_STATES)
    selected = select_tasks([item for item in tasks if isinstance(item, dict)], args.owner, states, args.limit)
    if not selected:
        result = {"ok": True, "count": 0, "items": []}
        if args.format == "md":
            print("# builder_intake\n\n- no tasks matched\n", end="")
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    handoffs_dir = Path(args.handoffs_dir).expanduser()
    packet_dir = Path(args.packet_dir).expanduser()
    packet_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for task in selected:
        task_id = str(task.get("task_id"))
        latest_handoff = find_latest_handoff(handoffs_dir, task_id, args.owner)
        packet_path = packet_dir / f"{task_id}.md"
        packet_path.write_text(build_packet(task, latest_handoff, execution_target), encoding="utf-8")
        items.append(
            {
                "task_id": task_id,
                "title": task.get("title"),
                "state": task.get("state"),
                "priority": task.get("priority"),
                "updated_at": task.get("updated_at"),
                "latest_handoff": latest_handoff,
                "packet_path": str(packet_path),
                "repo_root": execution_target["repo_root"],
                "test_commands": execution_target["test_commands"],
            }
        )

    result = {"ok": True, "count": len(items), "items": items}
    if args.format == "md":
        lines = ["# builder_intake", "", f"- count: {len(items)}"]
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
                    f"- repo_root: {item['repo_root']}",
                ]
            )
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ACTIVE_STATES = {
    "Intake",
    "Researching",
    "Scoped",
    "Planned",
    "Approved",
    "Building",
    "Verifying",
    "Staging",
    "Released",
    "Observing",
    "Replan",
    "Rework",
}

VIEW_STATES = {
    "all": None,
    "active": ACTIVE_STATES,
    "blocked": ACTIVE_STATES,
    "build_queue": {"Building", "Rework"},
    "captain": ACTIVE_STATES,
    "dispatcher": {"Approved", "Building", "Verifying", "Staging", "Observing", "Rework", "Replan"},
    "verifying": {"Verifying"},
    "observing": {"Observing"},
}

PRIORITY_ORDER = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
}


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return float("-inf")


def has_blocker(task: dict[str, Any]) -> bool:
    blocker = task.get("blocker")
    if blocker is None:
        return False
    if isinstance(blocker, str):
        return bool(blocker.strip())
    if isinstance(blocker, list):
        return any(isinstance(item, str) and item.strip() for item in blocker)
    return True


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def filter_tasks(
    tasks: list[dict[str, Any]],
    *,
    view: str,
    states: list[str],
    owners: list[str],
    blocked_only: bool,
    limit: int | None,
) -> list[dict[str, Any]]:
    allowed_states = VIEW_STATES[view]
    result: list[dict[str, Any]] = []

    for task in tasks:
        state = task.get("state")
        owner = task.get("owner")

        if allowed_states is not None and state not in allowed_states:
            continue
        if states and state not in states:
            continue
        if owners and owner not in owners:
            continue
        if view == "blocked" and not has_blocker(task):
            continue
        if blocked_only and not has_blocker(task):
            continue

        result.append(task)

    result.sort(
        key=lambda task: (
            0 if has_blocker(task) else 1,
            PRIORITY_ORDER.get(task.get("priority"), 99),
            -parse_dt(task.get("updated_at")),
            str(task.get("task_id", "")),
        )
    )

    if limit is not None:
        return result[:limit]
    return result


def render_md(path: Path, view: str, tasks: list[dict[str, Any]]) -> str:
    lines = [
        "# task_registry_query",
        "",
        f"- path: `{path}`",
        f"- view: `{view}`",
        f"- count: {len(tasks)}",
    ]

    if not tasks:
        lines.extend(["", "- no tasks matched"])
        return "\n".join(lines) + "\n"

    for task in tasks:
        blocker = task.get("blocker")
        blocker_text = "none"
        if isinstance(blocker, list):
            blocker_text = "; ".join(item for item in blocker if isinstance(item, str) and item) or "none"
        elif isinstance(blocker, str) and blocker.strip():
            blocker_text = blocker.strip()

        evidence = normalize_list(task.get("evidence_pointer"))
        evidence_text = ", ".join(evidence[:3]) if evidence else "none"

        lines.extend(
            [
                "",
                f"## {task.get('task_id', '<missing-task-id>')} | {task.get('title', '<missing-title>')}",
                f"- state: {task.get('state', '<missing-state>')}",
                f"- owner: {task.get('owner', '<missing-owner>')}",
                f"- priority: {task.get('priority', '<missing-priority>')}",
                f"- updated_at: {task.get('updated_at', '<missing-updated_at>')}",
                f"- blocker: {blocker_text}",
                f"- next_step: {task.get('next_step', '<missing-next_step>')}",
                f"- evidence: {evidence_text}",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Query tasks/registry.json and render filtered summaries.")
    parser.add_argument("--path", default="tasks/registry.json")
    parser.add_argument("--view", choices=sorted(VIEW_STATES.keys()), default="active")
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--owner", action="append", default=[])
    parser.add_argument("--blocked-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--format", choices=["json", "md"], default="md")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    registry = load_registry(path)
    tasks = registry.get("tasks", [])
    if not isinstance(tasks, list):
        raise SystemExit("tasks must be a list")

    filtered = filter_tasks(
        [task for task in tasks if isinstance(task, dict)],
        view=args.view,
        states=args.state,
        owners=args.owner,
        blocked_only=args.blocked_only,
        limit=args.limit,
    )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": str(path),
                    "view": args.view,
                    "count": len(filtered),
                    "tasks": filtered,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(render_md(path, args.view, filtered), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

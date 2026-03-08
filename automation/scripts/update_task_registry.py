#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_STATES = {
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
    "Closed",
    "Replan",
    "Rework",
}

REQUIRED_CREATE_FIELDS = {
    "title",
    "state",
    "owner",
    "priority",
    "next_step",
}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_registry() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "updatedAt": None,
        "sourceType": "local_registry",
        "externalSource": None,
        "tasks": [],
    }


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_registry()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("registry root must be an object")
    if "tasks" not in data or not isinstance(data["tasks"], list):
        raise SystemExit("registry.tasks must be a list")
    return data


def write_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def normalize_list(value: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def ensure_state(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in ALLOWED_STATES:
        raise SystemExit(f"invalid state: {value}")
    return value


def build_breakpoint(args: argparse.Namespace, existing: Any) -> dict[str, Any] | None:
    if args.clear_breakpoint:
        return None

    has_new_values = any(
        (
            args.breakpoint_completed,
            args.breakpoint_next,
            args.breakpoint_design_note,
            args.breakpoint_pending,
        )
    )
    if not has_new_values:
        return existing if isinstance(existing, dict) else None

    if args.breakpoint_reset or not isinstance(existing, dict):
        breakpoint_value: dict[str, Any] = {
            "completed": [],
            "next": [],
            "design_notes": [],
            "pending_confirmation": [],
        }
    else:
        breakpoint_value = {
            "completed": list(existing.get("completed", [])),
            "next": list(existing.get("next", [])),
            "design_notes": list(existing.get("design_notes", [])),
            "pending_confirmation": list(existing.get("pending_confirmation", [])),
        }

    if args.breakpoint_completed:
        breakpoint_value["completed"] = list(args.breakpoint_completed)
    if args.breakpoint_next:
        breakpoint_value["next"] = list(args.breakpoint_next)
    if args.breakpoint_design_note:
        breakpoint_value["design_notes"] = list(args.breakpoint_design_note)
    if args.breakpoint_pending:
        breakpoint_value["pending_confirmation"] = list(args.breakpoint_pending)

    return breakpoint_value


def upsert_task(registry: dict[str, Any], args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    tasks = registry["tasks"]
    task = None
    for item in tasks:
        if isinstance(item, dict) and item.get("task_id") == args.task_id:
            task = item
            break

    action = "updated"
    if task is None:
        missing = [
            key
            for key in REQUIRED_CREATE_FIELDS
            if getattr(args, key) is None
        ]
        if missing:
            raise SystemExit(f"creating a task requires: {', '.join(sorted(missing))}")

        task = {
            "task_id": args.task_id,
            "title": args.title,
            "state": ensure_state(args.state),
            "owner": args.owner,
            "priority": args.priority,
            "updated_at": args.updated_at or now_iso(),
            "blocker": args.blocker if args.blocker is not None else None,
            "next_step": args.next_step,
            "evidence_pointer": normalize_list(list(args.evidence) + list(args.append_evidence)),
        }
        if args.acceptance:
            task["acceptance"] = list(args.acceptance)
        if args.notes:
            task["notes"] = list(args.notes)
        if args.tags:
            task["tags"] = normalize_list(list(args.tags))

        breakpoint_value = build_breakpoint(args, None)
        if breakpoint_value is not None:
            task["breakpoint"] = breakpoint_value

        tasks.append(task)
        action = "created"
        return action, task

    if args.title is not None:
        task["title"] = args.title
    if args.state is not None:
        task["state"] = ensure_state(args.state)
    if args.owner is not None:
        task["owner"] = args.owner
    if args.priority is not None:
        task["priority"] = args.priority
    if args.next_step is not None:
        task["next_step"] = args.next_step

    if args.clear_blocker:
        task["blocker"] = None
    elif args.blocker is not None:
        task["blocker"] = args.blocker

    if args.evidence:
        task["evidence_pointer"] = normalize_list(list(args.evidence))
    else:
        current_evidence = task.get("evidence_pointer", [])
        if not isinstance(current_evidence, list):
            current_evidence = []
        if args.append_evidence:
            task["evidence_pointer"] = normalize_list(list(current_evidence) + list(args.append_evidence))

    if args.acceptance:
        task["acceptance"] = list(args.acceptance)
    if args.notes:
        existing_notes = task.get("notes", [])
        if not isinstance(existing_notes, list):
            existing_notes = []
        task["notes"] = list(existing_notes) + list(args.notes)
    if args.tags:
        existing_tags = task.get("tags", [])
        if not isinstance(existing_tags, list):
            existing_tags = []
        task["tags"] = normalize_list(list(existing_tags) + list(args.tags))

    breakpoint_value = build_breakpoint(args, task.get("breakpoint"))
    if args.clear_breakpoint:
        task["breakpoint"] = None
    elif breakpoint_value is not None:
        task["breakpoint"] = breakpoint_value

    task["updated_at"] = args.updated_at or now_iso()
    return action, task


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update tasks/registry.json entries.")
    parser.add_argument("--path", default="tasks/registry.json")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--title")
    parser.add_argument("--state")
    parser.add_argument("--owner")
    parser.add_argument("--priority")
    parser.add_argument("--next-step")
    parser.add_argument("--blocker")
    parser.add_argument("--clear-blocker", action="store_true")
    parser.add_argument("--updated-at")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--append-evidence", action="append", default=[])
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--notes", action="append", default=[])
    parser.add_argument("--tags", action="append", default=[])
    parser.add_argument("--clear-breakpoint", action="store_true")
    parser.add_argument("--breakpoint-reset", action="store_true")
    parser.add_argument("--breakpoint-completed", action="append", default=[])
    parser.add_argument("--breakpoint-next", action="append", default=[])
    parser.add_argument("--breakpoint-design-note", action="append", default=[])
    parser.add_argument("--breakpoint-pending", action="append", default=[])
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    registry = load_registry(path)
    action, task = upsert_task(registry, args)
    registry["updatedAt"] = now_iso()
    write_registry(path, registry)

    print(
        json.dumps(
            {
                "ok": True,
                "action": action,
                "path": str(path),
                "task": task,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

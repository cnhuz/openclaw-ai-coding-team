#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


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

REQUIRED_ROOT_KEYS = {
    "schemaVersion",
    "updatedAt",
    "sourceType",
    "externalSource",
    "tasks",
}

REQUIRED_TASK_KEYS = {
    "task_id",
    "title",
    "state",
    "owner",
    "priority",
    "updated_at",
    "blocker",
    "next_step",
    "evidence_pointer",
}


def validate_registry(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"registry not found: {path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid json: {exc}"]

    if not isinstance(data, dict):
        return ["root must be a JSON object"]

    for key in sorted(REQUIRED_ROOT_KEYS):
        if key not in data:
            errors.append(f"missing root key: {key}")

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("tasks must be a list")
        return errors

    seen_task_ids: set[str] = set()

    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for key in sorted(REQUIRED_TASK_KEYS):
            if key not in task:
                errors.append(f"{prefix} missing key: {key}")

        task_id = task.get("task_id")
        if isinstance(task_id, str) and task_id:
            if task_id in seen_task_ids:
                errors.append(f"duplicate task_id: {task_id}")
            seen_task_ids.add(task_id)
        else:
            errors.append(f"{prefix}.task_id must be a non-empty string")

        state = task.get("state")
        if not isinstance(state, str) or state not in ALLOWED_STATES:
            errors.append(f"{prefix}.state invalid: {state!r}")

        evidence_pointer = task.get("evidence_pointer")
        if not isinstance(evidence_pointer, list):
            errors.append(f"{prefix}.evidence_pointer must be a list")
        else:
            for item_index, item in enumerate(evidence_pointer):
                if not isinstance(item, str) or not item:
                    errors.append(f"{prefix}.evidence_pointer[{item_index}] must be a non-empty string")

        breakpoint_value = task.get("breakpoint")
        if breakpoint_value is not None and not isinstance(breakpoint_value, dict):
            errors.append(f"{prefix}.breakpoint must be an object or null")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tasks/registry.json")
    parser.add_argument("--path", default="tasks/registry.json")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    errors = validate_registry(path)

    result = {
        "ok": not errors,
        "path": str(path),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from create_handoff import build_handoff_markdown, default_handoff_path
from lockfile import acquire, release
from query_task_registry import PRIORITY_ORDER, parse_dt
from update_task_registry import load_registry, now_iso, upsert_task, write_registry


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def select_task(tasks: list[dict[str, Any]], owner: str) -> dict[str, Any] | None:
    rows = [
        item
        for item in tasks
        if isinstance(item, dict)
        and item.get("state") == "Approved"
        and item.get("owner") == owner
    ]
    rows.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(item.get("priority"), 99),
            -parse_dt(item.get("updated_at")),
            str(item.get("task_id", "")),
        )
    )
    return rows[0] if rows else None


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


def create_builder_handoff(
    handoff_dir: Path,
    task: dict[str, Any],
    evidence: list[str],
    from_owner: str,
    next_owner: str,
    breakpoint_text: str,
) -> Path:
    handoff_dt = datetime.now().astimezone().replace(microsecond=0)
    output_path = default_handoff_path(handoff_dir, str(task["task_id"]), next_owner, handoff_dt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_args = SimpleNamespace(
        task_id=task["task_id"],
        current_stage="Building",
        goal="把已批准任务交给 builder 开始实现",
        deliverable="已审议通过的 Spec + 验收标准 + 当前下一步",
        evidence=evidence,
        risk="实现时必须保留验收标准与清理边界，避免范围膨胀或误操作。",
        next_owner=next_owner,
        breakpoint=breakpoint_text,
        closed=False,
        from_owner=from_owner,
    )
    content = build_handoff_markdown(
        handoff_args,
        handoff_dt.isoformat(),
        [],
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def update_task(registry_path: Path, task_id: str, next_owner: str, next_step: str, evidence: list[str]) -> dict[str, Any]:
    registry = load_registry(registry_path)
    args = SimpleNamespace(
        task_id=task_id,
        title=None,
        state="Building",
        owner=next_owner,
        priority=None,
        next_step=next_step,
        blocker=None,
        clear_blocker=True,
        updated_at=now_iso(),
        evidence=[],
        append_evidence=evidence,
        acceptance=[],
        notes=[],
        tags=[],
        clear_breakpoint=False,
        breakpoint_reset=False,
        breakpoint_completed=[],
        breakpoint_next=[next_step],
        breakpoint_design_note=[],
        breakpoint_pending=[],
    )
    action, task = upsert_task(registry, args)
    registry["updatedAt"] = now_iso()
    write_registry(registry_path, registry)
    return {"action": action, "task": task}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge one Approved dispatcher-owned task into the builder queue.")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--handoffs-dir", required=True)
    parser.add_argument("--lock", default="tasks/_state/registry.lock")
    parser.add_argument("--task-owner", default="aic-dispatcher")
    parser.add_argument("--next-owner", default="aic-builder")
    parser.add_argument("--from-owner", default="aic-dispatcher")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    registry_path = Path(args.registry_path).expanduser()
    handoffs_dir = Path(args.handoffs_dir).expanduser()
    lock_path = Path(args.lock).expanduser()

    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire task lock: {lock_path}")

    try:
        registry = load_registry(registry_path)
        tasks = registry.get("tasks", [])
        if not isinstance(tasks, list):
            raise SystemExit("registry.tasks must be a list")
        task = select_task([item for item in tasks if isinstance(item, dict)], args.task_owner)
        if task is None:
            result = {"ok": True, "decision": "no-approved-task"}
            if args.format == "md":
                print("# bridge_approved_task\n\n- decision: no-approved-task\n", end="")
                return 0
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        latest_handoff = find_latest_handoff(handoffs_dir, str(task["task_id"]), args.task_owner)
        evidence = normalize_list(task.get("evidence_pointer"))
        spec_path = next((item for item in evidence if item.endswith(".md") and "/specs/" in item), None)
        handoff_evidence = [item for item in [spec_path, latest_handoff] if item]
        if not handoff_evidence:
            handoff_evidence = evidence[:3] or [str(task["task_id"])]

        next_step = "基于已批准 spec 开始实现，并保留 acceptance 与 cleanup 安全边界"
        handoff_path = create_builder_handoff(
            handoffs_dir,
            task,
            handoff_evidence,
            args.from_owner,
            args.next_owner,
            next_step,
        )
        task_result = update_task(
            registry_path,
            str(task["task_id"]),
            args.next_owner,
            next_step,
            [str(handoff_path)],
        )
    finally:
        release(lock_path)

    result = {
        "ok": True,
        "decision": "building",
        "task_id": task_result["task"]["task_id"],
        "task_action": task_result["action"],
        "handoff_path": str(handoff_path),
    }
    if args.format == "md":
        print(
            "\n".join(
                [
                    "# bridge_approved_task",
                    "",
                    "- decision: building",
                    f"- task_id: {result['task_id']}",
                    f"- handoff_path: {result['handoff_path']}",
                ]
            )
            + "\n",
            end="",
        )
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from update_task_registry import load_registry, now_iso, upsert_task, write_registry


def parse_extra_fields(values: list[str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --extra-field format: {value!r}; expected Label=Value")
        key, content = value.split("=", 1)
        key = key.strip()
        content = content.strip()
        if not key or not content:
            raise SystemExit(f"invalid --extra-field content: {value!r}")
        result.append((key, content))
    return result


def detect_from_owner(explicit: str | None) -> str | None:
    if explicit:
        return explicit

    env_agent_id = os.environ.get("OPENCLAW_AGENT_ID", "").strip()
    if env_agent_id:
        return env_agent_id

    cwd_name = Path.cwd().name
    if cwd_name.startswith("workspace-") and len(cwd_name) > len("workspace-"):
        return cwd_name[len("workspace-") :]

    return None


def build_handoff_markdown(args: argparse.Namespace, handoff_time: str, extra_fields: list[tuple[str, str]]) -> str:
    evidence_lines = "\n".join(f"- {item}" for item in args.evidence)
    breakpoint_value = "无" if args.closed else args.breakpoint
    from_owner = detect_from_owner(args.from_owner)

    lines = [
        "# Handoff",
        "",
        f"生成时间: {handoff_time}",
        f"发送方: {from_owner or 'unknown'}",
        "",
        f"任务ID: {args.task_id}",
        f"当前阶段: {args.current_stage}",
        f"目标: {args.goal}",
        f"交付物: {args.deliverable}",
        "证据:",
        evidence_lines,
        f"风险/阻塞: {args.risk}",
        f"下一负责人: {args.next_owner}",
        f"Breakpoint: {breakpoint_value}",
    ]

    if extra_fields:
        lines.extend(["", "## 补充字段", ""])
        for key, value in extra_fields:
            lines.append(f"- {key}: {value}")

    lines.append("")
    return "\n".join(lines)


def default_handoff_path(base_dir: Path, task_id: str, next_owner: str, handoff_time: datetime) -> Path:
    day_dir = base_dir / handoff_time.strftime("%Y-%m-%d")
    filename = f"{handoff_time.strftime('%H%M%S')}-{task_id}-to-{next_owner}.md"
    return day_dir / filename


def sync_registry(args: argparse.Namespace, handoff_path: Path) -> dict:
    registry_path = Path(args.registry_path).expanduser()
    registry = load_registry(registry_path)

    evidence = list(args.sync_evidence)
    evidence.extend(args.evidence)
    evidence.append(str(handoff_path))

    sync_breakpoint_completed = list(args.sync_breakpoint_completed)
    sync_breakpoint_next = list(args.sync_breakpoint_next)
    if args.breakpoint and not args.closed and not sync_breakpoint_next:
        sync_breakpoint_next = [args.breakpoint]

    update_args = SimpleNamespace(
        task_id=args.task_id,
        title=args.sync_title,
        state=args.sync_state,
        owner=args.sync_owner or args.next_owner,
        priority=args.sync_priority,
        next_step=args.sync_next_step,
        blocker=args.sync_blocker,
        clear_blocker=args.sync_clear_blocker,
        updated_at=args.sync_updated_at,
        evidence=[],
        append_evidence=evidence,
        acceptance=[],
        notes=args.sync_note,
        tags=args.sync_tag,
        clear_breakpoint=False,
        breakpoint_reset=args.sync_breakpoint_reset,
        breakpoint_completed=sync_breakpoint_completed,
        breakpoint_next=sync_breakpoint_next,
        breakpoint_design_note=args.sync_breakpoint_design_note,
        breakpoint_pending=args.sync_breakpoint_pending,
    )

    action, task = upsert_task(registry, update_args)
    registry["updatedAt"] = now_iso()
    write_registry(registry_path, registry)
    return {
        "action": action,
        "path": str(registry_path),
        "task": task,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a structured handoff file and optionally sync task registry.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--current-stage", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--deliverable", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--risk", default="无")
    parser.add_argument("--next-owner", required=True)
    parser.add_argument("--breakpoint")
    parser.add_argument("--closed", action="store_true")
    parser.add_argument("--from-owner")
    parser.add_argument("--handoff-dir", default="handoffs")
    parser.add_argument("--output-path")
    parser.add_argument("--extra-field", action="append", default=[])

    parser.add_argument("--sync-registry", action="store_true")
    parser.add_argument("--registry-path", default="tasks/registry.json")
    parser.add_argument("--sync-title")
    parser.add_argument("--sync-state")
    parser.add_argument("--sync-owner")
    parser.add_argument("--sync-priority")
    parser.add_argument("--sync-next-step")
    parser.add_argument("--sync-blocker")
    parser.add_argument("--sync-clear-blocker", action="store_true")
    parser.add_argument("--sync-updated-at")
    parser.add_argument("--sync-evidence", "--sync-append-evidence", dest="sync_evidence", action="append", default=[])
    parser.add_argument("--sync-note", action="append", default=[])
    parser.add_argument("--sync-tag", action="append", default=[])
    parser.add_argument("--sync-breakpoint-reset", action="store_true")
    parser.add_argument("--sync-breakpoint-completed", action="append", default=[])
    parser.add_argument("--sync-breakpoint-next", action="append", default=[])
    parser.add_argument("--sync-breakpoint-design-note", action="append", default=[])
    parser.add_argument("--sync-breakpoint-pending", action="append", default=[])
    args = parser.parse_args()

    if not args.evidence:
        raise SystemExit("handoff requires at least one --evidence")
    if not args.closed and not args.breakpoint:
        raise SystemExit("open handoff requires --breakpoint or use --closed")

    extra_fields = parse_extra_fields(args.extra_field)
    handoff_dt = datetime.now().astimezone().replace(microsecond=0)
    handoff_time = handoff_dt.isoformat()

    if args.output_path:
        output_path = Path(args.output_path).expanduser()
    else:
        output_path = default_handoff_path(Path(args.handoff_dir).expanduser(), args.task_id, args.next_owner, handoff_dt)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = build_handoff_markdown(args, handoff_time, extra_fields)
    output_path.write_text(content, encoding="utf-8")

    result = {
        "ok": True,
        "handoff_path": str(output_path),
    }

    if args.sync_registry:
        result["registry_sync"] = sync_registry(args, output_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

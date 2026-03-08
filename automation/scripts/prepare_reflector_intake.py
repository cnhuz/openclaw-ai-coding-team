#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from execution_target import load_execution_target
from prepare_planner_intake import find_latest_handoff, normalize_list, select_tasks
from update_task_registry import load_registry


TARGET_STATES = {"Released"}


def openclaw_home_from_handoffs(handoffs_dir: Path) -> Path:
    return handoffs_dir.resolve().parents[1]


def find_first_match(evidence: list[str], marker: str) -> str | None:
    for item in evidence:
        if marker in item and item.endswith(".md"):
            return item
    return None


def build_packet(
    task: dict[str, Any],
    latest_handoff: str | None,
    execution_target: dict[str, Any],
    verification_report: str,
    release_note: str,
    knowledge_protocol: str,
    knowledge_template: str,
    reflection_output: str,
    proposal_output: str,
    captain_registry: str,
    captain_dashboard: str,
    captain_handoffs: str,
) -> str:
    evidence = normalize_list(task.get("evidence_pointer"))

    lines = [
        "# Reflector Intake Packet",
        "",
        f"- task_id: {task.get('task_id', 'unknown')}",
        f"- title: {task.get('title', 'unknown')}",
        f"- state: {task.get('state', 'unknown')}",
        f"- owner: {task.get('owner', 'unknown')}",
        f"- priority: {task.get('priority', 'unknown')}",
        f"- updated_at: {task.get('updated_at', 'unknown')}",
        f"- latest_handoff: {latest_handoff or 'none'}",
        f"- repo_root: {execution_target['repo_root']}",
        f"- captain_registry: {captain_registry}",
        f"- captain_dashboard: {captain_dashboard}",
        f"- captain_handoffs: {captain_handoffs}",
        "",
        "## Control Plane",
        "- state_source: captain_registry",
        "- dashboard_role: derived_observer",
        "- conflict_rule: if captain_registry and captain_dashboard disagree, trust captain_registry and refresh dashboard after state changes",
        "",
        "## Required Inputs",
        f"- verification_report: {verification_report}",
        f"- release_note: {release_note}",
        f"- knowledge_protocol: {knowledge_protocol}",
        f"- knowledge_template: {knowledge_template}",
        "",
        "## Required Outputs",
        f"- reflection_output: {reflection_output}",
        f"- proposal_output: {proposal_output}",
        "",
        "## Observe Checks",
    ]
    lines.extend(f"- {item}" for item in execution_target["observe_checks"] or ["none"])
    lines.extend(["", "## Evidence"])
    lines.extend(f"- {item}" for item in evidence or ["none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one reflector intake packet from the captain task registry.")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--handoffs-dir", required=True)
    parser.add_argument("--execution-target-path", required=True)
    parser.add_argument("--owner", default="aic-reflector")
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--packet-dir", default="reflection-intake")
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

    execution_target = load_execution_target(Path(args.execution_target_path).expanduser())
    states = set(args.state) if args.state else set(TARGET_STATES)
    selected = select_tasks([item for item in tasks if isinstance(item, dict)], args.owner, states, args.limit)
    if not selected:
        result = {"ok": True, "count": 0, "items": []}
        if args.format == "md":
            print("# reflector_intake\n\n- no tasks matched\n", end="")
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    openclaw_home = openclaw_home_from_handoffs(handoffs_dir)
    repo_root = Path(execution_target["repo_root"])
    knowledge_protocol = str((repo_root / "protocols/knowledge-pipeline.md").resolve())
    knowledge_template = str((repo_root / "templates/common/data/knowledge-proposals/TEMPLATE.json").resolve())
    captain_dashboard = str((registry_path.parent.parent / "data/dashboard.md").resolve())
    tester_workspace = openclaw_home / "workspace-aic-tester"
    releaser_workspace = openclaw_home / "workspace-aic-releaser"
    reflector_workspace = openclaw_home / "workspace-aic-reflector"

    packet_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for task in selected:
        task_id = str(task.get("task_id"))
        evidence = normalize_list(task.get("evidence_pointer"))
        verification_report = find_first_match(evidence, "verification-reports/")
        if verification_report is None:
            verification_report = str((tester_workspace / "verification-reports" / f"{task_id}.md").resolve())
        release_note = find_first_match(evidence, "release-notes/")
        if release_note is None:
            release_note = str((releaser_workspace / "release-notes" / f"{task_id}.md").resolve())
        reflection_output = str((reflector_workspace / "reflections" / f"{task_id}.md").resolve())
        proposal_output = str((reflector_workspace / "data/knowledge-proposals" / f"proposal-{task_id}.json").resolve())
        latest_handoff = find_latest_handoff(handoffs_dir, task_id, args.owner)
        packet_path = packet_dir / f"{task_id}.md"
        packet_path.write_text(
            build_packet(
                task=task,
                latest_handoff=latest_handoff,
                execution_target=execution_target,
                verification_report=verification_report,
                release_note=release_note,
                knowledge_protocol=knowledge_protocol,
                knowledge_template=knowledge_template,
                reflection_output=reflection_output,
                proposal_output=proposal_output,
                captain_registry=str(registry_path.resolve()),
                captain_dashboard=captain_dashboard,
                captain_handoffs=str(handoffs_dir.resolve()),
            ),
            encoding="utf-8",
        )
        items.append(
            {
                "task_id": task_id,
                "title": task.get("title"),
                "state": task.get("state"),
                "priority": task.get("priority"),
                "updated_at": task.get("updated_at"),
                "latest_handoff": latest_handoff,
                "packet_path": str(packet_path),
                "verification_report": verification_report,
                "release_note": release_note,
                "knowledge_protocol": knowledge_protocol,
                "knowledge_template": knowledge_template,
                "reflection_output": reflection_output,
                "proposal_output": proposal_output,
            }
        )

    result = {"ok": True, "count": len(items), "items": items}
    if args.format == "md":
        lines = ["# reflector_intake", "", f"- count: {len(items)}"]
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
                    f"- verification_report: {item['verification_report']}",
                    f"- release_note: {item['release_note']}",
                    f"- knowledge_protocol: {item['knowledge_protocol']}",
                    f"- knowledge_template: {item['knowledge_template']}",
                ]
            )
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

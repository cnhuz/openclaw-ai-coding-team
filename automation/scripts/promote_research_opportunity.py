#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from update_task_registry import load_registry, now_iso, upsert_task, write_registry


ALLOWED_STATUS = {"watchlist", "candidate", "ready_review", "promoted", "rejected"}


def load_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("opportunities payload must be an object")
    opportunities = data.get("opportunities")
    if not isinstance(opportunities, list):
        raise SystemExit("opportunities must be a list")
    return data


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def build_card(opportunity: dict[str, Any], generated_at: str) -> str:
    evidence_urls = normalize_list(opportunity.get("evidence_urls"))
    evidence_titles = normalize_list(opportunity.get("evidence_titles"))
    evidence_lines: list[str] = []
    for index, url in enumerate(evidence_urls[:8]):
        title = evidence_titles[index] if index < len(evidence_titles) else ""
        line = f"- {title} | {url}" if title else f"- {url}"
        evidence_lines.append(line)
    if not evidence_lines:
        evidence_lines.append("- 暂无外部证据链接")

    topic_lines = [f"- {item}" for item in normalize_list(opportunity.get("topic_ids"))]
    if not topic_lines:
        topic_lines.append("- general")

    source_lines = [f"- {item}" for item in normalize_list(opportunity.get("source_ids"))]
    if not source_lines:
        source_lines.append("- unknown")

    keywords = normalize_list(opportunity.get("keywords"))
    keyword_text = "、".join(keywords[:12]) if keywords else "none"

    lines = [
        "# Opportunity Card",
        "",
        f"- generated_at: {generated_at}",
        f"- opportunity_id: {opportunity['opportunity_id']}",
        f"- status: {opportunity.get('status', 'unknown')}",
        f"- priority: {opportunity.get('priority', 'unknown')}",
        f"- score: {opportunity.get('score', 'unknown')}",
        f"- recommended_action: {opportunity.get('recommended_action', 'monitor')}",
        "",
        "## 标题",
        opportunity.get("title", "Untitled Opportunity"),
        "",
        "## 面向谁",
        "\n".join(topic_lines),
        "",
        "## 机会来源",
        "\n".join(source_lines),
        "",
        "## 证据",
        "\n".join(evidence_lines),
        "",
        "## 为什么值得做",
        opportunity.get("summary", "待补充"),
        "",
        "## 风险",
        "- 需要进一步验证用户真实强度与可交付边界",
        "- 需要确认是否与现有正式任务重复",
        "",
        "## 建议动作",
        f"- {opportunity.get('recommended_action', 'monitor')}",
        "",
        "## 建议优先级",
        opportunity.get("priority", "P2"),
        "",
        "## 补充信息",
        f"- keywords: {keyword_text}",
        f"- signal_count: {opportunity.get('signal_count', 0)}",
        f"- source_diversity: {opportunity.get('source_diversity', 0)}",
    ]
    return "\n".join(lines) + "\n"


def create_task(task_registry_path: Path, opportunity: dict[str, Any], card_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    task_id = args.task_id or opportunity.get("task_id") or f"TASK-{opportunity['opportunity_id']}"
    priority = args.task_priority or opportunity.get("priority") or "P2"
    next_step = (
        args.task_next_step
        or f"基于 Opportunity Card 收敛需求与范围：{opportunity.get('recommended_action', '继续研究')}"
    )
    evidence = [str(card_path), str(args.path)]
    evidence.extend(normalize_list(opportunity.get("evidence_urls"))[:5])

    update_args = SimpleNamespace(
        task_id=task_id,
        title=args.task_title or opportunity.get("title"),
        state=args.task_state,
        owner=args.task_owner,
        priority=priority,
        next_step=next_step,
        blocker=None,
        clear_blocker=False,
        updated_at=args.updated_at or now_iso(),
        evidence=[],
        append_evidence=evidence,
        acceptance=[],
        notes=[
            f"Promoted from {opportunity['opportunity_id']}",
            *list(args.note),
        ],
        tags=["research-opportunity"],
        clear_breakpoint=False,
        breakpoint_reset=False,
        breakpoint_completed=[],
        breakpoint_next=[],
        breakpoint_design_note=[],
        breakpoint_pending=[],
    )

    registry = load_registry(task_registry_path)
    action, task = upsert_task(registry, update_args)
    registry["updatedAt"] = now_iso()
    write_registry(task_registry_path, registry)
    return {"action": action, "path": str(task_registry_path), "task": task}


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize or promote a research opportunity into an opportunity card or formal task.")
    parser.add_argument("--path", default="data/research/opportunities.json")
    parser.add_argument("--opportunity-id", required=True)
    parser.add_argument("--status", choices=sorted(ALLOWED_STATUS))
    parser.add_argument("--card-dir", default="data/research/opportunity-cards")
    parser.add_argument("--create-task", action="store_true")
    parser.add_argument("--task-registry-path", default="tasks/registry.json")
    parser.add_argument("--task-id")
    parser.add_argument("--task-title")
    parser.add_argument("--task-state", default="Intake")
    parser.add_argument("--task-owner", default="aic-planner")
    parser.add_argument("--task-priority")
    parser.add_argument("--task-next-step")
    parser.add_argument("--updated-at")
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args()

    opportunities_path = Path(args.path).expanduser()
    payload = load_payload(opportunities_path)
    opportunities = payload["opportunities"]

    target = None
    for opportunity in opportunities:
        if isinstance(opportunity, dict) and opportunity.get("opportunity_id") == args.opportunity_id:
            target = opportunity
            break
    if target is None:
        raise SystemExit(f"opportunity not found: {args.opportunity_id}")

    card_dir = Path(args.card_dir).expanduser()
    card_dir.mkdir(parents=True, exist_ok=True)
    generated_at = args.updated_at or now_iso()
    card_path = card_dir / f"{args.opportunity_id}.md"
    card_path.write_text(build_card(target, generated_at), encoding="utf-8")

    target["card_path"] = str(card_path)
    if args.status is not None:
        target["status"] = args.status
    elif args.create_task:
        target["status"] = "promoted"
    target["updated_at"] = generated_at

    existing_notes = target.get("notes")
    if not isinstance(existing_notes, list):
        existing_notes = []
    if args.note:
        existing_notes.extend(args.note)
    target["notes"] = existing_notes

    result: dict[str, Any] = {
        "ok": True,
        "opportunity_id": args.opportunity_id,
        "card_path": str(card_path),
        "status": target.get("status"),
    }

    if args.create_task:
        task_result = create_task(Path(args.task_registry_path).expanduser(), target, card_path, args)
        target["task_id"] = task_result["task"]["task_id"]
        result["task_sync"] = task_result

    payload["updatedAt"] = generated_at
    opportunities_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from create_handoff import build_handoff_markdown, default_handoff_path
from lockfile import acquire, release
from promote_research_opportunity import build_card, load_payload, normalize_list
from update_task_registry import load_registry, now_iso, upsert_task, write_registry


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", "", value).strip().lower()


def workspace_root_from_opportunities(path: Path) -> Path:
    try:
        return path.parents[2]
    except IndexError as exc:
        raise SystemExit(f"invalid opportunities path: {path}") from exc


def resolve_card_path(workspace_root: Path, opportunity: dict[str, Any], card_dir: Path, generated_at: str) -> Path:
    raw_path = opportunity.get("card_path")
    if isinstance(raw_path, str) and raw_path.strip():
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate
        return workspace_root / candidate

    card_dir.mkdir(parents=True, exist_ok=True)
    card_path = card_dir / f"{opportunity['opportunity_id']}.md"
    card_path.write_text(build_card(opportunity, generated_at), encoding="utf-8")
    opportunity["card_path"] = str(card_path)
    return card_path


def sort_opportunities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[int, float, float, str]:
        recommended = 0 if item.get("recommended_action") == "create_task" else 1
        score = -float(item.get("score", 0) or 0)
        updated = item.get("updated_at")
        updated_ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp() if isinstance(updated, str) and updated else float("-inf")
        return (recommended, score, -updated_ts, str(item.get("opportunity_id", "")))

    return sorted(rows, key=sort_key)


def is_related_task(task: dict[str, Any], opportunity: dict[str, Any], card_path: Path) -> bool:
    opportunity_id = str(opportunity.get("opportunity_id", ""))
    task_id = opportunity.get("task_id")
    if isinstance(task_id, str) and task_id and task.get("task_id") == task_id:
        return True

    evidence = normalize_list(task.get("evidence_pointer"))
    tags = normalize_list(task.get("tags"))
    if f"opportunity:{opportunity_id}" in tags:
        return True
    if any(opportunity_id in item for item in evidence):
        return True

    card_text = str(card_path)
    card_name = card_path.name
    for item in evidence:
        if item == card_text or item.endswith(card_name):
            return True

    task_title = task.get("title")
    opp_title = opportunity.get("title")
    if isinstance(task_title, str) and isinstance(opp_title, str) and normalize_title(task_title) == normalize_title(opp_title):
        return True
    return False


def select_candidate(opportunities: list[dict[str, Any]], registry: dict[str, Any], workspace_root: Path, card_dir: Path, min_score: float) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    tasks = [item for item in registry.get("tasks", []) if isinstance(item, dict)]
    best_linked: tuple[dict[str, Any], dict[str, Any]] | None = None

    for opportunity in sort_opportunities(opportunities):
        if opportunity.get("status") != "ready_review":
            continue
        if float(opportunity.get("score", 0) or 0) < min_score:
            continue
        card_path = resolve_card_path(workspace_root, opportunity, card_dir, now_iso())
        for task in tasks:
            if is_related_task(task, opportunity, card_path):
                best_linked = (opportunity, task)
                break
        else:
            return ("promote", opportunity, None)

    if best_linked is not None:
        return ("linked_existing", best_linked[0], best_linked[1])
    return ("no-ready-review", None, None)


def upsert_opportunity_task(registry_path: Path, opportunity: dict[str, Any], card_path: Path, owner: str, next_step: str, state: str) -> dict[str, Any]:
    task_id = opportunity.get("task_id") or f"TASK-{opportunity['opportunity_id']}"
    evidence = [
        opportunity["opportunity_id"],
        str(card_path),
        *normalize_list(opportunity.get("evidence_urls"))[:5],
    ]
    update_args = SimpleNamespace(
        task_id=task_id,
        title=opportunity.get("title"),
        state=state,
        owner=owner,
        priority=opportunity.get("priority") or "P2",
        next_step=next_step,
        blocker=None,
        clear_blocker=False,
        updated_at=now_iso(),
        evidence=[],
        append_evidence=evidence,
        acceptance=[],
        notes=[
            f"Promoted from {opportunity['opportunity_id']}",
            f"recommended_action={opportunity.get('recommended_action', 'monitor')}",
            f"evidence_count={opportunity.get('evidence_count', 0)}",
            f"evidence_domain_diversity={opportunity.get('evidence_domain_diversity', 0)}",
        ],
        tags=[
            "research-opportunity",
            f"opportunity:{opportunity['opportunity_id']}",
            *[f"topic:{topic_id}" for topic_id in normalize_list(opportunity.get("topic_ids"))],
        ],
        clear_breakpoint=False,
        breakpoint_reset=False,
        breakpoint_completed=[],
        breakpoint_next=[],
        breakpoint_design_note=[],
        breakpoint_pending=[],
    )

    registry = load_registry(registry_path)
    action, task = upsert_task(registry, update_args)
    registry["updatedAt"] = now_iso()
    write_registry(registry_path, registry)
    return {"action": action, "task": task}


def create_planner_handoff(
    handoff_dir: Path,
    task: dict[str, Any],
    opportunity: dict[str, Any],
    card_path: Path,
    next_owner: str,
    from_owner: str,
    breakpoint_text: str,
) -> Path:
    handoff_dt = datetime.now().astimezone().replace(microsecond=0)
    output_path = default_handoff_path(handoff_dir, task["task_id"], next_owner, handoff_dt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_args = SimpleNamespace(
        task_id=task["task_id"],
        current_stage=task.get("state", "Intake"),
        goal="把机会研究转成正式规格任务",
        deliverable="Opportunity Card + 关键证据 + 推荐方向",
        evidence=[str(card_path), *normalize_list(opportunity.get("evidence_urls"))[:3]],
        risk="需确认需求边界、非目标与验收标准，避免把热点误判成立项",
        next_owner=next_owner,
        breakpoint=breakpoint_text,
        closed=False,
        from_owner=from_owner,
    )
    content = build_handoff_markdown(
        handoff_args,
        handoff_dt.isoformat(),
        [
            ("opportunity_id", str(opportunity["opportunity_id"])),
            ("score", str(opportunity.get("score", "unknown"))),
            ("evidence_count", str(opportunity.get("evidence_count", 0))),
            ("evidence_domain_diversity", str(opportunity.get("evidence_domain_diversity", 0))),
            ("has_official_source", str(opportunity.get("has_official_source", False))),
        ],
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def append_handoff_evidence(
    registry_path: Path,
    task_id: str,
    opportunity_id: str,
    handoff_path: Path,
    owner: str,
    next_step: str,
    state: str,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    update_args = SimpleNamespace(
        task_id=task_id,
        title=None,
        state=state,
        owner=owner,
        priority=None,
        next_step=next_step,
        blocker=None,
        clear_blocker=False,
        updated_at=now_iso(),
        evidence=[],
        append_evidence=[str(handoff_path)],
        acceptance=[],
        notes=[f"handoff:{handoff_path.name}"],
        tags=[],
        clear_breakpoint=False,
        breakpoint_reset=False,
        breakpoint_completed=[],
        breakpoint_next=["基于 Opportunity Card 收敛范围、非目标、验收标准，并决定是否进入 Scoped"],
        breakpoint_design_note=[
            f"source_opportunity={opportunity_id}",
        ],
        breakpoint_pending=[],
    )
    _, task = upsert_task(registry, update_args)
    registry["updatedAt"] = now_iso()
    write_registry(registry_path, registry)
    return task


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge one ready_review research opportunity into a formal planner-owned task.")
    parser.add_argument("--opportunities-path", default="data/research/opportunities.json")
    parser.add_argument("--task-registry-path", default="tasks/registry.json")
    parser.add_argument("--card-dir")
    parser.add_argument("--handoff-dir", default="handoffs")
    parser.add_argument("--research-lock", default="data/research/_state/research.lock")
    parser.add_argument("--task-lock", default="tasks/_state/registry.lock")
    parser.add_argument("--min-score", type=float, default=0.7)
    parser.add_argument("--task-state", default="Intake")
    parser.add_argument("--task-owner", default="aic-planner")
    parser.add_argument("--from-owner", default="aic-researcher")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    opportunities_path = Path(args.opportunities_path).expanduser()
    research_lock = Path(args.research_lock).expanduser()
    task_lock = Path(args.task_lock).expanduser()

    research_lock_result = acquire(research_lock, timeout=120, stale_seconds=7200)
    if not research_lock_result.get("ok"):
        raise SystemExit(f"failed to acquire research lock: {research_lock}")

    try:
        payload = load_payload(opportunities_path)
        opportunities = [item for item in payload.get("opportunities", []) if isinstance(item, dict)]
        workspace_root = workspace_root_from_opportunities(opportunities_path)
        card_dir = Path(args.card_dir).expanduser() if args.card_dir else workspace_root / "data/research/opportunity-cards"
        registry_path = Path(args.task_registry_path).expanduser()
        registry = load_registry(registry_path)

        decision, opportunity, existing_task = select_candidate(opportunities, registry, workspace_root, card_dir, args.min_score)
        result: dict[str, Any] = {"ok": True, "decision": decision}
        if opportunity is None:
            if args.format == "md":
                print("# bridge_ready_review_opportunity\n\n- decision: no-ready-review\n", end="")
                return 0
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        card_path = resolve_card_path(workspace_root, opportunity, card_dir, now_iso())

        if decision == "linked_existing" and existing_task is not None:
            opportunity["status"] = "promoted"
            opportunity["task_id"] = existing_task.get("task_id")
            opportunity["updated_at"] = now_iso()
            payload["updatedAt"] = now_iso()
            opportunities_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result.update(
                {
                    "opportunity_id": opportunity["opportunity_id"],
                    "task_id": existing_task.get("task_id"),
                    "card_path": str(card_path),
                }
            )
            if args.format == "md":
                print(
                    "\n".join(
                        [
                            "# bridge_ready_review_opportunity",
                            "",
                            "- decision: linked_existing",
                            f"- opportunity_id: {opportunity['opportunity_id']}",
                            f"- task_id: {existing_task.get('task_id')}",
                            f"- card_path: {card_path}",
                        ]
                    )
                    + "\n",
                    end="",
                )
                return 0
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        task_lock_result = acquire(task_lock, timeout=120, stale_seconds=7200)
        if not task_lock_result.get("ok"):
            raise SystemExit(f"failed to acquire task lock: {task_lock}")
        try:
            next_step = "基于 Opportunity Card 收敛需求、边界和验收标准，并决定是否进入 Scoped"
            task_result = upsert_opportunity_task(registry_path, opportunity, card_path, args.task_owner, next_step, args.task_state)
            task = task_result["task"]
            handoff_path = create_planner_handoff(
                Path(args.handoff_dir).expanduser(),
                task,
                opportunity,
                card_path,
                args.task_owner,
                args.from_owner,
                next_step,
            )
            task = append_handoff_evidence(
                registry_path,
                task["task_id"],
                str(opportunity["opportunity_id"]),
                handoff_path,
                args.task_owner,
                next_step,
                args.task_state,
            )
        finally:
            release(task_lock)

        existing_notes = opportunity.get("notes")
        if not isinstance(existing_notes, list):
            existing_notes = []
        existing_notes.append(f"bridged_to_task:{task['task_id']}")
        opportunity["notes"] = existing_notes
        opportunity["task_id"] = task["task_id"]
        opportunity["status"] = "promoted"
        opportunity["updated_at"] = now_iso()
        payload["updatedAt"] = now_iso()
        opportunities_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result.update(
            {
                "opportunity_id": opportunity["opportunity_id"],
                "task_id": task["task_id"],
                "task_action": task_result["action"],
                "handoff_path": str(handoff_path),
                "card_path": str(card_path),
            }
        )
    finally:
        release(research_lock)

    if args.format == "md":
        print(
            "\n".join(
                [
                    "# bridge_ready_review_opportunity",
                    "",
                    f"- decision: {result['decision']}",
                    f"- opportunity_id: {result['opportunity_id']}",
                    f"- task_id: {result['task_id']}",
                    f"- handoff_path: {result['handoff_path']}",
                    f"- card_path: {result['card_path']}",
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

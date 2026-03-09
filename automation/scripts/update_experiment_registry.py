#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUSES = {
    "planned",
    "running",
    "validated",
    "invalidated",
    "inconclusive",
    "paused",
    "stopped",
    "archived",
}

HYPOTHESIS_TYPES = {
    "revenue",
    "distribution",
    "pricing",
    "cost",
    "automation_fit",
    "influence",
    "other",
}

STOP_DECISIONS = {
    "continue",
    "pivot",
    "stop",
    "scale",
    "observe",
}

FINAL_STATUSES = {"validated", "invalidated", "stopped", "archived"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "updatedAt": now_iso(), "experiments": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("experiment registry must be a JSON object")
    experiments = data.get("experiments")
    if not isinstance(experiments, list):
        raise SystemExit("experiment registry experiments must be a list")
    return data


def write_registry(path: Path, registry: dict[str, Any]) -> None:
    registry["updatedAt"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_list(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def next_experiment_id(registry: dict[str, Any]) -> str:
    prefix = datetime.now(timezone.utc).strftime("EXP-%Y%m%d")
    max_value = 0
    for item in registry.get("experiments", []):
        if not isinstance(item, dict):
            continue
        experiment_id = item.get("experiment_id")
        if not isinstance(experiment_id, str):
            continue
        if not experiment_id.startswith(prefix + "-"):
            continue
        tail = experiment_id.rsplit("-", 1)[-1]
        if tail.isdigit():
            max_value = max(max_value, int(tail))
    return f"{prefix}-{max_value + 1:03d}"


def find_experiment(registry: dict[str, Any], experiment_id: str) -> dict[str, Any] | None:
    for item in registry.get("experiments", []):
        if isinstance(item, dict) and item.get("experiment_id") == experiment_id:
            return item
    return None


def render_md(experiment: dict[str, Any]) -> str:
    lines = [
        "# experiment_update",
        "",
        f"- experiment_id: {experiment.get('experiment_id', '-')}",
        f"- source: {experiment.get('source_type', '-')}/{experiment.get('source_id', '-')}",
        f"- status: {experiment.get('status', '-')}",
        f"- owner: {experiment.get('owner', '-')}",
        f"- hypothesis_type: {experiment.get('hypothesis_type', '-')}",
        f"- hypothesis: {experiment.get('hypothesis', '-')}",
        f"- metric_name: {experiment.get('metric_name', '-')}",
        f"- target_value: {experiment.get('target_value', '-')}",
        f"- current_value: {experiment.get('current_value', '-')}",
        f"- stop_decision: {experiment.get('stop_decision', '-')}",
        f"- next_step: {experiment.get('next_step', '-')}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a structured commercialization experiment record.")
    parser.add_argument("--path", required=True)
    parser.add_argument("--experiment-id")
    parser.add_argument("--source-type", choices=["task", "opportunity"])
    parser.add_argument("--source-id")
    parser.add_argument("--title")
    parser.add_argument("--owner")
    parser.add_argument("--status", choices=sorted(STATUSES))
    parser.add_argument("--hypothesis-type", choices=sorted(HYPOTHESIS_TYPES))
    parser.add_argument("--hypothesis")
    parser.add_argument("--metric-name")
    parser.add_argument("--target-value")
    parser.add_argument("--current-value")
    parser.add_argument("--unit")
    parser.add_argument("--result-summary")
    parser.add_argument("--stop-decision", choices=sorted(STOP_DECISIONS))
    parser.add_argument("--next-step")
    parser.add_argument("--business-model")
    parser.add_argument("--append-track", action="append", default=[])
    parser.add_argument("--append-distribution-path", action="append", default=[])
    parser.add_argument("--append-success-indicator", action="append", default=[])
    parser.add_argument("--append-stop-condition", action="append", default=[])
    parser.add_argument("--append-note", action="append", default=[])
    parser.add_argument("--append-evidence", action="append", default=[])
    parser.add_argument("--mark-started", action="store_true")
    parser.add_argument("--mark-completed", action="store_true")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    registry = load_registry(path)
    experiment_id = args.experiment_id or next_experiment_id(registry)
    experiment = find_experiment(registry, experiment_id)
    created = False
    if experiment is None:
        if not args.source_type or not args.source_id:
            raise SystemExit("new experiment requires --source-type and --source-id")
        experiment = {
            "experiment_id": experiment_id,
            "source_type": args.source_type,
            "source_id": args.source_id,
            "title": args.title or f"{args.source_type}:{args.source_id}",
            "owner": args.owner or "aic-captain",
            "status": args.status or "planned",
            "hypothesis_type": args.hypothesis_type or "other",
            "hypothesis": args.hypothesis or "",
            "metric_name": args.metric_name or "",
            "target_value": args.target_value or "",
            "current_value": args.current_value or "",
            "unit": args.unit or "",
            "result_summary": args.result_summary or "",
            "stop_decision": args.stop_decision or "observe",
            "next_step": args.next_step or "",
            "business_model": args.business_model or "",
            "tracks": normalize_list(args.append_track),
            "distribution_paths": normalize_list(args.append_distribution_path),
            "success_indicators": normalize_list(args.append_success_indicator),
            "stop_conditions": normalize_list(args.append_stop_condition),
            "notes": normalize_list(args.append_note),
            "evidence": normalize_list(args.append_evidence),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        if args.mark_started or experiment["status"] == "running":
            experiment["started_at"] = now_iso()
        registry["experiments"].append(experiment)
        created = True

    if args.source_type:
        experiment["source_type"] = args.source_type
    if args.source_id:
        experiment["source_id"] = args.source_id
    if args.title:
        experiment["title"] = args.title
    if args.owner:
        experiment["owner"] = args.owner
    if args.status:
        experiment["status"] = args.status
    if args.hypothesis_type:
        experiment["hypothesis_type"] = args.hypothesis_type
    if args.hypothesis is not None:
        experiment["hypothesis"] = args.hypothesis
    if args.metric_name is not None:
        experiment["metric_name"] = args.metric_name
    if args.target_value is not None:
        experiment["target_value"] = args.target_value
    if args.current_value is not None:
        experiment["current_value"] = args.current_value
    if args.unit is not None:
        experiment["unit"] = args.unit
    if args.result_summary is not None:
        experiment["result_summary"] = args.result_summary
    if args.stop_decision:
        experiment["stop_decision"] = args.stop_decision
    if args.next_step is not None:
        experiment["next_step"] = args.next_step
    if args.business_model is not None:
        experiment["business_model"] = args.business_model

    if args.append_track:
        experiment["tracks"] = normalize_list([*experiment.get("tracks", []), *args.append_track])
    if args.append_distribution_path:
        experiment["distribution_paths"] = normalize_list([*experiment.get("distribution_paths", []), *args.append_distribution_path])
    if args.append_success_indicator:
        experiment["success_indicators"] = normalize_list([*experiment.get("success_indicators", []), *args.append_success_indicator])
    if args.append_stop_condition:
        experiment["stop_conditions"] = normalize_list([*experiment.get("stop_conditions", []), *args.append_stop_condition])
    if args.append_note:
        experiment["notes"] = normalize_list([*experiment.get("notes", []), *args.append_note])
    if args.append_evidence:
        experiment["evidence"] = normalize_list([*experiment.get("evidence", []), *args.append_evidence])

    if args.mark_started and not experiment.get("started_at"):
        experiment["started_at"] = now_iso()
    if experiment.get("status") == "running" and not experiment.get("started_at"):
        experiment["started_at"] = now_iso()
    if args.mark_completed or experiment.get("status") in FINAL_STATUSES:
        experiment["completed_at"] = now_iso()

    experiment["updated_at"] = now_iso()
    write_registry(path, registry)

    payload = {
        "ok": True,
        "created": created,
        "experiment": experiment,
        "path": str(path),
    }
    if args.format == "md":
        print(render_md(experiment), end="")
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

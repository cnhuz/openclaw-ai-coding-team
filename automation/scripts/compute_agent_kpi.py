#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ACTIVE_TASK_STATES = {
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

TASK_ID_PATTERN = re.compile(r"TASK-[A-Z0-9-]+")

HANDOFF_REQUIRED_FIELDS = [
    "任务ID",
    "当前阶段",
    "目标",
    "交付物",
    "证据",
    "风险/阻塞",
    "下一负责人",
    "Breakpoint",
]

AGENT_ORDER = [
    "aic-captain",
    "aic-researcher",
    "aic-planner",
    "aic-reviewer",
    "aic-dispatcher",
    "aic-builder",
    "aic-tester",
    "aic-releaser",
    "aic-reflector",
    "aic-curator",
]

ROLE_OUTPUT_TARGETS = {
    "aic-captain": {"handoffs": 2, "opportunity_promotions": 1},
    "aic-researcher": {"opportunities": 2, "ready_review": 1},
    "aic-planner": {"specs": 1, "handoffs": 1},
    "aic-reviewer": {"handoffs": 1},
    "aic-dispatcher": {"handoffs": 1, "dispatch_logs": 1},
    "aic-builder": {"handoffs": 1, "task_updates": 1},
    "aic-tester": {"verification_reports": 1, "handoffs": 1},
    "aic-releaser": {"release_notes": 1, "handoffs": 1},
    "aic-reflector": {"reflections": 1, "proposals": 1},
    "aic-curator": {"closed_tasks": 1},
}

ROLE_QUALITY_TARGETS = {
    "aic-researcher": {"evidence_count": 4, "domain_diversity": 3},
}


@dataclass(frozen=True)
class RuntimePaths:
    openclaw_home: Path

    @property
    def captain_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-captain"

    @property
    def researcher_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-researcher"

    @property
    def planner_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-planner"

    @property
    def reviewer_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-reviewer"

    @property
    def dispatcher_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-dispatcher"

    @property
    def builder_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-builder"

    @property
    def tester_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-tester"

    @property
    def releaser_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-releaser"

    @property
    def reflector_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-reflector"

    @property
    def curator_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-curator"

    @property
    def registry_path(self) -> Path:
        return self.captain_workspace / "tasks/registry.json"

    @property
    def handoffs_dir(self) -> Path:
        return self.captain_workspace / "handoffs"

    @property
    def opportunities_path(self) -> Path:
        return self.researcher_workspace / "data/research/opportunities.json"

    @property
    def workspaces(self) -> dict[str, Path]:
        return {
            "aic-captain": self.captain_workspace,
            "aic-researcher": self.researcher_workspace,
            "aic-planner": self.planner_workspace,
            "aic-reviewer": self.reviewer_workspace,
            "aic-dispatcher": self.dispatcher_workspace,
            "aic-builder": self.builder_workspace,
            "aic-tester": self.tester_workspace,
            "aic-releaser": self.releaser_workspace,
            "aic-reflector": self.reflector_workspace,
            "aic-curator": self.curator_workspace,
        }


def clamp_score(value: float) -> int:
    if value < 0:
        return 0
    if value > 100:
        return 100
    return round(value)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def in_window(moment: datetime | None, start: datetime, end: datetime) -> bool:
    if moment is None:
        return False
    return start <= moment < end


def required_task_fields(task: dict) -> int:
    score = 0
    for key in ["task_id", "title", "state", "owner", "priority", "updated_at", "next_step"]:
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            score += 1
    evidence = task.get("evidence_pointer")
    if isinstance(evidence, list) and evidence:
        score += 1
    return score


def parse_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def task_self_sustainability_score(task: dict) -> float | None:
    notes = task.get("notes")
    if not isinstance(notes, list):
        return None
    for item in notes:
        if not isinstance(item, str):
            continue
        if not item.startswith("self_sustainability_score="):
            continue
        return parse_float(item.split("=", 1)[1].strip())
    return None


def task_track_count(task: dict) -> int:
    tags = task.get("tags")
    if not isinstance(tags, list):
        return 0
    return len([item for item in tags if isinstance(item, str) and item.startswith("track:")])


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def count_score(count: int, target: int) -> int:
    if target <= 0:
        return 100
    return clamp_score((count / target) * 100)


def proportion_score(good: int, total: int) -> int | None:
    if total == 0:
        return None
    return clamp_score((good / total) * 100)


def run_json_command(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"ok": False, "stderr": result.stderr.strip(), "stdout": result.stdout.strip()}
    return json.loads(result.stdout)


def detect_log_status(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace").lower()
    filename = path.name.lower()
    if "traceback" in content or "status=error" in content or "status: error" in content or "validator: failed" in content or " error:" in content or "failed" in filename:
        return "error"
    if "no-op" in filename or "no-op" in content or "decision: no-op" in content or "no tasks matched" in content or "heartbeat_ok" in content:
        return "noop"
    return "ok"


def parse_handoff(path: Path) -> dict:
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if ": " not in raw_line:
            continue
        key, value = raw_line.split(": ", 1)
        fields[key] = value
    recipient = "-"
    if "-to-" in path.stem:
        recipient = path.stem.rsplit("-to-", 1)[1]
    filled = 0
    for field in HANDOFF_REQUIRED_FIELDS:
        value = fields.get(field, "").strip()
        if value and value != "无":
            filled += 1
    return {
        "path": path,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        "sender": fields.get("发送方", "-"),
        "recipient": recipient,
        "task_id": fields.get("任务ID", "-"),
        "stage": fields.get("当前阶段", "-"),
        "completeness": filled / len(HANDOFF_REQUIRED_FIELDS),
    }


def load_handoffs(paths: RuntimePaths, start: datetime, end: datetime) -> list[dict]:
    rows: list[dict] = []
    if not paths.handoffs_dir.exists():
        return rows
    for path in paths.handoffs_dir.rglob("*.md"):
        if path.name in {"README.md", "TEMPLATE.md"}:
            continue
        handoff = parse_handoff(path)
        if in_window(handoff["updated_at"], start, end):
            rows.append(handoff)
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def load_exec_logs(paths: RuntimePaths, start: datetime, end: datetime) -> list[dict]:
    rows: list[dict] = []
    for agent_id, workspace in paths.workspaces.items():
        log_root = workspace / "data/exec-logs"
        if not log_root.exists():
            continue
        for path in log_root.rglob("*.md"):
            updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if not in_window(updated_at, start, end):
                continue
            task_match = TASK_ID_PATTERN.search(path.name)
            rows.append(
                {
                    "agent_id": agent_id,
                    "job_name": path.parent.name,
                    "path": path,
                    "updated_at": updated_at,
                    "status": detect_log_status(path),
                    "task_id": task_match.group(0) if task_match else None,
                }
            )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def load_artifacts(root: Path, start: datetime, end: datetime, suffixes: tuple[str, ...]) -> list[dict]:
    rows: list[dict] = []
    if not root.exists():
        return rows
    for suffix in suffixes:
        for path in root.rglob(f"*{suffix}"):
            updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if not in_window(updated_at, start, end):
                continue
            task_match = TASK_ID_PATTERN.search(path.name)
            rows.append(
                {
                    "path": path,
                    "updated_at": updated_at,
                    "task_id": task_match.group(0) if task_match else None,
                }
            )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def build_window(period: str, anchor_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    if period == "daily":
        start_local = datetime.combine(anchor_date, time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    weekday = anchor_date.weekday()
    monday = anchor_date - timedelta(days=weekday)
    start_local = datetime.combine(monday, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def load_rules(path: Path) -> dict:
    payload = load_json(path)
    if payload.get("schemaVersion") != 1:
        raise SystemExit("unsupported KPI rules schemaVersion")
    return payload


def load_runtime_snapshot() -> dict:
    return {
        "status": run_json_command(["openclaw", "status", "--deep", "--json"]),
        "cron": run_json_command(["openclaw", "cron", "list", "--json"]),
    }


def find_current_cron_rows(snapshot: dict, agent_id: str, relevant_jobs: list[str]) -> list[dict]:
    rows: list[dict] = []
    jobs = snapshot["cron"].get("jobs", [])
    for item in jobs:
        if item.get("agentId") != agent_id:
            continue
        if item.get("name") not in relevant_jobs:
            continue
        state = item.get("state", {})
        rows.append(
            {
                "name": item["name"],
                "enabled": item.get("enabled", False),
                "running": state.get("runningAtMs") is not None,
                "last_run_status": state.get("lastRunStatus") or "-",
                "consecutive_errors": int(state.get("consecutiveErrors", 0) or 0),
            }
        )
    return rows


def find_sessions(snapshot: dict, agent_id: str) -> tuple[int, datetime | None]:
    by_agent = snapshot["status"].get("sessions", {}).get("byAgent", [])
    for item in by_agent:
        if item.get("agentId") != agent_id:
            continue
        recent = item.get("recent", [])
        last_activity = None
        if recent:
            updated_at_ms = recent[0].get("updatedAt")
            if updated_at_ms is not None:
                last_activity = datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc)
        return int(item.get("count", 0) or 0), last_activity
    return 0, None


def build_role_outputs(paths: RuntimePaths, start: datetime, end: datetime) -> dict[str, dict[str, list[dict]]]:
    outputs = {
        "aic-planner": {
            "specs": load_artifacts(paths.planner_workspace / "specs", start, end, (".md",)),
        },
        "aic-tester": {
            "verification_reports": load_artifacts(paths.tester_workspace / "verification-reports", start, end, (".md",)),
        },
        "aic-releaser": {
            "release_notes": load_artifacts(paths.releaser_workspace / "release-notes", start, end, (".md",)),
        },
        "aic-reflector": {
            "reflections": load_artifacts(paths.reflector_workspace / "reflections", start, end, (".md",)),
            "proposals": load_artifacts(paths.reflector_workspace / "data/knowledge-proposals", start, end, (".json",)),
        },
    }
    return outputs


def compute_research_quality(opportunities: list[dict]) -> int | None:
    values: list[float] = []
    targets = ROLE_QUALITY_TARGETS["aic-researcher"]
    for item in opportunities:
        evidence_part = min(1.0, float(item.get("evidence_count", 0) or 0) / targets["evidence_count"])
        diversity_part = min(1.0, float(item.get("evidence_domain_diversity", 0) or 0) / targets["domain_diversity"])
        official_part = 1.0 if item.get("has_official_source") else 0.0
        values.append(evidence_part * 0.4 + diversity_part * 0.3 + official_part * 0.3)
    avg = average(values)
    if avg is None:
        return None
    return clamp_score(avg * 100)


def compute_north_star_opportunity_score(opportunities: list[dict]) -> int | None:
    values = [parse_float(item.get("self_sustainability_score")) for item in opportunities]
    filtered = [value for value in values if value is not None]
    avg = average(filtered)
    if avg is None:
        return None
    return clamp_score(avg * 100)


def compute_task_alignment_score(tasks: list[dict]) -> int | None:
    score_values: list[float] = []
    for task in tasks:
        score = task_self_sustainability_score(task)
        if score is not None:
            score_values.append(score)
    avg_score = average(score_values)
    if avg_score is not None:
        return clamp_score(avg_score * 100)

    track_values = [task_track_count(task) for task in tasks]
    if not track_values:
        return None
    if max(track_values) == 0:
        return None
    return clamp_score(min(1.0, average(track_values) / 2) * 100)


def build_agent_context(
    agent_id: str,
    role_rules: dict,
    tasks: list[dict],
    handoffs: list[dict],
    logs: list[dict],
    opportunities: list[dict],
    outputs: dict[str, dict[str, list[dict]]],
    snapshot: dict,
    window_start: datetime,
    window_end: datetime,
    stale_hours: int,
) -> dict:
    owned_tasks_all = [task for task in tasks if task.get("owner") == agent_id]
    current_tasks = [task for task in owned_tasks_all if task.get("state") in ACTIVE_TASK_STATES]
    updated_tasks = [
        task
        for task in current_tasks
        if in_window(parse_iso(task.get("updated_at")), window_start, window_end)
    ]
    updated_owned_tasks_all = [
        task
        for task in owned_tasks_all
        if in_window(parse_iso(task.get("updated_at")), window_start, window_end)
    ]
    stale_tasks = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    for task in current_tasks:
        updated_at = parse_iso(task.get("updated_at"))
        if updated_at is not None and updated_at < cutoff:
            stale_tasks.append(task)

    sent_handoffs = [item for item in handoffs if item["sender"] == agent_id]
    received_handoffs = [item for item in handoffs if item["recipient"] == agent_id]
    relevant_jobs = role_rules.get("relevant_jobs", [])
    agent_logs = [item for item in logs if item["agent_id"] == agent_id]
    relevant_logs = [item for item in agent_logs if item["job_name"] in relevant_jobs] if relevant_jobs else agent_logs
    failed_logs = [item for item in relevant_logs if item["status"] == "error"]
    noop_logs = [item for item in relevant_logs if item["status"] == "noop"]
    sessions_count, last_activity = find_sessions(snapshot, agent_id)
    current_cron_rows = find_current_cron_rows(snapshot, agent_id, relevant_jobs)
    current_failed_jobs = [item for item in current_cron_rows if item["consecutive_errors"] > 0 or item["last_run_status"] == "error"]
    running_jobs = [item for item in current_cron_rows if item["running"]]

    context = {
        "current_tasks": current_tasks,
        "owned_tasks_all": owned_tasks_all,
        "updated_tasks": updated_tasks,
        "updated_owned_tasks_all": updated_owned_tasks_all,
        "stale_tasks": stale_tasks,
        "sent_handoffs": sent_handoffs,
        "received_handoffs": received_handoffs,
        "relevant_logs": relevant_logs,
        "failed_logs": failed_logs,
        "noop_logs": noop_logs,
        "sessions_count": sessions_count,
        "last_activity": last_activity,
        "current_failed_jobs": current_failed_jobs,
        "running_jobs": running_jobs,
        "window_opportunities": [
            item
            for item in opportunities
            if in_window(parse_iso(item.get("updated_at")), window_start, window_end)
        ],
        "research_opportunities": [],
        "role_outputs": outputs.get(agent_id, {}),
    }

    if agent_id == "aic-researcher":
        context["research_opportunities"] = context["window_opportunities"]

    return context


def score_health(agent_id: str, context: dict, mandatory: bool) -> tuple[int | None, list[dict], list[str]]:
    applicable = mandatory or bool(context["current_tasks"]) or bool(context["relevant_logs"]) or bool(context["sent_handoffs"])
    if not applicable:
        return None, [], []

    penalty = 0
    metrics: list[dict] = []
    risks: list[str] = []
    failed_count = len(context["failed_logs"]) + len(context["current_failed_jobs"])
    stale_count = len(context["stale_tasks"])
    idle_flag = mandatory and not context["relevant_logs"] and not context["updated_tasks"] and not context["sent_handoffs"]

    if failed_count:
        penalty += min(70, failed_count * 25)
        risks.append(f"{agent_id} 存在 {failed_count} 次失败日志/失败 job")
    if stale_count:
        penalty += min(40, stale_count * 20)
        risks.append(f"{agent_id} 当前持有 {stale_count} 张陈旧任务")
    if idle_flag:
        penalty += 20
        risks.append(f"{agent_id} 本周期缺少应有的推进痕迹")

    metrics.append({"metric_id": "failed_events", "group": "health", "value": failed_count, "score": clamp_score(100 - min(70, failed_count * 25))})
    metrics.append({"metric_id": "stale_tasks", "group": "health", "value": stale_count, "score": clamp_score(100 - min(40, stale_count * 20))})
    metrics.append({"metric_id": "mandatory_activity", "group": "health", "value": 0 if idle_flag else 1, "score": 0 if idle_flag else 100})
    return clamp_score(100 - penalty), metrics, risks


def score_compliance(context: dict) -> tuple[int | None, list[dict], list[str]]:
    metrics: list[dict] = []
    risks: list[str] = []
    scores: list[float] = []

    if context["sent_handoffs"]:
        completeness = average([item["completeness"] for item in context["sent_handoffs"]])
        if completeness is not None:
            score = clamp_score(completeness * 100)
            scores.append(score)
            metrics.append({"metric_id": "handoff_completeness", "group": "compliance", "value": round(completeness, 3), "score": score})
            if score < 80:
                risks.append("handoff 合同完整度偏低")

    if context["current_tasks"]:
        task_field_scores = [required_task_fields(task) / 8 for task in context["current_tasks"]]
        task_completeness = average(task_field_scores)
        if task_completeness is not None:
            score = clamp_score(task_completeness * 100)
            scores.append(score)
            metrics.append({"metric_id": "task_hygiene", "group": "compliance", "value": round(task_completeness, 3), "score": score})
            if score < 80:
                risks.append("当前持有任务字段不够完整")

    if not scores:
        return None, [], []
    return clamp_score(sum(scores) / len(scores)), metrics, risks


def score_output(agent_id: str, context: dict, period: str) -> tuple[int | None, list[dict], list[str]]:
    metrics: list[dict] = []
    highlights: list[str] = []
    targets = ROLE_OUTPUT_TARGETS[agent_id]
    scale = 1 if period == "daily" else 3
    scores: list[float] = []

    def add(metric_id: str, value: int, target_key: str, label: str) -> None:
        target = targets[target_key] * scale
        score = count_score(value, target)
        scores.append(score)
        metrics.append({"metric_id": metric_id, "group": "output", "value": value, "target": target, "score": score})
        if value > 0:
            highlights.append(f"{label}: {value}")

    if agent_id == "aic-captain":
        add("captain_handoffs", len(context["sent_handoffs"]), "handoffs", "经营总控交接")
        promoted = len([item for item in context["window_opportunities"] if item.get("task_id")])
        add("opportunity_promotions", promoted, "opportunity_promotions", "机会晋升")
        offload_score = 100 if not context["current_tasks"] else 30
        scores.append(offload_score)
        metrics.append({"metric_id": "captain_offload", "group": "output", "value": len(context["current_tasks"]), "score": offload_score})
    elif agent_id == "aic-researcher":
        opportunities = context["research_opportunities"]
        add("research_opportunities", len(opportunities), "opportunities", "研究机会")
        ready_review = len([item for item in opportunities if item.get("status") == "ready_review"])
        promoted = len([item for item in opportunities if item.get("status") == "promoted"])
        add("ready_review_or_promoted", ready_review + promoted, "ready_review", "成熟机会")
    elif agent_id == "aic-planner":
        specs = len(context["role_outputs"].get("specs", []))
        add("planner_specs", specs, "specs", "规格产物")
        add("planner_handoffs", len(context["sent_handoffs"]), "handoffs", "规划交接")
    elif agent_id == "aic-reviewer":
        add("reviewer_handoffs", len(context["sent_handoffs"]), "handoffs", "审议交接")
    elif agent_id == "aic-dispatcher":
        dispatch_logs = len([item for item in context["relevant_logs"] if item["job_name"] == "dispatch-approved"])
        add("dispatcher_handoffs", len(context["sent_handoffs"]), "handoffs", "调度交接")
        add("dispatcher_logs", dispatch_logs, "dispatch_logs", "调度执行")
    elif agent_id == "aic-builder":
        add("builder_handoffs", len(context["sent_handoffs"]), "handoffs", "实现交接")
        add("builder_task_updates", len(context["updated_tasks"]), "task_updates", "实现推进")
    elif agent_id == "aic-tester":
        reports = len(context["role_outputs"].get("verification_reports", []))
        add("verification_reports", reports, "verification_reports", "验证报告")
        add("tester_handoffs", len(context["sent_handoffs"]), "handoffs", "测试交接")
    elif agent_id == "aic-releaser":
        notes = len(context["role_outputs"].get("release_notes", []))
        add("release_notes", notes, "release_notes", "发布记录")
        add("releaser_handoffs", len(context["sent_handoffs"]), "handoffs", "发布交接")
    elif agent_id == "aic-reflector":
        reflections = len(context["role_outputs"].get("reflections", []))
        proposals = len(context["role_outputs"].get("proposals", []))
        add("reflections", reflections, "reflections", "复盘文档")
        add("proposals", proposals, "proposals", "知识提案")
    elif agent_id == "aic-curator":
        closed_count = len([task for task in context["updated_owned_tasks_all"] if task.get("state") == "Closed"])
        add("closed_tasks", closed_count, "closed_tasks", "关单沉淀")

    if not scores:
        return None, [], []
    return clamp_score(sum(scores) / len(scores)), metrics, highlights


def score_quality(agent_id: str, context: dict, period: str) -> tuple[int | None, list[dict], list[str]]:
    metrics: list[dict] = []
    notes: list[str] = []
    scores: list[float] = []

    if context["sent_handoffs"]:
        handoff_score = clamp_score((average([item["completeness"] for item in context["sent_handoffs"]]) or 0) * 100)
        scores.append(handoff_score)
        metrics.append({"metric_id": "handoff_quality", "group": "quality", "value": len(context["sent_handoffs"]), "score": handoff_score})

    if agent_id == "aic-researcher":
        research_quality = compute_research_quality(context["research_opportunities"])
        if research_quality is not None:
            scores.append(research_quality)
            metrics.append({"metric_id": "research_evidence_quality", "group": "quality", "value": len(context["research_opportunities"]), "score": research_quality})
            if research_quality >= 80:
                notes.append("研究证据质量较好")
        north_star_score = compute_north_star_opportunity_score(context["research_opportunities"])
        if north_star_score is not None:
            scores.append(north_star_score)
            metrics.append({"metric_id": "research_north_star_alignment", "group": "quality", "value": len(context["research_opportunities"]), "score": north_star_score})
            if north_star_score >= 75:
                notes.append("研究机会更贴近自养方向")

    if agent_id == "aic-captain":
        captain_candidates = context["updated_owned_tasks_all"]
        captain_score = compute_task_alignment_score(captain_candidates)
        captain_value = len(captain_candidates)
        if captain_score is None:
            promoted_or_ready = [
                item
                for item in context["window_opportunities"]
                if item.get("status") in {"ready_review", "promoted"}
            ]
            captain_candidates = promoted_or_ready or context["window_opportunities"]
            captain_score = compute_north_star_opportunity_score(captain_candidates)
            captain_value = len(captain_candidates)
        if captain_score is not None:
            scores.append(captain_score)
            metrics.append({"metric_id": "captain_north_star_alignment", "group": "quality", "value": captain_value, "score": captain_score})

    if agent_id in {"aic-planner", "aic-reviewer", "aic-dispatcher", "aic-builder", "aic-tester", "aic-releaser", "aic-reflector", "aic-curator"}:
        task_alignment = compute_task_alignment_score(context["updated_owned_tasks_all"] or context["current_tasks"])
        if task_alignment is not None:
            scores.append(task_alignment)
            metrics.append({"metric_id": "task_north_star_alignment", "group": "quality", "value": len(context["updated_owned_tasks_all"] or context["current_tasks"]), "score": task_alignment})

    if agent_id == "aic-builder":
        rework_count = len([task for task in context["current_tasks"] if task.get("state") == "Rework"])
        score = clamp_score(100 - rework_count * 25)
        scores.append(score)
        metrics.append({"metric_id": "rework_penalty", "group": "quality", "value": rework_count, "score": score})
        if rework_count > 0:
            notes.append("存在返工任务")

    if agent_id == "aic-tester":
        reports = len(context["role_outputs"].get("verification_reports", []))
        if reports > 0:
            report_score = 100
            scores.append(report_score)
            metrics.append({"metric_id": "verification_output_quality", "group": "quality", "value": reports, "score": report_score})

    if agent_id == "aic-releaser":
        notes_count = len(context["role_outputs"].get("release_notes", []))
        if notes_count > 0:
            release_score = 100
            scores.append(release_score)
            metrics.append({"metric_id": "release_output_quality", "group": "quality", "value": notes_count, "score": release_score})

    if agent_id == "aic-reflector":
        reflections = len(context["role_outputs"].get("reflections", []))
        proposals = len(context["role_outputs"].get("proposals", []))
        if reflections > 0 or proposals > 0:
            pair_gap = abs(reflections - proposals)
            score = clamp_score(100 - pair_gap * 25)
            scores.append(score)
            metrics.append({"metric_id": "reflection_proposal_pairing", "group": "quality", "value": {"reflections": reflections, "proposals": proposals}, "score": score})

    failed_penalty = len(context["failed_logs"])
    if failed_penalty > 0:
        score = clamp_score(100 - failed_penalty * 30)
        scores.append(score)
        metrics.append({"metric_id": "failed_log_penalty", "group": "quality", "value": failed_penalty, "score": score})
        notes.append("本周期存在失败执行日志")

    if not scores:
        return None, [], []
    return clamp_score(sum(scores) / len(scores)), metrics, notes


def combine_scores(period_weights: dict[str, int], sections: dict[str, int | None]) -> tuple[int | None, dict[str, int | None]]:
    numerator = 0.0
    denominator = 0.0
    for section, weight in period_weights.items():
        value = sections.get(section)
        if value is None:
            continue
        numerator += value * weight
        denominator += weight
    if denominator == 0:
        return None, sections
    return clamp_score(numerator / denominator), sections


def build_scorecard(
    agent_id: str,
    role_rules: dict,
    period: str,
    window_start: datetime,
    window_end: datetime,
    weights: dict[str, int],
    context: dict,
    mandatory: bool,
) -> dict:
    obligation_count = (
        len(context["current_tasks"])
        + len(context["received_handoffs"])
        + len(context["sent_handoffs"])
        + len(context["updated_owned_tasks_all"])
        + len(context["research_opportunities"])
        + sum(len(rows) for rows in context["role_outputs"].values())
    )
    if not mandatory and obligation_count == 0:
        return {
            "agent_id": agent_id,
            "name": role_rules["name"],
            "title": role_rules["title"],
            "period": period,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "status": "n_a",
            "score_total": None,
            "score_breakdown": {
                "health": None,
                "compliance": None,
                "output": None,
                "quality": None,
            },
            "metrics": [],
            "highlights": [],
            "risks": [],
            "evidence": [],
            "facts": {
                "sessions_count": context["sessions_count"],
                "current_task_count": len(context["current_tasks"]),
                "updated_task_count": len(context["updated_tasks"]),
                "sent_handoff_count": len(context["sent_handoffs"]),
                "received_handoff_count": len(context["received_handoffs"]),
                "relevant_log_count": len(context["relevant_logs"]),
                "failed_log_count": len(context["failed_logs"]),
                "running_job_count": len(context["running_jobs"]),
            },
        }

    health_score, health_metrics, health_risks = score_health(agent_id, context, mandatory)
    compliance_score, compliance_metrics, compliance_risks = score_compliance(context)
    output_score, output_metrics, output_notes = score_output(agent_id, context, period)
    quality_score, quality_metrics, quality_notes = score_quality(agent_id, context, period)

    sections = {
        "health": health_score,
        "compliance": compliance_score,
        "output": output_score,
        "quality": quality_score,
    }
    score_total, breakdown = combine_scores(weights, sections)

    evidence: list[str] = []
    for handoff in context["sent_handoffs"][:3]:
        evidence.append(str(handoff["path"]))
    for log in context["relevant_logs"][:3]:
        evidence.append(str(log["path"]))
    if agent_id == "aic-researcher":
        for item in context["research_opportunities"][:3]:
            card_path = item.get("card_path")
            if isinstance(card_path, str) and card_path:
                evidence.append(card_path)
    for output_rows in context["role_outputs"].values():
        for item in output_rows[:2]:
            evidence.append(str(item["path"]))

    status = "scored"
    if score_total is None:
        status = "insufficient_evidence"

    return {
        "agent_id": agent_id,
        "name": role_rules["name"],
        "title": role_rules["title"],
        "period": period,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "status": status,
        "score_total": score_total,
        "score_breakdown": breakdown,
        "metrics": health_metrics + compliance_metrics + output_metrics + quality_metrics,
        "highlights": output_notes[:5],
        "risks": (health_risks + compliance_risks + quality_notes)[:8],
        "evidence": list(dict.fromkeys(evidence))[:12],
        "facts": {
            "sessions_count": context["sessions_count"],
            "current_task_count": len(context["current_tasks"]),
            "updated_task_count": len(context["updated_tasks"]),
            "sent_handoff_count": len(context["sent_handoffs"]),
            "received_handoff_count": len(context["received_handoffs"]),
            "relevant_log_count": len(context["relevant_logs"]),
            "failed_log_count": len(context["failed_logs"]),
            "running_job_count": len(context["running_jobs"]),
        },
    }


def render_md(output_path: Path | None, period: str, window_start: datetime, window_end: datetime, scorecards: list[dict]) -> str:
    lines = [
        "# agent_kpi_report",
        "",
        f"- period: `{period}`",
        f"- window_start: `{window_start.isoformat()}`",
        f"- window_end: `{window_end.isoformat()}`",
    ]
    if output_path is not None:
        lines.append(f"- output: `{output_path}`")

    for item in scorecards:
        score_text = "N/A" if item["score_total"] is None else str(item["score_total"])
        lines.extend(
            [
                "",
                f"## {item['name']} | {item['agent_id']}",
                f"- title: {item['title']}",
                f"- status: {item['status']}",
                f"- score_total: {score_text}",
                f"- breakdown: {json.dumps(item['score_breakdown'], ensure_ascii=False)}",
            ]
        )
        if item["highlights"]:
            lines.append(f"- highlights: {'; '.join(item['highlights'])}")
        if item["risks"]:
            lines.append(f"- risks: {'; '.join(item['risks'])}")
    return "\n".join(lines) + "\n"


def default_output_path(paths: RuntimePaths, period: str, anchor_date: date) -> Path:
    if period == "daily":
        return paths.captain_workspace / f"data/kpi/daily/{anchor_date.isoformat()}.json"
    iso_year, iso_week, _ = anchor_date.isocalendar()
    return paths.captain_workspace / f"data/kpi/weekly/{iso_year}-W{iso_week:02d}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute evidence-based KPI scorecards for the OpenClaw coding team.")
    parser.add_argument("--openclaw-home", default="~/.openclaw")
    parser.add_argument("--period", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--date", default=None, help="Anchor date in YYYY-MM-DD. Defaults to today in the configured timezone.")
    parser.add_argument("--timezone", default=None)
    parser.add_argument("--rules-path", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    paths = RuntimePaths(Path(args.openclaw_home).expanduser())
    default_rules = paths.captain_workspace / "data/kpi/rules.v1.json"
    if args.rules_path:
        rules_path = Path(args.rules_path).expanduser()
    elif default_rules.exists():
        rules_path = default_rules
    else:
        rules_path = Path(__file__).resolve().parents[2] / "templates/common/data/kpi/rules.v1.json"
    rules = load_rules(rules_path)

    tz = ZoneInfo(args.timezone or rules["timezone"])
    anchor_date = date.fromisoformat(args.date) if args.date else datetime.now(tz).date()
    window_start, window_end = build_window(args.period, anchor_date, tz)
    weights = rules["periods"][args.period]["weights"]
    stale_hours = int(rules["periods"][args.period]["stale_hours"])

    tasks_payload = load_json(paths.registry_path)
    tasks = [task for task in tasks_payload.get("tasks", []) if isinstance(task, dict)]
    handoffs = load_handoffs(paths, window_start, window_end)
    logs = load_exec_logs(paths, window_start, window_end)
    opportunities_payload = load_json(paths.opportunities_path)
    opportunities = [item for item in opportunities_payload.get("opportunities", []) if isinstance(item, dict)]
    outputs = build_role_outputs(paths, window_start, window_end)
    snapshot = load_runtime_snapshot()

    scorecards: list[dict] = []
    for agent_id in AGENT_ORDER:
        role_rules = rules["roles"][agent_id]
        context = build_agent_context(
            agent_id,
            role_rules,
            tasks,
            handoffs,
            logs,
            opportunities,
            outputs,
            snapshot,
            window_start,
            window_end,
            stale_hours,
        )
        mandatory = bool(role_rules.get("mandatory"))
        scorecards.append(
            build_scorecard(
                agent_id,
                role_rules,
                args.period,
                window_start,
                window_end,
                weights,
                context,
                mandatory,
            )
        )

    scorecards.sort(key=lambda item: (item["score_total"] is None, -(item["score_total"] or -1), item["agent_id"]))

    output_path = Path(args.output).expanduser() if args.output else default_output_path(paths, args.period, anchor_date)
    payload = {
        "schemaVersion": 1,
        "period": args.period,
        "timezone": str(tz),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scorecards": scorecards,
        "summary": {
            "scored_agents": len([item for item in scorecards if item["status"] == "scored"]),
            "na_agents": len([item for item in scorecards if item["status"] == "n_a"]),
            "top_agents": [item["agent_id"] for item in scorecards if item["score_total"] is not None][:3],
            "risk_agents": [item["agent_id"] for item in scorecards if item["risks"]][:5],
        },
    }

    if args.write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(render_md(output_path if args.write else None, args.period, window_start, window_end, scorecards), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_ORDER = [
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
]

CORE_JOBS = [
    "dashboard-refresh",
    "ambient-discovery",
    "signal-triage",
    "opportunity-deep-dive",
    "opportunity-promotion",
    "exploration-learning",
    "daily-reflection",
    "daily-curation",
    "research-sprint",
    "build-sprint",
]

OPTIONAL_JOBS = [
    "daily-backup",
    "memory-hourly",
    "memory-weekly",
]

CAPABILITY_CONFIGS = [
    {
        "name": "自主研究需求",
        "agents": ["aic-researcher"],
        "active_states": {"Researching"},
        "progressed_states": {
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
        },
        "jobs": ["research-sprint"],
    },
    {
        "name": "主动探索方向",
        "agents": ["aic-researcher"],
        "active_states": {"Researching"},
        "progressed_states": {
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
        },
        "jobs": ["research-sprint"],
    },
    {
        "name": "产出需求规格",
        "agents": ["aic-planner"],
        "active_states": {"Scoped"},
        "progressed_states": {
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
        },
        "jobs": [],
    },
    {
        "name": "设计技术方案",
        "agents": ["aic-planner", "aic-reviewer"],
        "active_states": {"Planned", "Approved", "Replan"},
        "progressed_states": {"Building", "Verifying", "Staging", "Released", "Observing", "Closed", "Rework"},
        "jobs": [],
    },
    {
        "name": "开发软件",
        "agents": ["aic-builder"],
        "active_states": {"Building", "Rework"},
        "progressed_states": {"Verifying", "Staging", "Released", "Observing", "Closed"},
        "jobs": ["build-sprint"],
    },
    {
        "name": "测试验证",
        "agents": ["aic-tester"],
        "active_states": {"Verifying"},
        "progressed_states": {"Staging", "Released", "Observing", "Closed"},
        "jobs": [],
    },
    {
        "name": "部署上线",
        "agents": ["aic-releaser"],
        "active_states": {"Staging", "Released", "Observing"},
        "progressed_states": {"Closed"},
        "jobs": [],
    },
    {
        "name": "复盘沉淀",
        "agents": ["aic-reflector", "aic-curator"],
        "active_states": set(),
        "progressed_states": {"Closed"},
        "jobs": ["daily-reflection", "daily-curation", "memory-weekly"],
    },
]

PRIORITY_ORDER = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
}

AGENT_ACTIVITY_ORDER = [
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


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_timestamp(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def format_epoch_ms(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    try:
        return datetime.fromtimestamp(float(value) / 1000).astimezone().replace(microsecond=0).isoformat()
    except (OverflowError, OSError, ValueError):
        return "-"


def has_blocker(task: dict[str, Any]) -> bool:
    blocker = task.get("blocker")
    if blocker is None:
        return False
    if isinstance(blocker, str):
        return bool(blocker.strip())
    if isinstance(blocker, list):
        return any(isinstance(item, str) and item.strip() for item in blocker)
    return True


def blocker_text(task: dict[str, Any]) -> str:
    blocker = task.get("blocker")
    if blocker is None:
        return "none"
    if isinstance(blocker, str):
        return blocker.strip() or "none"
    if isinstance(blocker, list):
        values = [item for item in blocker if isinstance(item, str) and item]
        return "; ".join(values) if values else "none"
    return str(blocker)


def load_registry(path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    if not path.exists():
        return None, []
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return data.get("updatedAt"), []
    return data.get("updatedAt"), [task for task in tasks if isinstance(task, dict)]


def sort_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tasks,
        key=lambda task: (
            0 if has_blocker(task) else 1,
            PRIORITY_ORDER.get(task.get("priority"), 99),
            -parse_timestamp(task.get("updated_at")),
            str(task.get("task_id", "")),
        ),
    )


def classify_exec_log(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    status_values = re.findall(r"^- Status:\s*(.+)$", text, flags=re.MULTILINE)
    normalized = [value.strip().lower() for value in status_values if value.strip()]

    if "traceback" in lowered or any("fail" in value or "error" in value for value in normalized):
        return "failed"
    if any("block" in value or "timeout" in value for value in normalized):
        return "blocked"
    if "memory-hourly ok" in lowered or "memory-weekly ok" in lowered:
        return "ok"
    if normalized:
        return "ok"
    return "unknown"


def global_latest_log(openclaw_home: Path | None, job_name: str) -> Path | None:
    if openclaw_home is None or not openclaw_home.exists():
        return None
    paths = sorted(
        openclaw_home.glob(f"workspace-*/data/exec-logs/{job_name}/*.md"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        return None
    return paths[-1]


def latest_exec_logs(exec_logs_dir: Path, openclaw_home: Path | None = None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    jobs: list[dict[str, Any]] = []
    missing_core_jobs: list[str] = []
    missing_optional_jobs: list[str] = []

    local_job_dirs = sorted(path for path in exec_logs_dir.iterdir() if path.is_dir()) if exec_logs_dir.exists() else []
    job_names = {path.name for path in local_job_dirs}
    job_names.update(CORE_JOBS)
    job_names.update(OPTIONAL_JOBS)

    for job_name in sorted(job_names):
        job_dir = exec_logs_dir / job_name
        local_logs = sorted(job_dir.glob("*.md")) if job_dir.exists() else []
        latest_path = local_logs[-1] if local_logs else global_latest_log(openclaw_home, job_name)

        if latest_path is None:
            jobs.append(
                {
                    "job": job_name,
                    "latest_path": None,
                    "status": "missing",
                    "consecutive_failures": 0,
                }
            )
            continue

        latest_status = classify_exec_log(latest_path)
        if local_logs:
            logs_for_streak = list(reversed(local_logs))
        else:
            logs_for_streak = [latest_path]

        consecutive_failures = 0
        for log_path in logs_for_streak:
            if classify_exec_log(log_path) != "failed":
                break
            consecutive_failures += 1

        jobs.append(
            {
                "job": job_name,
                "latest_path": latest_path,
                "status": latest_status,
                "consecutive_failures": consecutive_failures,
            }
        )

    present_logs = {job["job"] for job in jobs if job["latest_path"] is not None}
    for expected in CORE_JOBS:
        if expected not in present_logs and not (exec_logs_dir / expected).exists():
            missing_core_jobs.append(expected)
    for expected in OPTIONAL_JOBS:
        if expected not in present_logs and not (exec_logs_dir / expected).exists():
            missing_optional_jobs.append(expected)

    jobs.sort(key=lambda item: item["job"])
    return jobs, missing_core_jobs, missing_optional_jobs


def parse_handoff(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    values: dict[str, str] = {
        "time": "",
        "from_owner": "",
        "task_id": "",
        "current_stage": "",
        "next_owner": "",
        "path": str(path),
    }

    for key, prefix in (
        ("time", "生成时间:"),
        ("from_owner", "发送方:"),
        ("task_id", "任务ID:"),
        ("current_stage", "当前阶段:"),
        ("next_owner", "下一负责人:"),
    ):
        for line in text.splitlines():
            if line.startswith(prefix):
                values[key] = line.split(":", 1)[1].strip()
                break

    if not values["task_id"]:
        values["task_id"] = path.stem.split("-")[1] if "-" in path.stem else path.stem

    return values


def latest_handoffs(handoffs_dir: Path, limit: int) -> list[dict[str, str]]:
    if not handoffs_dir.exists():
        return []
    paths = sorted(
        (
            path
            for path in handoffs_dir.rglob("*.md")
            if path.is_file() and path.name not in {"TEMPLATE.md", "README.md"}
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [parse_handoff(path) for path in paths[:limit]]


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    if not isinstance(data, dict):
        return default
    return data


def load_research_summary(research_root: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "sources_enabled": 0,
        "sites_known": 0,
        "sites_with_hot_pages": 0,
        "sites_with_feeds": 0,
        "active_topics": 0,
        "signals_last_24h": 0,
        "signal_sources_last_24h": 0,
        "tool_attempts_last_24h": 0,
        "tool_failures_last_24h": 0,
        "latest_signal_at": None,
        "status_counts": {
            "watchlist": 0,
            "candidate": 0,
            "ready_review": 0,
            "promoted": 0,
            "rejected": 0,
        },
        "top_opportunities": [],
    }
    if not research_root.exists():
        return summary

    sources_payload = load_json_file(research_root / "sources.json", {"sources": []})
    site_profiles_payload = load_json_file(research_root / "site_profiles.json", {"sites": []})
    topics_payload = load_json_file(research_root / "topic_profiles.json", {"profiles": []})
    opportunities_payload = load_json_file(research_root / "opportunities.json", {"opportunities": []})

    sources = sources_payload.get("sources")
    if isinstance(sources, list):
        summary["sources_enabled"] = sum(
            1 for item in sources if isinstance(item, dict) and item.get("enabled", False)
        )

    sites = site_profiles_payload.get("sites")
    if isinstance(sites, list):
        summary["sites_known"] = sum(1 for item in sites if isinstance(item, dict) and item.get("status", "active") != "inactive")
        summary["sites_with_hot_pages"] = sum(
            1
            for item in sites
            if isinstance(item, dict)
            and item.get("status", "active") != "inactive"
            and isinstance(item.get("hot_pages"), list)
            and any(isinstance(value, str) and value.strip() for value in item.get("hot_pages"))
        )
        summary["sites_with_feeds"] = sum(
            1
            for item in sites
            if isinstance(item, dict)
            and item.get("status", "active") != "inactive"
            and isinstance(item.get("feed_urls"), list)
            and any(isinstance(value, str) and value.strip() for value in item.get("feed_urls"))
        )

    profiles = topics_payload.get("profiles")
    if isinstance(profiles, list):
        summary["active_topics"] = sum(
            1
            for item in profiles
            if isinstance(item, dict) and item.get("status") in {"active", "discover"}
        )

    now_ts = datetime.now().astimezone().timestamp()
    latest_signal_ts = float("-inf")
    source_ids: set[str] = set()
    signals_root = research_root / "signals"
    if signals_root.exists():
        for path in sorted(signals_root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    signal = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(signal, dict):
                    continue
                discovered_ts = parse_timestamp(signal.get("discovered_at"))
                if discovered_ts == float("-inf"):
                    continue
                if now_ts - discovered_ts <= 24 * 3600:
                    summary["signals_last_24h"] += 1
                    source_id = signal.get("source_id")
                    if isinstance(source_id, str) and source_id:
                        source_ids.add(source_id)
                if discovered_ts > latest_signal_ts:
                    latest_signal_ts = discovered_ts
    summary["signal_sources_last_24h"] = len(source_ids)
    if latest_signal_ts != float("-inf"):
        summary["latest_signal_at"] = (
            datetime.fromtimestamp(latest_signal_ts).astimezone().replace(microsecond=0).isoformat()
        )

    attempts_root = research_root / "tool_attempts"
    if attempts_root.exists():
        for path in sorted(attempts_root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    attempt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(attempt, dict):
                    continue
                attempted_ts = parse_timestamp(attempt.get("attempted_at"))
                if attempted_ts == float("-inf") or now_ts - attempted_ts > 24 * 3600:
                    continue
                summary["tool_attempts_last_24h"] += 1
                if attempt.get("outcome") == "failure":
                    summary["tool_failures_last_24h"] += 1

    opportunities = opportunities_payload.get("opportunities")
    if isinstance(opportunities, list):
        rows = [item for item in opportunities if isinstance(item, dict)]
        for item in rows:
            status = item.get("status")
            if isinstance(status, str) and status in summary["status_counts"]:
                summary["status_counts"][status] += 1
        rows.sort(
            key=lambda item: (
                0 if item.get("status") == "ready_review" else 1,
                -float(item.get("score", 0) or 0),
                -parse_timestamp(item.get("updated_at")),
                str(item.get("opportunity_id", "")),
            )
        )
        summary["top_opportunities"] = rows[:5]

    return summary


def load_skill_summary(skills_root: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "candidates": 0,
        "approved": 0,
        "installed": 0,
        "eligible_skills": 0,
        "missing_skills": 0,
        "managed_skills_dir": None,
    }
    if not skills_root.exists():
        return summary

    catalog_payload = load_json_file(skills_root / "catalog.json", {"candidates": []})
    inventory_payload = load_json_file(skills_root / "inventory.json", {})

    candidates = catalog_payload.get("candidates")
    if isinstance(candidates, list):
        rows = [item for item in candidates if isinstance(item, dict)]
        summary["candidates"] = len(rows)
        summary["approved"] = sum(1 for item in rows if item.get("status") == "approved")
        summary["installed"] = sum(1 for item in rows if item.get("status") == "installed")

    eligible = inventory_payload.get("eligible_skills")
    if isinstance(eligible, list):
        summary["eligible_skills"] = sum(1 for item in eligible if isinstance(item, str) and item)
    missing = inventory_payload.get("missing_skills")
    if isinstance(missing, list):
        summary["missing_skills"] = sum(1 for item in missing if isinstance(item, str) and item)
    managed_skills_dir = inventory_payload.get("managedSkillsDir")
    if isinstance(managed_skills_dir, str) and managed_skills_dir:
        summary["managed_skills_dir"] = managed_skills_dir

    return summary


def run_probe(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def parse_backup_log(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^- ([a-z_]+):\s*(.+)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def load_backup_health(workspace_root: Path, exec_jobs: list[dict[str, Any]]) -> dict[str, str]:
    health = {
        "workspace_root": str(workspace_root),
        "git_initialized": "yes" if (workspace_root / ".git").exists() else "no",
        "origin_configured": "no",
        "remote_url": "none",
        "branch": "none",
        "gh_available": "yes" if shutil.which("gh") else "no",
        "gh_auth_ok": "unknown",
        "github_repo": "none",
        "last_backup_status": "none",
        "pull_ok": "unknown",
        "push_ok": "unknown",
        "latest_backup_log": "none",
    }

    if health["git_initialized"] == "yes":
        remote_result = run_probe(["git", "remote", "get-url", "origin"], workspace_root)
        if remote_result.returncode == 0:
            health["origin_configured"] = "yes"
            health["remote_url"] = remote_result.stdout.strip() or "none"

        branch_result = run_probe(["git", "branch", "--show-current"], workspace_root)
        if branch_result.returncode == 0 and branch_result.stdout.strip():
            health["branch"] = branch_result.stdout.strip()

    if health["gh_available"] == "yes":
        auth_result = run_probe(["gh", "auth", "status", "--hostname", "github.com"], workspace_root)
        health["gh_auth_ok"] = "yes" if auth_result.returncode == 0 else "no"

    for job in exec_jobs:
        if job["job"] != "daily-backup" or job.get("latest_path") is None:
            continue
        latest_backup_log = Path(job["latest_path"])
        parsed = parse_backup_log(latest_backup_log)
        health["last_backup_status"] = parsed.get("last_backup_status", job.get("status", "unknown"))
        health["pull_ok"] = parsed.get("pull_ok", health["pull_ok"])
        health["push_ok"] = parsed.get("push_ok", health["push_ok"])
        health["github_repo"] = parsed.get("github_repo", health["github_repo"])
        health["latest_backup_log"] = str(latest_backup_log)
        break

    return health


def load_sessions_summary(sessions_root: Path) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    if not sessions_root.exists():
        return summary

    for agent_dir in sorted(path for path in sessions_root.iterdir() if path.is_dir()):
        sessions_path = agent_dir / "sessions" / "sessions.json"
        if not sessions_path.exists():
            summary[agent_dir.name] = {"count": 0, "last_updated_at_ms": None}
            continue

        try:
            data = json.loads(sessions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary[agent_dir.name] = {"count": 0, "last_updated_at_ms": None, "error": "invalid_json"}
            continue

        if not isinstance(data, dict):
            summary[agent_dir.name] = {"count": 0, "last_updated_at_ms": None, "error": "invalid_shape"}
            continue

        timestamps = [
            value.get("updatedAt")
            for value in data.values()
            if isinstance(value, dict) and isinstance(value.get("updatedAt"), (int, float))
        ]
        summary[agent_dir.name] = {
            "count": len(data),
            "last_updated_at_ms": max(timestamps) if timestamps else None,
        }

    return summary


def summarize_capabilities(
    tasks: list[dict[str, Any]],
    exec_jobs: list[dict[str, Any]],
    handoffs: list[dict[str, str]],
    sessions_summary: dict[str, dict[str, Any]],
    research_summary: dict[str, Any],
) -> list[dict[str, str]]:
    exec_jobs_by_name = {job["job"]: job for job in exec_jobs}
    rows: list[dict[str, str]] = []

    for capability in CAPABILITY_CONFIGS:
        active_tasks = [task for task in tasks if task.get("state") in capability["active_states"]]
        progressed_tasks = [task for task in tasks if task.get("state") in capability["progressed_states"]]
        blocked_tasks = [task for task in active_tasks if has_blocker(task)]
        relevant_jobs = [exec_jobs_by_name[name] for name in capability["jobs"] if name in exec_jobs_by_name]
        relevant_sessions = {
            agent: sessions_summary.get(agent, {"count": 0, "last_updated_at_ms": None})
            for agent in capability["agents"]
        }
        session_count = sum(int(item.get("count", 0) or 0) for item in relevant_sessions.values())
        relevant_handoffs = [
            handoff
            for handoff in handoffs
            if handoff.get("next_owner") in capability["agents"] or handoff.get("from_owner") in capability["agents"]
        ]
        is_research_capability = "aic-researcher" in capability["agents"]
        research_signals = int(research_summary.get("signals_last_24h", 0) or 0) if is_research_capability else 0
        research_candidates = (
            int(research_summary.get("status_counts", {}).get("candidate", 0) or 0) if is_research_capability else 0
        )
        research_ready = (
            int(research_summary.get("status_counts", {}).get("ready_review", 0) or 0)
            if is_research_capability
            else 0
        )

        if blocked_tasks or any(job["status"] in {"failed", "blocked"} for job in relevant_jobs):
            status = "阻塞/异常"
        elif active_tasks:
            status = "进行中"
        elif is_research_capability and (research_signals > 0 or research_candidates > 0 or research_ready > 0):
            status = "进行中"
        elif progressed_tasks or relevant_handoffs or any(job["status"] == "ok" for job in relevant_jobs):
            status = "已进入后续"
        elif session_count > 0:
            status = "已启动"
        else:
            status = "未开始"

        signal_parts: list[str] = []
        if active_tasks:
            signal_parts.append(f"active_tasks={len(active_tasks)}")
        if progressed_tasks:
            signal_parts.append(f"progressed_tasks={len(progressed_tasks)}")
        if session_count:
            session_bits = [f"{agent}×{info.get('count', 0)}" for agent, info in relevant_sessions.items() if info.get("count")]
            if session_bits:
                signal_parts.append("sessions=" + ", ".join(session_bits))
        if is_research_capability:
            if research_signals:
                signal_parts.append(f"signals24h={research_signals}")
            if research_candidates:
                signal_parts.append(f"candidates={research_candidates}")
            if research_ready:
                signal_parts.append(f"ready_review={research_ready}")
        if relevant_jobs:
            signal_parts.append("jobs=" + ", ".join(f"{job['job']}({job['status']})" for job in relevant_jobs))

        evidence_parts: list[str] = []
        if active_tasks:
            evidence_parts.append(", ".join(task.get("task_id", "") for task in active_tasks[:2] if task.get("task_id")))
        elif progressed_tasks:
            evidence_parts.append(", ".join(task.get("task_id", "") for task in progressed_tasks[:2] if task.get("task_id")))
        if relevant_handoffs:
            evidence_parts.append(f"handoff:`{relevant_handoffs[0]['path']}`")
        elif relevant_jobs and relevant_jobs[0].get("latest_path"):
            evidence_parts.append(f"log:`{relevant_jobs[0]['latest_path']}`")
        elif session_count:
            newest = max(
                (
                    (agent, info.get("last_updated_at_ms"))
                    for agent, info in relevant_sessions.items()
                    if info.get("last_updated_at_ms")
                ),
                key=lambda item: item[1],
                default=(None, None),
            )
            if newest[0]:
                evidence_parts.append(f"session:{newest[0]}@{format_epoch_ms(newest[1])}")
        if is_research_capability and research_summary.get("top_opportunities"):
            top = research_summary["top_opportunities"][0]
            if isinstance(top, dict):
                evidence_parts.append(f"opp:{top.get('opportunity_id', 'unknown')}")

        rows.append(
            {
                "capability": capability["name"],
                "status": status,
                "signal": "; ".join(signal_parts) if signal_parts else "none",
                "evidence": " | ".join(part for part in evidence_parts if part) if evidence_parts else "none",
            }
        )

    return rows


def render_dashboard(
    registry_path: Path,
    registry_updated_at: str | None,
    tasks: list[dict[str, Any]],
    exec_jobs: list[dict[str, Any]],
    missing_core_jobs: list[str],
    missing_optional_jobs: list[str],
    handoffs: list[dict[str, str]],
    sessions_summary: dict[str, dict[str, Any]],
    backup_health: dict[str, str],
    research_summary: dict[str, Any],
    skill_summary: dict[str, Any],
    output_path: Path,
) -> str:
    state_counter = Counter(task.get("state", "Unknown") for task in tasks)
    active_tasks = sort_tasks([task for task in tasks if task.get("state") != "Closed"])
    blocked_tasks = [task for task in active_tasks if has_blocker(task)]
    build_queue = [task for task in active_tasks if task.get("state") in {"Building", "Rework"}]
    capability_rows = summarize_capabilities(tasks, exec_jobs, handoffs, sessions_summary, research_summary)
    workflow_started = any(row["status"] in {"进行中", "已进入后续", "阻塞/异常"} for row in capability_rows)
    captain_sessions = int(sessions_summary.get("aic-captain", {}).get("count", 0) or 0)

    anomalies: list[str] = []
    if blocked_tasks:
        anomalies.append(f"{len(blocked_tasks)} blocked task(s) need attention")
    for row in capability_rows:
        if row["status"] == "阻塞/异常":
            anomalies.append(f"{row['capability']} has blockers or failed jobs")
    for job in exec_jobs:
        if job["status"] == "failed":
            detail = f"{job['job']} latest log failed"
            if job["consecutive_failures"]:
                detail += f" ({job['consecutive_failures']} consecutive)"
            anomalies.append(detail)
    if missing_core_jobs:
        anomalies.append(f"missing core exec log directories: {', '.join(missing_core_jobs)}")
    if backup_health["git_initialized"] != "yes":
        anomalies.append("git backup baseline missing")
    if backup_health["origin_configured"] != "yes":
        anomalies.append("git origin remote not configured")
    if backup_health["gh_available"] != "yes":
        anomalies.append("gh CLI unavailable for GitHub backup automation")
    if backup_health["gh_auth_ok"] == "no":
        anomalies.append("gh auth not ready for GitHub backup automation")
    if backup_health["pull_ok"] == "no":
        anomalies.append("git pull check failed in latest backup run")
    if backup_health["push_ok"] == "no":
        anomalies.append("git push check failed in latest backup run")
    if research_summary["sources_enabled"] == 0:
        anomalies.append("research discovery sources are not configured")
    if research_summary["sites_known"] == 0:
        anomalies.append("research site profiles are not configured")
    if research_summary["active_topics"] == 0:
        anomalies.append("research topic profiles are inactive")

    lines = [
        "# Automation Dashboard",
        "",
        f"> Auto-updated: {now_iso()}",
        f"> Source: `{output_path}`",
        f"> Control plane: task state, owner, blocker, next step, and closeout truth come from `{registry_path}`",
        "> Dashboard role: derived observer; it may lag behind until refreshed",
        "",
        "## Summary",
        "",
        f"- task_registry: `{registry_path}`",
        f"- task_registry_updated_at: {registry_updated_at or 'unknown'}",
        "- task_state_source: registry",
        "- dashboard_role: derived_observer",
        f"- team_entry_active: {'yes' if captain_sessions > 0 else 'no'}",
        f"- workflow_started: {'yes' if workflow_started else 'no'}",
        f"- tasks_total: {len(tasks)}",
        f"- active_tasks: {len(active_tasks)}",
        f"- blocked_tasks: {len(blocked_tasks)}",
        f"- recent_handoffs: {len(handoffs)}",
        f"- exec_jobs_tracked: {len(exec_jobs)}",
        f"- missing_core_jobs: {len(missing_core_jobs)}",
        f"- missing_optional_jobs: {len(missing_optional_jobs)}",
        "",
        "## Backup Health",
        "",
        f"- workspace_root: `{backup_health['workspace_root']}`",
        f"- git_initialized: {backup_health['git_initialized']}",
        f"- origin_configured: {backup_health['origin_configured']}",
        f"- remote_url: {backup_health['remote_url']}",
        f"- branch: {backup_health['branch']}",
        f"- gh_available: {backup_health['gh_available']}",
        f"- gh_auth_ok: {backup_health['gh_auth_ok']}",
        f"- github_repo: {backup_health['github_repo']}",
        f"- last_backup_status: {backup_health['last_backup_status']}",
        f"- pull_ok: {backup_health['pull_ok']}",
        f"- push_ok: {backup_health['push_ok']}",
        f"- latest_backup_log: {backup_health['latest_backup_log']}",
        "",
        "## Exploration Summary",
        "",
        f"- sources_enabled: {research_summary['sources_enabled']}",
        f"- sites_known: {research_summary['sites_known']}",
        f"- sites_with_hot_pages: {research_summary['sites_with_hot_pages']}",
        f"- sites_with_feeds: {research_summary['sites_with_feeds']}",
        f"- active_topics: {research_summary['active_topics']}",
        f"- signals_last_24h: {research_summary['signals_last_24h']}",
        f"- signal_sources_last_24h: {research_summary['signal_sources_last_24h']}",
        f"- tool_attempts_last_24h: {research_summary['tool_attempts_last_24h']}",
        f"- tool_failures_last_24h: {research_summary['tool_failures_last_24h']}",
        f"- latest_signal_at: {research_summary['latest_signal_at'] or 'none'}",
        f"- opportunities_watchlist: {research_summary['status_counts']['watchlist']}",
        f"- opportunities_candidate: {research_summary['status_counts']['candidate']}",
        f"- opportunities_ready_review: {research_summary['status_counts']['ready_review']}",
        f"- opportunities_promoted: {research_summary['status_counts']['promoted']}",
        f"- top_opportunity: {research_summary['top_opportunities'][0]['opportunity_id'] if research_summary['top_opportunities'] else 'none'}",
        "",
        "## Skills Summary",
        "",
        f"- candidates: {skill_summary['candidates']}",
        f"- approved: {skill_summary['approved']}",
        f"- installed: {skill_summary['installed']}",
        f"- eligible_skills: {skill_summary['eligible_skills']}",
        f"- missing_skills: {skill_summary['missing_skills']}",
        f"- managed_skills_dir: {skill_summary['managed_skills_dir'] or 'none'}",
        "",
        "## Capability Loop",
        "",
        "| Capability | Status | Signal | Evidence |",
        "|------------|--------|--------|----------|",
    ]

    for row in capability_rows:
        lines.append(f"| {row['capability']} | {row['status']} | {row['signal']} | {row['evidence']} |")

    lines.extend(
        [
            "",
            "## Agent Activity",
            "",
            "| Agent | Sessions | Last Activity |",
            "|-------|----------|---------------|",
        ]
    )
    for agent_id in AGENT_ACTIVITY_ORDER:
        info = sessions_summary.get(agent_id, {"count": 0, "last_updated_at_ms": None})
        lines.append(f"| {agent_id} | {info.get('count', 0)} | {format_epoch_ms(info.get('last_updated_at_ms'))} |")

    lines.extend(
        [
            "",
            "## Task State Counts",
            "",
            "| State | Count |",
            "|-------|-------|",
        ]
    )
    for state in STATE_ORDER:
        lines.append(f"| {state} | {state_counter.get(state, 0)} |")

    lines.extend(
        [
            "",
            "## Priority Tasks",
            "",
            "| Task ID | State | Owner | Priority | Blocker | Next Step |",
            "|---------|-------|-------|----------|---------|-----------|",
        ]
    )
    for task in active_tasks[:8]:
        lines.append(
            f"| {task.get('task_id', '')} | {task.get('state', '')} | {task.get('owner', '')} | "
            f"{task.get('priority', '')} | {blocker_text(task)} | {task.get('next_step', '')} |"
        )
    if not active_tasks:
        lines.append("| none | - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Build Queue",
            "",
            "| Task ID | Priority | Owner | Blocker | Next Step |",
            "|---------|----------|-------|---------|-----------|",
        ]
    )
    for task in build_queue[:6]:
        lines.append(
            f"| {task.get('task_id', '')} | {task.get('priority', '')} | {task.get('owner', '')} | "
            f"{blocker_text(task)} | {task.get('next_step', '')} |"
        )
    if not build_queue:
        lines.append("| none | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Top Opportunities",
            "",
            "| Opportunity | Status | Score | Topics | Action |",
            "|-------------|--------|-------|--------|--------|",
        ]
    )
    if research_summary["top_opportunities"]:
        for item in research_summary["top_opportunities"]:
            topic_text = ", ".join(item.get("topic_ids", [])[:3]) if isinstance(item.get("topic_ids"), list) else "none"
            lines.append(
                f"| {item.get('opportunity_id', 'unknown')} | {item.get('status', 'unknown')} | {item.get('score', 'unknown')} | {topic_text or 'none'} | {item.get('recommended_action', 'monitor')} |"
            )
    else:
        lines.append("| none | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Recent Handoffs",
            "",
            "| Time | Task | From | To | File |",
            "|------|------|------|----|------|",
        ]
    )
    for handoff in handoffs:
        lines.append(
            f"| {handoff['time'] or '-'} | {handoff['task_id'] or '-'} | {handoff['from_owner'] or '-'} | "
            f"{handoff['next_owner'] or '-'} | `{handoff['path']}` |"
        )
    if not handoffs:
        lines.append("| none | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Recent Execution Logs",
            "",
            "| Job | Latest Log | Status | Consecutive Failures |",
            "|-----|------------|--------|----------------------|",
        ]
    )
    for job in exec_jobs:
        latest_path = f"`{job['latest_path']}`" if job["latest_path"] else "none"
        lines.append(f"| {job['job']} | {latest_path} | {job['status']} | {job['consecutive_failures']} |")
    if not exec_jobs:
        lines.append("| none | - | - | - |")

    lines.extend(["", "## Optional Automation", ""])
    if missing_optional_jobs:
        lines.append(f"- missing_optional_jobs: {', '.join(missing_optional_jobs)}")
    else:
        lines.append("- missing_optional_jobs: none")

    lines.extend(["", "## Anomalies", ""])
    if anomalies:
        for anomaly in anomalies:
            lines.append(f"- {anomaly}")
    else:
        lines.append("- 暂无")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh data/dashboard.md from tasks, handoffs, exec logs, and OpenClaw sessions.")
    parser.add_argument("--registry-path", default="tasks/registry.json")
    parser.add_argument("--handoffs-dir", default="handoffs")
    parser.add_argument("--exec-logs-dir", default="data/exec-logs")
    parser.add_argument("--sessions-root", default="~/.openclaw/agents")
    parser.add_argument("--research-root", default="data/research")
    parser.add_argument("--skills-root", default="data/skills")
    parser.add_argument("--output", default="data/dashboard.md")
    parser.add_argument("--handoff-limit", type=int, default=8)
    args = parser.parse_args()

    registry_path = Path(args.registry_path).expanduser()
    handoffs_dir = Path(args.handoffs_dir).expanduser()
    exec_logs_dir = Path(args.exec_logs_dir).expanduser()
    sessions_root = Path(args.sessions_root).expanduser()
    research_root = Path(args.research_root).expanduser()
    skills_root = Path(args.skills_root).expanduser()
    output_path = Path(args.output).expanduser()
    workspace_root = registry_path.parent.parent
    openclaw_home = sessions_root.parent if sessions_root.name == "agents" else None

    registry_updated_at, tasks = load_registry(registry_path)
    exec_jobs, missing_core_jobs, missing_optional_jobs = latest_exec_logs(exec_logs_dir, openclaw_home)
    handoffs = latest_handoffs(handoffs_dir, args.handoff_limit)
    sessions_summary = load_sessions_summary(sessions_root)
    backup_health = load_backup_health(workspace_root, exec_jobs)
    research_summary = load_research_summary(research_root)
    skill_summary = load_skill_summary(skills_root)

    dashboard = render_dashboard(
        registry_path=registry_path,
        registry_updated_at=registry_updated_at,
        tasks=tasks,
        exec_jobs=exec_jobs,
        missing_core_jobs=missing_core_jobs,
        missing_optional_jobs=missing_optional_jobs,
        handoffs=handoffs,
        sessions_summary=sessions_summary,
        backup_health=backup_health,
        research_summary=research_summary,
        skill_summary=skill_summary,
        output_path=output_path,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dashboard, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path),
                "tasks": len(tasks),
                "handoffs": len(handoffs),
                "exec_jobs": len(exec_jobs),
                "missing_core_jobs": missing_core_jobs,
                "missing_optional_jobs": missing_optional_jobs,
                "backup_health": backup_health,
                "research_summary": research_summary,
                "skill_summary": skill_summary,
                "sessions_root": str(sessions_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

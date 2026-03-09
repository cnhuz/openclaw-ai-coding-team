#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import subprocess
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse


STATUS_ORDER = {
    "ready_review": 0,
    "candidate": 1,
    "watchlist": 2,
    "promoted": 3,
    "rejected": 4,
}

TASK_STATE_OPTIONS = [
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

OWNER_OPTIONS = [
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

AGENT_META = {
    "aic-captain": {"name": "船长", "title": "总指挥", "lane": "指挥层"},
    "aic-planner": {"name": "规划官", "title": "需求收敛与任务拆解", "lane": "规划层"},
    "aic-reviewer": {"name": "审议官", "title": "边界与质量把关", "lane": "规划层"},
    "aic-dispatcher": {"name": "调度官", "title": "派发与推进闭环", "lane": "调度层"},
    "aic-researcher": {"name": "研究官", "title": "需求与机会研究", "lane": "研究执行层"},
    "aic-builder": {"name": "实现编排官", "title": "实现与编码引擎编排", "lane": "研究执行层"},
    "aic-tester": {"name": "验证官", "title": "测试、回归与验收", "lane": "研究执行层"},
    "aic-releaser": {"name": "发布官", "title": "上线、回滚与观察", "lane": "研究执行层"},
    "aic-reflector": {"name": "反思官", "title": "复盘与流程修正", "lane": "复盘层"},
    "aic-curator": {"name": "典藏官", "title": "知识沉淀与归档", "lane": "复盘层"},
}

AGENT_LAYERS = [
    ["aic-captain"],
    ["aic-planner", "aic-dispatcher", "aic-reflector"],
    ["aic-researcher", "aic-reviewer", "aic-builder", "aic-tester", "aic-releaser", "aic-curator"],
]

CALL_GRAPH = [
    ("aic-captain", ["aic-planner", "aic-dispatcher", "aic-reflector"]),
    ("aic-planner", ["aic-researcher", "aic-reviewer"]),
    ("aic-dispatcher", ["aic-researcher", "aic-builder", "aic-tester", "aic-releaser", "aic-curator"]),
    ("aic-reflector", ["aic-curator"]),
]

EXPECTED_NEXT_OWNER = {
    "Intake": "aic-planner",
    "Researching": "aic-planner",
    "Scoped": "aic-reviewer",
    "Planned": "aic-reviewer",
    "Approved": "aic-dispatcher",
    "Building": "aic-tester",
    "Verifying": "aic-releaser",
    "Staging": "aic-releaser",
    "Released": "aic-reflector",
    "Observing": "aic-curator",
    "Replan": "aic-planner",
    "Rework": "aic-builder",
}

CORE_JOB_NAMES = {
    "dashboard-refresh",
    "planner-intake",
    "dispatch-approved",
    "build-sprint",
    "tester-gate",
    "releaser-gate",
    "reflect-release",
    "ambient-discovery",
    "signal-triage",
    "opportunity-deep-dive",
    "opportunity-promotion",
    "daily-kpi",
    "weekly-kpi",
}

ALERT_STALE_HOURS = 6
ALERT_CRITICAL_STALE_HOURS = 24
COMMAND_CACHE_TTL_SECONDS = 20.0
COMMAND_CACHE: dict[str, tuple[float, dict]] = {}
STATE_CACHE_TTL_SECONDS = 30.0
STATE_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_PREWARM_INTERVAL_SECONDS = 20.0
CACHE_LOCK = threading.Lock()
STATE_REFRESHING: set[str] = set()


@dataclass(frozen=True)
class AppConfig:
    openclaw_home: Path
    host: str
    port: int

    @property
    def captain_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-captain"

    @property
    def researcher_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-researcher"

    @property
    def reflector_workspace(self) -> Path:
        return self.openclaw_home / "workspace-aic-reflector"

    @property
    def registry_path(self) -> Path:
        return self.captain_workspace / "tasks/registry.json"

    @property
    def dashboard_path(self) -> Path:
        return self.captain_workspace / "data/dashboard.md"

    @property
    def handoffs_dir(self) -> Path:
        return self.captain_workspace / "handoffs"

    @property
    def opportunities_path(self) -> Path:
        return self.researcher_workspace / "data/research/opportunities.json"

    @property
    def research_root(self) -> Path:
        return self.researcher_workspace / "data/research"

    @property
    def kpi_root(self) -> Path:
        return self.captain_workspace / "data/kpi"

    @property
    def skills_root(self) -> Path:
        return self.researcher_workspace / "data/skills"

    @property
    def sessions_root(self) -> Path:
        return self.openclaw_home / "agents"

    @property
    def captain_exec_logs(self) -> Path:
        return self.captain_workspace / "data/exec-logs"

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def workspaces(self) -> dict[str, Path]:
        return {
            "aic-captain": self.captain_workspace,
            "aic-researcher": self.researcher_workspace,
            "aic-reflector": self.reflector_workspace,
            "aic-planner": self.openclaw_home / "workspace-aic-planner",
            "aic-dispatcher": self.openclaw_home / "workspace-aic-dispatcher",
            "aic-builder": self.openclaw_home / "workspace-aic-builder",
            "aic-tester": self.openclaw_home / "workspace-aic-tester",
            "aic-releaser": self.openclaw_home / "workspace-aic-releaser",
            "aic-curator": self.openclaw_home / "workspace-aic-curator",
            "aic-reviewer": self.openclaw_home / "workspace-aic-reviewer",
        }

    def refresh_dashboard_command(self) -> list[str]:
        script_path = self.captain_workspace / "scripts/refresh_dashboard.py"
        return [
            "python3",
            str(script_path),
            "--registry-path",
            str(self.registry_path),
            "--handoffs-dir",
            str(self.handoffs_dir),
            "--exec-logs-dir",
            str(self.captain_exec_logs),
            "--sessions-root",
            str(self.sessions_root),
            "--research-root",
            str(self.research_root),
            "--skills-root",
            str(self.skills_root),
            "--output",
            str(self.dashboard_path),
        ]


def parse_iso(value: str | None) -> datetime | None:
    if value is None or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_ts_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_age(value: datetime | None) -> str:
    if value is None:
        return "-"
    delta = datetime.now(timezone.utc) - value.astimezone(timezone.utc)
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m"
    if total_seconds < 86400:
        return f"{total_seconds // 3600}h"
    return f"{total_seconds // 86400}d"


def escape(value: object) -> str:
    return html.escape(str(value))


def agent_meta(agent_id: str) -> dict[str, str]:
    return AGENT_META.get(agent_id, {"name": agent_id, "title": "-", "lane": "未分类"})


def agent_name(agent_id: str) -> str:
    return agent_meta(agent_id)["name"]


def agent_title(agent_id: str) -> str:
    return agent_meta(agent_id)["title"]


def link(label: str, href: str) -> str:
    return f"<a href=\"{escape(href)}\">{escape(label)}</a>"


def load_json(path: Path, fallback: dict | list) -> dict | list:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def run_json_command(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"ok": False, "command": command, "stderr": result.stderr.strip(), "stdout": result.stdout.strip()}
    return json.loads(result.stdout)


def run_cached_json_command(cache_key: str, command: list[str], ttl_seconds: float = COMMAND_CACHE_TTL_SECONDS) -> dict:
    with CACHE_LOCK:
        cached = COMMAND_CACHE.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < ttl_seconds:
        return cached[1]
    payload = run_json_command(command)
    with CACHE_LOCK:
        COMMAND_CACHE[cache_key] = (now, payload)
    return payload


def invalidate_command_cache(cache_key: str | None = None) -> None:
    with CACHE_LOCK:
        if cache_key is None:
            COMMAND_CACHE.clear()
            return
        COMMAND_CACHE.pop(cache_key, None)


def invalidate_state_cache(cache_key: str | None = None) -> None:
    with CACHE_LOCK:
        if cache_key is None:
            STATE_CACHE.clear()
            return
        STATE_CACHE.pop(cache_key, None)


def run_command(command: list[str]) -> dict[str, object]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "command": command,
    }


def has_blocker(task: dict) -> bool:
    blocker = task.get("blocker")
    if blocker is None:
        return False
    if isinstance(blocker, str):
        return blocker.strip() != ""
    if isinstance(blocker, list):
        return any(isinstance(item, str) and item.strip() for item in blocker)
    return True


def file_path_to_url(path: Path) -> str:
    return "/file?" + urlencode({"path": str(path)})


def format_path(path: Path, roots: list[Path]) -> str:
    for root in roots:
        if path.is_relative_to(root):
            return str(path.relative_to(root))
    return str(path)


def resolve_viewable_path(config: AppConfig, raw: str) -> Path | None:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        candidates = [config.repo_root, *config.workspaces.values()]
        for base in candidates:
            candidate = (base / path).resolve()
            allowed_roots = [config.openclaw_home.resolve(), config.repo_root.resolve()]
            if any(candidate.is_relative_to(root) for root in allowed_roots) and candidate.exists() and candidate.is_file():
                return candidate
        path = (config.repo_root / path).resolve()
    else:
        path = path.resolve()
    allowed_roots = [config.openclaw_home.resolve(), config.repo_root.resolve()]
    if any(path.is_relative_to(root) for root in allowed_roots) and path.exists() and path.is_file():
        return path
    return None


def evidence_links(config: AppConfig, values: list[str]) -> str:
    parts: list[str] = []
    for item in values:
        if item.startswith("http://") or item.startswith("https://"):
            parts.append(f"<a href=\"{escape(item)}\" target=\"_blank\" rel=\"noreferrer\">{escape(item)}</a>")
            continue
        resolved = resolve_viewable_path(config, item)
        if resolved is not None:
            parts.append(link(format_path(resolved, [config.openclaw_home, config.repo_root]), file_path_to_url(resolved)))
            continue
        parts.append(f"<code>{escape(item)}</code>")
    return "<br>".join(parts) if parts else "<em>none</em>"


def select_html(name: str, values: list[str], current: str) -> str:
    options = ['<option value=""></option>']
    for item in values:
        selected = " selected" if item == current else ""
        options.append(f"<option value=\"{escape(item)}\"{selected}>{escape(item)}</option>")
    return f"<select name=\"{escape(name)}\">{''.join(options)}</select>"


def input_html(name: str, value: str, placeholder: str = "") -> str:
    return f"<input name=\"{escape(name)}\" value=\"{escape(value)}\" placeholder=\"{escape(placeholder)}\">"


def textarea_html(name: str, value: str, placeholder: str = "", rows: int = 3) -> str:
    return f"<textarea name=\"{escape(name)}\" rows=\"{rows}\" placeholder=\"{escape(placeholder)}\">{escape(value)}</textarea>"


def find_task(tasks: list[dict], task_id: str) -> dict | None:
    for task in tasks:
        if task.get("task_id") == task_id:
            return task
    return None


def find_opportunity(opportunities: list[dict], opportunity_id: str) -> dict | None:
    for item in opportunities:
        if item.get("opportunity_id") == opportunity_id:
            return item
    return None


def load_tasks(config: AppConfig) -> list[dict]:
    registry = load_json(config.registry_path, {"tasks": []})
    tasks = registry["tasks"]
    tasks.sort(
        key=lambda item: (
            0 if item.get("state") != "Closed" else 1,
            0 if has_blocker(item) else 1,
            item.get("priority", "P9"),
            -(parse_iso(item.get("updated_at")) or datetime.fromtimestamp(0, tz=timezone.utc)).timestamp(),
        )
    )
    return tasks


def load_opportunities(config: AppConfig) -> list[dict]:
    payload = load_json(config.opportunities_path, {"opportunities": []})
    opportunities = payload["opportunities"]
    opportunities.sort(
        key=lambda item: (
            STATUS_ORDER.get(str(item.get("status")), 99),
            -float(item.get("score", 0) or 0),
            item.get("opportunity_id", ""),
        )
    )
    return opportunities


def load_agents() -> list[dict]:
    payload = run_cached_json_command("openclaw-status", ["openclaw", "status", "--deep", "--json"])
    if not payload.get("ok", True) and "sessions" not in payload:
        return []
    rows: list[dict] = []
    for item in payload.get("sessions", {}).get("byAgent", []):
        recent = item.get("recent", [])
        last_activity = parse_ts_ms(recent[0].get("updatedAt")) if recent else None
        rows.append(
            {
                "agent_id": item.get("agentId"),
                "count": int(item.get("count", 0) or 0),
                "last_activity": last_activity,
            }
        )
    rows.sort(key=lambda item: item["last_activity"] or datetime.fromtimestamp(0, tz=timezone.utc), reverse=True)
    return rows


def load_cron_jobs() -> list[dict]:
    payload = run_cached_json_command("openclaw-cron-list", ["openclaw", "cron", "list", "--json"])
    if not payload.get("ok", True) and "jobs" not in payload:
        return []
    rows: list[dict] = []
    for item in payload.get("jobs", []):
        state = item.get("state", {})
        rows.append(
            {
                "id": item["id"],
                "name": item["name"],
                "agent_id": item["agentId"],
                "enabled": item["enabled"],
                "last_run_at": parse_ts_ms(state.get("lastRunAtMs")),
                "next_run_at": parse_ts_ms(state.get("nextRunAtMs")),
                "last_run_status": state.get("lastRunStatus") or "-",
                "consecutive_errors": int(state.get("consecutiveErrors", 0) or 0),
                "running": state.get("runningAtMs") is not None,
            }
        )
    rows.sort(
        key=lambda item: (
            0 if item["running"] else 1,
            0 if item["name"] in CORE_JOB_NAMES else 1,
            item["next_run_at"] or datetime.max.replace(tzinfo=timezone.utc),
            item["name"],
        )
    )
    return rows


def load_recent_handoffs(config: AppConfig, limit: int = 8) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(config.handoffs_dir.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name == "README.md" or path.name == "TEMPLATE.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        sender = "-"
        task_id = "-"
        current_stage = "-"
        recipient = "-"
        for line in lines:
            if line.startswith("发送方: "):
                sender = line.split(": ", 1)[1]
            elif line.startswith("任务ID: "):
                task_id = line.split(": ", 1)[1]
            elif line.startswith("当前阶段: "):
                current_stage = line.split(": ", 1)[1]
        if "-to-" in path.stem:
            recipient = path.stem.rsplit("-to-", 1)[1]
        rows.append(
            {
                "path": path,
                "task_id": task_id,
                "sender": sender,
                "recipient": recipient,
                "current_stage": current_stage,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                "summary": lines[5] if len(lines) > 5 else "",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def load_recent_logs(config: AppConfig, limit: int = 20) -> list[dict]:
    rows: list[dict] = []
    for agent_id, workspace in config.workspaces.items():
        log_root = workspace / "data/exec-logs"
        if not log_root.exists():
            continue
        for path in log_root.rglob("*.md"):
            job_name = path.parent.name
            rows.append(
                {
                    "agent_id": agent_id,
                    "job_name": job_name,
                    "path": path,
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                }
            )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows[:limit]


def load_task_handoffs(config: AppConfig, task_id: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(config.handoffs_dir.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name == "README.md" or path.name == "TEMPLATE.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        sender = "-"
        current_task_id = "-"
        current_stage = "-"
        recipient = "-"
        for line in lines:
            if line.startswith("发送方: "):
                sender = line.split(": ", 1)[1]
            elif line.startswith("任务ID: "):
                current_task_id = line.split(": ", 1)[1]
            elif line.startswith("当前阶段: "):
                current_stage = line.split(": ", 1)[1]
        if current_task_id != task_id:
            continue
        if "-to-" in path.stem:
            recipient = path.stem.rsplit("-to-", 1)[1]
        rows.append(
            {
                "path": path,
                "task_id": current_task_id,
                "sender": sender,
                "recipient": recipient,
                "current_stage": current_stage,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            }
        )
    return rows


def load_task_logs(config: AppConfig, task_id: str) -> list[dict]:
    rows: list[dict] = []
    for agent_id, workspace in config.workspaces.items():
        log_root = workspace / "data/exec-logs"
        if not log_root.exists():
            continue
        for path in log_root.rglob("*.md"):
            if task_id not in path.name:
                continue
            rows.append(
                {
                    "agent_id": agent_id,
                    "job_name": path.parent.name,
                    "path": path,
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                }
            )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def build_task_timeline(config: AppConfig, task: dict, handoffs: list[dict], logs: list[dict]) -> list[dict]:
    events: list[dict] = []
    updated_at = parse_iso(task.get("updated_at"))
    if updated_at is not None:
        events.append(
            {
                "when": updated_at,
                "kind": "registry",
                "actor": task.get("owner", "-"),
                "summary": f"registry -> {task.get('state', '-')}",
                "details": task.get("next_step", ""),
                "path": config.registry_path,
            }
        )

    for item in handoffs:
        events.append(
            {
                "when": item["updated_at"],
                "kind": "handoff",
                "actor": item["sender"],
                "summary": f"handoff -> {item['current_stage']}",
                "details": item["path"].name,
                "path": item["path"],
            }
        )

    for item in logs:
        events.append(
            {
                "when": item["updated_at"],
                "kind": "exec-log",
                "actor": item["agent_id"],
                "summary": item["job_name"],
                "details": item["path"].name,
                "path": item["path"],
            }
        )

    evidence = task.get("evidence_pointer", [])
    if isinstance(evidence, list):
        for raw in evidence:
            resolved = resolve_viewable_path(config, raw)
            if resolved is None or resolved == config.registry_path:
                continue
            events.append(
                {
                    "when": datetime.fromtimestamp(resolved.stat().st_mtime, tz=timezone.utc),
                    "kind": "evidence",
                    "actor": "-",
                    "summary": resolved.name,
                    "details": format_path(resolved, [config.openclaw_home, config.repo_root]),
                    "path": resolved,
                }
            )

    events.sort(key=lambda item: item["when"], reverse=True)
    return events


def build_global_events(state: dict, limit: int = 80) -> list[dict]:
    config: AppConfig = state["config"]
    events: list[dict] = []

    for task in state["active_tasks"]:
        updated_at = parse_iso(task.get("updated_at"))
        if updated_at is None:
            continue
        events.append(
            {
                "when": updated_at,
                "kind": "task",
                "actor": task.get("owner", "-"),
                "task_id": task.get("task_id", "-"),
                "summary": f"{task.get('task_id', '-')} -> {task.get('state', '-')}",
                "path": config.registry_path,
            }
        )

    for item in state["recent_handoffs"]:
        events.append(
            {
                "when": item["updated_at"],
                "kind": "handoff",
                "actor": item["sender"],
                "task_id": item["task_id"],
                "summary": f"{item['task_id']} -> {item['current_stage']}",
                "path": item["path"],
            }
        )

    for item in state["recent_logs"]:
        task_id = "-"
        for part in item["path"].stem.split("-"):
            if part.startswith("TASK"):
                task_id = item["path"].stem
                break
        events.append(
            {
                "when": item["updated_at"],
                "kind": "exec-log",
                "actor": item["agent_id"],
                "task_id": task_id,
                "summary": f"{item['agent_id']} / {item['job_name']}",
                "path": item["path"],
            }
        )

    events.sort(key=lambda item: item["when"], reverse=True)
    return events[:limit]


def build_alerts(state: dict) -> list[dict]:
    alerts: list[dict] = []
    now = datetime.now(timezone.utc)

    for task in state["stale_active_tasks"]:
        updated_at = parse_iso(task.get("updated_at"))
        age_hours = int((now - updated_at).total_seconds() // 3600) if updated_at is not None else 999
        level = "danger" if age_hours >= ALERT_CRITICAL_STALE_HOURS else "warn"
        alerts.append(
            {
                "level": level,
                "title": "主线任务陈旧",
                "summary": f"{task.get('task_id', '-')} 已 {age_hours}h 未更新，当前 {task.get('state', '-')}/{task.get('owner', '-')}",
                "href": "/task?" + urlencode({"id": str(task.get("task_id", ""))}),
            }
        )

    if state["failed_jobs"]:
        for job in state["failed_jobs"][:5]:
            alerts.append(
                {
                    "level": "danger",
                    "title": "Cron 连续失败",
                    "summary": f"{job['name']} / {job['agent_id']}，status={job['last_run_status']}，errors={job['consecutive_errors']}",
                    "href": "/cron",
                }
            )

    never_run_core = [job for job in state["never_run_jobs"] if job["name"] in CORE_JOB_NAMES]
    for job in never_run_core[:5]:
        alerts.append(
            {
                "level": "warn",
                "title": "核心 Job 未自然跑过",
                "summary": f"{job['name']} / {job['agent_id']} 还没有首轮自然执行记录",
                "href": "/cron",
            }
        )

    ready_review = state["opportunity_counts"].get("ready_review", 0)
    if ready_review > 0:
        alerts.append(
            {
                "level": "warn",
                "title": "机会池待晋升",
                "summary": f"当前有 {ready_review} 个 ready_review 机会未转正式任务",
                "href": "/opportunities?" + urlencode({"status": "ready_review"}),
            }
        )

    captain_owned = [
        task
        for task in state["active_tasks"]
        if task.get("owner") == "aic-captain" and task.get("state") not in {"Closed", "Observing"}
    ]
    for task in captain_owned[:3]:
        alerts.append(
            {
                "level": "warn",
                "title": "Captain 仍持有执行任务",
                "summary": f"{task.get('task_id', '-')} 还停在 captain 手里，当前 {task.get('state', '-')}",
                "href": "/task?" + urlencode({"id": str(task.get("task_id", ""))}),
            }
        )

    return alerts


def build_agent_stats(state: dict) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for agent_id in AGENT_META:
        stats[agent_id] = {
            "agent_id": agent_id,
            "name": agent_name(agent_id),
            "title": agent_title(agent_id),
            "lane": agent_meta(agent_id)["lane"],
            "sessions": 0,
            "last_activity": None,
            "active_tasks": [],
            "running_jobs": 0,
            "failed_jobs": 0,
            "handoff_out": 0,
            "handoff_in": 0,
        }

    for item in state["agents"]:
        agent_id = item["agent_id"]
        if agent_id not in stats:
            continue
        stats[agent_id]["sessions"] = item["count"]
        stats[agent_id]["last_activity"] = item["last_activity"]

    for task in state["active_tasks"]:
        owner = task.get("owner")
        if owner in stats:
            stats[owner]["active_tasks"].append(task)

    for job in state["running_jobs"]:
        agent_id = job["agent_id"]
        if agent_id in stats:
            stats[agent_id]["running_jobs"] += 1

    for job in state["failed_jobs"]:
        agent_id = job["agent_id"]
        if agent_id in stats:
            stats[agent_id]["failed_jobs"] += 1

    for handoff in state["recent_handoffs"]:
        sender = handoff.get("sender")
        recipient = handoff.get("recipient")
        if sender in stats:
            stats[sender]["handoff_out"] += 1
        if recipient in stats:
            stats[recipient]["handoff_in"] += 1

    return stats


def agent_health(agent_stats: dict) -> tuple[str, str]:
    if agent_stats["failed_jobs"] > 0:
        return ("danger", "告警")
    if len(agent_stats["active_tasks"]) > 0 or agent_stats["running_jobs"] > 0:
        return ("ok", "推进中")
    if agent_stats["sessions"] > 0:
        return ("warn", "活跃")
    return ("muted", "空闲")


def build_mainline_paths(state: dict) -> list[dict]:
    config: AppConfig = state["config"]
    rows: list[dict] = []
    for task in state["active_tasks"][:5]:
        handoffs = load_task_handoffs(config, task["task_id"])
        previous_owner = handoffs[0]["sender"] if handoffs else "-"
        next_owner = EXPECTED_NEXT_OWNER.get(str(task.get("state", "")), "-")
        rows.append(
            {
                "task_id": task["task_id"],
                "title": task.get("title", ""),
                "state": task.get("state", "-"),
                "previous_owner": previous_owner,
                "current_owner": task.get("owner", "-"),
                "next_owner": next_owner,
                "updated_at": parse_iso(task.get("updated_at")),
                "next_step": task.get("next_step", ""),
            }
        )
    return rows


def latest_report_file(root: Path) -> Path | None:
    if not root.exists():
        return None
    files = sorted(root.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not files:
        return None
    return files[0]


def assemble_state(
    config: AppConfig,
    tasks: list[dict],
    opportunities: list[dict],
    agents: list[dict],
    cron_jobs: list[dict],
    recent_handoffs: list[dict],
    recent_logs: list[dict],
    runtime_ready: bool,
    runtime_source: str,
) -> dict:
    active_tasks = [task for task in tasks if task.get("state") != "Closed"]
    blocked_tasks = [task for task in active_tasks if has_blocker(task)]
    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    stale_active_tasks = [
        task
        for task in active_tasks
        if (parse_iso(task.get("updated_at")) or datetime.fromtimestamp(0, tz=timezone.utc)) < stale_cutoff
    ]
    opportunity_counts = Counter(item.get("status", "unknown") for item in opportunities)
    running_jobs = [job for job in cron_jobs if job["running"]]
    never_run_jobs = [job for job in cron_jobs if job["last_run_at"] is None]
    failed_jobs = [job for job in cron_jobs if job["consecutive_errors"] > 0 or job["last_run_status"] == "failed"]
    state = {
        "config": config,
        "tasks": tasks,
        "active_tasks": active_tasks,
        "blocked_tasks": blocked_tasks,
        "stale_active_tasks": stale_active_tasks,
        "opportunities": opportunities,
        "opportunity_counts": opportunity_counts,
        "agents": agents,
        "cron_jobs": cron_jobs,
        "running_jobs": running_jobs,
        "never_run_jobs": never_run_jobs,
        "failed_jobs": failed_jobs,
        "recent_handoffs": recent_handoffs,
        "recent_logs": recent_logs,
        "runtime_ready": runtime_ready,
        "runtime_source": runtime_source,
    }
    state["alerts"] = build_alerts(state)
    state["events"] = build_global_events(state)
    state["agent_stats"] = build_agent_stats(state)
    state["mainline_paths"] = build_mainline_paths(state)
    daily_kpi_path = latest_report_file(config.kpi_root / "daily")
    weekly_kpi_path = latest_report_file(config.kpi_root / "weekly")
    state["kpi"] = {
        "daily_path": daily_kpi_path,
        "daily_report": load_kpi_report(daily_kpi_path),
        "weekly_path": weekly_kpi_path,
        "weekly_report": load_kpi_report(weekly_kpi_path),
    }
    return state


def build_fast_state(config: AppConfig) -> dict:
    return assemble_state(
        config=config,
        tasks=load_tasks(config),
        opportunities=load_opportunities(config),
        agents=[],
        cron_jobs=[],
        recent_handoffs=load_recent_handoffs(config),
        recent_logs=load_recent_logs(config),
        runtime_ready=False,
        runtime_source="fast-local",
    )


def load_kpi_report(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return load_json(path, {"scorecards": [], "summary": {}})


def find_kpi_scorecard(report: dict | None, agent_id: str) -> dict | None:
    if report is None:
        return None
    scorecards = report.get("scorecards", [])
    if not isinstance(scorecards, list):
        return None
    for item in scorecards:
        if isinstance(item, dict) and item.get("agent_id") == agent_id:
            return item
    return None


def compute_state(config: AppConfig) -> dict:
    tasks = load_tasks(config)
    opportunities = load_opportunities(config)
    agents = load_agents()
    cron_jobs = load_cron_jobs()
    active_tasks = [task for task in tasks if task.get("state") != "Closed"]
    blocked_tasks = [task for task in active_tasks if has_blocker(task)]
    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    stale_active_tasks = [
        task
        for task in active_tasks
        if (parse_iso(task.get("updated_at")) or datetime.fromtimestamp(0, tz=timezone.utc)) < stale_cutoff
    ]
    opportunity_counts = Counter(item.get("status", "unknown") for item in opportunities)
    running_jobs = [job for job in cron_jobs if job["running"]]
    never_run_jobs = [job for job in cron_jobs if job["last_run_at"] is None]
    failed_jobs = [job for job in cron_jobs if job["consecutive_errors"] > 0 or job["last_run_status"] == "failed"]
    state = {
        "config": config,
        "tasks": tasks,
        "active_tasks": active_tasks,
        "blocked_tasks": blocked_tasks,
        "stale_active_tasks": stale_active_tasks,
        "opportunities": opportunities,
        "opportunity_counts": opportunity_counts,
        "agents": agents,
        "cron_jobs": cron_jobs,
        "running_jobs": running_jobs,
        "never_run_jobs": never_run_jobs,
        "failed_jobs": failed_jobs,
        "recent_handoffs": load_recent_handoffs(config),
        "recent_logs": load_recent_logs(config),
        "runtime_ready": True,
        "runtime_source": "full-runtime",
    }
    state["alerts"] = build_alerts(state)
    state["events"] = build_global_events(state)
    state["agent_stats"] = build_agent_stats(state)
    state["mainline_paths"] = build_mainline_paths(state)
    daily_kpi_path = latest_report_file(config.kpi_root / "daily")
    weekly_kpi_path = latest_report_file(config.kpi_root / "weekly")
    state["kpi"] = {
        "daily_path": daily_kpi_path,
        "daily_report": load_kpi_report(daily_kpi_path),
        "weekly_path": weekly_kpi_path,
        "weekly_report": load_kpi_report(weekly_kpi_path),
    }
    return state


def refresh_state_cache(config: AppConfig) -> dict:
    cache_key = str(config.openclaw_home.resolve())
    try:
        state = compute_state(config)
        with CACHE_LOCK:
            STATE_CACHE[cache_key] = (time.monotonic(), state)
        return dict(state)
    finally:
        with CACHE_LOCK:
            STATE_REFRESHING.discard(cache_key)


def schedule_state_refresh(config: AppConfig) -> None:
    cache_key = str(config.openclaw_home.resolve())
    with CACHE_LOCK:
        if cache_key in STATE_REFRESHING:
            return
        STATE_REFRESHING.add(cache_key)

    thread = threading.Thread(target=refresh_state_cache, args=(config,), daemon=True)
    thread.start()


def build_state(config: AppConfig) -> dict:
    cache_key = str(config.openclaw_home.resolve())
    with CACHE_LOCK:
        cached = STATE_CACHE.get(cache_key)
    now = time.monotonic()
    if cached is None:
        state = build_fast_state(config)
        with CACHE_LOCK:
            STATE_CACHE[cache_key] = (now, state)
        schedule_state_refresh(config)
        return dict(state)
    if now - cached[0] < STATE_CACHE_TTL_SECONDS:
        return dict(cached[1])
    schedule_state_refresh(config)
    return dict(cached[1])


def prewarm_loop(config: AppConfig) -> None:
    while True:
        with CACHE_LOCK:
            cached = STATE_CACHE.get(str(config.openclaw_home.resolve()))
        if cached is None:
            schedule_state_refresh(config)
        else:
            cached_at, cached_state = cached
            if not cached_state.get("runtime_ready", False) or time.monotonic() - cached_at >= CACHE_PREWARM_INTERVAL_SECONDS:
                schedule_state_refresh(config)
        time.sleep(CACHE_PREWARM_INTERVAL_SECONDS)


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(item)}</th>" for item in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    if not body_rows:
        body_rows.append(f"<tr><td colspan=\"{len(headers)}\"><em>暂无</em></td></tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def card(title: str, value: str, hint: str = "") -> str:
    hint_html = f"<div class=\"hint\">{escape(hint)}</div>" if hint else ""
    return f"<div class=\"card\"><div class=\"card-title\">{escape(title)}</div><div class=\"card-value\">{escape(value)}</div>{hint_html}</div>"


def layout(title: str, body: str, current: str, message: str) -> bytes:
    nav_items = [
        ("总览", "/"),
        ("任务", "/tasks"),
        ("机会池", "/opportunities"),
        ("KPI", "/kpi"),
        ("事件流", "/events"),
        ("Handoffs", "/handoffs"),
        ("团队", "/agents"),
        ("Cron", "/cron"),
        ("日志", "/logs"),
    ]
    nav = []
    for label, href in nav_items:
        cls = "active" if href == current else ""
        nav.append(f"<a class=\"{cls}\" href=\"{href}\">{escape(label)}</a>")
    flash = f"<div class=\"flash\">{escape(message)}</div>" if message else ""
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #121a2f;
      --muted: #8ea0c9;
      --text: #ecf2ff;
      --accent: #6ea8fe;
      --danger: #ff7875;
      --warn: #f7c948;
      --ok: #73d13d;
      --border: #223154;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 16px 20px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: rgba(11,16,32,0.94); backdrop-filter: blur(8px); }}
    h1 {{ margin: 0 0 10px; font-size: 22px; }}
    nav {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    nav a {{ color: var(--muted); text-decoration: none; padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px; }}
    nav a.active {{ color: var(--text); border-color: var(--accent); }}
    main {{ padding: 20px; max-width: 1500px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card, .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }}
    .card-title {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .card-value {{ font-size: 28px; font-weight: 700; }}
    .hint {{ margin-top: 6px; color: var(--muted); font-size: 12px; }}
    .flash {{ margin-bottom: 12px; padding: 10px 12px; border: 1px solid var(--accent); border-radius: 10px; background: rgba(110,168,254,0.12); }}
    .row {{ display: grid; gap: 16px; margin-top: 16px; }}
    .two {{ grid-template-columns: 1.4fr 1fr; }}
    .three {{ grid-template-columns: repeat(3, 1fr); }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    h3 {{ margin: 0 0 10px; font-size: 15px; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; vertical-align: top; padding: 10px 8px; border-top: 1px solid var(--border); font-size: 14px; }}
    th {{ color: var(--muted); border-top: none; }}
    code {{ color: #d3e1ff; }}
    .muted {{ color: var(--muted); }}
    .danger {{ color: var(--danger); }}
    .warn {{ color: var(--warn); }}
    .ok {{ color: var(--ok); }}
    .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; }}
    form.inline {{ display: inline; }}
    button {{ cursor: pointer; border: 1px solid var(--border); background: #182443; color: var(--text); padding: 6px 10px; border-radius: 8px; }}
    input, select, textarea {{ width: 100%; border: 1px solid var(--border); background: #0f1832; color: var(--text); padding: 8px 10px; border-radius: 8px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .form-grid .full {{ grid-column: 1 / -1; }}
    .topology-layer {{ display: grid; gap: 12px; margin-top: 14px; }}
    .topology-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .agent-card {{ background: #0f1832; border: 1px solid var(--border); border-radius: 12px; padding: 12px; }}
    .agent-card.ok {{ border-color: rgba(115,209,61,0.7); }}
    .agent-card.warn {{ border-color: rgba(247,201,72,0.7); }}
    .agent-card.danger {{ border-color: rgba(255,120,117,0.8); }}
    .agent-card .agent-name {{ font-size: 18px; font-weight: 700; }}
    .agent-card .agent-id {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}
    .agent-card .agent-role {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
    .agent-stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 12px; }}
    .agent-stat {{ background: rgba(255,255,255,0.03); border-radius: 8px; padding: 8px; }}
    .agent-stat-label {{ color: var(--muted); font-size: 12px; }}
    .agent-stat-value {{ font-size: 16px; font-weight: 700; margin-top: 2px; }}
    .edge-strip {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }}
    .edge-node {{ padding: 4px 8px; border: 1px solid var(--border); border-radius: 999px; font-size: 12px; }}
    .edge-node.hot {{ border-color: var(--accent); color: var(--text); }}
    @media (max-width: 980px) {{
      .two, .three {{ grid-template-columns: 1fr; }}
      .form-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <nav>{''.join(nav)}</nav>
  </header>
  <main>
    {flash}
    {body}
  </main>
</body>
</html>"""
    return html_text.encode("utf-8")


def render_summary(state: dict, message: str) -> bytes:
    config: AppConfig = state["config"]
    runtime_ready = bool(state.get("runtime_ready", False))
    active_tasks = state["active_tasks"]
    blocked_tasks = state["blocked_tasks"]
    stale_active_tasks = state["stale_active_tasks"]
    ready_review = state["opportunity_counts"].get("ready_review", 0)
    candidates = state["opportunity_counts"].get("candidate", 0)
    running_jobs = state["running_jobs"]
    never_run_core = [job for job in state["never_run_jobs"] if job["name"] in CORE_JOB_NAMES]
    active_agents = [item for item in state["agents"] if item["count"] > 0]
    alerts = state["alerts"]
    daily_kpi = state["kpi"]["daily_report"]
    daily_summary = daily_kpi.get("summary", {}) if isinstance(daily_kpi, dict) else {}
    if isinstance(daily_summary.get("top_agents"), list):
        daily_top = ", ".join(agent_name(item) for item in daily_summary.get("top_agents", [])[:3])
    else:
        daily_top = "-"

    runtime_jobs_value = str(len(running_jobs)) if runtime_ready else "加载中"
    runtime_never_run_value = str(len(never_run_core)) if runtime_ready else "加载中"
    runtime_agents_value = str(len(active_agents)) if runtime_ready else "加载中"
    cards = "".join(
        [
            card("活跃任务", str(len(active_tasks)), "正式任务控制面"),
            card("阻塞任务", str(len(blocked_tasks)), "以 registry 为准"),
            card("陈旧活跃任务", str(len(stale_active_tasks)), "超过 6 小时未更新"),
            card("Ready Review 机会", str(ready_review), "可晋升正式任务"),
            card("候选机会", str(candidates), "研究池"),
            card("运行中的 Jobs", runtime_jobs_value, "来自 openclaw cron"),
            card("未自然跑过核心 Jobs", runtime_never_run_value, "需要区分未到时间和未触发"),
            card("活跃 Agents", runtime_agents_value, "最近有 session"),
            card("Daily KPI Top", daily_top or "-", "最新评分 Top 3"),
        ]
    )

    summary_rows = []
    for task in active_tasks[:10]:
        updated_at = parse_iso(task.get("updated_at"))
        summary_rows.append(
            [
                link(task["task_id"], "/task?" + urlencode({"id": str(task["task_id"])})),
                f"<span class=\"pill\">{escape(task['state'])}</span>",
                escape(task["owner"]),
                escape(task["priority"]),
                escape(format_age(updated_at)),
                escape(task.get("next_step", "")),
            ]
        )

    opportunity_rows = []
    for item in state["opportunities"][:8]:
        opportunity_rows.append(
            [
                link(str(item.get("opportunity_id", "-")), "/opportunity?" + urlencode({"id": str(item.get("opportunity_id", ""))})),
                f"<span class=\"pill\">{escape(item.get('status', '-'))}</span>",
                escape(item.get("score", "-")),
                escape(item.get("recommended_action", "-")),
                escape(item.get("summary", "")),
            ]
        )

    job_rows = []
    for job in state["cron_jobs"][:10]:
        action = (
            "<form class=\"inline\" method=\"post\" action=\"/actions/run-cron\">"
            f"<input type=\"hidden\" name=\"job_id\" value=\"{escape(job['id'])}\">"
            f"<input type=\"hidden\" name=\"next\" value=\"/cron\">"
            "<button type=\"submit\">Run now</button>"
            "</form>"
        )
        status = "running" if job["running"] else job["last_run_status"]
        job_rows.append(
            [
                escape(job["name"]),
                escape(job["agent_id"]),
                escape(status),
                escape(format_dt(job["last_run_at"])),
                escape(format_dt(job["next_run_at"])),
                action,
            ]
        )

    log_rows = []
    for item in state["recent_logs"][:10]:
        relative = format_path(item["path"], [config.openclaw_home, config.repo_root])
        log_rows.append(
            [
                escape(item["agent_id"]),
                escape(item["job_name"]),
                escape(format_dt(item["updated_at"])),
                link(relative, file_path_to_url(item["path"])),
            ]
        )

    alert_rows = [
        [
            f"<span class=\"pill {escape(item['level'])}\">{escape(item['level'])}</span>",
            escape(item["title"]),
            link(item["summary"], item["href"]),
        ]
        for item in alerts[:12]
    ]

    event_rows = [
        [
            escape(format_dt(item["when"])),
            escape(item["kind"]),
            escape(item["actor"]),
            escape(item["task_id"]),
            link(item["summary"], file_path_to_url(item["path"])),
        ]
        for item in state["events"][:12]
    ]

    quick_actions = f"""
    <div class="panel">
      <h2>快捷操作</h2>
      <div class="actions">
        <form class="inline" method="post" action="/actions/refresh-dashboard">
          <input type="hidden" name="next" value="/">
          <button type="submit">刷新 Captain 看板</button>
        </form>
        {render_job_trigger(state, 'planner-intake', '/')}
        {render_job_trigger(state, 'ambient-discovery', '/')}
        {render_job_trigger(state, 'opportunity-promotion', '/')}
        {render_job_trigger(state, 'daily-kpi', '/')}
        {render_job_trigger(state, 'weekly-kpi', '/')}
      </div>
      <div class="hint">默认只绑定本机地址。若要公网访问，建议放到反向代理和鉴权后面。</div>
    </div>
    """

    runtime_banner = ""
    if not runtime_ready:
        runtime_banner = """
    <div class="panel">
      <h2>运行态后台加载中</h2>
      <div class="muted">当前页已先展示本地任务、机会、交接和 KPI 快照；OpenClaw 的 agent/session/cron 运行态正在后台刷新，页面会自动再刷新一次。</div>
    </div>
    <script>setTimeout(function(){ window.location.reload(); }, 2500);</script>
    """

    body = f"""
    {runtime_banner}
    <div class="panel">
      <h2>控制面说明</h2>
      <div class="muted">正式任务状态以 <code>{escape(config.registry_path)}</code> 为真相源；本页面和 <code>dashboard.md</code> 都是观察面。</div>
    </div>
    <div class="grid" style="margin-top:16px">{cards}</div>
    <div class="row two">
      <div class="panel">
        <h2>活跃任务</h2>
        {table(['Task', 'State', 'Owner', 'Priority', 'Age', 'Next Step'], summary_rows)}
      </div>
      <div class="panel">
        <h2>机会池 Top</h2>
        {table(['Opportunity', 'Status', 'Score', 'Action', 'Summary'], opportunity_rows)}
      </div>
    </div>
    <div class="row two">
      <div class="panel">
        <h2>Cron 概览</h2>
        {table(['Job', 'Agent', 'Status', 'Last Run', 'Next Run', 'Action'], job_rows)}
      </div>
      {quick_actions}
    </div>
    <div class="row two">
      <div class="panel">
        <h2>运行告警</h2>
        {table(['Level', 'Type', 'Summary'], alert_rows)}
      </div>
      <div class="panel">
        <h2>全局事件流</h2>
        {table(['Time', 'Kind', 'Actor', 'Task', 'Summary'], event_rows)}
      </div>
    </div>
    <div class="row two">
      <div class="panel">
        <h2>最新执行日志</h2>
        {table(['Agent', 'Job', 'Updated', 'Path'], log_rows)}
      </div>
      <div class="panel">
        <h2>运行判断</h2>
        <ul>
          <li>主线活跃任务：<strong>{escape(len(active_tasks))}</strong> 张</li>
          <li>主线陈旧任务：<strong>{escape(len(stale_active_tasks))}</strong> 张</li>
          <li>研究池 ready_review：<strong>{escape(ready_review)}</strong> 个</li>
          <li>核心 job 未自然跑过：<strong>{escape(len(never_run_core))}</strong> 个</li>
          <li>若“活跃任务少 + 研究池堆积 + 核心 job 长期未自然跑”，通常不是偷懒，而是调度节奏或主线分配有问题。</li>
        </ul>
      </div>
    </div>
    """
    return layout("OpenClaw Team Control Plane", body, "/", message)


def render_tasks(state: dict, message: str) -> bytes:
    query = state["query"]
    owner_filter = query.get("owner", [""])[0]
    state_filter = query.get("state", [""])[0]
    rows = []
    for task in state["tasks"]:
        if owner_filter and task.get("owner") != owner_filter:
            continue
        if state_filter and task.get("state") != state_filter:
            continue
        updated_at = parse_iso(task.get("updated_at"))
        evidence = task.get("evidence_pointer", [])
        evidence_count = len(evidence) if isinstance(evidence, list) else 0
        rows.append(
            [
                link(task["task_id"], "/task?" + urlencode({"id": str(task["task_id"])})),
                escape(task.get("title", "")),
                f"<span class=\"pill\">{escape(task.get('state', '-'))}</span>",
                escape(task.get("owner", "-")),
                escape(task.get("priority", "-")),
                escape(format_dt(updated_at)),
                escape(task.get("blocker") or "none"),
                escape(task.get("next_step", "")),
                escape(evidence_count),
            ]
        )
    filters = f"""
    <div class="panel">
      <h2>过滤</h2>
      <form method="get" action="/tasks" class="actions">
        <input name="owner" placeholder="owner" value="{escape(owner_filter)}">
        <input name="state" placeholder="state" value="{escape(state_filter)}">
        <button type="submit">过滤</button>
      </form>
    </div>
    """
    body = filters + f"<div class=\"panel\"><h2>任务控制面</h2>{table(['Task', 'Title', 'State', 'Owner', 'Priority', 'Updated', 'Blocker', 'Next Step', 'Evidence'], rows)}</div>"
    return layout("Tasks", body, "/tasks", message)


def render_opportunities(state: dict, message: str) -> bytes:
    query = state["query"]
    status_filter = query.get("status", [""])[0]
    rows = []
    for item in state["opportunities"][:50]:
        if status_filter and item.get("status") != status_filter:
            continue
        topic_ids = item.get("topic_ids", [])
        topic_text = ", ".join(topic_ids) if isinstance(topic_ids, list) and topic_ids else "-"
        actions = [escape(item.get("recommended_action", "-"))]
        if item.get("status") == "ready_review":
            actions.append(
                (
                    "<form class=\"inline\" method=\"post\" action=\"/actions/promote-opportunity\">"
                    f"<input type=\"hidden\" name=\"opportunity_id\" value=\"{escape(item.get('opportunity_id', ''))}\">"
                    "<input type=\"hidden\" name=\"next\" value=\"/opportunities\">"
                    "<button type=\"submit\">晋升</button>"
                    "</form>"
                )
            )
        rows.append(
            [
                link(str(item.get("opportunity_id", "-")), "/opportunity?" + urlencode({"id": str(item.get("opportunity_id", ""))})),
                f"<span class=\"pill\">{escape(item.get('status', '-'))}</span>",
                escape(item.get("score", "-")),
                " ".join(actions),
                escape(topic_text),
                escape(item.get("evidence_count", 0)),
                escape(item.get("evidence_domain_diversity", 0)),
                link(str(item.get("task_id")), "/task?" + urlencode({"id": str(item.get("task_id"))})) if item.get("task_id") else "-",
                escape(item.get("summary", "")),
            ]
        )
    filters = f"""
    <div class="panel">
      <h2>过滤</h2>
      <form method="get" action="/opportunities" class="actions">
        <input name="status" placeholder="status" value="{escape(status_filter)}">
        <button type="submit">过滤</button>
      </form>
    </div>
    """
    body = filters + f"<div class=\"panel\"><h2>机会池</h2>{table(['Opportunity', 'Status', 'Score', 'Action', 'Topics', 'Evidence', 'Domains', 'Task', 'Summary'], rows)}</div>"
    return layout("Opportunities", body, "/opportunities", message)


def render_agents(state: dict, message: str) -> bytes:
    agent_stats = state["agent_stats"]
    layer_sections: list[str] = []
    for layer in AGENT_LAYERS:
        cards = []
        for agent_id in layer:
            stats = agent_stats[agent_id]
            health_class, health_label = agent_health(stats)
            active_tasks = stats["active_tasks"]
            active_task_links = "<br>".join(
                link(task["task_id"], "/task?" + urlencode({"id": str(task["task_id"])}))
                for task in active_tasks[:3]
            ) if active_tasks else "<span class=\"muted\">暂无</span>"
            cards.append(
                f"""
                <div class="agent-card {health_class}">
                  <div class="agent-name">{escape(stats['name'])}</div>
                  <div class="agent-id">{escape(agent_id)}</div>
                  <div class="agent-role">{escape(stats['title'])}</div>
                  <div style="margin-top:8px;"><span class="pill">{escape(health_label)}</span></div>
                  <div class="agent-stats">
                    <div class="agent-stat"><div class="agent-stat-label">Sessions</div><div class="agent-stat-value">{escape(stats['sessions'])}</div></div>
                    <div class="agent-stat"><div class="agent-stat-label">最近活动</div><div class="agent-stat-value">{escape(format_age(stats['last_activity']))}</div></div>
                    <div class="agent-stat"><div class="agent-stat-label">持有任务</div><div class="agent-stat-value">{escape(len(active_tasks))}</div></div>
                    <div class="agent-stat"><div class="agent-stat-label">失败 Jobs</div><div class="agent-stat-value">{escape(stats['failed_jobs'])}</div></div>
                  </div>
                  <div class="hint">当前任务</div>
                  <div>{active_task_links}</div>
                </div>
                """
            )
        layer_sections.append(f"<div class=\"topology-row\">{''.join(cards)}</div>")

    relation_rows = []
    recent_edges = {(item.get("sender"), item.get("recipient")) for item in state["recent_handoffs"]}
    for caller, callees in CALL_GRAPH:
        callee_nodes = []
        for callee in callees:
            hot = " hot" if (caller, callee) in recent_edges else ""
            callee_nodes.append(f"<span class=\"edge-node{hot}\">{escape(agent_name(callee))}</span>")
        relation_rows.append(
            f"""
            <div class="panel">
              <h3>{escape(agent_name(caller))} / {escape(agent_title(caller))}</h3>
              <div class="edge-strip">
                <span class="edge-node hot">{escape(agent_name(caller))}</span>
                <span>→</span>
                {''.join(callee_nodes)}
              </div>
            </div>
            """
        )

    path_rows = []
    for item in state["mainline_paths"]:
        path_rows.append(
            [
                link(item["task_id"], "/task?" + urlencode({"id": item["task_id"]})),
                escape(item["state"]),
                escape(agent_name(item["previous_owner"]) if item["previous_owner"] in AGENT_META else item["previous_owner"]),
                escape(agent_name(item["current_owner"]) if item["current_owner"] in AGENT_META else item["current_owner"]),
                escape(agent_name(item["next_owner"]) if item["next_owner"] in AGENT_META else item["next_owner"]),
                escape(format_dt(item["updated_at"])),
                escape(item["next_step"]),
            ]
        )

    rows = []
    for agent_id in AGENT_META:
        stats = agent_stats[agent_id]
        health_label = agent_health(stats)[1]
        rows.append(
            [
                escape(stats["name"]),
                escape(agent_id),
                escape(stats["title"]),
                escape(stats["sessions"]),
                escape(len(stats["active_tasks"])),
                escape(stats["running_jobs"]),
                escape(stats["failed_jobs"]),
                escape(format_dt(stats["last_activity"])),
                escape(health_label),
            ]
        )

    body = f"""
    <div class="panel">
      <h2>团队拓扑</h2>
      <div class="muted">这里按中文角色名展示团队结构；静态关系来自 `AGENT_GRAPH.md`，动态高亮来自最近 handoff 与运行态。</div>
      <div class="topology-layer">{''.join(layer_sections)}</div>
    </div>
    <div class="row two">
      <div class="panel">
        <h2>调度关系</h2>
        {''.join(relation_rows)}
      </div>
      <div class="panel">
        <h2>当前主线路径</h2>
        {table(['Task', 'State', '上一步', '当前负责人', '下一站', 'Updated', 'Next Step'], path_rows)}
      </div>
    </div>
    <div class="panel">
      <h2>团队角色总览</h2>
      {table(['中文名', 'Agent ID', '职责', 'Sessions', '持有任务', '运行中 Jobs', '失败 Jobs', 'Last Activity', '状态'], rows)}
    </div>
    """
    return layout("团队", body, "/agents", message)


def render_handoffs(state: dict, message: str) -> bytes:
    config: AppConfig = state["config"]
    rows = []
    for item in state["recent_handoffs"]:
        rows.append(
            [
                link(item["task_id"], "/task?" + urlencode({"id": item["task_id"]})),
                escape(item["sender"]),
                escape(item["current_stage"]),
                escape(format_dt(item["updated_at"])),
                link(format_path(item["path"], [config.openclaw_home, config.repo_root]), file_path_to_url(item["path"])),
            ]
        )
    body = f"<div class=\"panel\"><h2>Recent Handoffs</h2>{table(['Task', 'From', 'Stage', 'Updated', 'File'], rows)}</div>"
    return layout("Handoffs", body, "/handoffs", message)


def render_events(state: dict, message: str) -> bytes:
    query = state["query"]
    kind_filter = query.get("kind", [""])[0]
    actor_filter = query.get("actor", [""])[0]
    rows = []
    for item in state["events"]:
        if kind_filter and item["kind"] != kind_filter:
            continue
        if actor_filter and item["actor"] != actor_filter:
            continue
        rows.append(
            [
                escape(format_dt(item["when"])),
                escape(item["kind"]),
                escape(item["actor"]),
                escape(item["task_id"]),
                link(format_path(item["path"], [state["config"].openclaw_home, state["config"].repo_root]), file_path_to_url(item["path"])),
                escape(item["summary"]),
            ]
        )
    filters = f"""
    <div class="panel">
      <h2>过滤</h2>
      <form method="get" action="/events" class="actions">
        <input name="kind" placeholder="kind" value="{escape(kind_filter)}">
        <input name="actor" placeholder="actor" value="{escape(actor_filter)}">
        <button type="submit">过滤</button>
      </form>
    </div>
    """
    body = filters + f"<div class=\"panel\"><h2>全局事件流</h2>{table(['Time', 'Kind', 'Actor', 'Task', 'File', 'Summary'], rows)}</div>"
    return layout("Events", body, "/events", message)


def render_kpi(state: dict, message: str) -> bytes:
    daily_report = state["kpi"]["daily_report"]
    weekly_report = state["kpi"]["weekly_report"]
    daily_path = state["kpi"]["daily_path"]
    weekly_path = state["kpi"]["weekly_path"]

    def render_report_section(title: str, report: dict | None, report_path: Path | None, period: str) -> str:
        if report is None:
            return f"<div class=\"panel\"><h2>{escape(title)}</h2><div class=\"muted\">暂无评分文件</div></div>"
        summary = report.get("summary", {})
        scorecards = report.get("scorecards", [])
        top_agents = ", ".join(summary.get("top_agents", [])) if isinstance(summary.get("top_agents"), list) else "-"
        risk_agents = ", ".join(summary.get("risk_agents", [])) if isinstance(summary.get("risk_agents"), list) else "-"
        rows = []
        for item in scorecards:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    link(agent_name(str(item.get("agent_id", "-"))), "/kpi/agent?" + urlencode({"id": str(item.get("agent_id", "")), "period": period})),
                    escape(item.get("agent_id", "-")),
                    escape(item.get("status", "-")),
                    escape(item.get("score_total", "N/A")),
                    escape(len(item.get("highlights", [])) if isinstance(item.get("highlights"), list) else 0),
                    escape(len(item.get("risks", [])) if isinstance(item.get("risks"), list) else 0),
                ]
            )
        meta = [
            ("window_start", escape(report.get("window_start", "-"))),
            ("window_end", escape(report.get("window_end", "-"))),
            ("top_agents", escape(top_agents or "-")),
            ("risk_agents", escape(risk_agents or "-")),
            ("output", link(format_path(report_path, [state["config"].openclaw_home, state["config"].repo_root]), file_path_to_url(report_path)) if report_path else "-"),
        ]
        return render_kv_table(title, meta) + table(["Agent", "Agent ID", "Status", "Score", "Highlights", "Risks"], rows)

    actions = f"""
    <div class="panel">
      <h2>快捷操作</h2>
      <div class="actions">
        {render_job_trigger(state, 'daily-kpi', '/kpi')}
        {render_job_trigger(state, 'weekly-kpi', '/kpi')}
      </div>
    </div>
    """
    body = actions + render_report_section("Daily KPI", daily_report, daily_path, "daily") + render_report_section("Weekly KPI", weekly_report, weekly_path, "weekly")
    return layout("KPI", body, "/kpi", message)


def render_kpi_agent(state: dict, agent_id: str, period: str, message: str) -> bytes:
    report = state["kpi"]["daily_report"] if period == "daily" else state["kpi"]["weekly_report"]
    scorecard = find_kpi_scorecard(report, agent_id)
    if scorecard is None:
        return layout("KPI Agent", f"<div class=\"panel\"><h2>KPI</h2><div class=\"muted\">未找到该 agent 的 {escape(period)} 评分</div></div>", "/kpi", message)

    breakdown_rows = [
        [escape(key), escape(value if value is not None else "N/A")]
        for key, value in scorecard.get("score_breakdown", {}).items()
    ]
    metric_rows = []
    for item in scorecard.get("metrics", []):
        metric_rows.append(
            [
                escape(item.get("group", "-")),
                escape(item.get("metric_id", "-")),
                escape(item.get("value", "-")),
                escape(item.get("target", "-")),
                escape(item.get("score", "-")),
            ]
        )
    evidence_rows = []
    for item in scorecard.get("evidence", []):
        evidence_rows.append([evidence_links(state["config"], [item])])

    facts_rows = [
        [escape(key), escape(value)]
        for key, value in scorecard.get("facts", {}).items()
    ]
    highlights = scorecard.get("highlights", [])
    risks = scorecard.get("risks", [])
    body = f"""
    {render_kv_table('评分概览', [
        ('agent', escape(agent_name(agent_id))),
        ('agent_id', escape(agent_id)),
        ('period', escape(period)),
        ('status', escape(scorecard.get('status', '-'))),
        ('score_total', escape(scorecard.get('score_total', 'N/A')))
    ])}
    <div class="row two">
      <div class="panel"><h2>分项评分</h2>{table(['Item', 'Score'], breakdown_rows)}</div>
      <div class="panel"><h2>事实摘要</h2>{table(['Key', 'Value'], facts_rows)}</div>
    </div>
    <div class="row two">
      <div class="panel"><h2>亮点</h2><ul>{''.join(f'<li>{escape(item)}</li>' for item in highlights) or '<li class="muted">暂无</li>'}</ul></div>
      <div class="panel"><h2>风险</h2><ul>{''.join(f'<li>{escape(item)}</li>' for item in risks) or '<li class="muted">暂无</li>'}</ul></div>
    </div>
    <div class="panel"><h2>指标明细</h2>{table(['Group', 'Metric', 'Value', 'Target', 'Score'], metric_rows)}</div>
    <div class="panel"><h2>证据</h2>{table(['Path'], evidence_rows)}</div>
    """
    return layout(f"KPI {agent_name(agent_id)}", body, "/kpi", message)


def render_cron(state: dict, message: str) -> bytes:
    rows = []
    for job in state["cron_jobs"]:
        action = (
            "<form class=\"inline\" method=\"post\" action=\"/actions/run-cron\">"
            f"<input type=\"hidden\" name=\"job_id\" value=\"{escape(job['id'])}\">"
            f"<input type=\"hidden\" name=\"next\" value=\"/cron\">"
            "<button type=\"submit\">Run now</button>"
            "</form>"
        )
        rows.append(
            [
                escape(job["name"]),
                escape(job["agent_id"]),
                escape("yes" if job["enabled"] else "no"),
                escape("running" if job["running"] else job["last_run_status"]),
                escape(job["consecutive_errors"]),
                escape(format_dt(job["last_run_at"])),
                escape(format_dt(job["next_run_at"])),
                action,
            ]
        )
    body = f"<div class=\"panel\"><h2>Cron Jobs</h2>{table(['Job', 'Agent', 'Enabled', 'Status', 'Errors', 'Last Run', 'Next Run', 'Action'], rows)}</div>"
    return layout("Cron", body, "/cron", message)


def render_logs(state: dict, message: str) -> bytes:
    config: AppConfig = state["config"]
    rows = []
    for item in state["recent_logs"]:
        rows.append(
            [
                escape(item["agent_id"]),
                escape(item["job_name"]),
                escape(format_dt(item["updated_at"])),
                link(format_path(item["path"], [config.openclaw_home, config.repo_root]), file_path_to_url(item["path"])),
            ]
        )
    body = f"<div class=\"panel\"><h2>最新执行日志</h2>{table(['Agent', 'Job', 'Updated', 'Path'], rows)}</div>"
    return layout("Logs", body, "/logs", message)


def render_kv_table(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><th>{escape(key)}</th><td>{value}</td></tr>" for key, value in rows)
    return f"<div class=\"panel\"><h2>{escape(title)}</h2><table><tbody>{body}</tbody></table></div>"


def render_task_detail(state: dict, task: dict, message: str) -> bytes:
    config: AppConfig = state["config"]
    evidence = task.get("evidence_pointer", [])
    handoffs = load_task_handoffs(config, task["task_id"])
    logs = load_task_logs(config, task["task_id"])
    timeline = build_task_timeline(config, task, handoffs, logs)
    details = render_kv_table(
        "任务详情",
        [
            ("task_id", escape(task["task_id"])),
            ("title", escape(task.get("title", ""))),
            ("state", f"<span class=\"pill\">{escape(task.get('state', '-'))}</span>"),
            ("owner", escape(task.get("owner", "-"))),
            ("priority", escape(task.get("priority", "-"))),
            ("updated_at", escape(task.get("updated_at", "-"))),
            ("blocker", escape(task.get("blocker") or "none")),
            ("next_step", escape(task.get("next_step", ""))),
            ("evidence", evidence_links(config, evidence if isinstance(evidence, list) else [])),
        ],
    )
    blocker_value = task.get("blocker") if isinstance(task.get("blocker"), str) else ""
    handoff_rows = [
        [
            escape(item["sender"]),
            escape(item["current_stage"]),
            escape(format_dt(item["updated_at"])),
            link(format_path(item["path"], [config.openclaw_home, config.repo_root]), file_path_to_url(item["path"])),
        ]
        for item in handoffs
    ]
    log_rows = [
        [
            escape(item["agent_id"]),
            escape(item["job_name"]),
            escape(format_dt(item["updated_at"])),
            link(format_path(item["path"], [config.openclaw_home, config.repo_root]), file_path_to_url(item["path"])),
        ]
        for item in logs
    ]
    timeline_rows = [
        [
            escape(format_dt(item["when"])),
            escape(item["kind"]),
            escape(item["actor"]),
            escape(item["summary"]),
            link(format_path(item["path"], [config.openclaw_home, config.repo_root]), file_path_to_url(item["path"])),
        ]
        for item in timeline[:40]
    ]
    actions = f"""
    <div class="panel">
      <h2>任务流转</h2>
      <form method="post" action="/actions/update-task">
        <input type="hidden" name="task_id" value="{escape(task['task_id'])}">
        <input type="hidden" name="next" value="/task?id={escape(task['task_id'])}">
        <div class="form-grid">
          <div>
            <label>State</label>
            {select_html("state", TASK_STATE_OPTIONS, str(task.get("state", "")))}
          </div>
          <div>
            <label>Owner</label>
            {select_html("owner", OWNER_OPTIONS, str(task.get("owner", "")))}
          </div>
          <div>
            <label>Priority</label>
            {input_html("priority", str(task.get("priority", "")), "P1")}
          </div>
          <div>
            <label>Clear blocker</label>
            <div class="actions"><label><input style="width:auto" type="checkbox" name="clear_blocker" value="1"> clear</label></div>
          </div>
          <div class="full">
            <label>Next step</label>
            {textarea_html("next_step", str(task.get("next_step", "")), "下一步", 3)}
          </div>
          <div class="full">
            <label>Blocker</label>
            {textarea_html("blocker", blocker_value, "阻塞原因；若要清空请勾选 clear blocker", 3)}
          </div>
          <div class="full">
            <label>Note</label>
            {input_html("note", "", "写入 task.notes，便于审计")}
          </div>
        </div>
        <div class="actions" style="margin-top:12px;">
          <button type="submit">更新任务</button>
        </div>
      </form>
    </div>
    <div class="panel">
      <h2>快捷操作</h2>
      <div class="actions">
        <form class="inline" method="post" action="/actions/refresh-dashboard">
          <input type="hidden" name="next" value="/task?id={escape(task['task_id'])}">
          <button type="submit">刷新看板</button>
        </form>
      </div>
    </div>
    """
    body = (
        details
        + actions
        + table(["Time", "Kind", "Actor", "Summary", "File"], timeline_rows)
        + table(["From", "Stage", "Updated", "File"], handoff_rows)
        + table(["Agent", "Job", "Updated", "Log"], log_rows)
    )
    return layout(f"Task {task['task_id']}", body, "/tasks", message)


def render_opportunity_detail(state: dict, opportunity: dict, message: str) -> bytes:
    config: AppConfig = state["config"]
    evidence = opportunity.get("evidence_urls", [])
    if not isinstance(evidence, list):
        evidence = []
    if opportunity.get("card_path"):
        evidence = [str(opportunity["card_path"]), *evidence]
    task_link = "-"
    if opportunity.get("task_id"):
        task_link = link(str(opportunity["task_id"]), "/task?" + urlencode({"id": str(opportunity["task_id"])}))
    details = render_kv_table(
        "机会详情",
        [
            ("opportunity_id", escape(opportunity.get("opportunity_id", "-"))),
            ("status", f"<span class=\"pill\">{escape(opportunity.get('status', '-'))}</span>"),
            ("score", escape(opportunity.get("score", "-"))),
            ("recommended_action", escape(opportunity.get("recommended_action", "-"))),
            ("task_id", task_link),
            ("topic_ids", escape(", ".join(opportunity.get("topic_ids", [])) if isinstance(opportunity.get("topic_ids"), list) else "-")),
            ("evidence_count", escape(opportunity.get("evidence_count", 0))),
            ("evidence_domain_diversity", escape(opportunity.get("evidence_domain_diversity", 0))),
            ("has_official_source", escape(opportunity.get("has_official_source", False))),
            ("summary", escape(opportunity.get("summary", ""))),
            ("evidence", evidence_links(config, evidence)),
        ],
    )
    actions = ""
    if opportunity.get("status") == "ready_review":
        actions = f"""
        <div class="panel">
          <h2>快捷操作</h2>
          <div class="actions">
            <form class="inline" method="post" action="/actions/promote-opportunity">
              <input type="hidden" name="opportunity_id" value="{escape(opportunity.get('opportunity_id', ''))}">
              <input type="hidden" name="next" value="/opportunity?id={escape(opportunity.get('opportunity_id', ''))}">
              <button type="submit">晋升为正式任务</button>
            </form>
          </div>
        </div>
        """
    body = details + actions
    return layout(f"Opportunity {opportunity.get('opportunity_id', '-')}", body, "/opportunities", message)


def render_file_detail(config: AppConfig, path: Path, message: str) -> bytes:
    content = path.read_text(encoding="utf-8", errors="replace")
    body = f"""
    <div class="panel">
      <h2>文件</h2>
      <div class="muted"><code>{escape(str(path))}</code></div>
      <pre style="white-space:pre-wrap;overflow:auto;margin-top:12px;">{escape(content)}</pre>
    </div>
    """
    return layout(f"File {format_path(path, [config.openclaw_home, config.repo_root])}", body, "", message)


def render_job_trigger(state: dict, job_name: str, next_path: str) -> str:
    job = next((item for item in state["cron_jobs"] if item["name"] == job_name), None)
    if job is None:
        return ""
    return (
        "<form class=\"inline\" method=\"post\" action=\"/actions/run-cron\">"
        f"<input type=\"hidden\" name=\"job_id\" value=\"{escape(job['id'])}\">"
        f"<input type=\"hidden\" name=\"next\" value=\"{escape(next_path)}\">"
        f"<button type=\"submit\">{escape(job_name)}</button>"
        "</form>"
    )


def json_response(handler: BaseHTTPRequestHandler, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler: BaseHTTPRequestHandler, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def redirect_with_message(handler: BaseHTTPRequestHandler, location: str, message: str) -> None:
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    if message:
        query["message"] = [message]
    target = parsed._replace(query=urlencode(query, doseq=True)).geturl()
    handler.send_response(HTTPStatus.SEE_OTHER)
    handler.send_header("Location", target)
    handler.end_headers()


def build_handler(config: AppConfig):
    class ControlPlaneHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            message = query.get("message", [""])[0]
            state = build_state(config)
            state["query"] = query

            if parsed.path == "/":
                html_response(self, render_summary(state, message))
                return
            if parsed.path == "/tasks":
                html_response(self, render_tasks(state, message))
                return
            if parsed.path == "/task":
                task_id = query.get("id", [""])[0]
                task = find_task(state["tasks"], task_id)
                if task is None:
                    json_response(self, {"ok": False, "error": "task not found"}, HTTPStatus.NOT_FOUND)
                    return
                html_response(self, render_task_detail(state, task, message))
                return
            if parsed.path == "/opportunities":
                html_response(self, render_opportunities(state, message))
                return
            if parsed.path == "/kpi":
                html_response(self, render_kpi(state, message))
                return
            if parsed.path == "/kpi/agent":
                agent_id = query.get("id", [""])[0]
                period = query.get("period", ["daily"])[0]
                html_response(self, render_kpi_agent(state, agent_id, period, message))
                return
            if parsed.path == "/events":
                html_response(self, render_events(state, message))
                return
            if parsed.path == "/opportunity":
                opportunity_id = query.get("id", [""])[0]
                opportunity = find_opportunity(state["opportunities"], opportunity_id)
                if opportunity is None:
                    json_response(self, {"ok": False, "error": "opportunity not found"}, HTTPStatus.NOT_FOUND)
                    return
                html_response(self, render_opportunity_detail(state, opportunity, message))
                return
            if parsed.path == "/handoffs":
                html_response(self, render_handoffs(state, message))
                return
            if parsed.path == "/agents":
                html_response(self, render_agents(state, message))
                return
            if parsed.path == "/cron":
                html_response(self, render_cron(state, message))
                return
            if parsed.path == "/logs":
                html_response(self, render_logs(state, message))
                return
            if parsed.path == "/file":
                raw_path = query.get("path", [""])[0]
                path = resolve_viewable_path(config, raw_path)
                if path is None:
                    json_response(self, {"ok": False, "error": "file not found or not allowed"}, HTTPStatus.NOT_FOUND)
                    return
                html_response(self, render_file_detail(config, path, message))
                return
            if parsed.path == "/api/summary":
                payload = {
                    "runtime_ready": state.get("runtime_ready", False),
                    "runtime_source": state.get("runtime_source", "-"),
                    "active_tasks": len(state["active_tasks"]),
                    "blocked_tasks": len(state["blocked_tasks"]),
                    "stale_active_tasks": len(state["stale_active_tasks"]),
                    "ready_review": state["opportunity_counts"].get("ready_review", 0),
                    "candidate": state["opportunity_counts"].get("candidate", 0),
                    "running_jobs": len(state["running_jobs"]),
                    "never_run_jobs": len(state["never_run_jobs"]),
                }
                json_response(self, payload)
                return
            if parsed.path == "/api/tasks":
                json_response(self, state["tasks"])
                return
            if parsed.path == "/api/task":
                task_id = query.get("id", [""])[0]
                task = find_task(state["tasks"], task_id)
                if task is None:
                    json_response(self, {"ok": False, "error": "task not found"}, HTTPStatus.NOT_FOUND)
                    return
                json_response(self, task)
                return
            if parsed.path == "/api/opportunities":
                json_response(self, state["opportunities"])
                return
            if parsed.path == "/api/opportunity":
                opportunity_id = query.get("id", [""])[0]
                opportunity = find_opportunity(state["opportunities"], opportunity_id)
                if opportunity is None:
                    json_response(self, {"ok": False, "error": "opportunity not found"}, HTTPStatus.NOT_FOUND)
                    return
                json_response(self, opportunity)
                return
            if parsed.path == "/api/agents":
                payload = [
                    {
                        "agent_id": item["agent_id"],
                        "name": agent_name(item["agent_id"]),
                        "title": agent_title(item["agent_id"]),
                        "count": item["sessions"],
                        "active_task_count": len(item["active_tasks"]),
                        "running_jobs": item["running_jobs"],
                        "failed_jobs": item["failed_jobs"],
                        "health": agent_health(item)[1],
                        "last_activity": item["last_activity"].isoformat() if item["last_activity"] else None,
                    }
                    for item in state["agent_stats"].values()
                ]
                json_response(self, payload)
                return
            if parsed.path == "/api/kpi":
                payload = {
                    "daily": {
                        "path": str(state["kpi"]["daily_path"]) if state["kpi"]["daily_path"] else None,
                        "report": state["kpi"]["daily_report"],
                    },
                    "weekly": {
                        "path": str(state["kpi"]["weekly_path"]) if state["kpi"]["weekly_path"] else None,
                        "report": state["kpi"]["weekly_report"],
                    },
                }
                json_response(self, payload)
                return
            if parsed.path == "/api/kpi/agent":
                agent_id = query.get("id", [""])[0]
                period = query.get("period", ["daily"])[0]
                report = state["kpi"]["daily_report"] if period == "daily" else state["kpi"]["weekly_report"]
                scorecard = find_kpi_scorecard(report, agent_id)
                if scorecard is None:
                    json_response(self, {"ok": False, "error": "kpi scorecard not found"}, HTTPStatus.NOT_FOUND)
                    return
                json_response(self, scorecard)
                return
            if parsed.path == "/api/events":
                payload = [
                    {
                        "when": item["when"].isoformat(),
                        "kind": item["kind"],
                        "actor": item["actor"],
                        "task_id": item["task_id"],
                        "summary": item["summary"],
                        "path": str(item["path"]),
                    }
                    for item in state["events"]
                ]
                json_response(self, payload)
                return
            if parsed.path == "/api/alerts":
                json_response(self, state["alerts"])
                return
            if parsed.path == "/api/cron":
                payload = [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "agent_id": item["agent_id"],
                        "enabled": item["enabled"],
                        "last_run_status": item["last_run_status"],
                        "last_run_at": item["last_run_at"].isoformat() if item["last_run_at"] else None,
                        "next_run_at": item["next_run_at"].isoformat() if item["next_run_at"] else None,
                        "running": item["running"],
                        "consecutive_errors": item["consecutive_errors"],
                    }
                    for item in state["cron_jobs"]
                ]
                json_response(self, payload)
                return
            json_response(self, {"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            form = parse_qs(body)
            next_location = form.get("next", ["/"])[0]

            if parsed.path == "/actions/refresh-dashboard":
                result = run_command(config.refresh_dashboard_command())
                invalidate_command_cache()
                invalidate_state_cache()
                message = "dashboard refreshed" if result["ok"] else f"refresh failed: {result['stderr'] or result['stdout']}"
                redirect_with_message(self, next_location, str(message))
                return

            if parsed.path == "/actions/run-cron":
                job_id = form.get("job_id", [""])[0]
                if job_id == "":
                    redirect_with_message(self, next_location, "missing cron job id")
                    return
                subprocess.Popen(
                    ["openclaw", "cron", "run", job_id, "--timeout", "5000"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                invalidate_command_cache("openclaw-cron-list")
                invalidate_state_cache()
                message = f"cron requested: {job_id}"
                redirect_with_message(self, next_location, message)
                return

            if parsed.path == "/actions/promote-opportunity":
                opportunity_id = form.get("opportunity_id", [""])[0]
                if opportunity_id == "":
                    redirect_with_message(self, next_location, "missing opportunity id")
                    return
                script_path = config.captain_workspace / "scripts/bridge_ready_review_opportunity.py"
                result = run_command(
                    [
                        "python3",
                        str(script_path),
                        "--opportunities-path",
                        str(config.opportunities_path),
                        "--task-registry-path",
                        str(config.registry_path),
                        "--handoff-dir",
                        str(config.handoffs_dir),
                        "--task-owner",
                        "aic-planner",
                        "--task-state",
                        "Intake",
                        "--opportunity-id",
                        opportunity_id,
                        "--format",
                        "json",
                    ]
                )
                invalidate_command_cache()
                invalidate_state_cache()
                message = result["stdout"] or result["stderr"] or f"opportunity promoted: {opportunity_id}"
                redirect_with_message(self, next_location, str(message))
                return

            if parsed.path == "/actions/update-task":
                task_id = form.get("task_id", [""])[0]
                if task_id == "":
                    redirect_with_message(self, next_location, "missing task id")
                    return
                script_path = config.captain_workspace / "scripts/update_task_registry.py"
                command = ["python3", str(script_path), "--path", str(config.registry_path), "--task-id", task_id]

                state_value = form.get("state", [""])[0].strip()
                owner_value = form.get("owner", [""])[0].strip()
                priority_value = form.get("priority", [""])[0].strip()
                next_step_value = form.get("next_step", [""])[0].strip()
                blocker_value = form.get("blocker", [""])[0].strip()
                note_value = form.get("note", [""])[0].strip()

                if state_value:
                    command.extend(["--state", state_value])
                if owner_value:
                    command.extend(["--owner", owner_value])
                if priority_value:
                    command.extend(["--priority", priority_value])
                if next_step_value:
                    command.extend(["--next-step", next_step_value])
                if "clear_blocker" in form:
                    command.append("--clear-blocker")
                elif blocker_value:
                    command.extend(["--blocker", blocker_value])
                if note_value:
                    command.extend(["--notes", note_value])

                result = run_command(command)
                if result["ok"]:
                    run_command(config.refresh_dashboard_command())
                invalidate_command_cache()
                invalidate_state_cache()
                message = result["stdout"] or result["stderr"] or f"task updated: {task_id}"
                redirect_with_message(self, next_location, str(message))
                return

            json_response(self, {"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return ControlPlaneHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight local web control plane for the OpenClaw coding team.")
    parser.add_argument("--openclaw-home", default="~/.openclaw")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    config = AppConfig(
        openclaw_home=Path(args.openclaw_home).expanduser(),
        host=args.host,
        port=args.port,
    )

    refresh_state_cache(config)
    threading.Thread(target=prewarm_loop, args=(config,), daemon=True).start()
    server = ThreadingHTTPServer((config.host, config.port), build_handler(config))
    print(f"control-plane listening on http://{config.host}:{config.port}")
    print(f"openclaw_home={config.openclaw_home}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

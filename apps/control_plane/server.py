#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import subprocess
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
}


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
    def skills_root(self) -> Path:
        return self.researcher_workspace / "data/skills"

    @property
    def sessions_root(self) -> Path:
        return self.openclaw_home / "agents"

    @property
    def captain_exec_logs(self) -> Path:
        return self.captain_workspace / "data/exec-logs"

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


def load_json(path: Path, fallback: dict | list) -> dict | list:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def run_json_command(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"ok": False, "command": command, "stderr": result.stderr.strip(), "stdout": result.stdout.strip()}
    return json.loads(result.stdout)


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
    payload = run_json_command(["openclaw", "status", "--deep", "--json"])
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
    payload = run_json_command(["openclaw", "cron", "list", "--json"])
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
        for line in lines:
            if line.startswith("发送方: "):
                sender = line.split(": ", 1)[1]
            elif line.startswith("任务ID: "):
                task_id = line.split(": ", 1)[1]
            elif line.startswith("当前阶段: "):
                current_stage = line.split(": ", 1)[1]
        rows.append(
            {
                "path": path,
                "task_id": task_id,
                "sender": sender,
                "current_stage": current_stage,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
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


def build_state(config: AppConfig) -> dict:
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
    return {
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
    }


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
        ("Agents", "/agents"),
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
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    @media (max-width: 980px) {{
      .two, .three {{ grid-template-columns: 1fr; }}
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
    active_tasks = state["active_tasks"]
    blocked_tasks = state["blocked_tasks"]
    stale_active_tasks = state["stale_active_tasks"]
    ready_review = state["opportunity_counts"].get("ready_review", 0)
    candidates = state["opportunity_counts"].get("candidate", 0)
    running_jobs = state["running_jobs"]
    never_run_core = [job for job in state["never_run_jobs"] if job["name"] in CORE_JOB_NAMES]
    active_agents = [item for item in state["agents"] if item["count"] > 0]

    cards = "".join(
        [
            card("活跃任务", str(len(active_tasks)), "正式任务控制面"),
            card("阻塞任务", str(len(blocked_tasks)), "以 registry 为准"),
            card("陈旧活跃任务", str(len(stale_active_tasks)), "超过 6 小时未更新"),
            card("Ready Review 机会", str(ready_review), "可晋升正式任务"),
            card("候选机会", str(candidates), "研究池"),
            card("运行中的 Jobs", str(len(running_jobs)), "来自 openclaw cron"),
            card("未自然跑过核心 Jobs", str(len(never_run_core)), "需要区分未到时间和未触发"),
            card("活跃 Agents", str(len(active_agents)), "最近有 session"),
        ]
    )

    summary_rows = []
    for task in active_tasks[:10]:
        updated_at = parse_iso(task.get("updated_at"))
        summary_rows.append(
            [
                escape(task["task_id"]),
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
                escape(item.get("opportunity_id", "-")),
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
        relative = item["path"].relative_to(config.openclaw_home)
        log_rows.append(
            [
                escape(item["agent_id"]),
                escape(item["job_name"]),
                escape(format_dt(item["updated_at"])),
                f"<code>{escape(relative)}</code>",
            ]
        )

    quick_actions = f"""
    <div class="panel">
      <h2>快捷操作</h2>
      <div class="actions">
        <form class="inline" method="post" action="/actions/refresh-dashboard">
          <input type="hidden" name="next" value="/">
          <button type="submit">刷新 Captain 看板</button>
        </form>
      </div>
      <div class="hint">默认只绑定本机地址。若要公网访问，建议放到反向代理和鉴权后面。</div>
    </div>
    """

    body = f"""
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
    rows = []
    for task in state["tasks"]:
        updated_at = parse_iso(task.get("updated_at"))
        evidence = task.get("evidence_pointer", [])
        evidence_count = len(evidence) if isinstance(evidence, list) else 0
        rows.append(
            [
                escape(task["task_id"]),
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
    body = f"<div class=\"panel\"><h2>任务控制面</h2>{table(['Task', 'Title', 'State', 'Owner', 'Priority', 'Updated', 'Blocker', 'Next Step', 'Evidence'], rows)}</div>"
    return layout("Tasks", body, "/tasks", message)


def render_opportunities(state: dict, message: str) -> bytes:
    rows = []
    for item in state["opportunities"][:50]:
        topic_ids = item.get("topic_ids", [])
        topic_text = ", ".join(topic_ids) if isinstance(topic_ids, list) and topic_ids else "-"
        rows.append(
            [
                escape(item.get("opportunity_id", "-")),
                f"<span class=\"pill\">{escape(item.get('status', '-'))}</span>",
                escape(item.get("score", "-")),
                escape(item.get("recommended_action", "-")),
                escape(topic_text),
                escape(item.get("evidence_count", 0)),
                escape(item.get("evidence_domain_diversity", 0)),
                escape(item.get("task_id") or "-"),
                escape(item.get("summary", "")),
            ]
        )
    body = f"<div class=\"panel\"><h2>机会池</h2>{table(['Opportunity', 'Status', 'Score', 'Action', 'Topics', 'Evidence', 'Domains', 'Task', 'Summary'], rows)}</div>"
    return layout("Opportunities", body, "/opportunities", message)


def render_agents(state: dict, message: str) -> bytes:
    rows = []
    for item in state["agents"]:
        rows.append(
            [
                escape(item["agent_id"]),
                escape(item["count"]),
                escape(format_dt(item["last_activity"])),
                escape(format_age(item["last_activity"])),
            ]
        )
    body = f"<div class=\"panel\"><h2>Agent 活动</h2>{table(['Agent', 'Sessions', 'Last Activity', 'Age'], rows)}</div>"
    return layout("Agents", body, "/agents", message)


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
                f"<code>{escape(item['path'].relative_to(config.openclaw_home))}</code>",
            ]
        )
    body = f"<div class=\"panel\"><h2>最新执行日志</h2>{table(['Agent', 'Job', 'Updated', 'Path'], rows)}</div>"
    return layout("Logs", body, "/logs", message)


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

            if parsed.path == "/":
                html_response(self, render_summary(state, message))
                return
            if parsed.path == "/tasks":
                html_response(self, render_tasks(state, message))
                return
            if parsed.path == "/opportunities":
                html_response(self, render_opportunities(state, message))
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
            if parsed.path == "/api/summary":
                payload = {
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
            if parsed.path == "/api/opportunities":
                json_response(self, state["opportunities"])
                return
            if parsed.path == "/api/agents":
                payload = [
                    {
                        "agent_id": item["agent_id"],
                        "count": item["count"],
                        "last_activity": item["last_activity"].isoformat() if item["last_activity"] else None,
                    }
                    for item in state["agents"]
                ]
                json_response(self, payload)
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
                message = f"cron requested: {job_id}"
                redirect_with_message(self, next_location, message)
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

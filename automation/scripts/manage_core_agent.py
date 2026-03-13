#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


CORE_SCRIPT_NAMES = [
    "scan_sessions_incremental.py",
    "lockfile.py",
    "weekly_gate.py",
]
CORE_EXEC_LOG_DIRS = [
    "memory-hourly",
    "daily-reflection",
    "daily-curation",
    "memory-weekly",
]


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def split_csv(values: list[str]) -> list[str]:
    result: list[str] = []
    for raw in values:
        for item in raw.split(","):
            value = item.strip()
            if value:
                result.append(value)
    return result


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            deep_merge(current, value)
            continue
        target[key] = value


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_workspace(openclaw_home: Path, agent_id: str) -> Path:
    if agent_id == "main":
        return openclaw_home / "workspace"
    return openclaw_home / f"workspace-{agent_id}"


def default_agent_dir(openclaw_home: Path, agent_id: str) -> Path:
    return openclaw_home / "agents" / agent_id


def find_agent(config: dict[str, Any], agent_id: str) -> dict[str, Any] | None:
    agents = config.setdefault("agents", {}).setdefault("list", [])
    for item in agents:
        if isinstance(item, dict) and item.get("id") == agent_id:
            return item
    return None


def ensure_agent(
    config: dict[str, Any],
    openclaw_home: Path,
    agent_id: str,
    create_if_missing: bool,
    heartbeat_every: str,
) -> dict[str, Any]:
    entry = find_agent(config, agent_id)
    if entry is None and not create_if_missing:
        raise SystemExit(f"agent not found in openclaw.json: {agent_id}")
    if entry is None:
        entry = {
            "id": agent_id,
            "workspace": str(default_workspace(openclaw_home, agent_id)),
            "agentDir": str(default_agent_dir(openclaw_home, agent_id)),
            "subagents": {"allowAgents": []},
        }
        if heartbeat_every:
            entry["heartbeat"] = {"every": heartbeat_every, "target": "last"}
        config.setdefault("agents", {}).setdefault("list", []).append(entry)
    entry["workspace"] = str(Path(entry.get("workspace") or default_workspace(openclaw_home, agent_id)).expanduser().resolve())
    entry["agentDir"] = str(Path(entry.get("agentDir") or default_agent_dir(openclaw_home, agent_id)).expanduser().resolve())
    subagents = entry.get("subagents")
    if not isinstance(subagents, dict):
        subagents = {}
        entry["subagents"] = subagents
    allow_agents = subagents.get("allowAgents")
    if not isinstance(allow_agents, list):
        subagents["allowAgents"] = []
    return entry


def ensure_allow_agent(config: dict[str, Any], caller_id: str, callee_id: str) -> None:
    caller = find_agent(config, caller_id)
    if caller is None:
        raise SystemExit(f"caller agent not found in openclaw.json: {caller_id}")
    subagents = caller.get("subagents")
    if not isinstance(subagents, dict):
        subagents = {}
        caller["subagents"] = subagents
    allow_agents = subagents.get("allowAgents")
    if not isinstance(allow_agents, list):
        allow_agents = []
        subagents["allowAgents"] = allow_agents
    if callee_id not in allow_agents:
        allow_agents.append(callee_id)


def merge_managed_block(path: Path, marker: str, content: str, dry_run: bool) -> None:
    if not path.exists():
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:]).lstrip()
    start_marker = f"<!-- OPENCLAW-CORE:{marker}:BEGIN -->"
    end_marker = f"<!-- OPENCLAW-CORE:{marker}:END -->"
    original = path.read_text(encoding="utf-8")
    block = f"{start_marker}\n{content.rstrip()}\n{end_marker}\n"
    if start_marker in original and end_marker in original:
        before = original.split(start_marker, 1)[0].rstrip()
        after = original.split(end_marker, 1)[1].lstrip()
        merged = before + "\n\n" + block
        if after:
            merged += "\n" + after
    else:
        merged = original.rstrip() + "\n\n" + block if original.strip() else block
    if not dry_run:
        path.write_text(merged.rstrip() + "\n", encoding="utf-8")


def sync_missing_tree(source: Path, target: Path, dry_run: bool) -> None:
    if source.is_file():
        if target.exists() or dry_run:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            if not dry_run:
                destination.mkdir(parents=True, exist_ok=True)
            continue
        if destination.exists() or dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def render_template(path: Path, replacements: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def ensure_today_daily_log(workspace: Path, repo: Path, dry_run: bool) -> None:
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    daily_path = workspace / "memory" / f"{today}.md"
    if daily_path.exists():
        return
    template_path = repo / "templates/common/memory/daily/TEMPLATE.md"
    weekday = datetime.now().astimezone().strftime("%A")
    content = template_path.read_text(encoding="utf-8").replace("YYYY-MM-DD", today).replace("(Day)", f"({weekday})")
    if not dry_run:
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        daily_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def update_tools_core_section(path: Path, dry_run: bool) -> None:
    if not path.exists() or dry_run:
        return
    original = path.read_text(encoding="utf-8")
    start_marker = "<!-- OPENCLAW-CORE-TOOLS:BEGIN -->"
    end_marker = "<!-- OPENCLAW-CORE-TOOLS:END -->"
    block = "\n".join(
        [
            start_marker,
            "## Core Runtime Scripts",
            "",
            "- `scripts/scan_sessions_incremental.py`：enabled",
            "- `scripts/lockfile.py`：enabled",
            "- `scripts/weekly_gate.py`：enabled",
            "",
            "## Core Profile Layout",
            "",
            "- `MEMORY.md`",
            "- `memory/`",
            "- `data/knowledge-proposals/`",
            "- `data/exec-logs/`",
            "- `data/core-profile.json`",
            end_marker,
            "",
        ]
    )
    if start_marker in original and end_marker in original:
        before = original.split(start_marker, 1)[0].rstrip()
        after = original.split(end_marker, 1)[1].lstrip()
        merged = before + "\n\n" + block
        if after:
            merged += "\n" + after
    else:
        merged = original.rstrip() + "\n\n" + block if original.strip() else block
    path.write_text(merged.rstrip() + "\n", encoding="utf-8")


def prime_qmd(repo: Path, agent_id: str, workspace: Path, agent_dir: Path, embed: bool, dry_run: bool) -> str:
    if shutil.which("qmd") is None:
        return "qmd not found; skipped"
    primer = repo / "setup/prime_qmd_memory.py"
    command = [
        "python3",
        str(primer),
        "--agent-id",
        agent_id,
        "--workspace",
        str(workspace),
        "--agent-dir",
        str(agent_dir),
        "--profile",
        "core",
    ]
    if embed:
        command.append("--embed")
    if dry_run:
        command.append("--dry-run")
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        return "qmd dry-run prepared with embed" if embed else "qmd dry-run prepared"
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    return "qmd primed with embed" if embed else "qmd primed"


def render_prompt(prompt_path: Path, agent_id: str, timezone: str, openclaw_home: Path) -> str:
    text = prompt_path.read_text(encoding="utf-8")
    return text.replace("__AGENT_ID__", agent_id).replace("__TIMEZONE__", timezone).replace("__OPENCLAW_HOME__", str(openclaw_home))


def job_ids_by_name(job_name: str) -> list[str]:
    result = subprocess.run(["openclaw", "cron", "list", "--json"], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    ids: list[str] = []
    for job in payload.get("jobs", []):
        if isinstance(job, dict) and job.get("name") == job_name and job.get("id"):
            ids.append(str(job["id"]))
    return ids


def remove_existing_jobs(job_names: list[str], dry_run: bool) -> None:
    for job_name in job_names:
        for job_id in job_ids_by_name(job_name):
            if dry_run:
                continue
            subprocess.run(["openclaw", "cron", "remove", job_id], check=True, stdout=subprocess.DEVNULL)


def install_interval_job(name: str, agent_id: str, every: str, prompt_path: Path, description: str, timezone: str, openclaw_home: Path, dry_run: bool) -> None:
    message = render_prompt(prompt_path, agent_id, timezone, openclaw_home)
    remove_existing_jobs([name], dry_run)
    if dry_run:
        return
    subprocess.run(
        [
            "openclaw",
            "cron",
            "add",
            "--name",
            name,
            "--description",
            description,
            "--agent",
            agent_id,
            "--session",
            "isolated",
            "--light-context",
            "--no-deliver",
            "--timeout-seconds",
            "1800",
            "--every",
            every,
            "--message",
            message,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def install_daily_job(name: str, agent_id: str, cron_expr: str, prompt_path: Path, description: str, timezone: str, openclaw_home: Path, dry_run: bool) -> None:
    message = render_prompt(prompt_path, agent_id, timezone, openclaw_home)
    remove_existing_jobs([name], dry_run)
    if dry_run:
        return
    subprocess.run(
        [
            "openclaw",
            "cron",
            "add",
            "--name",
            name,
            "--description",
            description,
            "--agent",
            agent_id,
            "--session",
            "isolated",
            "--light-context",
            "--no-deliver",
            "--timeout-seconds",
            "1800",
            "--cron",
            cron_expr,
            "--tz",
            timezone,
            "--exact",
            "--message",
            message,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def install_core_jobs(
    repo: Path,
    agent_id: str,
    openclaw_home: Path,
    timezone: str,
    memory_hourly_every: str,
    daily_reflection_cron: str,
    daily_curation_cron: str,
    memory_weekly_cron: str,
    dry_run: bool,
) -> list[str]:
    if shutil.which("openclaw") is None:
        raise SystemExit("openclaw command not found; cannot install core cron jobs")
    prompt_root = repo / "automation/core-prompts"
    installed = [
        f"core-memory-hourly-{agent_id}",
        f"core-daily-reflection-{agent_id}",
        f"core-daily-curation-{agent_id}",
        f"core-memory-weekly-{agent_id}",
    ]
    install_interval_job(
        installed[0],
        agent_id,
        memory_hourly_every,
        prompt_root / "memory-hourly.md",
        f"Core memory-hourly sync for {agent_id}.",
        timezone,
        openclaw_home,
        dry_run,
    )
    install_daily_job(
        installed[1],
        agent_id,
        daily_reflection_cron,
        prompt_root / "daily-reflection.md",
        f"Daily reflection for {agent_id}.",
        timezone,
        openclaw_home,
        dry_run,
    )
    install_daily_job(
        installed[2],
        agent_id,
        daily_curation_cron,
        prompt_root / "daily-curation.md",
        f"Daily knowledge curation for {agent_id}.",
        timezone,
        openclaw_home,
        dry_run,
    )
    install_daily_job(
        installed[3],
        agent_id,
        memory_weekly_cron,
        prompt_root / "memory-weekly.md",
        f"Weekly memory consolidation for {agent_id}.",
        timezone,
        openclaw_home,
        dry_run,
    )
    return installed


def ensure_core_workspace(
    repo: Path,
    workspace: Path,
    agent_dir: Path,
    agent_id: str,
    role_name: str,
    role_title: str,
    mission: str,
    dry_run: bool,
    write_identity: bool,
) -> None:
    if not dry_run:
        workspace.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)
    sync_missing_tree(repo / "templates/common/memory", workspace / "memory", dry_run)
    sync_missing_tree(repo / "templates/common/data/knowledge-proposals", workspace / "data" / "knowledge-proposals", dry_run)
    for job_name in CORE_EXEC_LOG_DIRS:
        if not dry_run:
            (workspace / "data" / "exec-logs" / job_name).mkdir(parents=True, exist_ok=True)
    merge_managed_block(workspace / "AGENTS.md", "profile", (repo / "templates/core-profile/AGENTS.md").read_text(encoding="utf-8"), dry_run)
    merge_managed_block(workspace / "TOOLS.md", "profile", (repo / "templates/core-profile/TOOLS.md").read_text(encoding="utf-8"), dry_run)
    update_tools_core_section(workspace / "TOOLS.md", dry_run)
    if not (workspace / "BOOT.md").exists() and not dry_run:
        shutil.copy2(repo / "templates/core-profile/BOOT.md", workspace / "BOOT.md")
    if not (workspace / "MEMORY.md").exists() and not dry_run:
        shutil.copy2(repo / "templates/core-profile/MEMORY.md", workspace / "MEMORY.md")
    if not (workspace / "scripts" / "README.md").exists() and not dry_run:
        (workspace / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / "templates/core-profile/scripts/README.md", workspace / "scripts" / "README.md")
    if not dry_run:
        (workspace / "scripts").mkdir(parents=True, exist_ok=True)
        for script_name in CORE_SCRIPT_NAMES:
            shutil.copy2(repo / "automation/scripts" / script_name, workspace / "scripts" / script_name)
    if write_identity:
        identity = render_template(
            repo / "templates/core-profile/agent/IDENTITY.md.tmpl",
            {"role_name": role_name, "role_title": role_title, "mission": mission},
        )
        soul = render_template(
            repo / "templates/core-profile/agent/SOUL.md.tmpl",
            {
                "agent_id": agent_id,
                "role_name": role_name,
                "role_title": role_title,
                "mission": mission,
            },
        )
        if not dry_run:
            (workspace / "IDENTITY.md").write_text(identity.rstrip() + "\n", encoding="utf-8")
            (workspace / "SOUL.md").write_text(soul.rstrip() + "\n", encoding="utf-8")
    ensure_today_daily_log(workspace, repo, dry_run)


def update_core_profile_metadata(
    workspace: Path,
    agent_id: str,
    role_name: str,
    role_title: str,
    mission: str,
    qmd_status: str,
    job_names: list[str],
    dry_run: bool,
) -> None:
    payload = {
        "profile": "agent-core",
        "agent_id": agent_id,
        "role_name": role_name,
        "role_title": role_title,
        "mission": mission,
        "features": ["memory", "knowledge-structure", "daily-reflection", "qmd-search"],
        "qmd": qmd_status,
        "cron_jobs": job_names,
        "updated_at": now_iso(),
    }
    if not dry_run:
        write_json(workspace / "data" / "core-profile.json", payload)


def configure_core(
    agent_id: str,
    role_name: str,
    role_title: str,
    mission: str,
    accepted_from: list[str],
    allow_call: list[str],
    heartbeat_every: str,
    create_if_missing: bool,
    openclaw_home: Path,
    config_path: Path,
    timezone: str,
    skip_jobs: bool,
    skip_qmd_init: bool,
    qmd_embed: bool,
    memory_hourly_every: str,
    daily_reflection_cron: str,
    daily_curation_cron: str,
    memory_weekly_cron: str,
    dry_run: bool,
) -> dict[str, Any]:
    repo = repo_root()
    config = load_json(config_path, {"agents": {"defaults": {}, "list": []}})
    defaults = config.setdefault("agents", {}).setdefault("defaults", {})
    defaults["skipBootstrap"] = True
    defaults["userTimezone"] = timezone
    memory_snippet = json.loads((repo / "config/openclaw.memory.core.qmd.snippet.json").read_text(encoding="utf-8"))
    memory_root = memory_snippet.get("memory")
    if isinstance(memory_root, dict):
        existing_memory = config.get("memory")
        if not isinstance(existing_memory, dict):
            existing_memory = {}
        deep_merge(existing_memory, memory_root)
        config["memory"] = existing_memory

    entry = ensure_agent(config, openclaw_home, agent_id, create_if_missing, heartbeat_every)
    workspace = Path(entry["workspace"]).expanduser().resolve()
    agent_dir = Path(entry["agentDir"]).expanduser().resolve()
    for caller in accepted_from:
        if caller == agent_id:
            continue
        ensure_allow_agent(config, caller, agent_id)
    if allow_call:
        entry["subagents"]["allowAgents"] = allow_call
    ensure_core_workspace(repo, workspace, agent_dir, agent_id, role_name, role_title, mission, dry_run, create_if_missing or not (workspace / "SOUL.md").exists())
    qmd_status = "qmd skipped"
    if not skip_qmd_init:
        qmd_status = prime_qmd(repo, agent_id, workspace, agent_dir, qmd_embed, dry_run)
    job_names: list[str] = []
    if not skip_jobs:
        job_names = install_core_jobs(
            repo,
            agent_id,
            openclaw_home,
            timezone,
            memory_hourly_every,
            daily_reflection_cron,
            daily_curation_cron,
            memory_weekly_cron,
            dry_run,
        )
    update_core_profile_metadata(workspace, agent_id, role_name, role_title, mission, qmd_status, job_names, dry_run)
    if not dry_run:
        write_json(config_path, config)
    return {
        "agent_id": agent_id,
        "workspace": str(workspace),
        "agentDir": str(agent_dir),
        "role_name": role_name,
        "role_title": role_title,
        "mission": mission,
        "qmd": qmd_status,
        "cron_jobs": job_names,
        "created": create_if_missing,
    }


def render_md(result: dict[str, Any]) -> str:
    lines = [
        f"- agent_id: {result['agent_id']}",
        f"- workspace: {result['workspace']}",
        f"- agentDir: {result['agentDir']}",
        f"- role_name: {result['role_name']}",
        f"- role_title: {result['role_title']}",
        f"- qmd: {result['qmd']}",
    ]
    if result["cron_jobs"]:
        lines.append(f"- cron_jobs: {', '.join(result['cron_jobs'])}")
    else:
        lines.append("- cron_jobs: skipped")
    return "\n".join(lines)


def default_role_name(agent_id: str) -> str:
    if agent_id == "main":
        return "主助理"
    return agent_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or create a minimal core profile for an OpenClaw agent.")
    parser.add_argument("--openclaw-home", default=str(Path.home() / ".openclaw"))
    parser.add_argument("--config-path", default="")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--skip-jobs", action="store_true")
    parser.add_argument("--skip-qmd-init", action="store_true")
    parser.add_argument("--qmd-embed", action="store_true")
    parser.add_argument("--memory-hourly-every", default="1h")
    parser.add_argument("--daily-reflection-cron", default="10 0 * * *")
    parser.add_argument("--daily-curation-cron", default="20 0 * * *")
    parser.add_argument("--memory-weekly-cron", default="40 0 * * *")
    parser.add_argument("--format", choices=["md", "json"], default=None, dest="global_format")
    parser.add_argument("--dry-run", action="store_true", dest="global_dry_run")

    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--agent-id", default="main")
    apply_parser.add_argument("--role-name", default="")
    apply_parser.add_argument("--role-title", default="核心助理")
    apply_parser.add_argument("--mission", default="围绕用户目标稳定积累记忆、整理知识并执行每日反思。")
    apply_parser.add_argument("--accepted-from", action="append", default=["main"])
    apply_parser.add_argument("--allow-call", action="append", default=[])
    apply_parser.add_argument("--format", choices=["md", "json"], default=None)
    apply_parser.add_argument("--dry-run", action="store_true")

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--agent-id", required=True)
    create_parser.add_argument("--role-name", default="")
    create_parser.add_argument("--role-title", default="核心助理")
    create_parser.add_argument("--mission", default="围绕用户目标稳定积累记忆、整理知识并执行每日反思。")
    create_parser.add_argument("--accepted-from", action="append", default=["main"])
    create_parser.add_argument("--allow-call", action="append", default=[])
    create_parser.add_argument("--heartbeat-every", default="")
    create_parser.add_argument("--format", choices=["md", "json"], default=None)
    create_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    openclaw_home = Path(args.openclaw_home).expanduser().resolve()
    config_path = Path(args.config_path or openclaw_home / "openclaw.json").expanduser().resolve()
    role_name = args.role_name or default_role_name(args.agent_id)
    accepted_from = split_csv(args.accepted_from)
    allow_call = split_csv(args.allow_call)
    heartbeat_every = getattr(args, "heartbeat_every", "")
    dry_run = bool(args.global_dry_run or args.dry_run)
    result = configure_core(
        agent_id=args.agent_id,
        role_name=role_name,
        role_title=args.role_title,
        mission=args.mission,
        accepted_from=accepted_from,
        allow_call=allow_call,
        heartbeat_every=heartbeat_every,
        create_if_missing=args.command == "create",
        openclaw_home=openclaw_home,
        config_path=config_path,
        timezone=args.timezone,
        skip_jobs=args.skip_jobs,
        skip_qmd_init=args.skip_qmd_init,
        qmd_embed=args.qmd_embed,
        memory_hourly_every=args.memory_hourly_every,
        daily_reflection_cron=args.daily_reflection_cron,
        daily_curation_cron=args.daily_curation_cron,
        memory_weekly_cron=args.memory_weekly_cron,
        dry_run=dry_run,
    )
    output_format = args.format or args.global_format or "md"
    if output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_md(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

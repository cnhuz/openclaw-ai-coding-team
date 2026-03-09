#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


CORE_EXEC_LOG_JOBS = [
    "dashboard-refresh",
    "ambient-discovery",
    "signal-triage",
    "opportunity-deep-dive",
    "opportunity-promotion",
    "exploration-learning",
    "planner-intake",
    "reviewer-gate",
    "dispatch-approved",
    "tester-gate",
    "releaser-gate",
    "reflect-release",
    "daily-kpi",
    "weekly-kpi",
    "skill-scout",
    "skill-maintenance",
    "research-sprint",
    "build-sprint",
    "daily-reflection",
    "daily-curation",
    "daily-backup",
    "memory-hourly",
    "memory-weekly",
]
PROTECTED_AGENT_IDS = {"main", "aic-captain"}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    return default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], dry_run: bool) -> None:
    if dry_run:
        return
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def read_repo_root(repo_root: str, execution_target_path: Path) -> Path:
    if repo_root:
        return Path(repo_root).expanduser().resolve()
    if execution_target_path.exists():
        payload = load_json(execution_target_path, {})
        target = payload.get("target")
        if isinstance(target, dict):
            raw = target.get("repo_root")
            if isinstance(raw, str) and raw.strip():
                return Path(raw).expanduser().resolve()
    script_path = Path(__file__).resolve()
    if (script_path.parents[2] / "templates/common").exists():
        return script_path.parents[2]
    raise SystemExit("无法确定 repo_root；请显式传 --repo-root 或提供 data/execution-target.json")


def split_csv(raw: str) -> list[str]:
    values = []
    for item in raw.split(","):
        value = item.strip()
        if value:
            values.append(value)
    return values


def render_bullets(items: list[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join(f"- {item}" for item in items)


def render_template(path: Path, replacements: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def merge_role_agents(workspace_path: Path, role_content: str, agent_id: str, dry_run: bool) -> None:
    agents_path = workspace_path / "AGENTS.md"
    original = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    start_marker = f"<!-- OPENCLAW-ROLE:{agent_id}:BEGIN -->"
    end_marker = f"<!-- OPENCLAW-ROLE:{agent_id}:END -->"
    block = f"{start_marker}\n{role_content.strip()}\n{end_marker}\n"
    if start_marker in original and end_marker in original:
        before = original.split(start_marker, 1)[0].rstrip()
        after = original.split(end_marker, 1)[1].lstrip()
        merged = before + "\n\n" + block
        if after:
            merged += "\n" + after
        if not dry_run:
            agents_path.write_text(merged.rstrip() + "\n", encoding="utf-8")
        return
    merged = original.rstrip() + "\n\n" + block if original.strip() else block
    if not dry_run:
        agents_path.write_text(merged.rstrip() + "\n", encoding="utf-8")


def ensure_today_daily_log(workspace_path: Path, repo_root: Path, dry_run: bool) -> None:
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    daily_path = workspace_path / "memory" / f"{today}.md"
    if daily_path.exists():
        return
    template_path = repo_root / "templates/common/memory/daily/TEMPLATE.md"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        weekday = datetime.now().astimezone().strftime("%A")
        content = template.replace("YYYY-MM-DD", today).replace("(Day)", f"({weekday})")
        if not dry_run:
            daily_path.parent.mkdir(parents=True, exist_ok=True)
            daily_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def merge_memory_seed(workspace_path: Path, dry_run: bool) -> None:
    memory_path = workspace_path / "MEMORY.md"
    seed_path = workspace_path / "MEMORY.seed.md"
    if not seed_path.exists():
        return
    seed = seed_path.read_text(encoding="utf-8").strip()
    if not seed:
        return
    existing = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
    if seed in existing:
        return
    merged = existing.rstrip() + "\n\n" + seed if existing.strip() else seed
    if not dry_run:
        memory_path.write_text(merged.rstrip() + "\n", encoding="utf-8")


def ensure_git_repo(workspace_path: Path, commit_message: str, dry_run: bool) -> None:
    if shutil.which("git") is None:
        return
    if not (workspace_path / ".git").exists():
        if dry_run:
            return
        subprocess.run(["git", "-C", str(workspace_path), "init"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(workspace_path), "branch", "-M", "main"], check=True, stdout=subprocess.DEVNULL)
    user_name = subprocess.run(["git", "-C", str(workspace_path), "config", "user.name"], check=False, capture_output=True, text=True).stdout.strip()
    user_email = subprocess.run(["git", "-C", str(workspace_path), "config", "user.email"], check=False, capture_output=True, text=True).stdout.strip()
    if not user_name or not user_email:
        return
    if dry_run:
        return
    subprocess.run(["git", "-C", str(workspace_path), "add", "."], check=True, stdout=subprocess.DEVNULL)
    status = subprocess.run(["git", "-C", str(workspace_path), "status", "--short"], check=True, capture_output=True, text=True).stdout.strip()
    if status:
        subprocess.run(["git", "-C", str(workspace_path), "commit", "-m", commit_message], check=True, stdout=subprocess.DEVNULL)


def prime_qmd_memory(repo_root: Path, agent_id: str, workspace_path: Path, agent_dir: Path, embed: bool, dry_run: bool) -> str:
    if shutil.which("qmd") is None:
        return "qmd not found; skipped"
    primer = repo_root / "setup/prime_qmd_memory.py"
    if not primer.exists():
        return "prime_qmd_memory.py missing; skipped"
    command = [
        "python3",
        str(primer),
        "--agent-id",
        agent_id,
        "--workspace",
        str(workspace_path),
        "--agent-dir",
        str(agent_dir),
    ]
    if embed:
        command.append("--embed")
    if dry_run:
        command.append("--dry-run")
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        return "qmd dry-run prepared with embed" if embed else "qmd dry-run prepared"
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    return "qmd primed with embed" if embed else "qmd primed"


def sync_managed_skill(repo_root: Path, openclaw_home: Path, skill_name: str, dry_run: bool) -> Path:
    source_dir = repo_root / "managed-skills" / skill_name
    if not source_dir.exists():
        raise SystemExit(f"missing managed skill: {source_dir}")
    target_dir = openclaw_home / "skills" / skill_name
    if not dry_run:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target_dir)
    return target_dir


def load_config(config_path: Path) -> dict[str, Any]:
    payload = load_json(config_path, {"agents": {"defaults": {}, "list": []}, "bindings": []})
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        agents = {"defaults": {}, "list": []}
        payload["agents"] = agents
    if not isinstance(agents.get("list"), list):
        agents["list"] = []
    if "bindings" not in payload or not isinstance(payload["bindings"], list):
        payload["bindings"] = []
    return payload


def find_agent_entry(config: dict[str, Any], agent_id: str) -> dict[str, Any] | None:
    for item in config["agents"]["list"]:
        if isinstance(item, dict) and item.get("id") == agent_id:
            return item
    return None


def ensure_allow_agent(config: dict[str, Any], caller_id: str, callee_id: str) -> None:
    caller = find_agent_entry(config, caller_id)
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


def remove_allow_agent(config: dict[str, Any], target_id: str) -> None:
    for item in config["agents"]["list"]:
        if not isinstance(item, dict):
            continue
        subagents = item.get("subagents")
        if not isinstance(subagents, dict):
            continue
        allow_agents = subagents.get("allowAgents")
        if not isinstance(allow_agents, list):
            continue
        subagents["allowAgents"] = [agent for agent in allow_agents if agent != target_id]


def create_workspace(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    openclaw_home = Path(args.openclaw_home).expanduser().resolve()
    config_path = Path(args.config_path).expanduser().resolve()
    workspace_path = openclaw_home / f"workspace-{args.agent_id}"
    agent_dir = openclaw_home / "agents" / args.agent_id
    if workspace_path.exists():
        raise SystemExit(f"workspace already exists: {workspace_path}")
    if agent_dir.exists():
        raise SystemExit(f"agentDir already exists: {agent_dir}")

    config = load_config(config_path)
    if find_agent_entry(config, args.agent_id) is not None:
        raise SystemExit(f"agent already exists in config: {args.agent_id}")
    for caller_id in args.accepted_from:
        ensure_allow_agent(config, caller_id, args.agent_id)
    managed_skill_path = sync_managed_skill(repo_root, openclaw_home, "team-agent-factory", args.dry_run)

    if args.dry_run:
        qmd_status = prime_qmd_memory(repo_root, args.agent_id, workspace_path, agent_dir, args.qmd_embed, True)
        return {
            "ok": True,
            "action": "add",
            "dry_run": True,
            "agent_id": args.agent_id,
            "workspace": str(workspace_path),
            "agentDir": str(agent_dir),
            "accepted_from": args.accepted_from,
            "allow_call": args.allow_call,
            "heartbeat_every": args.heartbeat_every or "",
            "managed_skill": str(managed_skill_path),
            "qmd": qmd_status,
        }

    common_root = repo_root / "templates/common"
    if not common_root.exists():
        raise SystemExit(f"missing common template root: {common_root}")
    shutil.copytree(common_root, workspace_path)
    agent_dir.mkdir(parents=True, exist_ok=True)

    merge_defaults = repo_root / "setup/merge_runtime_defaults.py"
    subprocess.run(
        ["python3", str(merge_defaults), "--workspace", str(workspace_path), "--common-root", str(common_root)],
        args.dry_run,
    )

    bootstrap_path = workspace_path / "BOOTSTRAP.md"
    if bootstrap_path.exists():
        bootstrap_path.unlink()
    for job_name in CORE_EXEC_LOG_JOBS:
        (workspace_path / "data/exec-logs" / job_name).mkdir(parents=True, exist_ok=True)

    templates_root = repo_root / "templates/dynamic-agent"
    replacements = {
        "agent_id": args.agent_id,
        "role_name": args.role_name,
        "role_title": args.role_title,
        "mission": args.mission,
        "memory_scope": render_bullets(args.memory_focus),
        "reflection_scope": render_bullets(args.reflection_focus),
        "accepted_from": ", ".join(args.accepted_from) if args.accepted_from else "aic-captain",
        "allow_call": ", ".join(args.allow_call) if args.allow_call else "无",
        "core_responsibilities": render_bullets(args.core_responsibilities),
        "inputs": render_bullets(args.inputs),
        "outputs": render_bullets(args.outputs),
        "boundaries": render_bullets(args.boundaries),
        "style": args.style,
        "identity_name": args.identity_name,
        "creature": args.creature,
        "vibe": args.vibe,
        "emoji": args.emoji,
    }
    role_agents = render_template(templates_root / "AGENTS.role.md.tmpl", replacements)
    merge_role_agents(workspace_path, role_agents, args.agent_id, args.dry_run)
    for name in ["SOUL.md", "IDENTITY.md", "MEMORY.seed.md"]:
        target = workspace_path / name
        target.write_text(render_template(templates_root / f"{name}.tmpl", replacements).rstrip() + "\n", encoding="utf-8")
    if args.heartbeat_every:
        (workspace_path / "HEARTBEAT.md").write_text(
            render_template(templates_root / "HEARTBEAT.md.tmpl", replacements).rstrip() + "\n",
            encoding="utf-8",
        )

    scripts_dir = workspace_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for script in (repo_root / "automation/scripts").glob("*.py"):
        shutil.copy2(script, scripts_dir / script.name)

    ensure_today_daily_log(workspace_path, repo_root, args.dry_run)
    merge_memory_seed(workspace_path, args.dry_run)
    ensure_git_repo(workspace_path, f"chore: bootstrap {args.agent_id} workspace", args.dry_run)

    agent_entry: dict[str, Any] = {
        "id": args.agent_id,
        "workspace": str(workspace_path),
        "agentDir": str(agent_dir),
        "subagents": {"allowAgents": args.allow_call},
    }
    if args.heartbeat_every:
        agent_entry["heartbeat"] = {"every": args.heartbeat_every, "target": "last"}
    config["agents"]["list"].append(agent_entry)
    write_json(config_path, config)

    qmd_status = prime_qmd_memory(repo_root, args.agent_id, workspace_path, agent_dir, args.qmd_embed, args.dry_run)
    return {
        "ok": True,
        "action": "add",
        "dry_run": False,
        "agent_id": args.agent_id,
        "workspace": str(workspace_path),
        "agentDir": str(agent_dir),
        "accepted_from": args.accepted_from,
        "allow_call": args.allow_call,
        "heartbeat_every": args.heartbeat_every or "",
        "managed_skill": str(managed_skill_path),
        "qmd": qmd_status,
    }


def retire_agent(args: argparse.Namespace) -> dict[str, Any]:
    if args.agent_id in PROTECTED_AGENT_IDS:
        raise SystemExit(f"agent is protected and cannot be retired: {args.agent_id}")
    openclaw_home = Path(args.openclaw_home).expanduser().resolve()
    config_path = Path(args.config_path).expanduser().resolve()
    config = load_config(config_path)
    agent = find_agent_entry(config, args.agent_id)
    if agent is None:
        raise SystemExit(f"agent not found in config: {args.agent_id}")

    registry_path = openclaw_home / "workspace-aic-captain" / "tasks/registry.json"
    registry = load_json(registry_path, {"tasks": []})
    active_tasks = [
        task for task in registry.get("tasks", [])
        if isinstance(task, dict) and task.get("owner") == args.agent_id and task.get("state") != "Closed"
    ]
    if active_tasks and not args.reassign_active_tasks_to:
        task_ids = ", ".join(str(task.get("task_id", "-")) for task in active_tasks)
        raise SystemExit(f"agent still owns active tasks: {task_ids}; 请先 reassign 或传 --reassign-active-tasks-to")
    reassigned_task_ids = [str(task.get("task_id", "-")) for task in active_tasks]
    if args.dry_run:
        removed_jobs: list[str] = []
        if shutil.which("openclaw") is not None:
            cron_payload = json.loads(subprocess.run(["openclaw", "cron", "list", "--all", "--json"], check=True, capture_output=True, text=True).stdout)
            for job in cron_payload.get("jobs", []):
                if job.get("agentId") == args.agent_id:
                    removed_jobs.append(str(job.get("name", job.get("id", "-"))))
        return {
            "ok": True,
            "action": "retire",
            "dry_run": True,
            "agent_id": args.agent_id,
            "reassigned_to": args.reassign_active_tasks_to or "",
            "reassigned_tasks": reassigned_task_ids,
            "removed_jobs": removed_jobs,
            "archive_workspace": str(Path(args.archive_root).expanduser().resolve() / f"{now_stamp()}-workspace-{args.agent_id}"),
            "archive_agentDir": str(Path(args.archive_root).expanduser().resolve() / f"{now_stamp()}-agentdir-{args.agent_id}"),
        }
    if active_tasks and args.reassign_active_tasks_to:
        for task in active_tasks:
            task["owner"] = args.reassign_active_tasks_to
            task["updated_at"] = now_iso()
            task["next_step"] = f"原 {args.agent_id} 已退役，改由 {args.reassign_active_tasks_to} 接手"
        write_json(registry_path, registry)

    config["agents"]["list"] = [item for item in config["agents"]["list"] if item.get("id") != args.agent_id]
    config["bindings"] = [item for item in config["bindings"] if item.get("agentId") != args.agent_id]
    remove_allow_agent(config, args.agent_id)
    write_json(config_path, config)

    removed_jobs: list[str] = []
    if shutil.which("openclaw") is not None:
        cron_payload = json.loads(subprocess.run(["openclaw", "cron", "list", "--all", "--json"], check=True, capture_output=True, text=True).stdout)
        for job in cron_payload.get("jobs", []):
            if job.get("agentId") != args.agent_id:
                continue
            removed_jobs.append(str(job.get("name", job.get("id", "-"))))
            subprocess.run(["openclaw", "cron", "rm", str(job["id"])], check=True, stdout=subprocess.DEVNULL)

    archive_root = Path(args.archive_root).expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    archived_workspace = None
    archived_agent_dir = None
    workspace_path = openclaw_home / f"workspace-{args.agent_id}"
    agent_dir = openclaw_home / "agents" / args.agent_id
    if workspace_path.exists():
        archived_workspace = archive_root / f"{now_stamp()}-workspace-{args.agent_id}"
        shutil.move(str(workspace_path), archived_workspace)
    if agent_dir.exists():
        archived_agent_dir = archive_root / f"{now_stamp()}-agentdir-{args.agent_id}"
        shutil.move(str(agent_dir), archived_agent_dir)

    return {
        "ok": True,
        "action": "retire",
        "dry_run": False,
        "agent_id": args.agent_id,
        "reassigned_to": args.reassign_active_tasks_to or "",
        "reassigned_tasks": reassigned_task_ids,
        "removed_jobs": removed_jobs,
        "archived_workspace": str(archived_workspace) if archived_workspace else "",
        "archived_agentDir": str(archived_agent_dir) if archived_agent_dir else "",
    }


def list_agents(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(Path(args.config_path).expanduser().resolve())
    registry_path = Path(args.openclaw_home).expanduser().resolve() / "workspace-aic-captain" / "tasks/registry.json"
    registry = load_json(registry_path, {"tasks": []})
    active_counts: dict[str, int] = {}
    for task in registry.get("tasks", []):
        if not isinstance(task, dict) or task.get("state") == "Closed":
            continue
        owner = str(task.get("owner", ""))
        active_counts[owner] = active_counts.get(owner, 0) + 1
    items = []
    for agent in config["agents"]["list"]:
        allow = []
        subagents = agent.get("subagents")
        if isinstance(subagents, dict):
            allow_raw = subagents.get("allowAgents")
            if isinstance(allow_raw, list):
                allow = [str(item) for item in allow_raw]
        items.append(
            {
                "agent_id": str(agent.get("id", "-")),
                "workspace": str(agent.get("workspace", "")),
                "agentDir": str(agent.get("agentDir", "")),
                "allow_call": allow,
                "heartbeat_every": str(agent.get("heartbeat", {}).get("every", "")) if isinstance(agent.get("heartbeat"), dict) else "",
                "active_task_count": active_counts.get(str(agent.get("id", "")), 0),
            }
        )
    return {"ok": True, "action": "list", "agents": items}


def print_result(result: dict[str, Any], as_markdown: bool) -> None:
    if as_markdown:
        lines = [f"# team_agent_manager", ""]
        for key, value in result.items():
            if isinstance(value, list):
                display = ", ".join(str(item) for item in value) if value else "-"
            elif isinstance(value, dict):
                display = json.dumps(value, ensure_ascii=False)
            else:
                display = str(value) if value != "" else "-"
            lines.append(f"- {key}: {display}")
        print("\n".join(lines) + "\n", end="")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


def add_shared_args(parser: argparse.ArgumentParser, suppress_defaults: bool) -> None:
    kwargs = {"default": argparse.SUPPRESS} if suppress_defaults else {}
    parser.add_argument("--openclaw-home", **kwargs)
    parser.add_argument("--config-path", **kwargs)
    parser.add_argument("--repo-root", **kwargs)
    parser.add_argument("--execution-target-path", **kwargs)
    parser.add_argument("--format", choices=["json", "md"], **kwargs)
    parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create, retire, and inspect runtime OpenClaw team agents.")
    add_shared_args(parser, suppress_defaults=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a new full-function agent and sync runtime openclaw.json.")
    add_shared_args(add_parser, suppress_defaults=True)
    add_parser.add_argument("--agent-id", required=True)
    add_parser.add_argument("--role-name", required=True)
    add_parser.add_argument("--role-title", required=True)
    add_parser.add_argument("--mission", required=True)
    add_parser.add_argument("--identity-name", default="")
    add_parser.add_argument("--creature", default="具有明确分工的协作体")
    add_parser.add_argument("--vibe", default="克制、直接、可交付")
    add_parser.add_argument("--emoji", default="🧩")
    add_parser.add_argument("--style", default="结构化、证据导向、先完成再汇报。")
    add_parser.add_argument("--heartbeat-every", default="")
    add_parser.add_argument("--qmd-embed", action="store_true")
    add_parser.add_argument("--accepted-from", action="append", default=[])
    add_parser.add_argument("--allow-call", action="append", default=[])
    add_parser.add_argument("--core-responsibility", action="append", dest="core_responsibilities", default=[])
    add_parser.add_argument("--input", action="append", dest="inputs", default=[])
    add_parser.add_argument("--output", action="append", dest="outputs", default=[])
    add_parser.add_argument("--boundary", action="append", dest="boundaries", default=[])
    add_parser.add_argument("--memory-focus", action="append", default=[])
    add_parser.add_argument("--reflection-focus", action="append", default=[])

    retire_parser = subparsers.add_parser("retire", help="Retire an agent, remove config, and archive workspace.")
    add_shared_args(retire_parser, suppress_defaults=True)
    retire_parser.add_argument("--agent-id", required=True)
    retire_parser.add_argument("--archive-root", default="~/.openclaw/archived-agents")
    retire_parser.add_argument("--reassign-active-tasks-to", default="")

    list_parser = subparsers.add_parser("list", help="List current runtime agents and active task counts.")
    add_shared_args(list_parser, suppress_defaults=True)

    args = parser.parse_args()
    if not hasattr(args, "openclaw_home") or args.openclaw_home is None:
        args.openclaw_home = "~/.openclaw"
    if not hasattr(args, "config_path") or args.config_path is None:
        args.config_path = "~/.openclaw/openclaw.json"
    if not hasattr(args, "repo_root") or args.repo_root is None:
        args.repo_root = ""
    if not hasattr(args, "execution_target_path") or args.execution_target_path is None:
        args.execution_target_path = "data/execution-target.json"
    if not hasattr(args, "format") or args.format is None:
        args.format = "json"
    if not hasattr(args, "dry_run") or args.dry_run is None:
        args.dry_run = False
    args.openclaw_home = args.openclaw_home or "~/.openclaw"
    args.config_path = args.config_path or "~/.openclaw/openclaw.json"
    args.repo_root = args.repo_root or ""
    args.execution_target_path = args.execution_target_path or "data/execution-target.json"
    args.format = args.format or "json"
    repo_root = read_repo_root(args.repo_root, Path(args.execution_target_path).expanduser())

    if args.command == "add":
        if not args.accepted_from:
            args.accepted_from = ["aic-captain"]
        if not args.identity_name:
            args.identity_name = args.role_name
        result = create_workspace(args, repo_root)
    elif args.command == "retire":
        result = retire_agent(args)
    else:
        result = list_agents(args)

    print_result(result, args.format == "md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

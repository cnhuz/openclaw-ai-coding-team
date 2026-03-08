#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lockfile import acquire, release


SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    chars: list[str] = []
    for char in value:
        if char.isalnum():
            chars.append(char.lower())
            continue
        if char in {"-", "_", "."}:
            chars.append("-")
            continue
        chars.append("-")
    slug = "".join(chars).strip("-")
    return slug or "item"


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def process_state(pid: int) -> str | None:
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], text=True, capture_output=True)
    if result.returncode != 0:
        return None
    state = result.stdout.strip()
    return state or None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def normalize_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, int) and item > 0]


def repo_root_from_arg(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"repo root not found: {path}")
    result = run_command(["git", "rev-parse", "--show-toplevel"], path)
    if result["returncode"] != 0 or not result["stdout"]:
        raise SystemExit(f"not a git repository: {path}")
    return Path(result["stdout"]).resolve()


def default_state_root(repo_root: Path) -> Path:
    return repo_root / ".openclaw-runtime" / "worktree-state"


def default_worktree_root(repo_root: Path) -> Path:
    return repo_root.parent / ".openclaw-worktrees" / repo_root.name


def registration_id(agent_id: str, task_id: str) -> str:
    return f"{slugify(agent_id)}--{slugify(task_id)}"


def registration_path(state_root: Path, agent_id: str, task_id: str) -> Path:
    return state_root / "registrations" / f"{registration_id(agent_id, task_id)}.json"


def lock_path(state_root: Path) -> Path:
    return state_root / "_state" / "lifecycle.lock"


def ensure_git_worktree(repo_root: Path, worktree_path: Path, branch: str, base_ref: str) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if worktree_path.exists() and (worktree_path / ".git").exists():
        commands.append(
            {
                "command": ["git", "worktree", "add", str(worktree_path), branch],
                "returncode": 0,
                "stdout": "reused existing worktree path",
                "stderr": "",
            }
        )
        return commands

    branch_exists = run_command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo_root)
    commands.append(branch_exists)
    if branch_exists["returncode"] == 0:
        add_result = run_command(["git", "worktree", "add", str(worktree_path), branch], repo_root)
        commands.append(add_result)
        return commands

    add_result = run_command(["git", "worktree", "add", "-b", branch, str(worktree_path), base_ref], repo_root)
    commands.append(add_result)
    return commands


def preferred_branch(agent_id: str, task_id: str) -> str:
    return f"agent/{slugify(agent_id)}/{slugify(task_id)}"


def port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def allocate_port(key: str, base: int, slots: int) -> dict[str, Any]:
    if slots <= 0:
        raise SystemExit("port slots must be > 0")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    preferred = base + (int(digest[:8], 16) % slots)
    for offset in range(slots):
        candidate = base + ((preferred - base + offset) % slots)
        if port_is_available(candidate):
            return {
                "strategy": "hash-slot-walk",
                "base": base,
                "slots": slots,
                "preferred": preferred,
                "assigned": candidate,
                "offset": offset,
            }
    raise SystemExit("unable to allocate an available port in configured range")


def load_hook_config(path: Path | None) -> dict[str, Any]:
    payload = {
        "setup": [],
        "cleanup": [],
        "env": {"vars": {}},
    }
    if path is None or not path.exists():
        return payload

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("hook config root must be an object")

    setup_items = data.get("setup", [])
    cleanup_items = data.get("cleanup", [])
    env_section = data.get("env", {})
    if not isinstance(setup_items, list):
        raise SystemExit("hook config setup must be a list")
    if not isinstance(cleanup_items, list):
        raise SystemExit("hook config cleanup must be a list")
    if not isinstance(env_section, dict):
        raise SystemExit("hook config env must be an object")

    for phase_name, source in (("setup", setup_items), ("cleanup", cleanup_items)):
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(source, start=1):
            if not isinstance(item, dict):
                raise SystemExit(f"{phase_name} hook #{index} must be an object")
            name = item.get("name")
            command = item.get("command")
            if not isinstance(name, str) or not name:
                raise SystemExit(f"{phase_name} hook #{index} missing name")
            if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                raise SystemExit(f"{phase_name} hook {name} command must be a non-empty string list")
            normalized.append({"name": name, "command": command})
        payload[phase_name] = normalized

    env_vars = env_section.get("vars", {})
    if env_vars and not isinstance(env_vars, dict):
        raise SystemExit("hook config env.vars must be an object")
    payload["env"] = {"vars": {key: value for key, value in env_vars.items() if isinstance(key, str) and isinstance(value, str)}}
    return payload


def render_template(value: str, context: dict[str, str]) -> str:
    rendered = value
    for key, replacement in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
    return rendered


def render_hook_command(command: list[str], context: dict[str, str]) -> list[str]:
    return [render_template(item, context) for item in command]


def write_env_file(worktree_path: Path, env_vars: dict[str, str]) -> Path | None:
    if not env_vars:
        return None
    env_path = worktree_path / ".openclaw-agent.env"
    lines = [f"{key}={value}" for key, value in env_vars.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def run_hooks(phase: str, hooks: list[dict[str, Any]], cwd: Path, context: dict[str, str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for hook in hooks:
        command = render_hook_command(hook["command"], context)
        result = run_command(command, cwd, env={**os.environ, **context})
        results.append(
            {
                "name": hook["name"],
                "command": command,
                "returncode": result["returncode"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "status": "ok" if result["returncode"] == 0 else "failed",
            }
        )
        if result["returncode"] != 0:
            raise SystemExit(f"{phase} hook failed: {hook['name']}")
    return results


def metadata_context(metadata: dict[str, Any]) -> dict[str, str]:
    resources = metadata["resources"]
    port_info = resources["port"]
    env_file = resources["env_file"] or ""
    return {
        "agent_id": metadata["agent_id"],
        "task_id": metadata["task_id"],
        "repo_root": metadata["repo_root"],
        "state_root": metadata["state_root"],
        "worktree_path": metadata["worktree_path"],
        "branch": metadata["branch"],
        "base_ref": metadata["base_ref"],
        "assigned_port": str(port_info["assigned"]),
        "preferred_port": str(port_info["preferred"]),
        "env_file": env_file,
        "registration_path": metadata["registration_path"],
    }


def load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"registration not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("registration root must be an object")
    return data


def resolve_registration(args: argparse.Namespace, repo_root: Path | None = None) -> Path:
    if args.registration_path:
        return Path(args.registration_path).expanduser().resolve()
    if repo_root is None:
        repo_root = repo_root_from_arg(args.repo_root)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else default_state_root(repo_root)
    return registration_path(state_root, args.agent_id, args.task_id)


def build_setup_metadata(
    repo_root: Path,
    state_root: Path,
    worktree_root: Path,
    agent_id: str,
    task_id: str,
    branch: str,
    base_ref: str,
    worktree_path: Path,
    hook_config_path: Path | None,
    port_info: dict[str, Any],
    env_file: Path | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "registration_id": registration_id(agent_id, task_id),
        "agent_id": agent_id,
        "task_id": task_id,
        "repo_root": str(repo_root),
        "state_root": str(state_root),
        "worktree_root": str(worktree_root),
        "worktree_path": str(worktree_path),
        "branch": branch,
        "base_ref": base_ref,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "ready",
        "resources": {
            "port": port_info,
            "env_file": str(env_file) if env_file else None,
            "processes": [],
            "temp_paths": [],
        },
        "hooks": {
            "config_path": str(hook_config_path) if hook_config_path else None,
            "setup": [],
            "cleanup": [],
        },
        "cleanup": None,
        "notes": [],
        "registration_path": str(registration_path(state_root, agent_id, task_id)),
    }


def to_md_setup(metadata: dict[str, Any], commands: list[dict[str, Any]]) -> str:
    lines = [
        "# worktree_lifecycle setup",
        "",
        f"- task_id: {metadata['task_id']}",
        f"- agent_id: {metadata['agent_id']}",
        f"- worktree_path: {metadata['worktree_path']}",
        f"- branch: {metadata['branch']}",
        f"- assigned_port: {metadata['resources']['port']['assigned']}",
        f"- env_file: {metadata['resources']['env_file'] or 'none'}",
        f"- registration_path: {metadata['registration_path']}",
        "",
        "## Commands",
    ]
    for item in commands:
        lines.extend(
            [
                f"- cmd: `{' '.join(item['command'])}`",
                f"  - returncode: {item['returncode']}",
                f"  - stdout: {item['stdout'] or 'none'}",
                f"  - stderr: {item['stderr'] or 'none'}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def terminate_registered_processes(process_ids: list[int], *, force: bool) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    residuals: list[str] = []
    for pid in process_ids:
        try:
            os.kill(pid, signal.SIGTERM)
            results.append({"pid": pid, "signal": "SIGTERM", "status": "sent"})
        except ProcessLookupError:
            results.append({"pid": pid, "signal": "SIGTERM", "status": "not-found"})
            continue
        except PermissionError:
            residuals.append(f"pid:{pid}:permission-denied")
            results.append({"pid": pid, "signal": "SIGTERM", "status": "permission-denied"})
            continue

        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            results.append({"pid": pid, "signal": "SIGTERM", "status": "terminated"})
            continue
        except PermissionError:
            residuals.append(f"pid:{pid}:permission-denied-after-term")
            results.append({"pid": pid, "signal": "SIGTERM", "status": "permission-denied-after-term"})
            continue
        if process_state(pid) == "Z":
            results.append({"pid": pid, "signal": "SIGTERM", "status": "terminated-zombie"})
            continue

        if not force:
            residuals.append(f"pid:{pid}:still-running")
            results.append({"pid": pid, "signal": "SIGTERM", "status": "still-running"})
            continue

        try:
            os.kill(pid, signal.SIGKILL)
            results.append({"pid": pid, "signal": "SIGKILL", "status": "sent"})
            time.sleep(0.2)
            os.kill(pid, 0)
            if process_state(pid) == "Z":
                results.append({"pid": pid, "signal": "SIGKILL", "status": "terminated-zombie"})
                continue
            residuals.append(f"pid:{pid}:still-running-after-kill")
        except ProcessLookupError:
            results.append({"pid": pid, "signal": "SIGKILL", "status": "terminated"})
        except PermissionError:
            residuals.append(f"pid:{pid}:permission-denied-after-kill")
            results.append({"pid": pid, "signal": "SIGKILL", "status": "permission-denied"})
    return results, residuals


def cleanup_registered_paths(paths: list[str], allowed_roots: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    residuals: list[str] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not any(path == root or root in path.parents for root in allowed_roots):
            residuals.append(f"path:{path}:outside-allowed-roots")
            results.append({"path": str(path), "status": "outside-allowed-roots"})
            continue
        if not path.exists():
            results.append({"path": str(path), "status": "not-found"})
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            path.rmdir()
        else:
            path.unlink()
        results.append({"path": str(path), "status": "removed"})
    return results, residuals


def status_rows(state_root: Path, active_only: bool) -> list[dict[str, Any]]:
    registrations_dir = state_root / "registrations"
    if not registrations_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(registrations_dir.glob("*.json")):
        item = load_metadata(path)
        if active_only and item.get("status") == "cleaned":
            continue
        rows.append(
            {
                "task_id": item.get("task_id"),
                "agent_id": item.get("agent_id"),
                "status": item.get("status"),
                "worktree_path": item.get("worktree_path"),
                "branch": item.get("branch"),
                "assigned_port": item.get("resources", {}).get("port", {}).get("assigned"),
                "updated_at": item.get("updated_at"),
                "registration_path": str(path),
            }
        )
    return rows


def cmd_setup(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else default_state_root(repo_root)
    worktree_root = Path(args.worktree_root).expanduser().resolve() if args.worktree_root else default_worktree_root(repo_root)
    worktree_path = worktree_root / registration_id(args.agent_id, args.task_id)
    branch = args.branch or preferred_branch(args.agent_id, args.task_id)
    base_ref = args.base_ref or "HEAD"
    registration = registration_path(state_root, args.agent_id, args.task_id)

    lock_result = acquire(lock_path(state_root), timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire lifecycle lock: {lock_path(state_root)}")

    commands: list[dict[str, Any]] = []
    try:
        if registration.exists() and not args.force_recreate:
            existing = load_metadata(registration)
            existing_path = Path(str(existing["worktree_path"]))
            if existing_path.exists():
                result = {"ok": True, "action": "reused", "metadata": existing, "commands": commands}
                if args.format == "md":
                    print(to_md_setup(existing, commands), end="")
                    return 0
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0

        worktree_root.mkdir(parents=True, exist_ok=True)
        state_root.mkdir(parents=True, exist_ok=True)

        port_info = allocate_port(registration_id(args.agent_id, args.task_id), args.port_base, args.port_slots)
        hook_config_path = Path(args.hook_config).expanduser().resolve() if args.hook_config else None
        hook_config = load_hook_config(hook_config_path)

        metadata = build_setup_metadata(
            repo_root,
            state_root,
            worktree_root,
            args.agent_id,
            args.task_id,
            branch,
            base_ref,
            worktree_path,
            hook_config_path,
            port_info,
            None,
        )
        context = metadata_context(metadata)
        env_vars = {
            "OPENCLAW_AGENT_ID": args.agent_id,
            "OPENCLAW_TASK_ID": args.task_id,
            "OPENCLAW_REPO_ROOT": str(repo_root),
            "OPENCLAW_WORKTREE_PATH": str(worktree_path),
            "OPENCLAW_ASSIGNED_PORT": str(port_info["assigned"]),
        }
        for key, value in hook_config["env"]["vars"].items():
            env_vars[key] = render_template(value, {**context, **env_vars})

        commands.extend(ensure_git_worktree(repo_root, worktree_path, branch, base_ref))
        if commands[-1]["returncode"] != 0:
            raise SystemExit(commands[-1]["stderr"] or "git worktree add failed")

        env_file = write_env_file(worktree_path, env_vars)
        metadata["resources"]["env_file"] = str(env_file) if env_file else None
        metadata["updated_at"] = now_iso()
        context = metadata_context(metadata)

        if not args.skip_hooks:
            metadata["hooks"]["setup"] = run_hooks("setup", hook_config["setup"], worktree_path, {**context, **env_vars})

        write_json(registration, metadata)
    finally:
        release(lock_path(state_root))

    result = {"ok": True, "action": "created", "metadata": metadata, "commands": commands}
    if args.format == "md":
        print(to_md_setup(metadata, commands), end="")
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    registration = resolve_registration(args, repo_root)
    metadata = load_metadata(registration)
    resources = metadata["resources"]
    processes = normalize_int_list(resources.get("processes"))
    temp_paths = normalize_string_list(resources.get("temp_paths"))

    for pid in args.process_pid:
        if pid not in processes:
            processes.append(pid)
    for temp_path in args.temp_path:
        if temp_path not in temp_paths:
            temp_paths.append(temp_path)
    resources["processes"] = processes
    resources["temp_paths"] = temp_paths
    metadata["updated_at"] = now_iso()
    metadata["status"] = args.status or metadata.get("status", "in_use")
    if args.note:
        notes = normalize_string_list(metadata.get("notes"))
        notes.extend(args.note)
        metadata["notes"] = notes

    write_json(registration, metadata)
    print(json.dumps({"ok": True, "action": "annotated", "metadata": metadata}, ensure_ascii=False, indent=2))
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else default_state_root(repo_root)
    registration = resolve_registration(args, repo_root)
    lock_result = acquire(lock_path(state_root), timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire lifecycle lock: {lock_path(state_root)}")

    try:
        metadata = load_metadata(registration)
        worktree_path = Path(str(metadata["worktree_path"])).resolve()
        hook_config_path_raw = metadata.get("hooks", {}).get("config_path")
        hook_config_path = Path(hook_config_path_raw).expanduser().resolve() if isinstance(hook_config_path_raw, str) and hook_config_path_raw else None
        hook_config = load_hook_config(hook_config_path)

        context = metadata_context(metadata)
        cleanup_record: dict[str, Any] = {
            "started_at": now_iso(),
            "hook_results": [],
            "process_results": [],
            "path_results": [],
            "git_remove": None,
            "git_prune": None,
            "residuals": [],
            "completed_at": None,
            "status": "cleanup_failed",
        }

        if not args.skip_hooks:
            cleanup_record["hook_results"] = run_hooks("cleanup", hook_config["cleanup"], worktree_path, context)

        process_results, process_residuals = terminate_registered_processes(
            normalize_int_list(metadata["resources"].get("processes")),
            force=args.force_kill,
        )
        cleanup_record["process_results"] = process_results
        cleanup_record["residuals"].extend(process_residuals)

        removable_paths = normalize_string_list(metadata["resources"].get("temp_paths"))
        env_file = metadata["resources"].get("env_file")
        if isinstance(env_file, str) and env_file:
            removable_paths.append(env_file)
        path_results, path_residuals = cleanup_registered_paths(
            removable_paths,
            [worktree_path, state_root],
        )
        cleanup_record["path_results"] = path_results
        cleanup_record["residuals"].extend(path_residuals)

        remove_result = run_command(["git", "worktree", "remove", "--force", str(worktree_path)], repo_root)
        prune_result = run_command(["git", "worktree", "prune"], repo_root)
        cleanup_record["git_remove"] = remove_result
        cleanup_record["git_prune"] = prune_result
        if remove_result["returncode"] != 0:
            cleanup_record["residuals"].append(f"worktree-remove:{remove_result['stderr'] or 'failed'}")
        if worktree_path.exists():
            cleanup_record["residuals"].append(f"worktree-path-still-exists:{worktree_path}")

        cleanup_record["completed_at"] = now_iso()
        cleanup_record["status"] = "cleaned" if not cleanup_record["residuals"] else "cleanup_failed"
        metadata["cleanup"] = cleanup_record
        metadata["updated_at"] = now_iso()
        metadata["status"] = cleanup_record["status"]
        write_json(registration, metadata)
    finally:
        release(lock_path(state_root))

    result = {"ok": metadata["status"] == "cleaned", "action": "cleanup", "metadata": metadata}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if metadata["status"] == "cleaned" else 1


def cmd_status(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else default_state_root(repo_root)
    if args.registration_path or (args.agent_id and args.task_id):
        registration = resolve_registration(args, repo_root)
        payload = {"ok": True, "registration": load_metadata(registration)}
        if args.format == "md":
            item = payload["registration"]
            print(
                "\n".join(
                    [
                        "# worktree_lifecycle status",
                        "",
                        f"- task_id: {item['task_id']}",
                        f"- agent_id: {item['agent_id']}",
                        f"- status: {item['status']}",
                        f"- worktree_path: {item['worktree_path']}",
                        f"- branch: {item['branch']}",
                        f"- assigned_port: {item['resources']['port']['assigned']}",
                        f"- updated_at: {item['updated_at']}",
                    ]
                )
                + "\n",
                end="",
            )
            return 0
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    rows = status_rows(state_root, args.active_only)
    payload = {"ok": True, "count": len(rows), "items": rows}
    if args.format == "md":
        lines = ["# worktree_lifecycle status", "", f"- count: {len(rows)}"]
        for item in rows:
            lines.extend(
                [
                    "",
                    f"## {item['task_id']} | {item['agent_id']}",
                    f"- status: {item['status']}",
                    f"- worktree_path: {item['worktree_path']}",
                    f"- branch: {item['branch']}",
                    f"- assigned_port: {item['assigned_port']}",
                    f"- updated_at: {item['updated_at']}",
                ]
            )
        print("\n".join(lines) + "\n", end="")
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage explicit git worktree lifecycle for one agent/task pair.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--repo-root", required=True)
    setup_parser.add_argument("--agent-id", required=True)
    setup_parser.add_argument("--task-id", required=True)
    setup_parser.add_argument("--branch")
    setup_parser.add_argument("--base-ref")
    setup_parser.add_argument("--state-root")
    setup_parser.add_argument("--worktree-root")
    setup_parser.add_argument("--hook-config")
    setup_parser.add_argument("--port-base", type=int, default=42000)
    setup_parser.add_argument("--port-slots", type=int, default=2000)
    setup_parser.add_argument("--skip-hooks", action="store_true")
    setup_parser.add_argument("--force-recreate", action="store_true")
    setup_parser.add_argument("--format", choices=["json", "md"], default="json")

    annotate_parser = sub.add_parser("annotate")
    annotate_parser.add_argument("--repo-root", required=True)
    annotate_parser.add_argument("--agent-id")
    annotate_parser.add_argument("--task-id")
    annotate_parser.add_argument("--registration-path")
    annotate_parser.add_argument("--state-root")
    annotate_parser.add_argument("--process-pid", type=int, action="append", default=[])
    annotate_parser.add_argument("--temp-path", action="append", default=[])
    annotate_parser.add_argument("--note", action="append", default=[])
    annotate_parser.add_argument("--status")

    cleanup_parser = sub.add_parser("cleanup")
    cleanup_parser.add_argument("--repo-root", required=True)
    cleanup_parser.add_argument("--agent-id")
    cleanup_parser.add_argument("--task-id")
    cleanup_parser.add_argument("--registration-path")
    cleanup_parser.add_argument("--state-root")
    cleanup_parser.add_argument("--skip-hooks", action="store_true")
    cleanup_parser.add_argument("--force-kill", action="store_true")

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--repo-root", required=True)
    status_parser.add_argument("--agent-id")
    status_parser.add_argument("--task-id")
    status_parser.add_argument("--registration-path")
    status_parser.add_argument("--state-root")
    status_parser.add_argument("--active-only", action="store_true")
    status_parser.add_argument("--format", choices=["json", "md"], default="json")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "setup":
        return cmd_setup(args)
    if args.cmd == "annotate":
        return cmd_annotate(args)
    if args.cmd == "cleanup":
        return cmd_cleanup(args)
    return cmd_status(args)


if __name__ == "__main__":
    raise SystemExit(main())

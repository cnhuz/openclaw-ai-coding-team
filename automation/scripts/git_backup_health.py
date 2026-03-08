#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def load_policy(path: Path, workspace_root: Path) -> dict[str, Any]:
    policy = {
        "enabled": True,
        "provider": "github",
        "owner": None,
        "visibility": "private",
        "repo_name": workspace_root.name,
        "remote_name": "origin",
        "branch": "main",
        "auto_create_repo": True,
        "auto_pull": True,
        "auto_push": True,
        "allow_git_init": True,
    }
    if not path.exists():
        return policy

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return policy

    for key in policy:
        if key in data and data[key] is not None:
            policy[key] = data[key]
    if policy["repo_name"] is None:
        policy["repo_name"] = workspace_root.name
    return policy


def repo_has_head(workspace_root: Path) -> bool:
    result = run_command(["git", "rev-parse", "--verify", "HEAD"], workspace_root)
    return result["returncode"] == 0


def current_branch(workspace_root: Path, fallback: str) -> str:
    result = run_command(["git", "branch", "--show-current"], workspace_root)
    branch = result["stdout"].strip()
    if branch:
        return branch
    return fallback


def ensure_local_repo(
    workspace_root: Path,
    policy: dict[str, Any],
    commands: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    git_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], workspace_root)
    commands.append(git_check)
    if git_check["returncode"] != 0:
        if not policy["allow_git_init"]:
            return

        summary["git_initialized"] = True
        summary["git_initialized_now"] = "yes"
        if not dry_run:
            init_result = run_command(["git", "init"], workspace_root)
            commands.append(init_result)
            branch_result = run_command(["git", "branch", "-M", policy["branch"]], workspace_root)
            commands.append(branch_result)
    else:
        summary["git_initialized"] = True

    name_result = run_command(["git", "config", "user.name"], workspace_root)
    email_result = run_command(["git", "config", "user.email"], workspace_root)
    commands.extend([name_result, email_result])
    summary["git_user_name"] = name_result["stdout"] if name_result["returncode"] == 0 else None
    summary["git_user_email"] = email_result["stdout"] if email_result["returncode"] == 0 else None
    if name_result["returncode"] != 0 or email_result["returncode"] != 0:
        summary["error"] = "git user.name or user.email is missing"
        return

    has_head = repo_has_head(workspace_root)
    dirty_result = run_command(["git", "status", "--short"], workspace_root)
    commands.append(dirty_result)
    dirty = bool(dirty_result["stdout"])
    if not has_head or dirty:
        summary["commit_needed"] = "yes"
        if dry_run:
            summary["commit_created"] = "dry-run"
            return

        add_result = run_command(["git", "add", "-A"], workspace_root)
        commands.append(add_result)
        commit_message = f"chore: backup baseline {now_iso()}"
        commit_command = ["git", "commit", "-m", commit_message]
        if not has_head:
            commit_command = ["git", "commit", "--allow-empty", "-m", commit_message]
        commit_result = run_command(commit_command, workspace_root)
        commands.append(commit_result)
        summary["commit_created"] = "yes" if commit_result["returncode"] == 0 else "no"
        if commit_result["returncode"] != 0:
            summary["error"] = "git commit failed"


def ensure_remote(
    workspace_root: Path,
    policy: dict[str, Any],
    commands: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    remote_name = str(policy["remote_name"])
    remote_result = run_command(["git", "remote", "get-url", remote_name], workspace_root)
    commands.append(remote_result)
    if remote_result["returncode"] == 0:
        summary["origin_configured"] = True
        summary["remote_url"] = remote_result["stdout"]
        return

    gh_path = shutil.which("gh")
    summary["gh_available"] = yes_no(gh_path is not None)
    if gh_path is None:
        return

    auth_result = run_command(["gh", "auth", "status", "--hostname", "github.com"], workspace_root)
    commands.append(auth_result)
    summary["gh_auth_ok"] = yes_no(auth_result["returncode"] == 0)
    if auth_result["returncode"] != 0 or not policy["enabled"] or not policy["auto_create_repo"]:
        return

    setup_git_result = run_command(["gh", "auth", "setup-git"], workspace_root)
    commands.append(setup_git_result)

    owner = policy["owner"]
    if owner is None:
        owner_result = run_command(["gh", "api", "user", "--jq", ".login"], workspace_root)
        commands.append(owner_result)
        if owner_result["returncode"] != 0:
            summary["error"] = "unable to determine GitHub owner"
            return
        owner = owner_result["stdout"].strip()

    repo_name = str(policy["repo_name"])
    full_name = f"{owner}/{repo_name}"
    summary["github_repo"] = full_name

    if dry_run:
        summary["origin_configured"] = True
        summary["repo_created"] = "dry-run"
        summary["remote_url"] = f"https://github.com/{full_name}.git"
        return

    view_result = run_command(["gh", "repo", "view", full_name, "--json", "url", "--jq", ".url"], workspace_root)
    commands.append(view_result)
    if view_result["returncode"] != 0:
        create_result = run_command(
            [
                "gh",
                "repo",
                "create",
                full_name,
                f"--{policy['visibility']}",
                "--source",
                ".",
                "--remote",
                remote_name,
            ],
            workspace_root,
        )
        commands.append(create_result)
        summary["repo_created"] = "yes" if create_result["returncode"] == 0 else "no"
        if create_result["returncode"] != 0:
            summary["error"] = "gh repo create failed"
            return
    else:
        summary["repo_created"] = "no"
        remote_url = view_result["stdout"].strip()
        if remote_url and not remote_url.endswith(".git"):
            remote_url = f"{remote_url}.git"
        add_remote_result = run_command(["git", "remote", "add", remote_name, remote_url], workspace_root)
        commands.append(add_remote_result)
        if add_remote_result["returncode"] != 0:
            summary["error"] = "git remote add failed"
            return

    final_remote = run_command(["git", "remote", "get-url", remote_name], workspace_root)
    commands.append(final_remote)
    summary["origin_configured"] = final_remote["returncode"] == 0
    if final_remote["returncode"] == 0:
        summary["remote_url"] = final_remote["stdout"]


def check_sync(
    workspace_root: Path,
    policy: dict[str, Any],
    commands: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    if not summary["origin_configured"]:
        summary["fetch_ok"] = "skipped-no-origin"
        summary["pull_ok"] = "skipped-no-origin"
        summary["push_ok"] = "skipped-no-origin"
        return

    branch = current_branch(workspace_root, str(policy["branch"]))
    summary["branch"] = branch

    if dry_run:
        summary["fetch_ok"] = "dry-run"
        summary["pull_ok"] = "dry-run"
        summary["push_ok"] = "dry-run"
        return

    fetch_result = run_command(["git", "fetch", policy["remote_name"]], workspace_root)
    commands.append(fetch_result)
    summary["fetch_ok"] = "yes" if fetch_result["returncode"] == 0 else "no"
    if fetch_result["returncode"] != 0:
        summary["pull_ok"] = "skipped-fetch-failed"
        summary["push_ok"] = "skipped-fetch-failed"
        summary["error"] = "git fetch failed"
        return

    if policy["auto_pull"]:
        remote_head = run_command(["git", "ls-remote", "--exit-code", "--heads", policy["remote_name"], branch], workspace_root)
        commands.append(remote_head)
        if remote_head["returncode"] == 0:
            pull_result = run_command(["git", "pull", "--ff-only", policy["remote_name"], branch], workspace_root)
            commands.append(pull_result)
            summary["pull_ok"] = "yes" if pull_result["returncode"] == 0 else "no"
            if pull_result["returncode"] != 0 and summary["error"] is None:
                summary["error"] = "git pull failed"
        else:
            summary["pull_ok"] = "skipped-no-remote-branch"
    else:
        summary["pull_ok"] = "skipped-policy-disabled"

    if policy["auto_push"]:
        upstream_result = run_command(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], workspace_root)
        commands.append(upstream_result)
        if upstream_result["returncode"] == 0:
            push_command = ["git", "push", policy["remote_name"], branch]
        else:
            push_command = ["git", "push", "-u", policy["remote_name"], branch]
        push_result = run_command(push_command, workspace_root)
        commands.append(push_result)
        summary["push_ok"] = "yes" if push_result["returncode"] == 0 else "no"
        if push_result["returncode"] != 0 and summary["error"] is None:
            summary["error"] = "git push failed"
    else:
        summary["push_ok"] = "skipped-policy-disabled"


def finalize_status(summary: dict[str, Any], dry_run: bool) -> str:
    if dry_run:
        return "skipped"
    if summary["git_initialized"] and summary["push_ok"] == "yes":
        return "ok"
    if summary["git_initialized"]:
        return "partial"
    return "failed"


def write_log(path: Path, summary: dict[str, Any], commands: list[dict[str, Any]]) -> None:
    lines = [
        f"# Daily Backup | {summary['run_at']}",
        "",
        "## Metadata",
        f"- Trigger: {summary['trigger']}",
        f"- Workspace: `{summary['workspace_root']}`",
        f"- Status: {summary['last_backup_status']}",
        f"- DryRun: {summary['dry_run']}",
        "",
        "## Summary",
        f"- git_initialized: {yes_no(summary['git_initialized'])}",
        f"- git_initialized_now: {summary['git_initialized_now']}",
        f"- origin_configured: {yes_no(summary['origin_configured'])}",
        f"- remote_url: {summary['remote_url'] or 'none'}",
        f"- branch: {summary['branch'] or 'none'}",
        f"- gh_available: {summary['gh_available']}",
        f"- gh_auth_ok: {summary['gh_auth_ok']}",
        f"- github_repo: {summary['github_repo'] or 'none'}",
        f"- repo_created: {summary['repo_created']}",
        f"- commit_created: {summary['commit_created']}",
        f"- fetch_ok: {summary['fetch_ok']}",
        f"- pull_ok: {summary['pull_ok']}",
        f"- push_ok: {summary['push_ok']}",
        f"- last_backup_status: {summary['last_backup_status']}",
        f"- error: {summary['error'] or 'none'}",
        "",
        "## Commands",
    ]

    for index, command_result in enumerate(commands, start=1):
        lines.extend(
            [
                f"### Command {index}",
                f"- cmd: `{' '.join(command_result['command'])}`",
                f"- returncode: {command_result['returncode']}",
                f"- stdout: {command_result['stdout'] or 'none'}",
                f"- stderr: {command_result['stderr'] or 'none'}",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure local Git backup baseline, GitHub remote, and pull/push health.")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--policy-path", default="data/github-backup-policy.json")
    parser.add_argument("--log-dir", default="data/exec-logs/daily-backup")
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    policy_path_input = Path(args.policy_path).expanduser()
    log_dir_input = Path(args.log_dir).expanduser()
    policy_path = policy_path_input if policy_path_input.is_absolute() else (workspace_root / policy_path_input)
    log_dir = log_dir_input if log_dir_input.is_absolute() else (workspace_root / log_dir_input)

    summary: dict[str, Any] = {
        "run_at": now_iso(),
        "trigger": args.trigger,
        "workspace_root": str(workspace_root),
        "dry_run": yes_no(args.dry_run),
        "git_initialized": False,
        "git_initialized_now": "no",
        "origin_configured": False,
        "remote_url": None,
        "branch": None,
        "gh_available": yes_no(shutil.which("gh") is not None),
        "gh_auth_ok": "unknown",
        "github_repo": None,
        "repo_created": "no",
        "commit_created": "no",
        "fetch_ok": "unknown",
        "pull_ok": "unknown",
        "push_ok": "unknown",
        "error": None,
    }
    commands: list[dict[str, Any]] = []

    if shutil.which("git") is None:
        summary["last_backup_status"] = "failed"
        summary["error"] = "git command not found"
    else:
        policy = load_policy(policy_path, workspace_root)
        ensure_local_repo(workspace_root, policy, commands, summary, dry_run=args.dry_run)
        if summary["error"] is None:
            ensure_remote(workspace_root, policy, commands, summary, dry_run=args.dry_run)
        if summary["error"] is None:
            check_sync(workspace_root, policy, commands, summary, dry_run=args.dry_run)
        summary["last_backup_status"] = finalize_status(summary, args.dry_run)

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d-%H%M")
    log_path = log_dir / f"{timestamp}.md"
    write_log(log_path, summary, commands)
    summary["log_path"] = str(log_path)

    print(json.dumps({"ok": summary["last_backup_status"] != "failed", "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["last_backup_status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

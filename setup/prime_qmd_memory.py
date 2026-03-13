#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def sanitize_name(value: str) -> str:
    parts: list[str] = []
    for char in value.lower():
        if char.isalnum() or char == "-":
            parts.append(char)
        else:
            parts.append("-")
    text = "".join(parts).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text or "collection"


def collection_name(base: str, agent_id: str) -> str:
    return f"{sanitize_name(base)}-{sanitize_name(agent_id)}"


def run_qmd(command: list[str], env: dict[str, str], allow_exists: bool = False) -> str:
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        return (result.stdout or result.stderr).strip()
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).lower()
    if allow_exists and ("already exists" in output or "exists" in output):
        return (result.stdout or result.stderr).strip()
    raise SystemExit(f"qmd command failed: {' '.join(command)}\n{result.stdout}{result.stderr}")


def managed_collections(workspace: Path, agent_id: str, profile: str) -> list[dict[str, str]]:
    collections = [
        {"name": collection_name("memory-root", agent_id), "path": str(workspace), "pattern": "MEMORY.md"},
        {"name": collection_name("memory-alt", agent_id), "path": str(workspace), "pattern": "memory.md"},
        {"name": collection_name("memory-dir", agent_id), "path": str(workspace / "memory"), "pattern": "**/*.md"},
    ]
    if profile == "core":
        return collections
    collections.extend(
        [
            {"name": collection_name("handoffs", agent_id), "path": str(workspace / "handoffs"), "pattern": "**/*.md"},
            {
                "name": collection_name("research-cards", agent_id),
                "path": str(workspace / "data" / "research" / "opportunity-cards"),
                "pattern": "**/*.md",
            },
            {"name": collection_name("dashboard", agent_id), "path": str(workspace / "data"), "pattern": "dashboard.md"},
        ]
    )
    return collections


def ensure_collection_roots(collections: list[dict[str, str]]) -> None:
    for item in collections:
        pattern = item["pattern"]
        root = Path(item["path"])
        if "*" in pattern or "?" in pattern or "[" in pattern:
            root.mkdir(parents=True, exist_ok=True)


def build_env(agent_dir: Path) -> dict[str, str]:
    qmd_dir = agent_dir / "qmd"
    config_home = qmd_dir / "xdg-config"
    cache_home = qmd_dir / "xdg-cache"
    config_home.mkdir(parents=True, exist_ok=True)
    cache_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["XDG_CACHE_HOME"] = str(cache_home)
    env["NO_COLOR"] = "1"
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description="Prime QMD memory for a single OpenClaw agent workspace.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--agent-dir", required=True)
    parser.add_argument("--qmd-command", default="qmd")
    parser.add_argument("--profile", choices=["team", "core"], default="team")
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    agent_dir = Path(args.agent_dir).expanduser()
    env = build_env(agent_dir)
    collections = managed_collections(workspace, args.agent_id, args.profile)
    ensure_collection_roots(collections)

    commands: list[list[str]] = []
    for item in collections:
        commands.append(
            [
                args.qmd_command,
                "collection",
                "add",
                item["path"],
                "--name",
                item["name"],
                "--mask",
                item["pattern"],
            ]
        )
    commands.append([args.qmd_command, "update"])
    if args.embed:
        commands.append([args.qmd_command, "embed"])
    commands.append([args.qmd_command, "status"])

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "agent_id": args.agent_id,
                    "workspace": str(workspace),
                    "agent_dir": str(agent_dir),
                    "profile": args.profile,
                    "embed": args.embed,
                    "commands": commands,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    status_output = ""
    for command in commands[:-1]:
        allow_exists = len(command) > 2 and command[1] == "collection" and command[2] == "add"
        run_qmd(command, env, allow_exists=allow_exists)
    status_output = run_qmd(commands[-1], env)

    print(
        json.dumps(
            {
                "ok": True,
                "agent_id": args.agent_id,
                "workspace": str(workspace),
                "agent_dir": str(agent_dir),
                "profile": args.profile,
                "embed": args.embed,
                "collections": [item["name"] for item in collections],
                "status": status_output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

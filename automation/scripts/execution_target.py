#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def load_execution_target(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"execution target not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("execution target root must be an object")

    target = payload.get("target")
    if not isinstance(target, dict):
        raise SystemExit("execution target must contain a target object")

    repo_root = target.get("repo_root")
    if not isinstance(repo_root, str) or not repo_root.strip():
        raise SystemExit("execution target.repo_root must be a non-empty string")

    normalized = dict(target)
    normalized["repo_root"] = str(Path(repo_root).expanduser().resolve())
    normalized["default_branch"] = str(normalized.get("default_branch") or "main")
    normalized["release_mode"] = str(normalized.get("release_mode") or "repo_only")
    normalized["test_commands"] = normalize_list(normalized.get("test_commands"))
    normalized["observe_checks"] = normalize_list(normalized.get("observe_checks"))

    release_command = normalized.get("release_command")
    if release_command is None:
        normalized["release_command"] = ""
    elif not isinstance(release_command, str):
        raise SystemExit("execution target.release_command must be a string")

    rollback_command = normalized.get("rollback_command")
    if rollback_command is None:
        normalized["rollback_command"] = ""
    elif not isinstance(rollback_command, str):
        raise SystemExit("execution target.rollback_command must be a string")

    build_entrypoint = normalized.get("build_entrypoint")
    if build_entrypoint is None:
        normalized["build_entrypoint"] = ""
    elif not isinstance(build_entrypoint, str):
        raise SystemExit("execution target.build_entrypoint must be a string")

    return normalized

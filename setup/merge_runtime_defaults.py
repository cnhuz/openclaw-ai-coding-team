#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def deep_fill(target: dict[str, Any], defaults: dict[str, Any]) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = value
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, dict):
            deep_fill(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            for item in value:
                if item not in current:
                    current.append(item)


def merge_entries(target_items: list[dict[str, Any]], default_items: list[dict[str, Any]], key_name: str) -> list[dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    result: list[dict[str, Any]] = []

    for item in target_items:
        if not isinstance(item, dict):
            continue
        key = item.get(key_name)
        if not isinstance(key, str) or not key:
            continue
        index[key] = item
        result.append(item)

    for item in default_items:
        if not isinstance(item, dict):
            continue
        key = item.get(key_name)
        if not isinstance(key, str) or not key:
            continue
        existing = index.get(key)
        if existing is None:
            result.append(item)
            index[key] = item
            continue
        deep_fill(existing, item)

    return result


def merge_catalog_file(workspace_path: Path, common_root: Path, relative_path: str, list_key: str, id_key: str) -> None:
    workspace_file = workspace_path / relative_path
    common_file = common_root / relative_path
    if not common_file.exists():
        return
    if not workspace_file.exists():
        workspace_file.parent.mkdir(parents=True, exist_ok=True)
        workspace_file.write_text(common_file.read_text(encoding="utf-8"), encoding="utf-8")
        return

    target = load_json(workspace_file)
    defaults = load_json(common_file)
    if not target:
        write_json(workspace_file, defaults)
        return

    target_items = target.get(list_key)
    default_items = defaults.get(list_key)
    if not isinstance(target_items, list):
        target_items = []
    if not isinstance(default_items, list):
        default_items = []
    target[list_key] = merge_entries(target_items, default_items, id_key)
    settings = target.get("settings")
    default_settings = defaults.get("settings")
    if isinstance(settings, dict) and isinstance(default_settings, dict):
        deep_fill(settings, default_settings)
    elif "settings" not in target and isinstance(default_settings, dict):
        target["settings"] = default_settings
    if "schemaVersion" not in target and "schemaVersion" in defaults:
        target["schemaVersion"] = defaults["schemaVersion"]
    if "updatedAt" not in target and "updatedAt" in defaults:
        target["updatedAt"] = defaults["updatedAt"]
    write_json(workspace_file, target)


def merge_policy_file(workspace_path: Path, common_root: Path, relative_path: str) -> None:
    workspace_file = workspace_path / relative_path
    common_file = common_root / relative_path
    if not common_file.exists():
        return
    if not workspace_file.exists():
        workspace_file.parent.mkdir(parents=True, exist_ok=True)
        workspace_file.write_text(common_file.read_text(encoding="utf-8"), encoding="utf-8")
        return

    target = load_json(workspace_file)
    defaults = load_json(common_file)
    if not target:
        write_json(workspace_file, defaults)
        return
    deep_fill(target, defaults)
    write_json(workspace_file, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge new runtime default catalogs into an existing OpenClaw workspace.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--common-root", required=True)
    args = parser.parse_args()

    workspace_path = Path(args.workspace).expanduser()
    common_root = Path(args.common_root).expanduser()

    merge_catalog_file(workspace_path, common_root, "data/research/sources.json", "sources", "source_id")
    merge_catalog_file(workspace_path, common_root, "data/research/site_profiles.json", "sites", "site_id")
    merge_catalog_file(workspace_path, common_root, "data/research/tool_profiles.json", "tools", "tool_id")
    merge_policy_file(workspace_path, common_root, "data/execution-target.json")
    merge_policy_file(workspace_path, common_root, "data/kpi/rules.v1.json")
    merge_policy_file(workspace_path, common_root, "data/skills/policy.json")
    merge_policy_file(workspace_path, common_root, "data/skills/catalog.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

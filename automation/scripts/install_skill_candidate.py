#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from bootstrap_skill_dependency import ensure_installer
from lockfile import acquire, release


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def fetch_skill_markdown(slug: str) -> str:
    result = subprocess.run(
        ["npx", "--yes", "clawhub", "inspect", slug, "--file", "SKILL.md"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"failed to inspect skill {slug}\n{result.stdout}{result.stderr}")
    lines = [line for line in result.stdout.splitlines() if not line.startswith("- Fetching skill")]
    return "\n".join(lines).strip()

def risk_allowed(candidate_risk: str, max_risk: str) -> bool:
    return RISK_ORDER.get(candidate_risk, 99) <= RISK_ORDER.get(max_risk, -1)


def relative_dir(workdir: Path, managed_dir: str) -> str:
    managed_path = Path(managed_dir).expanduser()
    if not managed_path.is_absolute():
        return managed_dir
    try:
        return str(managed_path.relative_to(workdir))
    except ValueError:
        raise SystemExit(f"managedSkillsDir must be inside workdir: {managed_path} vs {workdir}")


def parse_frontmatter(markdown: str) -> dict[str, Any]:
    if not markdown.startswith("---\n"):
        return {}
    parts = markdown.split("\n---\n", 1)
    if len(parts) != 2:
        return {}
    frontmatter = parts[0].removeprefix("---\n")
    result: dict[str, Any] = {}
    for line in frontmatter.splitlines():
        if ": " not in line:
            continue
        key, raw_value = line.split(": ", 1)
        result[key.strip()] = raw_value.strip()
    return result


def parse_install_entries(markdown: str) -> list[dict[str, Any]]:
    frontmatter = parse_frontmatter(markdown)
    metadata_raw = frontmatter.get("metadata")
    if not isinstance(metadata_raw, str) or not metadata_raw.startswith("{"):
        return []
    metadata = json.loads(metadata_raw)
    if not isinstance(metadata, dict):
        return []
    for value in metadata.values():
        if not isinstance(value, dict):
            continue
        install = value.get("install")
        if isinstance(install, list):
            return [item for item in install if isinstance(item, dict)]
    return []


def command_from_install_entry(entry: dict[str, Any]) -> tuple[list[str], str]:
    kind = entry.get("kind")
    if kind == "go":
        module = entry.get("module")
        bins = entry.get("bins")
        if not isinstance(module, str) or not module:
            raise SystemExit("go install entry missing module")
        binary_name = bins[0] if isinstance(bins, list) and bins and isinstance(bins[0], str) else module
        return (["go", "install", module], binary_name)
    if kind == "node":
        package = entry.get("package")
        bins = entry.get("bins")
        if not isinstance(package, str) or not package:
            raise SystemExit("node install entry missing package")
        binary_name = bins[0] if isinstance(bins, list) and bins and isinstance(bins[0], str) else package
        return (["npm", "i", "-g", package], binary_name)
    raise SystemExit(f"unsupported install entry kind: {kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install one approved skill candidate if policy allows.")
    parser.add_argument("--catalog", default="data/skills/catalog.json")
    parser.add_argument("--policy", default="data/skills/policy.json")
    parser.add_argument("--dependency-policy", default="data/skills/dependency_policy.json")
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--lock", default="data/skills/catalog.lock")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    catalog_path = Path(args.catalog).expanduser()
    policy_path = Path(args.policy).expanduser()
    dependency_policy_path = Path(args.dependency_policy).expanduser()
    lock_path = Path(args.lock).expanduser()

    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire skill catalog lock: {lock_path}")

    try:
        catalog = load_json(catalog_path, {"candidates": []})
        policy = load_json(policy_path, {"settings": {}})
        settings = policy.get("settings")
        if not isinstance(settings, dict) or settings.get("enabled") is not True:
            raise SystemExit("skill auto install is disabled by policy")

        candidates = catalog.get("candidates")
        if not isinstance(candidates, list):
            raise SystemExit("invalid skill catalog")

        target: dict[str, Any] | None = None
        for item in candidates:
            if isinstance(item, dict) and item.get("candidate_id") == args.candidate_id:
                target = item
                break
        if target is None:
            raise SystemExit(f"candidate not found: {args.candidate_id}")

        review_status = target.get("review_status")
        status = target.get("status")
        source_type = target.get("source_type")
        install_method = target.get("install_method")
        risk = target.get("risk", "unknown")

        if review_status != "approved":
            raise SystemExit(f"candidate is not approved: {review_status}")
        if status == "installed":
            raise SystemExit("candidate already installed")
        if not isinstance(source_type, str) or source_type not in settings.get("trustedSources", []):
            raise SystemExit(f"untrusted source: {source_type}")
        if not isinstance(install_method, str) or install_method not in settings.get("allowedInstallMethods", []):
            raise SystemExit(f"install method not allowed: {install_method}")
        if settings.get("autoInstallTrustedLowRisk") is not True:
            raise SystemExit("auto install is disabled for trusted low risk skills")
        if not isinstance(risk, str) or not risk_allowed(risk, str(settings.get("maxAutoInstallRisk", "low"))):
            raise SystemExit(f"risk too high: {risk}")

        slug = target.get("slug")
        if not isinstance(slug, str) or not slug:
            raise SystemExit("candidate slug is required")

        workdir = Path(str(settings.get("managedSkillsWorkdir", "~/.openclaw"))).expanduser()
        managed_dir = str(settings.get("managedSkillsDir", "skills"))
        dir_argument = relative_dir(workdir, managed_dir)

        if source_type == "openclaw-bundled" and install_method == "npx-clawhub":
            install_method = "bundled-auto"

        if install_method == "npx-clawhub":
            command = ["npx", "--yes", "clawhub", "install", slug, "--workdir", str(workdir), "--dir", dir_argument]
            if not args.dry_run:
                subprocess.run(command, check=True)
            installed_path = workdir / dir_argument / slug
        elif install_method == "bundled-auto":
            markdown = fetch_skill_markdown(slug)
            install_entries = parse_install_entries(markdown)
            if not install_entries:
                raise SystemExit(f"no install metadata found for bundled skill: {slug}")
            command, binary_name = command_from_install_entry(install_entries[0])
            env = os.environ.copy()
            dependency_policy = load_json(dependency_policy_path, {"settings": {}})
            dependency_settings = dependency_policy.get("settings")
            if not isinstance(dependency_settings, dict):
                dependency_settings = {}
            if shutil.which(command[0]) is None:
                bootstrap = ensure_installer(command[0], dependency_policy_path, args.dry_run)
                path_prefix = bootstrap.get("path_prefix")
                if isinstance(path_prefix, str) and path_prefix:
                    env["PATH"] = path_prefix + os.pathsep + env.get("PATH", "")
            if command[0] == "go":
                go_binary_root = Path(str(dependency_settings.get("goBinaryRoot", "~/.local/bin"))).expanduser()
                go_binary_root.mkdir(parents=True, exist_ok=True)
                env["GOBIN"] = str(go_binary_root)
                env["PATH"] = str(go_binary_root) + os.pathsep + env.get("PATH", "")
            if not args.dry_run:
                subprocess.run(command, check=True, env=env)
            binary_path = shutil.which(binary_name, path=env.get("PATH"))
            installed_path = Path(binary_path) if binary_path else Path(binary_name)
        else:
            raise SystemExit(f"unsupported install method: {install_method}")

        if not args.dry_run and not installed_path.exists():
            raise SystemExit(f"installed path missing: {installed_path}")

        if not args.dry_run:
            target["status"] = "installed"
            target["installed_at"] = now_iso()
            target["installed_path"] = str(installed_path)
            target["updated_at"] = now_iso()
            catalog["updatedAt"] = now_iso()
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        release(lock_path)

    if args.format == "md":
        print(
            "\n".join(
                [
                    "# install_skill_candidate",
                    "",
                    f"- candidate_id: {args.candidate_id}",
                    f"- status: {'dry-run' if args.dry_run else 'installed'}",
                    f"- installed_path: {installed_path}",
                    f"- dry_run: {'yes' if args.dry_run else 'no'}",
                ]
            )
            + "\n",
            end="",
        )
        return 0

    print(
        json.dumps(
            {
                "ok": True,
                "candidate_id": args.candidate_id,
                "status": "dry-run" if args.dry_run else "installed",
                "installed_path": str(installed_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

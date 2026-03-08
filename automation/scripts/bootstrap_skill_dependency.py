#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from lockfile import acquire, release


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def machine_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "amd64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    raise SystemExit(f"unsupported machine architecture: {machine}")


def os_name() -> str:
    name = platform.system().lower()
    if name in {"linux", "darwin", "windows"}:
        return name
    raise SystemExit(f"unsupported operating system: {name}")


def go_index(index_url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(index_url, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise SystemExit(f"unexpected Go index payload: {index_url}")
    return [item for item in payload if isinstance(item, dict)]


def choose_go_release(index: list[dict[str, Any]], version: str, os_id: str, arch_id: str) -> tuple[str, dict[str, Any]]:
    target_release: dict[str, Any] | None = None
    if version == "latest":
        for item in index:
            if item.get("stable") is True:
                target_release = item
                break
    else:
        for item in index:
            if item.get("version") == version:
                target_release = item
                break
    if target_release is None:
        raise SystemExit(f"unable to find Go release: {version}")

    files = target_release.get("files")
    if not isinstance(files, list):
        raise SystemExit("selected Go release has no files")

    target_kind = "archive"
    for item in files:
        if not isinstance(item, dict):
            continue
        if item.get("os") == os_id and item.get("arch") == arch_id and item.get("kind") == target_kind:
            return str(target_release["version"]), item
    raise SystemExit(f"no Go archive for {os_id}/{arch_id}")


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    temp_path.write_bytes(data)
    temp_path.replace(destination)


def extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as handle:
            handle.extractall(destination)
        return
    with tarfile.open(archive_path, "r:*") as handle:
        handle.extractall(destination)


def ensure_go(policy: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    settings = policy.get("settings")
    if not isinstance(settings, dict):
        raise SystemExit("dependency policy settings missing")
    if settings.get("enabled") is not True:
        raise SystemExit("dependency bootstrap disabled by policy")

    go_policy = settings.get("go")
    if not isinstance(go_policy, dict) or go_policy.get("enabled") is not True:
        raise SystemExit("go bootstrap disabled by policy")

    root = Path(str(settings.get("toolchainRoot", "~/.openclaw/toolchains"))).expanduser()
    cache_dir = Path(str(settings.get("cacheDir", root / "cache"))).expanduser()
    lock_path = Path(str(settings.get("bootstrapLock", root / "bootstrap-go.lock"))).expanduser()
    index_url = str(go_policy.get("indexUrl", "https://go.dev/dl/?mode=json"))
    base_url = str(go_policy.get("baseUrl", "https://go.dev/dl"))
    version_request = str(go_policy.get("version", "latest"))

    arch_id = machine_arch()
    os_id = os_name()
    index = go_index(index_url)
    version, file_meta = choose_go_release(index, version_request, os_id, arch_id)
    filename = str(file_meta["filename"])
    expected_size = int(file_meta.get("size", 0) or 0)
    install_root = root / "go" / version
    extracted_root = install_root / "go"
    binary_name = "go.exe" if os_id == "windows" else "go"
    binary_path = extracted_root / "bin" / binary_name
    archive_path = cache_dir / filename

    if binary_path.exists():
        return {
            "ok": True,
            "bootstrapped": False,
            "installer": "go",
            "version": version,
            "binary": str(binary_path),
            "path_prefix": str(binary_path.parent),
            "archive": str(archive_path),
        }

    if dry_run:
        return {
            "ok": True,
            "bootstrapped": False,
            "installer": "go",
            "version": version,
            "binary": str(binary_path),
            "path_prefix": str(binary_path.parent),
            "archive": str(archive_path),
            "dry_run": True,
        }

    lock_result = acquire(lock_path, timeout=300, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire Go bootstrap lock: {lock_path}")
    try:
        if binary_path.exists():
            return {
                "ok": True,
                "bootstrapped": False,
                "installer": "go",
                "version": version,
                "binary": str(binary_path),
                "path_prefix": str(binary_path.parent),
                "archive": str(archive_path),
            }

        if archive_path.exists() and expected_size and archive_path.stat().st_size != expected_size:
            archive_path.unlink()

        url = f"{base_url}/{filename}"
        if not archive_path.exists():
            download(url, archive_path)
        if expected_size and archive_path.stat().st_size != expected_size:
            archive_path.unlink(missing_ok=True)
            raise SystemExit(f"downloaded Go archive has unexpected size: {archive_path}")

        install_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="go-bootstrap-") as temp_dir:
            temp_path = Path(temp_dir)
            extract_archive(archive_path, temp_path)
            extracted = temp_path / "go"
            if not extracted.exists():
                raise SystemExit(f"unexpected Go archive layout: {archive_path}")
            if extracted_root.exists():
                shutil.rmtree(extracted_root)
            shutil.move(str(extracted), str(extracted_root))

        if not binary_path.exists():
            raise SystemExit(f"go binary missing after bootstrap: {binary_path}")

        return {
            "ok": True,
            "bootstrapped": True,
            "installer": "go",
            "version": version,
            "binary": str(binary_path),
            "path_prefix": str(binary_path.parent),
            "archive": str(archive_path),
        }
    finally:
        release(lock_path)


def ensure_installer(installer: str, policy_path: Path, dry_run: bool) -> dict[str, Any]:
    if shutil.which(installer):
        binary = shutil.which(installer)
        return {
            "ok": True,
            "bootstrapped": False,
            "installer": installer,
            "binary": binary,
            "path_prefix": str(Path(binary).parent) if binary else None,
        }

    policy = load_json(policy_path, {"settings": {}})
    if installer == "go":
        return ensure_go(policy, dry_run)
    raise SystemExit(f"required installer is missing: {installer}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a missing installer or toolchain for skill installation.")
    parser.add_argument("--installer", required=True)
    parser.add_argument("--policy-path", default="data/skills/dependency_policy.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    result = ensure_installer(args.installer, Path(args.policy_path).expanduser(), args.dry_run)
    if args.format == "md":
        lines = [
            "# bootstrap_skill_dependency",
            "",
            f"- installer: {result['installer']}",
            f"- bootstrapped: {'yes' if result.get('bootstrapped') else 'no'}",
            f"- binary: {result.get('binary') or '-'}",
            f"- path_prefix: {result.get('path_prefix') or '-'}",
        ]
        if result.get("version"):
            lines.append(f"- version: {result['version']}")
        if result.get("archive"):
            lines.append(f"- archive: {result['archive']}")
        if args.dry_run:
            lines.append("- dry_run: yes")
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

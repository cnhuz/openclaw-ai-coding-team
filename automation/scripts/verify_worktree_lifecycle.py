#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def ensure_ok(result: dict[str, Any], message: str) -> None:
    if result["returncode"] != 0:
        raise SystemExit(f"{message}: {result['stderr'] or result['stdout'] or result['returncode']}")


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the worktree lifecycle tool in a temporary git repo.")
    parser.add_argument("--tool-path", default=str(Path(__file__).resolve().with_name("worktree_lifecycle.py")))
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    tool_path = Path(args.tool_path).expanduser().resolve()
    if not tool_path.exists():
        raise SystemExit(f"tool not found: {tool_path}")

    summary: dict[str, Any] = {"ok": False, "steps": []}
    with tempfile.TemporaryDirectory(prefix="worktree-lifecycle-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        repo_root = tmp_root / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)

        summary["repo_root"] = str(repo_root)
        commands = [
            run(["git", "init"], repo_root),
            run(["git", "config", "user.name", "OpenClaw Test"], repo_root),
            run(["git", "config", "user.email", "openclaw@example.com"], repo_root),
        ]
        for result in commands:
            ensure_ok(result, "git bootstrap failed")
            summary["steps"].append(result)

        (repo_root / "README.md").write_text("# temp repo\n", encoding="utf-8")
        commit_steps = [
            run(["git", "add", "README.md"], repo_root),
            run(["git", "commit", "-m", "chore: init"], repo_root),
        ]
        for result in commit_steps:
            ensure_ok(result, "initial commit failed")
            summary["steps"].append(result)

        hook_config = repo_root / ".openclaw-worktree-hooks.json"
        hook_config.write_text(
            json.dumps(
                {
                    "setup": [
                        {
                            "name": "setup-marker",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path('setup.marker').write_text('ok', encoding='utf-8')",
                            ],
                        }
                    ],
                    "cleanup": [
                        {
                            "name": "cleanup-marker",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path('{{state_root}}/cleanup.marker').write_text('ok', encoding='utf-8')",
                            ],
                        }
                    ],
                    "env": {
                        "vars": {
                            "APP_PORT": "{{assigned_port}}",
                            "OPENCLAW_REGISTRATION": "{{registration_path}}",
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        setup_result = run(
            [
                sys.executable,
                str(tool_path),
                "setup",
                "--repo-root",
                str(repo_root),
                "--agent-id",
                "agent-alpha",
                "--task-id",
                "TASK-001",
                "--hook-config",
                str(hook_config),
            ]
        )
        ensure_ok(setup_result, "setup failed")
        summary["steps"].append(setup_result)
        setup_payload = json.loads(setup_result["stdout"])
        metadata = setup_payload["metadata"]
        worktree_path = Path(metadata["worktree_path"])
        registration_path = Path(metadata["registration_path"])
        state_root = Path(metadata["state_root"])
        env_file = Path(str(metadata["resources"]["env_file"]))

        if not worktree_path.exists():
            raise SystemExit("setup did not create worktree path")
        if not registration_path.exists():
            raise SystemExit("setup did not write registration metadata")
        if not env_file.exists():
            raise SystemExit("setup did not write env file")
        if not (worktree_path / "setup.marker").exists():
            raise SystemExit("setup hook did not run")

        temp_path = worktree_path / "tmp-artifact.txt"
        temp_path.write_text("artifact", encoding="utf-8")
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=worktree_path)
        time.sleep(0.3)
        annotate_result = run(
            [
                sys.executable,
                str(tool_path),
                "annotate",
                "--repo-root",
                str(repo_root),
                "--agent-id",
                "agent-alpha",
                "--task-id",
                "TASK-001",
                "--process-pid",
                str(sleeper.pid),
                "--temp-path",
                str(temp_path),
                "--status",
                "in_use",
            ]
        )
        ensure_ok(annotate_result, "annotate failed")
        summary["steps"].append(annotate_result)

        cleanup_result = run(
            [
                sys.executable,
                str(tool_path),
                "cleanup",
                "--repo-root",
                str(repo_root),
                "--agent-id",
                "agent-alpha",
                "--task-id",
                "TASK-001",
                "--force-kill",
            ]
        )
        ensure_ok(cleanup_result, "cleanup failed")
        summary["steps"].append(cleanup_result)
        cleanup_payload = json.loads(cleanup_result["stdout"])
        cleaned = cleanup_payload["metadata"]

        try:
            sleeper.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

        if worktree_path.exists():
            raise SystemExit("cleanup did not remove worktree")
        if temp_path.exists():
            raise SystemExit("cleanup did not remove registered temp path")
        if process_is_alive(sleeper.pid):
            raise SystemExit("cleanup did not stop registered process")
        if cleaned["status"] != "cleaned":
            raise SystemExit("cleanup metadata did not reach cleaned state")
        if not (state_root / "cleanup.marker").exists():
            raise SystemExit("cleanup hook did not run")

        summary["ok"] = True
        summary["registration_path"] = str(registration_path)
        summary["cleanup_status"] = cleaned["status"]
        summary["cleanup_marker"] = str(state_root / "cleanup.marker")

    if args.format == "md":
        lines = [
            "# verify_worktree_lifecycle",
            "",
            f"- ok: {'yes' if summary['ok'] else 'no'}",
            f"- cleanup_status: {summary.get('cleanup_status', 'unknown')}",
            f"- registration_path: {summary.get('registration_path', 'none')}",
            f"- cleanup_marker: {summary.get('cleanup_marker', 'none')}",
        ]
        print("\n".join(lines) + "\n", end="")
        return 0 if summary["ok"] else 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

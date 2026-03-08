#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(command)}\n{result.stdout}{result.stderr}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync current OpenClaw skills inventory into runtime data.")
    parser.add_argument("--output", default="data/skills/inventory.json")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    payload = json.loads(run_command(["openclaw", "skills", "list", "--json"]))
    skills = payload.get("skills")
    if not isinstance(skills, list):
        skills = []

    eligible: list[str] = []
    missing: list[str] = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        name = skill.get("name")
        if not isinstance(name, str) or not name:
            continue
        if skill.get("eligible") is True:
            eligible.append(name)
        else:
            missing.append(name)

    result: dict[str, Any] = {
        "schemaVersion": 1,
        "updatedAt": now_iso(),
        "workspaceDir": payload.get("workspaceDir"),
        "managedSkillsDir": payload.get("managedSkillsDir"),
        "eligible_skills": sorted(eligible),
        "missing_skills": sorted(missing),
        "skills": skills,
    }

    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.format == "md":
        lines = [
            "# skill_inventory",
            "",
            f"- eligible_count: {len(eligible)}",
            f"- missing_count: {len(missing)}",
            f"- managed_skills_dir: {result['managedSkillsDir'] or '-'}",
        ]
        if eligible:
            lines.append(f"- eligible_skills: {', '.join(sorted(eligible))}")
        if missing:
            lines.append(f"- missing_skills: {', '.join(sorted(missing)[:12])}")
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps({"ok": True, "output": str(output_path), "eligible_count": len(eligible), "missing_count": len(missing)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

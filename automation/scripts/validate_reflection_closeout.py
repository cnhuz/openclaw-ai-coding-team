#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CHECK_BLOCK_RE = re.compile(
    r"- check:\s*(?P<check>.+?)\n\s*- result:\s*(?P<result>pass|fail|n/a)\n\s*- evidence:\s*(?P<evidence>.+?)(?=\n(?:\s*\n)*(?:- check:|## )|\Z)",
    re.DOTALL,
)


def read_text(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"file not found: {path}")
    return path.read_text(encoding="utf-8")


def extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    rest = text[start + len(marker) :]
    next_heading = rest.find("\n## ")
    if next_heading == -1:
        return rest.strip()
    return rest[:next_heading].strip()


def extract_packet_checks(packet_text: str) -> list[str]:
    section = extract_section(packet_text, "Observe Checks")
    checks: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        content = line[2:].strip()
        if content:
            checks.append(content)
    return checks


def extract_reflection_checks(reflection_text: str) -> dict[str, dict[str, str]]:
    section = extract_section(reflection_text, "Observe Checks")
    results: dict[str, dict[str, str]] = {}
    for match in CHECK_BLOCK_RE.finditer(section):
        check = match.group("check").strip()
        results[check] = {
            "result": match.group("result").strip(),
            "evidence": match.group("evidence").strip(),
        }
    return results


def load_template(path: Path) -> dict[str, Any]:
    payload = json.loads(read_text(path))
    if not isinstance(payload, dict):
        raise SystemExit("knowledge proposal template must be an object")
    return payload


def load_proposal(path: Path) -> dict[str, Any]:
    payload = json.loads(read_text(path))
    if not isinstance(payload, dict):
        raise SystemExit("knowledge proposal must be an object")
    return payload


def validate_proposal(template: dict[str, Any], proposal: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, template_value in template.items():
        if key not in proposal:
            errors.append(f"missing proposal field: {key}")
            continue
        value = proposal[key]
        if isinstance(template_value, list) and not isinstance(value, list):
            errors.append(f"proposal field must be a list: {key}")
        elif isinstance(template_value, str) and not isinstance(value, str):
            errors.append(f"proposal field must be a string: {key}")
        elif isinstance(template_value, dict) and not isinstance(value, dict):
            errors.append(f"proposal field must be an object: {key}")
        elif isinstance(value, str) and not value.strip():
            errors.append(f"proposal field must be non-empty: {key}")
        elif isinstance(value, list) and not value:
            errors.append(f"proposal field must be non-empty: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reflector closeout artifacts before closing a task.")
    parser.add_argument("--packet-path", required=True)
    parser.add_argument("--reflection-path", required=True)
    parser.add_argument("--proposal-path", required=True)
    parser.add_argument("--proposal-template-path")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    packet_path = Path(args.packet_path).expanduser()
    reflection_path = Path(args.reflection_path).expanduser()
    proposal_path = Path(args.proposal_path).expanduser()

    packet_text = read_text(packet_path)
    reflection_text = read_text(reflection_path)

    packet_checks = extract_packet_checks(packet_text)
    reflection_checks = extract_reflection_checks(reflection_text)

    missing_checks = [item for item in packet_checks if item not in reflection_checks]
    incomplete_checks = [
        item
        for item, payload in reflection_checks.items()
        if not payload["result"] or not payload["evidence"]
    ]

    template_path: Path | None = None
    packet_template_line = next(
        (
            line.split(":", 1)[1].strip()
            for line in packet_text.splitlines()
            if line.strip().startswith("- knowledge_template:")
        ),
        "",
    )
    if args.proposal_template_path:
        template_path = Path(args.proposal_template_path).expanduser()
    elif packet_template_line:
        template_path = Path(packet_template_line).expanduser()

    proposal_errors: list[str] = []
    if template_path is not None:
        template = load_template(template_path)
        proposal = load_proposal(proposal_path)
        proposal_errors = validate_proposal(template, proposal)

    ok = not missing_checks and not incomplete_checks and not proposal_errors
    result = {
        "ok": ok,
        "packet_path": str(packet_path),
        "reflection_path": str(reflection_path),
        "proposal_path": str(proposal_path),
        "required_checks": packet_checks,
        "missing_checks": missing_checks,
        "incomplete_checks": incomplete_checks,
        "proposal_errors": proposal_errors,
    }

    if args.format == "md":
        lines = [
            "# validate_reflection_closeout",
            "",
            f"- ok: {'yes' if ok else 'no'}",
            f"- packet_path: {packet_path}",
            f"- reflection_path: {reflection_path}",
            f"- proposal_path: {proposal_path}",
            f"- required_checks: {len(packet_checks)}",
            f"- missing_checks: {len(missing_checks)}",
            f"- incomplete_checks: {len(incomplete_checks)}",
            f"- proposal_errors: {len(proposal_errors)}",
        ]
        if missing_checks:
            lines.extend(["", "## Missing Checks", *[f"- {item}" for item in missing_checks]])
        if incomplete_checks:
            lines.extend(["", "## Incomplete Checks", *[f"- {item}" for item in incomplete_checks]])
        if proposal_errors:
            lines.extend(["", "## Proposal Errors", *[f"- {item}" for item in proposal_errors]])
        print("\n".join(lines) + "\n", end="")
        return 0 if ok else 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

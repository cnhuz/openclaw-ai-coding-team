#!/usr/bin/env python3
"""AI-assisted change governance (Phase 0 / MVP)

- Classify PR risk (Low/Medium/High) based on configurable rules.
- Emit explainable reasons + structured summary.
- Enforce merge gate by failing the workflow job when policy is not satisfied.

Design constraints:
- No external services.
- No third-party Python deps (config file uses JSON that is valid YAML 1.2).

NOTE: This is intended to be run inside a GitHub Actions workflow.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SEVERITY_RANK = {"Low": 1, "Medium": 2, "High": 3}


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    rule_name: str
    severity: str
    reasons: list[str]


class GH:
    def __init__(self, token: str, repo_full_name: str):
        self.token = token
        self.repo = repo_full_name
        self.api = "https://api.github.com"

    def request(self, method: str, path: str, query: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> Any:
        url = self.api + path
        if query:
            url += "?" + urllib.parse.urlencode(query)

        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-change-governance",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {method} {path}: HTTP {e.code}: {raw}") from e

    def paginate(self, method: str, path: str, query: dict[str, str] | None = None) -> Iterable[Any]:
        page = 1
        while True:
            q = dict(query or {})
            q.update({"per_page": "100", "page": str(page)})
            data = self.request(method, path, query=q)
            if not isinstance(data, list):
                raise RuntimeError(f"Expected list from {path}, got {type(data)}")
            if not data:
                return
            for item in data:
                yield item
            page += 1


def load_event(event_path: str) -> dict[str, Any]:
    p = Path(event_path)
    if not p.exists():
        raise RuntimeError(f"GITHUB_EVENT_PATH not found: {event_path}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_config(config_path: str) -> dict[str, Any]:
    p = Path(config_path)
    if not p.exists():
        raise RuntimeError(f"Config not found: {config_path}")
    # Config file is JSON (valid YAML 1.2). Keep it dependency-free.
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Config parse failed (expected JSON that is valid YAML 1.2). path={config_path}, error={e}"
        ) from e


def severity_max(a: str, b: str) -> str:
    return a if SEVERITY_RANK.get(a, 0) >= SEVERITY_RANK.get(b, 0) else b


def match_any_glob(path: str, patterns: list[str]) -> tuple[bool, list[str]]:
    matched: list[str] = []
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            matched.append(pat)
    return (len(matched) > 0), matched


def match_any_keyword(patch: str, keywords: list[str]) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for kw in keywords:
        try:
            if re.search(kw, patch, flags=re.IGNORECASE | re.MULTILINE):
                hits.append(kw)
        except re.error as e:
            raise RuntimeError(f"Invalid regex keyword: {kw} ({e})") from e
    return (len(hits) > 0), hits


def classify(pr_files: list[dict[str, Any]], rules: list[dict[str, Any]]) -> tuple[str, list[RuleMatch]]:
    matches: list[RuleMatch] = []
    overall = "Low"

    for rule in rules:
        rid = str(rule.get("id", "rule"))
        rname = str(rule.get("name", rid))
        severity = str(rule.get("severity", "Low"))
        if severity not in SEVERITY_RANK:
            raise RuntimeError(f"Unknown severity '{severity}' for rule {rid}")

        paths = rule.get("paths") or []
        keywords = rule.get("keywords") or []
        if not isinstance(paths, list) or not isinstance(keywords, list):
            raise RuntimeError(f"Rule {rid} paths/keywords must be lists")

        reasons: list[str] = []

        for f in pr_files:
            filename = str(f.get("filename", ""))
            patch = f.get("patch") or ""

            if paths:
                ok, pats = match_any_glob(filename, [str(x) for x in paths])
                if ok:
                    reasons.append(f"file '{filename}' matched path patterns: {', '.join(pats)}")

            if keywords and patch:
                ok, hits = match_any_keyword(patch, [str(x) for x in keywords])
                if ok:
                    reasons.append(f"file '{filename}' patch matched keywords: {', '.join(hits)}")

        if reasons:
            matches.append(RuleMatch(rule_id=rid, rule_name=rname, severity=severity, reasons=reasons))
            overall = severity_max(overall, severity)

    # Heuristic: if ONLY docs rules matched, keep Low.
    # (If docs_only rule exists and it was the only match.)
    if matches:
        non_docs = [m for m in matches if m.rule_id != "docs_only"]
        if not non_docs:
            overall = "Low"

    return overall, matches


def latest_review_state_by_user(reviews: list[dict[str, Any]]) -> dict[str, str]:
    # Use the latest submitted_at per user.
    per_user: dict[str, tuple[str, str]] = {}
    for r in reviews:
        user = r.get("user") or {}
        login = str(user.get("login", ""))
        if not login:
            continue
        state = str(r.get("state", ""))
        submitted_at = str(r.get("submitted_at") or "")
        prev = per_user.get(login)
        if prev is None or submitted_at >= prev[0]:
            per_user[login] = (submitted_at, state)
    return {u: st for u, (_t, st) in per_user.items()}


def find_codeowners(repo_root: Path, candidates: list[str]) -> Path | None:
    for rel in candidates:
        p = repo_root / rel
        if p.exists() and p.is_file():
            return p
    return None


def _codeowners_pattern_to_fnmatch(pattern: str) -> list[str]:
    # Very small subset / best-effort matcher.
    # CODEOWNERS patterns are gitignore-like; we keep this conservative and predictable.
    p = pattern.strip()
    if not p:
        return []

    anchored = p.startswith("/")
    if anchored:
        p = p[1:]

    if p.endswith("/"):
        p = p + "*"

    # If no slash, match basename anywhere.
    if "/" not in p:
        return [p, f"**/{p}"]

    return [p] if anchored else [p, f"**/{p}"]


def parse_codeowners(path: Path) -> list[tuple[list[str], list[str]]]:
    entries: list[tuple[list[str], list[str]]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Format: pattern owner1 owner2 ...
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = parts[1:]
        pats = _codeowners_pattern_to_fnmatch(pattern)
        if not pats:
            continue
        entries.append((pats, owners))
    return entries


def owners_for_file(filename: str, entries: list[tuple[list[str], list[str]]]) -> list[str]:
    matched: list[str] = []
    for patterns, owners in entries:
        ok, _ = match_any_glob(filename, patterns)
        if ok:
            matched = owners  # last match wins
    return matched


def evaluate_required_checks(gh: GH, sha: str, required: list[str]) -> tuple[bool, list[str]]:
    required = [str(x) for x in required]
    if not required:
        return True, []

    ok_set: set[str] = set()

    # check-runs
    cr = gh.request("GET", f"/repos/{gh.repo}/commits/{sha}/check-runs", query={"per_page": "100"})
    if isinstance(cr, dict):
        for run in cr.get("check_runs", []) or []:
            name = str(run.get("name", ""))
            conclusion = str(run.get("conclusion", ""))
            if name and conclusion == "success":
                ok_set.add(name)

    # status contexts
    st = gh.request("GET", f"/repos/{gh.repo}/commits/{sha}/status")
    if isinstance(st, dict):
        for s in st.get("statuses", []) or []:
            ctx = str(s.get("context", ""))
            state = str(s.get("state", ""))
            if ctx and state == "success":
                ok_set.add(ctx)

    missing = [c for c in required if c not in ok_set]
    return (len(missing) == 0), missing


def post_or_update_comment(gh: GH, pr_number: int, body: str, marker: str) -> None:
    # Keep a single rolling comment to avoid timeline spam.
    comments = list(gh.paginate("GET", f"/repos/{gh.repo}/issues/{pr_number}/comments"))
    target_id: int | None = None
    for c in reversed(comments):
        cb = str(c.get("body", ""))
        if marker in cb:
            target_id = int(c.get("id"))
            break

    payload = {"body": body}
    if target_id is None:
        gh.request("POST", f"/repos/{gh.repo}/issues/{pr_number}/comments", body=payload)
    else:
        gh.request("PATCH", f"/repos/{gh.repo}/issues/comments/{target_id}", body=payload)


def build_summary(
    *,
    risk: str,
    matches: list[RuleMatch],
    approvals: int,
    required_approvals: int,
    require_codeowner: bool,
    codeowner_status: tuple[bool, str],
    required_checks: list[str],
    checks_status: tuple[bool, list[str]],
    pr_files: list[dict[str, Any]],
    gate_ok: bool,
    config_path: str,
    elapsed_ms: int,
    comment_marker: str,
) -> str:
    ok_checks, missing_checks = checks_status
    ok_codeowner, codeowner_note = codeowner_status

    lines: list[str] = []
    lines.append(comment_marker)
    lines.append("# AI Change Governance")
    lines.append("")
    lines.append(f"- **Risk:** `{risk}`")
    lines.append(f"- **Files changed:** {len(pr_files)}")
    lines.append(f"- **Config:** `{config_path}`")
    lines.append(f"- **Runtime:** {elapsed_ms}ms")
    lines.append("")

    lines.append("## Why")
    if not matches:
        lines.append("- No rules matched (default Low).")
    else:
        for m in matches:
            lines.append(f"- `{m.severity}` `{m.rule_id}` — {m.rule_name}")
            # Limit verbosity
            for r in m.reasons[:8]:
                lines.append(f"  - {r}")
            if len(m.reasons) > 8:
                lines.append(f"  - (and {len(m.reasons) - 8} more)")
    lines.append("")

    lines.append("## Gate evaluation")
    lines.append(f"- Result: {'✅ pass' if gate_ok else '❌ fail'}")
    lines.append(f"- Approvals: {approvals} / required {required_approvals}")
    if require_codeowner:
        lines.append(f"- CODEOWNERS approval: {'ok' if ok_codeowner else 'missing'}")
        if codeowner_note:
            lines.append(f"  - {codeowner_note}")
    if required_checks:
        lines.append(f"- Required checks: {'ok' if ok_checks else 'missing/failed'}")
        if missing_checks:
            for c in missing_checks:
                lines.append(f"  - missing/failed: {c}")
    lines.append("")

    lines.append("## Suggested review focus")
    if risk == "High":
        lines.append("- Verify permissions / IaC / prod config changes are intentional and scoped.")
        lines.append("- Ask for rollback steps + minimal tests if not provided.")
    elif risk == "Medium":
        lines.append("- Verify behavior change is covered by tests.")
    else:
        lines.append("- Quick sanity review.")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="AI change governance for GitHub PRs")
    parser.add_argument("--config-path", default=os.environ.get("AICG_CONFIG", ".github/ai-change-governance.yml"))
    args = parser.parse_args()

    start = time.time()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
    if not token:
        raise SystemExit("Missing GITHUB_TOKEN in environment")

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("Missing GITHUB_EVENT_PATH")

    event = load_event(event_path)

    # pull_request and pull_request_review events both include pull_request
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        raise SystemExit("This workflow must run on pull_request or pull_request_review events")

    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        repo_obj = (event.get("repository") or {})
        repo = str(repo_obj.get("full_name", ""))
    if not repo:
        raise SystemExit("Missing repository context (GITHUB_REPOSITORY)")

    pr_number = int(pr.get("number"))
    head_sha = str((pr.get("head") or {}).get("sha", ""))
    if not head_sha:
        raise SystemExit("Missing pull_request.head.sha")

    gh = GH(token=token, repo_full_name=repo)

    cfg = load_config(args.config_path)
    rules = cfg.get("rules") or []
    policy = cfg.get("policy") or {}
    comment_cfg = cfg.get("comment") or {}
    comment_mode = str(comment_cfg.get("mode", "update"))
    comment_marker = str(comment_cfg.get("marker", "<!-- ai-change-governance -->"))

    if not isinstance(rules, list) or not isinstance(policy, dict):
        raise SystemExit("Invalid config: rules must be list; policy must be object")

    pr_files = list(gh.paginate("GET", f"/repos/{repo}/pulls/{pr_number}/files"))

    risk, matches = classify(pr_files, rules)

    # Policy lookup per risk
    p = policy.get(risk) or {}
    required_approvals = int(p.get("required_approvals", 0))
    require_codeowner = bool(p.get("require_codeowner_approval", False))
    required_checks = p.get("required_checks") or []
    if not isinstance(required_checks, list):
        raise SystemExit("Invalid config: policy.<Risk>.required_checks must be a list")

    # approvals
    reviews = list(gh.paginate("GET", f"/repos/{repo}/pulls/{pr_number}/reviews"))
    state_by_user = latest_review_state_by_user(reviews)
    approvals = sum(1 for st in state_by_user.values() if st == "APPROVED")

    # CODEOWNERS
    repo_root = Path(os.getcwd())
    codeowner_ok = True
    codeowner_note = ""
    if require_codeowner:
        co_cfg = cfg.get("codeowners") or {}
        candidates = co_cfg.get("paths") or ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]
        if not isinstance(candidates, list):
            raise SystemExit("Invalid config: codeowners.paths must be list")

        co_path = find_codeowners(repo_root, [str(x) for x in candidates])
        if not co_path:
            codeowner_ok = False
            codeowner_note = "CODEOWNERS file not found (searched: " + ", ".join([str(x) for x in candidates]) + ")"
        else:
            entries = parse_codeowners(co_path)
            owners: set[str] = set()
            for f in pr_files:
                filename = str(f.get("filename", ""))
                for o in owners_for_file(filename, entries):
                    owners.add(o)

            user_owners = sorted([o for o in owners if o.startswith("@") and "/" not in o[1:]])
            team_owners = sorted([o for o in owners if o.startswith("@") and "/" in o[1:]])

            approved_users = {u for u, st in state_by_user.items() if st == "APPROVED"}

            # user owners
            ok_user = any(o[1:] in approved_users for o in user_owners)

            # team owners (cannot verify membership without extra permissions)
            team_mode = str(((co_cfg.get("team_owners") or {}).get("mode")) or "strict")
            if team_owners:
                if team_mode == "any_approval":
                    ok_team = approvals > 0
                else:
                    ok_team = False
            else:
                ok_team = True

            codeowner_ok = ok_user and ok_team

            parts: list[str] = [f"CODEOWNERS: {co_path}"]
            if user_owners:
                parts.append("owners=" + ", ".join(user_owners))
            if team_owners:
                parts.append("team_owners=" + ", ".join(team_owners) + f" (mode={team_mode})")
            if not codeowner_ok:
                if not user_owners and team_owners and team_mode == "strict":
                    parts.append("team owners present but cannot be verified without team membership visibility")
                elif user_owners and not ok_user:
                    parts.append("no approving review from matched user codeowners")
            codeowner_note = "; ".join(parts)

    # checks
    checks_ok, missing_checks = evaluate_required_checks(gh, head_sha, [str(x) for x in required_checks])

    gate_ok = True
    if approvals < required_approvals:
        gate_ok = False
    if require_codeowner and not codeowner_ok:
        gate_ok = False
    if required_checks and not checks_ok:
        gate_ok = False

    elapsed_ms = int((time.time() - start) * 1000)

    summary = build_summary(
        risk=risk,
        matches=matches,
        approvals=approvals,
        required_approvals=required_approvals,
        require_codeowner=require_codeowner,
        codeowner_status=(codeowner_ok, codeowner_note),
        required_checks=[str(x) for x in required_checks],
        checks_status=(checks_ok, missing_checks),
        pr_files=pr_files,
        gate_ok=gate_ok,
        config_path=args.config_path,
        elapsed_ms=elapsed_ms,
        comment_marker=comment_marker,
    )

    # Job summary
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        try:
            Path(step_summary_path).write_text(summary, encoding="utf-8")
        except Exception as e:
            print(f"WARN: failed to write GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    # PR comment
    if comment_mode in {"always", "update"} or (comment_mode == "on-fail" and not gate_ok):
        try:
            if comment_mode == "update":
                post_or_update_comment(gh, pr_number, summary, comment_marker)
            else:
                gh.request("POST", f"/repos/{repo}/issues/{pr_number}/comments", body={"body": summary})
        except Exception as e:
            # Do not silently pass; print a clear diagnostic but still enforce gate by exit code.
            print(f"ERROR: failed to post PR comment: {e}", file=sys.stderr)

    # Final gate
    if not gate_ok:
        print(summary)
        return 2

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

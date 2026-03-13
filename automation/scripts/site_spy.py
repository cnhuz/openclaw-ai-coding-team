#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


DEFAULT_API_URL = "https://detect.coolify.vkuprin.com/api/v1"
DEFAULT_AUTH_URL = "https://sitespy.app/dashboard"
DEFAULT_RSS_BASE_URL = "https://sitespy.app/api/rss"

DEFAULT_TIMEOUT_SECS = 30
DEFAULT_MAX_CHARS = 20_000


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


@dataclass
class TruncatedText:
    text: str
    truncated: bool
    original_chars: int


def truncate_text(value: str, max_chars: int) -> TruncatedText:
    if max_chars <= 0:
        return TruncatedText(text="", truncated=True, original_chars=len(value))
    if len(value) <= max_chars:
        return TruncatedText(text=value, truncated=False, original_chars=len(value))
    return TruncatedText(text=value[:max_chars], truncated=True, original_chars=len(value))


def require_api_key(api_key: str, auth_url: str) -> None:
    if api_key:
        return
    raise SystemExit(
        f"Missing SITE_SPY_API_KEY. Ask the user to open {auth_url} → Settings → API and provide an API key via env var SITE_SPY_API_KEY."
    )


def build_url(api_url: str, path: str, query: dict[str, str] | None = None) -> str:
    base = api_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = urllib.parse.urljoin(base + "/", path.lstrip("/"))
    if query:
        q = {k: v for k, v in query.items() if v is not None and v != ""}
        if q:
            url = url + "?" + urllib.parse.urlencode(q)
    return url


def http_json(
    *,
    api_url: str,
    api_key: str,
    auth_url: str,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECS,
) -> Any:
    require_api_key(api_key, auth_url)

    url = build_url(api_url, path, query)
    data = None
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as err:
        # Never print API key; include only status + trimmed body.
        raw = err.read() if hasattr(err, "read") else b""
        details = raw.decode("utf-8", errors="replace")
        details = details.strip()
        if len(details) > 800:
            details = details[:800] + "…(truncated)"

        if err.code in (401, 403):
            raise SystemExit(
                f"Auth failed (HTTP {err.code}). Verify SITE_SPY_API_KEY is valid. Get/refresh key at {auth_url}. Response: {details}"
            )
        raise SystemExit(f"API error (HTTP {err.code}). Response: {details}")

    text = raw.decode("utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    # Some endpoints may return text; return as-is.
    return text


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def extract_candidate_text(payload: Any) -> str:
    # Heuristic extraction: prefer common string-bearing keys.
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in (
            "text",
            "content",
            "contents",
            "html",
            "body",
            "snapshot",
            "difference",
            "diff",
            "raw",
            "data",
        ):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                return v
        # fallback
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def summarize_diff_text(diff_text: str, *, max_items: int = 12) -> tuple[list[str], list[str]]:
    """Extract additions/deletions from a unified-ish diff text.

    We intentionally keep this conservative: only lines starting with '+'/'-' and
    not '+++'/'---'. If no diff markers exist, returns empty lists.
    """
    added: list[str] = []
    removed: list[str] = []

    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") and not line.startswith("++"):
            s = line[1:].strip()
            if s:
                added.append(s)
        elif line.startswith("-") and not line.startswith("--"):
            s = line[1:].strip()
            if s:
                removed.append(s)
        if len(added) >= max_items and len(removed) >= max_items:
            break

    return added[:max_items], removed[:max_items]


def format_md_summary(summary: dict[str, Any]) -> str:
    added = summary.get("added", []) or []
    removed = summary.get("removed", []) or []
    refs = summary.get("references", {}) or {}

    lines: list[str] = []
    lines.append(f"# Site Spy change summary")
    lines.append("")
    lines.append(f"- watch: `{summary.get('watch_uuid','')}`")
    lines.append(f"- changed_at: `{summary.get('changed_at','')}`")
    lines.append(f"- from: `{summary.get('from_timestamp','')}`")
    lines.append(f"- to: `{summary.get('to_timestamp','')}`")
    if summary.get("diff_truncated"):
        lines.append(f"- note: diff truncated (original_chars={summary.get('diff_original_chars')})")
    lines.append("")

    lines.append("## Added")
    if added:
        for item in added:
            lines.append(f"- {item}")
    else:
        lines.append("- (none detected)")
    lines.append("")

    lines.append("## Removed")
    if removed:
        for item in removed:
            lines.append(f"- {item}")
    else:
        lines.append("- (none detected)")
    lines.append("")

    lines.append("## References")
    for k in ("watch_uuid", "from_timestamp", "to_timestamp"):
        if refs.get(k):
            lines.append(f"- {k}: `{refs[k]}`")

    return "\n".join(lines).strip() + "\n"


def cmd_auth_status(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)
    if not api_key:
        print_json(
            {
                "authenticated": False,
                "auth_url": auth_url,
                "message": f"Not connected. Ask the user to open {auth_url} → Settings → API and set SITE_SPY_API_KEY.",
            }
        )
        return
    # Validate key by hitting /watch.
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    _ = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/watch",
        timeout=args.timeout,
    )
    print_json({"authenticated": True, "api_url": api_url})


def cmd_list_watches(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    query: dict[str, str] = {}
    if args.tag:
        query["tag"] = args.tag

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/watch",
        query=query if query else None,
        timeout=args.timeout,
    )
    print_json(data)


def cmd_create_watch(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    body: dict[str, Any] = {"url": args.url}
    if args.title:
        body["title"] = args.title
    if args.tag:
        body["tag"] = args.tag
    if args.fetch_backend:
        body["fetch_backend"] = args.fetch_backend

    if args.check_hours is not None or args.check_minutes is not None:
        t: dict[str, int] = {}
        if args.check_hours is not None:
            t["hours"] = args.check_hours
        if args.check_minutes is not None:
            t["minutes"] = args.check_minutes
        body["time_between_check"] = t
        body["time_between_check_use_default"] = False

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="POST",
        path="/watch",
        body=body,
        timeout=args.timeout,
    )
    print_json(data)


def cmd_get_watch(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path=f"/watch/{args.uuid}",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_update_watch(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    body: dict[str, Any] = {}
    for key in ("title", "paused", "notification_muted", "tag", "url"):
        v = getattr(args, key)
        if v is not None:
            body[key] = v

    if args.check_hours is not None or args.check_minutes is not None:
        t: dict[str, int] = {}
        if args.check_hours is not None:
            t["hours"] = args.check_hours
        if args.check_minutes is not None:
            t["minutes"] = args.check_minutes
        body["time_between_check"] = t
        body["time_between_check_use_default"] = False

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="PUT",
        path=f"/watch/{args.uuid}",
        body=body,
        timeout=args.timeout,
    )
    print_json(data)


def cmd_delete_watch(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="DELETE",
        path=f"/watch/{args.uuid}",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_search_watches(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/search",
        query={"q": args.query},
        timeout=args.timeout,
    )
    print_json(data)


def cmd_list_tags(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/tags",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_trigger_recheck(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    query: dict[str, str] = {"recheck_all": "1"}
    if args.tag:
        query["tag"] = args.tag

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/watch",
        query=query,
        timeout=args.timeout,
    )
    print_json(data)


def cmd_get_change_history(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path=f"/watch/{args.uuid}/history",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_get_snapshot(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path=f"/watch/{args.uuid}/history/{urllib.parse.quote(args.timestamp, safe='')}"
        ,
        timeout=args.timeout,
    )

    # Enforce truncation of any extracted text.
    max_chars = args.max_chars
    candidate = extract_candidate_text(data)
    truncated = truncate_text(candidate, max_chars)

    out = {
        "watch_uuid": args.uuid,
        "timestamp": args.timestamp,
        "snapshot_truncated": truncated.truncated,
        "snapshot_original_chars": truncated.original_chars,
        "snapshot": truncated.text,
    }
    print_json(out)


def cmd_get_diff(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    path = f"/watch/{args.uuid}/difference/{urllib.parse.quote(args.from_timestamp, safe='')}/{urllib.parse.quote(args.to_timestamp, safe='')}"
    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path=path,
        timeout=args.timeout,
    )

    max_chars = args.max_chars
    candidate = extract_candidate_text(data)
    truncated = truncate_text(candidate, max_chars)

    out = {
        "watch_uuid": args.uuid,
        "from_timestamp": args.from_timestamp,
        "to_timestamp": args.to_timestamp,
        "diff_truncated": truncated.truncated,
        "diff_original_chars": truncated.original_chars,
        "diff": truncated.text,
    }
    print_json(out)


def cmd_rss_settings(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path="/rss",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_rss_generate_token(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="POST",
        path="/rss",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_rss_revoke_token(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    data = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="DELETE",
        path="/rss",
        timeout=args.timeout,
    )
    print_json(data)


def cmd_rss_urls(args: argparse.Namespace) -> None:
    rss_base = os.environ.get("SITE_SPY_RSS_BASE_URL", DEFAULT_RSS_BASE_URL).rstrip("/")

    token = args.token
    all_url = f"{rss_base}?token={urllib.parse.quote(token)}"

    out: dict[str, str] = {"all": all_url}
    if args.watch:
        out["watch"] = f"{rss_base}/watch/{urllib.parse.quote(args.watch)}?token={urllib.parse.quote(token)}"
    if args.tag:
        out["tag"] = f"{rss_base}/tag/{urllib.parse.quote(args.tag)}?token={urllib.parse.quote(token)}"

    print_json(
        {
            "rss_base": rss_base,
            "token_hint": token[:4] + "***" if token else "",
            "urls": out,
        }
    )


def cmd_summarize_change(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SITE_SPY_API_KEY", "")
    api_url = os.environ.get("SITE_SPY_API_URL", DEFAULT_API_URL)
    auth_url = os.environ.get("SITE_SPY_AUTH_URL", DEFAULT_AUTH_URL)

    path = f"/watch/{args.uuid}/difference/{urllib.parse.quote(args.from_timestamp, safe='')}/{urllib.parse.quote(args.to_timestamp, safe='')}"
    diff_payload = http_json(
        api_url=api_url,
        api_key=api_key,
        auth_url=auth_url,
        method="GET",
        path=path,
        timeout=args.timeout,
    )

    candidate = extract_candidate_text(diff_payload)
    truncated = truncate_text(candidate, args.max_chars)
    added, removed = summarize_diff_text(truncated.text)

    summary = {
        "watch_uuid": args.uuid,
        "changed_at": args.to_timestamp,
        "from_timestamp": args.from_timestamp,
        "to_timestamp": args.to_timestamp,
        "added": added,
        "removed": removed,
        "diff_truncated": truncated.truncated,
        "diff_original_chars": truncated.original_chars,
        "references": {
            "watch_uuid": args.uuid,
            "from_timestamp": args.from_timestamp,
            "to_timestamp": args.to_timestamp,
        },
        "generated_at": now_iso(),
    }

    if args.format == "json":
        print_json(summary)
        return

    if args.format == "md":
        print(format_md_summary(summary))
        return

    raise SystemExit(f"unknown format: {args.format}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="site_spy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            Site Spy API CLI helper (repo-local).

            Auth:
              export SITE_SPY_API_KEY=...   # never commit or log this

            Optional overrides:
              export SITE_SPY_API_URL=https://detect.coolify.vkuprin.com/api/v1
              export SITE_SPY_AUTH_URL=https://sitespy.app/dashboard
              export SITE_SPY_RSS_BASE_URL=https://sitespy.app/api/rss
            """
        ).strip(),
    )

    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECS, help="HTTP timeout seconds")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth-status", help="Validate SITE_SPY_API_KEY by calling /watch").set_defaults(func=cmd_auth_status)

    sp = sub.add_parser("list-watches", help="List watches")
    sp.add_argument("--tag", default=None, help="Filter by tag UUID")
    sp.set_defaults(func=cmd_list_watches)

    sp = sub.add_parser("create-watch", help="Create a watch")
    sp.add_argument("--url", required=True)
    sp.add_argument("--title", default=None)
    sp.add_argument("--tag", default=None)
    sp.add_argument("--check-hours", type=int, default=None)
    sp.add_argument("--check-minutes", type=int, default=None)
    sp.add_argument("--fetch-backend", choices=["html_requests", "html_webdriver"], default=None)
    sp.set_defaults(func=cmd_create_watch)

    sp = sub.add_parser("get-watch", help="Get watch")
    sp.add_argument("--uuid", required=True)
    sp.set_defaults(func=cmd_get_watch)

    sp = sub.add_parser("update-watch", help="Update watch")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--title", default=None)
    sp.add_argument("--paused", type=lambda v: v.lower() == "true", default=None)
    sp.add_argument("--notification-muted", type=lambda v: v.lower() == "true", default=None)
    sp.add_argument("--tag", default=None)
    sp.add_argument("--check-hours", type=int, default=None)
    sp.add_argument("--check-minutes", type=int, default=None)
    sp.add_argument("--url", default=None)
    sp.set_defaults(func=cmd_update_watch)

    sp = sub.add_parser("delete-watch", help="Delete watch")
    sp.add_argument("--uuid", required=True)
    sp.set_defaults(func=cmd_delete_watch)

    sp = sub.add_parser("search-watches", help="Search watches by URL/title")
    sp.add_argument("--query", required=True)
    sp.set_defaults(func=cmd_search_watches)

    sp = sub.add_parser("list-tags", help="List tags")
    sp.set_defaults(func=cmd_list_tags)

    sp = sub.add_parser("trigger-recheck", help="Trigger immediate recheck")
    sp.add_argument("--tag", default=None, help="Optional tag UUID filter")
    sp.set_defaults(func=cmd_trigger_recheck)

    sp = sub.add_parser("get-change-history", help="Get change timestamps")
    sp.add_argument("--uuid", required=True)
    sp.set_defaults(func=cmd_get_change_history)

    sp = sub.add_parser("get-snapshot", help="Get snapshot at timestamp (truncated)")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--timestamp", required=True)
    sp.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    sp.set_defaults(func=cmd_get_snapshot)

    sp = sub.add_parser("get-diff", help="Get diff between two timestamps (truncated)")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--from", dest="from_timestamp", required=True)
    sp.add_argument("--to", dest="to_timestamp", required=True)
    sp.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    sp.set_defaults(func=cmd_get_diff)

    sp = sub.add_parser("summarize-change", help="Generate a structured summary from diff")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--from", dest="from_timestamp", required=True)
    sp.add_argument("--to", dest="to_timestamp", required=True)
    sp.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    sp.add_argument("--format", choices=["json", "md"], default="json")
    sp.set_defaults(func=cmd_summarize_change)

    sp = sub.add_parser("rss-settings", help="Get RSS settings")
    sp.set_defaults(func=cmd_rss_settings)

    sp = sub.add_parser("rss-generate-token", help="Generate/regenerate RSS token")
    sp.set_defaults(func=cmd_rss_generate_token)

    sp = sub.add_parser("rss-revoke-token", help="Revoke RSS token")
    sp.set_defaults(func=cmd_rss_revoke_token)

    sp = sub.add_parser("rss-urls", help="Build RSS URLs from token")
    sp.add_argument("--token", required=True)
    sp.add_argument("--watch", default=None)
    sp.add_argument("--tag", default=None)
    sp.set_defaults(func=cmd_rss_urls)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

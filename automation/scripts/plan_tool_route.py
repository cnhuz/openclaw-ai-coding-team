#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def browser_available() -> bool:
    try:
        result = subprocess.run(
            ["openclaw", "browser", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("enabled"))


def domain_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed.netloc.lower().replace("www.", "")


def load_inventory(path: Path) -> set[str]:
    payload = load_json(path, {})
    values = payload.get("eligible_skills")
    if not isinstance(values, list):
        return set()
    return {item for item in values if isinstance(item, str) and item}


def tool_available(tool_id: str, eligible_skills: set[str], browser_enabled: bool) -> bool:
    if tool_id in {"web.search", "web.fetch"}:
        return True
    if tool_id == "browser":
        return browser_enabled
    if tool_id.startswith("skill:"):
        return tool_id.split(":", 1)[1] in eligible_skills
    return False


def match_site(sites: list[dict[str, Any]], site_id: str, domain: str) -> dict[str, Any] | None:
    if site_id:
        for site in sites:
            if site.get("site_id") == site_id:
                return site
    if domain:
        for site in sites:
            for item in normalize_list(site.get("domains")):
                if item.replace("www.", "") == domain:
                    return site
    return None


def prepend_unique(base: list[str], extras: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in [*extras, *base]:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def route_for_site(
    site: dict[str, Any],
    settings: dict[str, Any],
    force_login: bool,
    force_js_heavy: bool,
    target_kind: str,
    eligible_skills: set[str],
) -> list[str]:
    route = normalize_list(site.get("preferred_tools"))
    learning = site.get("learning")
    if isinstance(learning, dict):
        route = [*normalize_list(learning.get("learned_preferred_tools")), *route]
        avoid = set(normalize_list(learning.get("learned_avoid_tools")))
    else:
        avoid = set()
    route.extend(normalize_list(site.get("fallback_tools")))
    if not route:
        route = normalize_list(settings.get("defaultPublicRoute"))

    access = site.get("access")
    if force_login or access == "login-required":
        route = prepend_unique(route, normalize_list(settings.get("defaultLoginRoute")))
    elif force_js_heavy or bool(site.get("js_heavy")):
        route = prepend_unique(route, normalize_list(settings.get("defaultInteractiveRoute")))

    if target_kind == "feed" and normalize_list(site.get("feed_urls")) and "blogwatcher" in eligible_skills:
        route = prepend_unique(route, ["skill:blogwatcher", "web.fetch"])

    if isinstance(learning, dict):
        last_failure_kind = learning.get("last_failure_kind")
        if last_failure_kind in {"login-required", "auth", "captcha", "blocked", "js-heavy", "render-failed"}:
            route = prepend_unique(route, ["browser"])
        if last_failure_kind in {"feed-unavailable", "rate-limited"} and "blogwatcher" in eligible_skills:
            route = prepend_unique(route, ["skill:blogwatcher"])

    seen: set[str] = set()
    result: list[str] = []
    for item in route:
        if item in avoid or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan the best tool route for a site/domain.")
    parser.add_argument("--site-profiles", default="data/research/site_profiles.json")
    parser.add_argument("--tool-profiles", default="data/research/tool_profiles.json")
    parser.add_argument("--inventory", default="data/skills/inventory.json")
    parser.add_argument("--site-id", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--domain", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--channel", default="")
    parser.add_argument("--login-required", action="store_true")
    parser.add_argument("--js-heavy", action="store_true")
    parser.add_argument("--target-kind", choices=["hot_page", "feed", "query", "article", "post", "timeline", "unknown"], default="unknown")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    site_profiles = load_json(Path(args.site_profiles).expanduser(), {"sites": [], "settings": {}})
    tool_profiles = load_json(Path(args.tool_profiles).expanduser(), {"tools": [], "settings": {}})
    sites = site_profiles.get("sites")
    if not isinstance(sites, list):
        sites = []
    settings: dict[str, Any] = {}
    tool_settings = tool_profiles.get("settings")
    if isinstance(tool_settings, dict):
        settings.update(tool_settings)
    site_settings = site_profiles.get("settings")
    if isinstance(site_settings, dict):
        settings.update(site_settings)

    input_domain = args.domain.strip()
    if not input_domain and args.url.strip():
        input_domain = domain_from_url(args.url)

    matched = match_site([item for item in sites if isinstance(item, dict)], args.site_id.strip(), input_domain)
    if matched is None:
        matched = {
            "site_id": args.site_id.strip() or input_domain or "generic-public-web",
            "label": args.site_id.strip() or input_domain or "Generic Public Web",
            "domains": [input_domain] if input_domain else [],
            "channel": args.channel.strip() or "public-web",
            "access": "login-required" if args.login_required else "public",
            "js_heavy": bool(args.js_heavy),
            "hot_pages": [],
            "feed_urls": [],
            "quality_signals": [],
            "learning": {},
        }
        requires_registration = True
    else:
        requires_registration = False

    eligible_skills = load_inventory(Path(args.inventory).expanduser())
    browser_enabled = browser_available()
    route = route_for_site(matched, settings, args.login_required, args.js_heavy, args.target_kind, eligible_skills)
    available_route = [item for item in route if tool_available(item, eligible_skills, browser_enabled)]
    if not available_route:
        default_route = normalize_list(settings.get("defaultPublicRoute"))
        available_route = [item for item in default_route if tool_available(item, eligible_skills, browser_enabled)]

    result = {
        "ok": True,
        "site_id": matched.get("site_id"),
        "label": matched.get("label"),
        "domain": input_domain,
        "channel": matched.get("channel"),
        "access": matched.get("access"),
        "js_heavy": bool(matched.get("js_heavy")),
        "route": available_route,
        "requires_registration": requires_registration,
        "hot_pages": normalize_list(matched.get("hot_pages")),
        "feed_urls": normalize_list(matched.get("feed_urls")),
        "quality_signals": normalize_list(matched.get("quality_signals")),
        "browser_available": browser_enabled,
        "eligible_skills": sorted(eligible_skills),
    }

    if args.format == "md":
        lines = [
            "# tool_route",
            "",
            f"- site_id: {result['site_id']}",
            f"- label: {result['label']}",
            f"- domain: {result['domain'] or '-'}",
            f"- access: {result['access']}",
            f"- js_heavy: {'yes' if result['js_heavy'] else 'no'}",
            f"- browser_available: {'yes' if browser_enabled else 'no'}",
            f"- requires_registration: {'yes' if requires_registration else 'no'}",
            f"- route: {', '.join(available_route) if available_route else '-'}",
        ]
        hot_pages = result["hot_pages"]
        if hot_pages:
            lines.append("- hot_pages:")
            lines.extend(f"  - {item}" for item in hot_pages)
        feed_urls = result["feed_urls"]
        if feed_urls:
            lines.append("- feed_urls:")
            lines.extend(f"  - {item}" for item in feed_urls)
        quality = result["quality_signals"]
        if quality:
            lines.append("- quality_signals:")
            lines.extend(f"  - {item}" for item in quality)
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

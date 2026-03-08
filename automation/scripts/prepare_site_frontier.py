#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from plan_tool_route import browser_available, load_inventory, load_json, normalize_list, route_for_site


def topic_priority_map(path: Path) -> dict[str, float]:
    payload = load_json(path, {"topics": []})
    topics = payload.get("topics")
    if not isinstance(topics, list):
        return {}
    result: dict[str, float] = {}
    for item in topics:
        if not isinstance(item, dict):
            continue
        topic_id = item.get("topic_id")
        priority = item.get("priority")
        if not isinstance(topic_id, str) or not topic_id:
            continue
        if isinstance(priority, int):
            result[topic_id] = float(priority)
        elif isinstance(priority, float):
            result[topic_id] = priority
        else:
            result[topic_id] = 0.5
    return result


def numeric_total(values: Any) -> float:
    if not isinstance(values, dict):
        return 0.0
    total = 0.0
    for value in values.values():
        if isinstance(value, int):
            total += float(value)
        elif isinstance(value, float):
            total += value
    return total


def score_site(site: dict[str, Any], topic_scores: dict[str, float], eligible_skills: set[str], browser_enabled: bool) -> float:
    score = 0.35
    for topic_id in normalize_list(site.get("topic_tags")):
        score += topic_scores.get(topic_id, 0.4)

    learning = site.get("learning")
    if isinstance(learning, dict):
        score += min(numeric_total(learning.get("quality_by_tool")) * 0.03, 0.45)
        score += min(numeric_total(learning.get("success_by_tool")) * 0.02, 0.25)
        score -= min(numeric_total(learning.get("failure_by_tool")) * 0.015, 0.2)

    if normalize_list(site.get("feed_urls")) and "blogwatcher" in eligible_skills:
        score += 0.25
    if normalize_list(site.get("hot_pages")):
        score += 0.12
    if site.get("access") == "login-required" and not browser_enabled:
        score -= 0.35
    return score


def ordered_frontier_kinds(site: dict[str, Any]) -> list[str]:
    learning = site.get("learning")
    preferred = normalize_list(learning.get("preferred_frontier_kinds")) if isinstance(learning, dict) else []
    result: list[str] = []
    seen: set[str] = set()
    for item in [*preferred, "hot_page", "feed", "query"]:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_items(
    site: dict[str, Any],
    settings: dict[str, Any],
    eligible_skills: set[str],
    browser_enabled: bool,
    topic_scores: dict[str, float],
) -> list[dict[str, Any]]:
    site_score = score_site(site, topic_scores, eligible_skills, browser_enabled)
    items: list[dict[str, Any]] = []
    force_login = site.get("access") == "login-required"
    force_js_heavy = bool(site.get("js_heavy"))

    for kind in ordered_frontier_kinds(site):
        if kind == "hot_page":
            for index, target in enumerate(normalize_list(site.get("hot_pages"))):
                items.append(
                    {
                        "site_id": site.get("site_id"),
                        "label": site.get("label"),
                        "channel": site.get("channel"),
                        "target_kind": "hot_page",
                        "target": target,
                        "score": round(site_score + max(0.18 - index * 0.03, 0.0), 3),
                        "route": route_for_site(site, settings, force_login, force_js_heavy, "hot_page", eligible_skills),
                        "topic_tags": normalize_list(site.get("topic_tags")),
                        "reason": "site hot page",
                    }
                )
        elif kind == "feed":
            for index, target in enumerate(normalize_list(site.get("feed_urls"))):
                items.append(
                    {
                        "site_id": site.get("site_id"),
                        "label": site.get("label"),
                        "channel": site.get("channel"),
                        "target_kind": "feed",
                        "target": target,
                        "score": round(site_score + max(0.24 - index * 0.04, 0.0), 3),
                        "route": route_for_site(site, settings, force_login, force_js_heavy, "feed", eligible_skills),
                        "topic_tags": normalize_list(site.get("topic_tags")),
                        "reason": "site feed",
                    }
                )
        elif kind == "query":
            for index, target in enumerate(normalize_list(site.get("discovery_queries"))):
                items.append(
                    {
                        "site_id": site.get("site_id"),
                        "label": site.get("label"),
                        "channel": site.get("channel"),
                        "target_kind": "query",
                        "target": target,
                        "score": round(site_score + max(0.1 - index * 0.02, 0.0), 3),
                        "route": route_for_site(site, settings, force_login, force_js_heavy, "query", eligible_skills),
                        "topic_tags": normalize_list(site.get("topic_tags")),
                        "reason": "discovery query",
                    }
                )
    return items


def diversified_frontier(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    items.sort(key=lambda item: (-float(item["score"]), str(item["site_id"]), str(item["target"])))
    result: list[dict[str, Any]] = []
    site_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}

    for item in items:
        site_id = str(item["site_id"])
        target_kind = str(item["target_kind"])
        if site_counts.get(site_id, 0) >= 2:
            continue
        if kind_counts.get(target_kind, 0) >= max(2, limit // 2):
            continue
        result.append(item)
        site_counts[site_id] = site_counts.get(site_id, 0) + 1
        kind_counts[target_kind] = kind_counts.get(target_kind, 0) + 1
        if len(result) >= limit:
            return result

    for item in items:
        if item in result:
            continue
        result.append(item)
        if len(result) >= limit:
            break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare prioritized hot/feed/query frontiers for continuous exploration.")
    parser.add_argument("--site-profiles", default="data/research/site_profiles.json")
    parser.add_argument("--topic-profiles", default="data/research/topic_profiles.json")
    parser.add_argument("--inventory", default="data/skills/inventory.json")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    site_profiles = load_json(Path(args.site_profiles).expanduser(), {"sites": [], "settings": {}})
    sites = site_profiles.get("sites")
    if not isinstance(sites, list):
        sites = []
    settings = site_profiles.get("settings")
    if not isinstance(settings, dict):
        settings = {}

    topic_scores = topic_priority_map(Path(args.topic_profiles).expanduser())
    eligible_skills = load_inventory(Path(args.inventory).expanduser())
    browser_enabled = browser_available()

    items: list[dict[str, Any]] = []
    for site in sites:
        if not isinstance(site, dict):
            continue
        if site.get("status") not in {None, "", "active"}:
            continue
        items.extend(build_items(site, settings, eligible_skills, browser_enabled, topic_scores))

    selected = diversified_frontier(items, args.limit)

    if args.format == "md":
        lines = ["# site_frontier", ""]
        if not selected:
            lines.append("- no frontier items")
        for item in selected:
            lines.append(
                f"- `{item['site_id']}` | kind={item['target_kind']} | score={item['score']:.2f} | "
                f"route={', '.join(item['route']) if item['route'] else '-'} | target={item['target']}"
            )
        print("\n".join(lines) + "\n", end="")
        return 0

    print(json.dumps({"ok": True, "count": len(selected), "frontier": selected}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

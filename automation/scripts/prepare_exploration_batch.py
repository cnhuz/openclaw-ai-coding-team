#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PRIORITY_WEIGHT = {
    "P0": 1.35,
    "P1": 1.2,
    "P2": 1.05,
    "P3": 0.92,
    "P4": 0.82,
}

ACTIVE_TOPIC_STATUS = {"active", "discover"}
LEARNABLE_OPPORTUNITY_STATUS = {"candidate", "ready_review", "promoted"}
GENERIC_QUERY_TERMS = {
    "tool",
    "tools",
    "product",
    "products",
    "review",
    "discussion",
    "community",
    "trend",
    "trends",
    "论坛",
    "社区",
    "热点",
    "趋势",
}


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default
    return data


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def normalize_query_candidate(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) < 4:
        return ""
    lowered = text.lower()
    if lowered in GENERIC_QUERY_TERMS:
        return ""
    if re.fullmatch(r"[a-z0-9-]+", lowered) and len(text) < 6:
        return ""
    return text[:120]


def priority_score(value: Any) -> float:
    if isinstance(value, str):
        return PRIORITY_WEIGHT.get(value, 1.0)
    return 1.0


def parse_iso(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def build_source_score_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = data.get("sources")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        if isinstance(source_id, str) and source_id:
            result[source_id] = item
    return result


def learned_queries(opportunities: list[dict[str, Any]], topic_id: str) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for opportunity in opportunities:
        if opportunity.get("status") not in LEARNABLE_OPPORTUNITY_STATUS:
            continue
        topic_ids = normalize_list(opportunity.get("topic_ids"))
        if topic_id not in topic_ids:
            continue
        for candidate in [opportunity.get("title"), *normalize_list(opportunity.get("keywords"))]:
            if not isinstance(candidate, str):
                continue
            text = normalize_query_candidate(candidate)
            if not text or text in seen:
                continue
            seen.add(text)
            queries.append(text)
            if len(queries) >= 4:
                return queries
    return queries


def learned_query_expansions(profile: dict[str, Any]) -> list[str]:
    learning = profile.get("learning")
    if not isinstance(learning, dict):
        return []
    values = learning.get("query_expansions")
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        text = normalize_query_candidate(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def blocked_terms(profile: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in normalize_list(profile.get("negative_keywords")):
        result.append(item.lower())
    learning = profile.get("learning")
    if isinstance(learning, dict):
        values = learning.get("blocked_terms")
        if isinstance(values, list):
            for item in values:
                if isinstance(item, str) and item:
                    result.append(item.lower())
    return result


def learned_source_bias(profile: dict[str, Any]) -> dict[str, float]:
    learning = profile.get("learning")
    if not isinstance(learning, dict):
        return {}
    values = learning.get("source_bias")
    if not isinstance(values, dict):
        return {}
    result: dict[str, float] = {}
    for source_id, bias in values.items():
        if not isinstance(source_id, str) or not source_id:
            continue
        if not isinstance(bias, (int, float)):
            continue
        result[source_id] = float(bias)
    return result


def low_yield_sources(profile: dict[str, Any]) -> set[str]:
    learning = profile.get("learning")
    if not isinstance(learning, dict):
        return set()
    values = learning.get("low_yield_sources")
    if not isinstance(values, list):
        return set()
    return {item for item in values if isinstance(item, str) and item}


def high_yield_sources(profile: dict[str, Any]) -> set[str]:
    learning = profile.get("learning")
    if not isinstance(learning, dict):
        return set()
    values = learning.get("high_yield_sources")
    if not isinstance(values, list):
        return set()
    return {item for item in values if isinstance(item, str) and item}


def topic_score(profile: dict[str, Any], opportunities: list[dict[str, Any]]) -> float:
    base_weight = profile.get("north_star_weight", 1.0)
    if not isinstance(base_weight, (int, float)):
        base_weight = 1.0
    learning = profile.get("learning")
    if isinstance(learning, dict):
        promoted = int(learning.get("promoted_count", 0) or 0)
        rejected = int(learning.get("rejected_count", 0) or 0)
        signals = int(learning.get("signal_count", 0) or 0)
    else:
        promoted = 0
        rejected = 0
        signals = 0

    score = float(base_weight) + min(promoted, 5) * 0.12 + min(signals, 20) * 0.01 - min(rejected, 5) * 0.06

    topic_id = profile.get("topic_id")
    if isinstance(topic_id, str) and topic_id:
        for opportunity in opportunities:
            if opportunity.get("status") not in LEARNABLE_OPPORTUNITY_STATUS:
                continue
            topic_ids = normalize_list(opportunity.get("topic_ids"))
            if topic_id not in topic_ids:
                continue
            updated_at = parse_iso(opportunity.get("updated_at"))
            if updated_at == float("-inf"):
                continue
            age_hours = max((datetime.now().astimezone().timestamp() - updated_at) / 3600, 0)
            if age_hours <= 24:
                score += 0.08
                break
            if age_hours <= 72:
                score += 0.04
                break

    return round(score, 3)


def topic_source_affinity(source: dict[str, Any], topic_id: str) -> float:
    topic_tags = set(normalize_list(source.get("topic_tags")))
    if not topic_tags:
        return 1.0
    if topic_id in topic_tags:
        return 1.18
    return 0.94


def render_query(template: str, topic_name: str, topic_keywords: str, query: str) -> str:
    return (
        template.replace("{topic_name}", topic_name)
        .replace("{topic_keywords}", topic_keywords)
        .replace("{query}", query)
    )


def dedupe_queries(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = normalize_query_candidate(item)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def diversify_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[tuple[str, str, str]] = set()
    topic_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}

    def take(row: dict[str, Any]) -> None:
        key = (str(row["topic_id"]), str(row["source_id"]), str(row["query"]))
        selected_ids.add(key)
        selected.append(row)
        topic_id = str(row["topic_id"])
        source_id = str(row["source_id"])
        topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
        source_counts[source_id] = source_counts.get(source_id, 0) + 1

    phases = [
        (1, 1),
        (2, 1),
        (2, 2),
        (3, 2),
    ]
    for max_topic, max_source in phases:
        for row in rows:
            if len(selected) >= limit:
                return selected
            key = (str(row["topic_id"]), str(row["source_id"]), str(row["query"]))
            if key in selected_ids:
                continue
            if topic_counts.get(str(row["topic_id"]), 0) >= max_topic:
                continue
            if source_counts.get(str(row["source_id"]), 0) >= max_source:
                continue
            take(row)

    for row in rows:
        if len(selected) >= limit:
            break
        key = (str(row["topic_id"]), str(row["source_id"]), str(row["query"]))
        if key in selected_ids:
            continue
        take(row)
    return selected


def build_plan(
    sources_data: dict[str, Any],
    topics_data: dict[str, Any],
    source_scores_data: dict[str, Any],
    opportunities_data: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    sources = sources_data.get("sources")
    topics = topics_data.get("profiles")
    opportunities = opportunities_data.get("opportunities")
    if not isinstance(sources, list) or not isinstance(topics, list) or not isinstance(opportunities, list):
        return []

    source_scores = build_source_score_map(source_scores_data)
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for profile in topics:
        if not isinstance(profile, dict):
            continue
        topic_id = profile.get("topic_id")
        topic_name = profile.get("name")
        status = profile.get("status")
        if not isinstance(topic_id, str) or not isinstance(topic_name, str):
            continue
        if status not in ACTIVE_TOPIC_STATUS:
            continue

        base_queries = normalize_list(profile.get("queries"))
        base_queries.extend(learned_query_expansions(profile))
        base_queries.extend(learned_queries([item for item in opportunities if isinstance(item, dict)], topic_id))
        base_queries = dedupe_queries(base_queries)
        if not base_queries:
            keywords = normalize_list(profile.get("keywords"))
            if keywords:
                keyword_query = normalize_query_candidate(" ".join(keywords[:4]))
                if keyword_query:
                    base_queries.append(keyword_query)
        if not base_queries:
            continue

        topic_keywords = " ".join(normalize_list(profile.get("keywords"))[:5])
        topic_blocked_terms = blocked_terms(profile)
        preferred_sources = set(normalize_list(profile.get("source_preferences")))
        learned_high_yield = high_yield_sources(profile)
        learned_low_yield = low_yield_sources(profile)
        source_bias = learned_source_bias(profile)
        topic_weight = topic_score(profile, [item for item in opportunities if isinstance(item, dict)])

        for source in sources:
            if not isinstance(source, dict):
                continue
            if not source.get("enabled", False):
                continue

            source_id = source.get("source_id")
            label = source.get("label")
            if not isinstance(source_id, str) or not isinstance(label, str):
                continue
            if source_id in learned_low_yield and source_id not in preferred_sources:
                continue

            source_learning = source_scores.get(source_id, {})
            learning_score = float(source_learning.get("score", 1.0) or 1.0)
            source_weight = priority_score(source.get("priority")) * learning_score * topic_source_affinity(source, topic_id)
            if source_id in preferred_sources:
                source_weight += 0.18
            if source_id in learned_high_yield:
                source_weight += 0.12
            source_weight += source_bias.get(source_id, 0.0)

            templates = normalize_list(source.get("search_templates"))
            if not templates:
                templates = ["{query}"]

            for raw_query in base_queries:
                for template in templates:
                    query = render_query(template, topic_name, topic_keywords, raw_query).strip()
                    lowered_query = query.lower()
                    if topic_blocked_terms and any(term in lowered_query for term in topic_blocked_terms):
                        continue
                    pair_key = (source_id, query)
                    if not query or pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    score = round(topic_weight * source_weight, 3)
                    reason_parts: list[str] = []
                    if source_id in preferred_sources:
                        reason_parts.append("preferred-source")
                    if source_id in learned_high_yield:
                        reason_parts.append("learned-high-yield")
                    if topic_id in set(normalize_list(source.get("topic_tags"))):
                        reason_parts.append("topic-fit")
                    if not reason_parts:
                        reason_parts.append("broad-scan")
                    rows.append(
                        {
                            "topic_id": topic_id,
                            "topic_name": topic_name,
                            "source_id": source_id,
                            "source_label": label,
                            "channel": source.get("channel", "public-web"),
                            "query": query,
                            "base_url": source.get("base_url", ""),
                            "score": score,
                            "reason": ",".join(reason_parts),
                        }
                    )

    rows.sort(key=lambda item: (-float(item["score"]), item["topic_name"], item["source_label"], item["query"]))
    return diversify_rows(rows, limit)


def render_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# exploration_batch",
        "",
        f"- count: {len(rows)}",
    ]
    if not rows:
        lines.extend(["", "- no exploration targets"])
        return "\n".join(lines) + "\n"

    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                "",
                f"## {index}. {row['topic_name']} -> {row['source_label']}",
                f"- topic_id: {row['topic_id']}",
                f"- source_id: {row['source_id']}",
                f"- channel: {row['channel']}",
                f"- score: {row['score']}",
                f"- query: {row['query']}",
                f"- base_url: {row['base_url'] or 'none'}",
                f"- reason: {row['reason']}",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a prioritized exploration batch for the continuous research loop.")
    parser.add_argument("--sources", default="data/research/sources.json")
    parser.add_argument("--topics", default="data/research/topic_profiles.json")
    parser.add_argument("--source-scores", default="data/research/source_scores.json")
    parser.add_argument("--opportunities", default="data/research/opportunities.json")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--format", choices=["json", "md"], default="md")
    args = parser.parse_args()

    rows = build_plan(
        load_json(Path(args.sources).expanduser(), {"sources": []}),
        load_json(Path(args.topics).expanduser(), {"profiles": []}),
        load_json(Path(args.source_scores).expanduser(), {"sources": []}),
        load_json(Path(args.opportunities).expanduser(), {"opportunities": []}),
        args.limit,
    )

    if args.format == "json":
        print(json.dumps({"ok": True, "count": len(rows), "items": rows}, ensure_ascii=False, indent=2))
        return 0

    print(render_md(rows), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

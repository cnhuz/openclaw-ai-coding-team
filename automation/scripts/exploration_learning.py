#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def tokenize_title(title: str) -> list[str]:
    tokens = re.split(r"[\s,，。:：;；/|()（）\-]+", title)
    result: list[str] = []
    for token in tokens:
        text = token.strip().lower()
        if len(text) < 3:
            continue
        result.append(text)
    return result


def top_terms(counter: Counter[str], limit: int) -> list[str]:
    return [item for item, _ in counter.most_common(limit)]


def learn_from_opportunities(
    profiles_payload: dict[str, Any],
    opportunities_payload: dict[str, Any],
    stale_days: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profiles = profiles_payload.get("profiles")
    opportunities = opportunities_payload.get("opportunities")
    if not isinstance(profiles, list) or not isinstance(opportunities, list):
        return profiles_payload, {"updated_profiles": 0, "stale_downgraded": 0}

    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        for topic_id in normalize_list(item.get("topic_ids")) or ["general"]:
            by_topic[topic_id].append(item)

    now_dt = datetime.now().astimezone()
    stale_cutoff = now_dt - timedelta(days=stale_days)
    stale_downgraded = 0

    for item in opportunities:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "candidate":
            continue
        updated_at = parse_iso(item.get("updated_at"))
        if updated_at is None or updated_at >= stale_cutoff:
            continue
        item["status"] = "watchlist"
        item["updated_at"] = now_iso()
        notes = item.get("notes")
        if not isinstance(notes, list):
            notes = []
            item["notes"] = notes
        notes.append("candidate downgraded to watchlist by exploration-learning due to staleness")
        stale_downgraded += 1

    updated_profiles = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        topic_id = profile.get("topic_id")
        if not isinstance(topic_id, str) or not topic_id:
            continue

        learning = profile.get("learning")
        if not isinstance(learning, dict):
            learning = {}
            profile["learning"] = learning

        topic_items = by_topic.get(topic_id, [])
        strong_items = [item for item in topic_items if item.get("status") in {"candidate", "ready_review", "promoted"}]
        rejected_items = [item for item in topic_items if item.get("status") == "rejected"]

        query_counter: Counter[str] = Counter()
        blocked_counter: Counter[str] = Counter()
        for item in strong_items:
            for keyword in normalize_list(item.get("keywords")):
                query_counter[keyword] += 1
            title = item.get("title")
            if isinstance(title, str):
                for token in tokenize_title(title):
                    query_counter[token] += 1

        for item in rejected_items:
            for keyword in normalize_list(item.get("keywords")):
                blocked_counter[keyword.lower()] += 1
            title = item.get("title")
            if isinstance(title, str):
                for token in tokenize_title(title):
                    blocked_counter[token] += 1

        learning["query_expansions"] = top_terms(query_counter, 6)
        learning["blocked_terms"] = top_terms(blocked_counter, 6)
        learning["last_learning_at"] = now_iso()
        updated_profiles += 1

    profiles_payload["updatedAt"] = now_iso()
    opportunities_payload["updatedAt"] = now_iso()
    return profiles_payload, {"updated_profiles": updated_profiles, "stale_downgraded": stale_downgraded}


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn query expansions and blocked terms from exploration outcomes.")
    parser.add_argument("--topics", default="data/research/topic_profiles.json")
    parser.add_argument("--opportunities", default="data/research/opportunities.json")
    parser.add_argument("--stale-days", type=int, default=7)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()

    topics_path = Path(args.topics).expanduser()
    opportunities_path = Path(args.opportunities).expanduser()
    topics_payload = load_json(topics_path, {"profiles": []})
    opportunities_payload = load_json(opportunities_path, {"opportunities": []})
    topics_payload, summary = learn_from_opportunities(topics_payload, opportunities_payload, args.stale_days)

    topics_path.parent.mkdir(parents=True, exist_ok=True)
    opportunities_path.parent.mkdir(parents=True, exist_ok=True)
    topics_path.write_text(json.dumps(topics_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    opportunities_path.write_text(json.dumps(opportunities_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.format == "md":
        lines = [
            "# exploration_learning",
            "",
            f"- updated_profiles: {summary['updated_profiles']}",
            f"- stale_downgraded: {summary['stale_downgraded']}",
        ]
        print("\n".join(lines) + "\n", end="")
        return 0

    print(
        json.dumps(
            {
                "ok": True,
                "topics_path": str(topics_path),
                "opportunities_path": str(opportunities_path),
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

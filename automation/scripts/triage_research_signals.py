#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lockfile import acquire, release


STATUS_ORDER = {
    "ready_review": 0,
    "candidate": 1,
    "watchlist": 2,
    "promoted": 3,
    "rejected": 4,
}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_iso(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


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


def clamp(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 0.99:
        return 0.99
    return round(value, 3)


def clamp_weight(value: float) -> float:
    if value < 0.7:
        return 0.7
    if value > 1.5:
        return 1.5
    return round(value, 3)


def load_signals(signals_root: Path, lookback_hours: int) -> list[dict[str, Any]]:
    if not signals_root.exists():
        return []

    cutoff = datetime.now().astimezone().timestamp() - lookback_hours * 3600
    signals: list[dict[str, Any]] = []

    for path in sorted(signals_root.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                continue
            discovered_at = parse_iso(item.get("discovered_at"))
            if discovered_at < cutoff:
                continue
            signals.append(item)

    deduped: dict[str, dict[str, Any]] = {}
    for signal in signals:
        key = signal.get("dedupe_key")
        if not isinstance(key, str) or not key:
            continue
        existing = deduped.get(key)
        if existing is None or parse_iso(signal.get("discovered_at")) >= parse_iso(existing.get("discovered_at")):
            deduped[key] = signal

    return list(deduped.values())


def topic_id(signal: dict[str, Any]) -> str:
    topic_ids = normalize_list(signal.get("topic_ids"))
    if topic_ids:
        return topic_ids[0]
    return "general"


def normalize_title(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.strip().lower())
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")[:48] or "untitled"


def cluster_key(signal: dict[str, Any]) -> str:
    explicit = signal.get("cluster_key")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return f"{topic_id(signal)}:{normalize_title(str(signal.get('title', 'signal')))}"


def opportunity_id(cluster_value: str) -> str:
    digest = hashlib.sha1(cluster_value.encode("utf-8")).hexdigest()[:10].upper()
    return f"OPP-{digest}"


def choose_title(signals: list[dict[str, Any]]) -> str:
    titles = [str(signal.get("title", "")).strip() for signal in signals if str(signal.get("title", "")).strip()]
    if not titles:
        return "Untitled Opportunity"
    titles.sort(key=lambda item: (len(item), item), reverse=True)
    return titles[0]


def choose_summary(signals: list[dict[str, Any]]) -> str:
    signals_sorted = sorted(signals, key=lambda item: parse_iso(item.get("discovered_at")), reverse=True)
    for signal in signals_sorted:
        summary = str(signal.get("summary", "")).strip()
        if summary:
            return summary
    return "需要进一步补充证据。"


def derive_priority(score: float) -> str:
    if score >= 0.88:
        return "P0"
    if score >= 0.74:
        return "P1"
    if score >= 0.62:
        return "P2"
    if score >= 0.5:
        return "P3"
    return "P4"


def evidence_domains(urls: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().strip()
        if not domain or domain in seen:
            continue
        seen.add(domain)
        result.append(domain)
    return result


def ready_review_evidence_ok(
    evidence_count: int,
    evidence_domain_diversity: int,
    has_official_source: bool,
    signal_count: int,
    source_diversity: int,
    card_path: Any,
) -> bool:
    if isinstance(card_path, str) and card_path.strip() and evidence_count >= 3 and evidence_domain_diversity >= 2:
        return True
    if has_official_source and evidence_count >= 3 and evidence_domain_diversity >= 2:
        return True
    if evidence_count >= 5 and evidence_domain_diversity >= 3:
        return True
    if has_official_source and signal_count >= 3 and source_diversity >= 3:
        return True
    return False


def derive_status(
    existing_status: str,
    score: float,
    signal_count: int,
    source_diversity: int,
    candidate_threshold: float,
    ready_threshold: float,
    evidence_count: int,
    evidence_domain_diversity: int,
    has_official_source: bool,
    card_path: Any,
) -> str:
    if existing_status in {"promoted", "rejected"}:
        return existing_status
    if existing_status == "ready_review" and score >= candidate_threshold and ready_review_evidence_ok(
        evidence_count,
        evidence_domain_diversity,
        has_official_source,
        signal_count,
        source_diversity,
        card_path,
    ):
        return "ready_review"
    if score >= ready_threshold and ready_review_evidence_ok(
        evidence_count,
        evidence_domain_diversity,
        has_official_source,
        signal_count,
        source_diversity,
        card_path,
    ):
        return "ready_review"
    if score >= candidate_threshold:
        return "candidate"
    if existing_status == "candidate" and score >= candidate_threshold - 0.08:
        return "candidate"
    return "watchlist"


def derive_action(status: str) -> str:
    if status == "ready_review":
        return "create_task"
    if status == "candidate":
        return "deep_dive"
    if status == "promoted":
        return "track_delivery"
    if status == "rejected":
        return "archive"
    return "monitor"


def update_topic_profiles(path: Path, data: dict[str, Any], signals: list[dict[str, Any]], opportunities: list[dict[str, Any]]) -> None:
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        profiles = []

    profile_map: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = profile.get("topic_id")
        if isinstance(profile_id, str) and profile_id:
            profile_map[profile_id] = profile

    signal_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        for item in normalize_list(signal.get("topic_ids")) or ["general"]:
            signal_by_topic[item].append(signal)

    opp_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for opportunity in opportunities:
        for item in normalize_list(opportunity.get("topic_ids")) or ["general"]:
            opp_by_topic[item].append(opportunity)

    for topic_key in sorted(set(signal_by_topic) | set(opp_by_topic)):
        profile = profile_map.get(topic_key)
        if profile is None:
            profile = {
                "topic_id": topic_key,
                "name": topic_key,
                "status": "active",
                "goal": "待补充",
                "queries": [],
                "keywords": [],
                "negative_keywords": [],
                "source_preferences": [],
                "learning": {},
            }
            profiles.append(profile)
            profile_map[topic_key] = profile

        learning = profile.get("learning")
        if not isinstance(learning, dict):
            learning = {}
            profile["learning"] = learning

        topic_signals = signal_by_topic.get(topic_key, [])
        topic_opportunities = opp_by_topic.get(topic_key, [])
        learning["signal_count"] = len(topic_signals)
        learning["opportunity_count"] = len(topic_opportunities)
        learning["promoted_count"] = sum(1 for item in topic_opportunities if item.get("status") == "promoted")
        learning["rejected_count"] = sum(1 for item in topic_opportunities if item.get("status") == "rejected")
        newest_signal = max((parse_iso(item.get("discovered_at")) for item in topic_signals), default=float("-inf"))
        learning["last_signal_at"] = (
            datetime.fromtimestamp(newest_signal).astimezone().replace(microsecond=0).isoformat()
            if newest_signal != float("-inf")
            else None
        )

    data["profiles"] = profiles
    data["updatedAt"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_source_scores(path: Path, sources_data: dict[str, Any], signals: list[dict[str, Any]], opportunities: list[dict[str, Any]]) -> None:
    source_labels: dict[str, str] = {}
    enabled_sources = sources_data.get("sources")
    if isinstance(enabled_sources, list):
        for source in enabled_sources:
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            label = source.get("label")
            if isinstance(source_id, str) and isinstance(label, str):
                source_labels[source_id] = label

    signals_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        source_id = signal.get("source_id")
        if isinstance(source_id, str) and source_id:
            signals_by_source[source_id].append(signal)
            source_labels.setdefault(source_id, str(signal.get("source_label", source_id)))

    opportunities_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for opportunity in opportunities:
        for source_id in normalize_list(opportunity.get("source_ids")):
            opportunities_by_source[source_id].append(opportunity)

    rows: list[dict[str, Any]] = []
    for source_id in sorted(set(source_labels) | set(signals_by_source) | set(opportunities_by_source)):
        source_signals = signals_by_source.get(source_id, [])
        source_opportunities = opportunities_by_source.get(source_id, [])
        candidate_count = sum(1 for item in source_opportunities if item.get("status") in {"candidate", "ready_review", "promoted"})
        promoted_count = sum(1 for item in source_opportunities if item.get("status") == "promoted")
        rejected_count = sum(1 for item in source_opportunities if item.get("status") == "rejected")
        signal_count = len(source_signals)
        newest_signal = max((parse_iso(item.get("discovered_at")) for item in source_signals), default=float("-inf"))
        recency_bonus = 0.0
        if newest_signal != float("-inf"):
            age_hours = max((datetime.now().astimezone().timestamp() - newest_signal) / 3600, 0)
            if age_hours <= 24:
                recency_bonus = 0.08
            elif age_hours <= 72:
                recency_bonus = 0.04
        score = clamp_weight(
            0.92
            + min(signal_count, 20) * 0.01
            + min(candidate_count, 10) * 0.03
            + min(promoted_count, 5) * 0.12
            - min(rejected_count, 5) * 0.09
            + recency_bonus
        )
        rows.append(
            {
                "source_id": source_id,
                "label": source_labels.get(source_id, source_id),
                "signal_count": signal_count,
                "candidate_count": candidate_count,
                "promoted_count": promoted_count,
                "rejected_count": rejected_count,
                "score": score,
                "last_seen_at": (
                    datetime.fromtimestamp(newest_signal).astimezone().replace(microsecond=0).isoformat()
                    if newest_signal != float("-inf")
                    else None
                ),
            }
        )

    payload = {
        "schemaVersion": 1,
        "updatedAt": now_iso(),
        "sources": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_opportunities(
    existing_payload: dict[str, Any],
    signals: list[dict[str, Any]],
    candidate_threshold: float,
    ready_threshold: float,
) -> list[dict[str, Any]]:
    existing_rows = existing_payload.get("opportunities")
    existing_map: dict[str, dict[str, Any]] = {}
    if isinstance(existing_rows, list):
        for item in existing_rows:
            if not isinstance(item, dict):
                continue
            item_id = item.get("opportunity_id")
            if isinstance(item_id, str) and item_id:
                existing_map[item_id] = item

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped[cluster_key(signal)].append(signal)

    result: list[dict[str, Any]] = []
    touched_ids: set[str] = set()

    for group_key, group_signals in grouped.items():
        group_signals.sort(key=lambda item: parse_iso(item.get("discovered_at")), reverse=True)
        opp_id = opportunity_id(group_key)
        touched_ids.add(opp_id)
        existing = existing_map.get(opp_id, {})

        signal_scores = [float(item.get("score", 0.6) or 0.6) for item in group_signals]
        confidence_values = [float(item.get("confidence", 0.6) or 0.6) for item in group_signals]
        importance_values = [float(item.get("importance", 0.6) or 0.6) for item in group_signals]
        source_ids = sorted({str(item.get("source_id")) for item in group_signals if str(item.get("source_id", "")).strip()})
        topic_ids = sorted({item for signal in group_signals for item in normalize_list(signal.get("topic_ids"))} or {"general"})
        keywords = sorted({item for signal in group_signals for item in normalize_list(signal.get("keywords"))})
        evidence_urls = sorted(
            {
                entry.get("url", "")
                for signal in group_signals
                for entry in signal.get("evidence", [])
                if isinstance(entry, dict) and isinstance(entry.get("url"), str) and entry.get("url")
            }
        )
        evidence_titles = sorted(
            {
                entry.get("title", "")
                for signal in group_signals
                for entry in signal.get("evidence", [])
                if isinstance(entry, dict) and isinstance(entry.get("title"), str) and entry.get("title")
            }
        )
        evidence_domains_list = evidence_domains(evidence_urls)
        evidence_count = len(evidence_urls)
        evidence_domain_diversity = len(evidence_domains_list)
        has_official_source = "official-sites" in source_ids
        latest_seen = max(parse_iso(item.get("discovered_at")) for item in group_signals)
        freshness_hours = max((datetime.now().astimezone().timestamp() - latest_seen) / 3600, 0)
        source_diversity = len(source_ids)
        signal_count = len(group_signals)

        score = sum(signal_scores) / len(signal_scores)
        score += min(source_diversity - 1, 2) * 0.06
        if signal_count >= 3:
            score += 0.05
        if freshness_hours <= 24:
            score += 0.05
        elif freshness_hours <= 72:
            score += 0.02
        score = clamp(score)

        confidence = clamp(sum(confidence_values) / len(confidence_values))
        importance = clamp(sum(importance_values) / len(importance_values))
        existing_status = str(existing.get("status", "watchlist"))
        status = derive_status(
            existing_status,
            score,
            signal_count,
            source_diversity,
            candidate_threshold,
            ready_threshold,
            evidence_count,
            evidence_domain_diversity,
            has_official_source,
            existing.get("card_path"),
        )
        recommendation = derive_action(status)

        opportunity = {
            "opportunity_id": opp_id,
            "cluster_key": group_key,
            "title": choose_title(group_signals),
            "status": status,
            "priority": derive_priority(score),
            "score": score,
            "confidence": confidence,
            "importance": importance,
            "topic_ids": topic_ids,
            "source_ids": source_ids,
            "signal_ids": [str(item.get("signal_id")) for item in group_signals if str(item.get("signal_id", "")).strip()],
            "signal_count": signal_count,
            "source_diversity": source_diversity,
            "summary": choose_summary(group_signals),
            "recommended_action": recommendation,
            "keywords": keywords,
            "evidence_urls": evidence_urls,
            "evidence_titles": evidence_titles,
            "evidence_count": evidence_count,
            "evidence_domain_diversity": evidence_domain_diversity,
            "evidence_domains": evidence_domains_list,
            "has_official_source": has_official_source,
            "card_path": existing.get("card_path"),
            "task_id": existing.get("task_id"),
            "notes": existing.get("notes", []),
            "created_at": existing.get("created_at", now_iso()),
            "updated_at": now_iso(),
            "latest_signal_at": datetime.fromtimestamp(latest_seen).astimezone().replace(microsecond=0).isoformat(),
        }
        result.append(opportunity)

    for opp_id, existing in existing_map.items():
        if opp_id in touched_ids:
            continue
        result.append(existing)

    result.sort(
        key=lambda item: (
            STATUS_ORDER.get(str(item.get("status")), 99),
            -float(item.get("score", 0)),
            -parse_iso(item.get("updated_at")),
            str(item.get("opportunity_id", "")),
        )
    )
    return result


def render_md(opportunities: list[dict[str, Any]], signal_count: int) -> str:
    lines = [
        "# research_triage",
        "",
        f"- signals: {signal_count}",
        f"- opportunities: {len(opportunities)}",
    ]
    if not opportunities:
        lines.extend(["", "- no opportunities"])
        return "\n".join(lines) + "\n"

    for item in opportunities[:10]:
        lines.extend(
            [
                "",
                f"## {item['opportunity_id']} | {item['title']}",
                f"- status: {item['status']}",
                f"- priority: {item['priority']}",
                f"- score: {item['score']}",
                f"- recommended_action: {item['recommended_action']}",
                f"- signal_count: {item['signal_count']}",
                f"- source_diversity: {item['source_diversity']}",
                f"- evidence_count: {item.get('evidence_count', 0)}",
                f"- evidence_domain_diversity: {item.get('evidence_domain_diversity', 0)}",
                f"- has_official_source: {item.get('has_official_source', False)}",
                f"- topic_ids: {', '.join(item['topic_ids']) or 'none'}",
                f"- evidence_urls: {', '.join(item['evidence_urls'][:3]) or 'none'}",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage research signals into ranked opportunities.")
    parser.add_argument("--signals-root", default="data/research/signals")
    parser.add_argument("--sources", default="data/research/sources.json")
    parser.add_argument("--topics", default="data/research/topic_profiles.json")
    parser.add_argument("--source-scores", default="data/research/source_scores.json")
    parser.add_argument("--opportunities", default="data/research/opportunities.json")
    parser.add_argument("--lock", default="data/research/_state/research.lock")
    parser.add_argument("--lookback-hours", type=int, default=168)
    parser.add_argument("--candidate-threshold", type=float, default=0.58)
    parser.add_argument("--ready-threshold", type=float, default=0.74)
    parser.add_argument("--format", choices=["json", "md"], default="json")
    args = parser.parse_args()
    lock_path = Path(args.lock).expanduser()
    lock_result = acquire(lock_path, timeout=120, stale_seconds=7200)
    if not lock_result.get("ok"):
        raise SystemExit(f"failed to acquire research lock: {lock_path}")

    try:
        signals = load_signals(Path(args.signals_root).expanduser(), args.lookback_hours)
        sources_data = load_json(Path(args.sources).expanduser(), {"sources": []})
        topics_path = Path(args.topics).expanduser()
        topics_data = load_json(topics_path, {"profiles": []})
        opportunities_path = Path(args.opportunities).expanduser()
        existing_payload = load_json(opportunities_path, {"opportunities": []})

        opportunities = build_opportunities(existing_payload, signals, args.candidate_threshold, args.ready_threshold)
        payload = {
            "schemaVersion": 1,
            "updatedAt": now_iso(),
            "opportunities": opportunities,
        }
        opportunities_path.parent.mkdir(parents=True, exist_ok=True)
        opportunities_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        update_source_scores(Path(args.source_scores).expanduser(), sources_data, signals, opportunities)
        update_topic_profiles(topics_path, topics_data, signals, opportunities)
    finally:
        release(lock_path)

    if args.format == "md":
        print(render_md(opportunities, len(signals)), end="")
        return 0

    status_counter = Counter(str(item.get("status")) for item in opportunities)
    print(
        json.dumps(
            {
                "ok": True,
                "signals": len(signals),
                "opportunities": len(opportunities),
                "status_counts": dict(status_counter),
                "top": opportunities[:5],
                "opportunities_path": str(opportunities_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

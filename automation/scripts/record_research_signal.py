#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def normalize_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def build_evidence(urls: list[str], titles: list[str]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for index, url in enumerate(urls):
        title = titles[index] if index < len(titles) else ""
        evidence.append({"url": url, "title": title})
    return evidence


def signal_id(dedupe_key: str, discovered_at: str) -> str:
    digest = hashlib.sha1(f"{dedupe_key}|{discovered_at}".encode("utf-8")).hexdigest()[:10].upper()
    return f"SIG-{digest}"


def dedupe_key(source_id: str, title: str, urls: list[str]) -> str:
    first_url = urls[0] if urls else ""
    normalized = " ".join(title.strip().split()).lower()
    return hashlib.sha1(f"{source_id}|{normalized}|{first_url}".encode("utf-8")).hexdigest()


def clamp(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return round(value, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a structured research signal into data/research/signals.")
    parser.add_argument("--signals-root", default="data/research/signals")
    parser.add_argument("--discovered-at")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--topic-id", action="append", default=[])
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--signal-type", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--evidence-url", action="append", default=[])
    parser.add_argument("--evidence-title", action="append", default=[])
    parser.add_argument("--cluster-key")
    parser.add_argument("--novelty", type=float, default=0.6)
    parser.add_argument("--confidence", type=float, default=0.6)
    parser.add_argument("--importance", type=float, default=0.6)
    parser.add_argument("--score", type=float)
    parser.add_argument("--status", default="new")
    args = parser.parse_args()

    evidence_urls = normalize_list(args.evidence_url)
    if not evidence_urls:
      raise SystemExit("research signal requires at least one --evidence-url")

    discovered_at = args.discovered_at or now_iso()
    computed_score = args.score
    if computed_score is None:
        computed_score = (args.novelty + args.confidence + args.importance) / 3

    entry: dict[str, Any] = {
        "signal_id": signal_id(dedupe_key(args.source_id, args.title, evidence_urls), discovered_at),
        "dedupe_key": dedupe_key(args.source_id, args.title, evidence_urls),
        "discovered_at": discovered_at,
        "source_id": args.source_id,
        "source_label": args.source_label,
        "channel": args.channel,
        "topic_ids": normalize_list(args.topic_id),
        "title": args.title.strip(),
        "summary": args.summary.strip(),
        "signal_type": args.signal_type.strip(),
        "query": args.query.strip(),
        "keywords": normalize_list(args.keyword),
        "evidence": build_evidence(evidence_urls, args.evidence_title),
        "cluster_key": (args.cluster_key or "").strip(),
        "novelty": clamp(args.novelty),
        "confidence": clamp(args.confidence),
        "importance": clamp(args.importance),
        "score": clamp(float(computed_score)),
        "status": args.status.strip() or "new",
    }

    signals_root = Path(args.signals_root).expanduser()
    signals_root.mkdir(parents=True, exist_ok=True)
    day_path = signals_root / f"{discovered_at[:10]}.jsonl"
    with day_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "ok": True,
                "path": str(day_path),
                "signal_id": entry["signal_id"],
                "dedupe_key": entry["dedupe_key"],
                "score": entry["score"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

TRACK_LABELS = {
    "cashflow": "现金流",
    "ads": "广告流量",
    "oss_influence": "开源影响力",
    "compound_asset": "复利资产",
}

DEV_HEAVY_SOURCE_IDS = {"github-trending", "hacker-news", "lobsters", "juejin"}
BREADTH_SIGNAL_SOURCE_IDS = {"reddit-public", "x-public", "buyer-intent-web", "emergent-public-web", "indie-hackers", "news-and-analysis", "v2ex"}
BROAD_MARKET_TOPICS = {"broad-demand-pools", "search-intent-demand", "payment-intent", "distribution-leverage"}
SEARCH_INTENT_TERMS = [
    "best",
    "alternative",
    "alternatives",
    "review",
    "pricing",
    "price",
    "worth it",
    "template",
    "generator",
    "calculator",
    "download",
    "compare",
    "对比",
    "模板",
    "生成器",
    "计算器",
    "下载",
    "定价",
    "付费",
]
DEV_KEYWORDS = [
    "github",
    "copilot",
    "jira",
    "pull request",
    "pr review",
    "repo",
    "sdk",
    "cli",
    "developer workflow",
    "ai coding",
    "multi-agent coding",
    "code review",
    "agentic workflow",
]
BROAD_AUDIENCE_TERMS = [
    "parent",
    "parents",
    "student",
    "students",
    "creator",
    "creators",
    "small business",
    "small businesses",
    "seller",
    "sellers",
    "job seeker",
    "resume",
    "interview",
    "teacher",
    "teachers",
    "家长",
    "学生",
    "创作者",
    "小商家",
    "卖家",
    "求职",
    "简历",
    "面试",
    "老师",
]
SERVICE_HEAVY_TERMS = [
    "consulting",
    "agency",
    "implementation service",
    "enterprise rollout",
    "定制开发",
    "定制",
    "1对1",
    "高客服",
    "重服务",
]


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


def topic_profile_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in profiles:
        if not isinstance(item, dict):
            continue
        topic_id_value = item.get("topic_id")
        if isinstance(topic_id_value, str) and topic_id_value:
            result[topic_id_value] = item
    return result


def topic_weight(topic_ids: list[str], profiles: dict[str, dict[str, Any]]) -> float:
    weights: list[float] = []
    for topic_id_value in topic_ids:
        profile = profiles.get(topic_id_value)
        if not isinstance(profile, dict):
            continue
        weight = profile.get("north_star_weight", 1.0)
        if isinstance(weight, (int, float)):
            weights.append(float(weight))
    if not weights:
        return 1.0
    return sum(weights) / len(weights)


def infer_tracks(topic_ids: list[str], source_ids: list[str]) -> list[str]:
    tracks: list[str] = []
    if any(topic_id_value in {"payment-intent", "user-pain-demand", "broad-demand-pools", "search-intent-demand"} for topic_id_value in topic_ids):
        tracks.append("cashflow")
    if "distribution-leverage" in topic_ids:
        tracks.extend(["ads", "compound_asset"])
    if "technical-enablers" in topic_ids or ("community-trends" in topic_ids and not any(topic_id_value in BROAD_MARKET_TOPICS for topic_id_value in topic_ids)):
        tracks.append("oss_influence")
    if "automation-fit" in topic_ids or "unit-economics" in topic_ids:
        tracks.append("compound_asset")
    if any(source_id in {"buyer-intent-web", "product-hunt", "indie-hackers"} for source_id in source_ids):
        tracks.append("cashflow")
    result: list[str] = []
    seen: set[str] = set()
    for item in tracks:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def tracks_from_profiles(topic_ids: list[str], profiles: dict[str, dict[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for topic_id_value in topic_ids:
        profile = profiles.get(topic_id_value)
        if not isinstance(profile, dict):
            continue
        for track in normalize_list(profile.get("commercial_tracks")):
            if track in seen:
                continue
            seen.add(track)
            result.append(track)
    return result


def text_blob(title: str, summary: str, keywords: list[str]) -> str:
    return " ".join([title, summary, *keywords]).lower()


def contains_any(text: str, values: list[str]) -> bool:
    return any(item in text for item in values)


def is_dev_heavy(source_ids: list[str], text: str) -> bool:
    if source_ids and set(source_ids).issubset(DEV_HEAVY_SOURCE_IDS) and contains_any(text, DEV_KEYWORDS):
        return True
    return False


def is_broad_market(topic_ids: list[str], source_ids: list[str], text: str) -> bool:
    if any(topic_id_value in BROAD_MARKET_TOPICS for topic_id_value in topic_ids):
        return True
    if any(source_id in BREADTH_SIGNAL_SOURCE_IDS for source_id in source_ids) and contains_any(text, BROAD_AUDIENCE_TERMS + SEARCH_INTENT_TERMS):
        return True
    if contains_any(text, BROAD_AUDIENCE_TERMS):
        return True
    return False


def monetization_score(topic_ids: list[str], source_ids: list[str], text: str, has_official_source: bool) -> float:
    score = 0.4
    if "payment-intent" in topic_ids:
        score += 0.24
    if "search-intent-demand" in topic_ids:
        score += 0.18
    if "broad-demand-pools" in topic_ids:
        score += 0.12
    if "user-pain-demand" in topic_ids:
        score += 0.12
    if contains_any(text, ["pricing", "price", "subscription", "付费", "定价", "购买", "订阅", "worth it", "template", "generator", "calculator"]):
        score += 0.12
    if any(source_id in {"buyer-intent-web", "product-hunt", "indie-hackers"} for source_id in source_ids):
        score += 0.06
    if has_official_source:
        score += 0.05
    if contains_any(text, BROAD_AUDIENCE_TERMS):
        score += 0.05
    if contains_any(text, SERVICE_HEAVY_TERMS):
        score -= 0.18
    if is_dev_heavy(source_ids, text) and not any(topic_id_value in {"payment-intent", "search-intent-demand"} for topic_id_value in topic_ids):
        score -= 0.08
    return clamp(score)


def distribution_score(topic_ids: list[str], source_ids: list[str], text: str) -> float:
    score = 0.42
    if "distribution-leverage" in topic_ids:
        score += 0.25
    if "search-intent-demand" in topic_ids:
        score += 0.16
    if any(source_id in {"reddit-public", "x-public", "product-hunt", "v2ex", "medium-devto", "buyer-intent-web", "emergent-public-web", "indie-hackers"} for source_id in source_ids):
        score += 0.12
    if contains_any(text, ["seo", "目录", "搜索", "product hunt", "reddit", "x.com", "template", "generator", "calculator", "download", "landing page", "着陆页"]):
        score += 0.1
    if is_dev_heavy(source_ids, text):
        score -= 0.08
    return clamp(score)


def automation_fit_score(topic_ids: list[str], text: str) -> float:
    score = 0.45
    if "automation-fit" in topic_ids:
        score += 0.25
    if "technical-enablers" in topic_ids:
        score += 0.08
    if contains_any(text, ["workflow", "tool", "template", "automation", "generator", "calculator", "checklist", "tracker", "report", "工具", "模板", "生成器", "计算器"]):
        score += 0.1
    if contains_any(text, SERVICE_HEAVY_TERMS + ["onboarding-heavy"]):
        score -= 0.2
    return clamp(score)


def unit_economics_score(topic_ids: list[str], text: str) -> float:
    score = 0.45
    if "unit-economics" in topic_ids:
        score += 0.25
    if "automation-fit" in topic_ids:
        score += 0.1
    if contains_any(text, ["low-touch", "self-serve", "低维护", "自助", "低价", "广谱", "template", "generator", "calculator", "ads", "affiliate"]):
        score += 0.1
    if contains_any(text, SERVICE_HEAVY_TERMS + ["service", "implementation"]):
        score -= 0.2
    return clamp(score)


def derive_business_model(tracks: list[str], topic_ids: list[str], text: str) -> str:
    if "search-intent-demand" in topic_ids or contains_any(text, ["template", "generator", "calculator", "download", "模板", "生成器", "计算器"]):
        return "搜索意图驱动的小工具/模板/生成器，优先 SEO + 自助付费或免费入口转付费"
    if "broad-demand-pools" in topic_ids and "cashflow" in tracks:
        return "面向广谱用户的低价微产品，优先一次性小额付费或轻量订阅"
    if "ads" in tracks or "distribution-leverage" in topic_ids:
        return "SEO / 内容流量驱动的小网站，辅以广告、affiliate 或导流变现"
    if "oss_influence" in tracks and ("technical-enablers" in topic_ids or "开源" in text or "github" in text):
        return "开源影响力引流，再转托管版、增强版或模板付费"
    if "cashflow" in tracks:
        return "低价、广谱、可自助购买的工具型产品，优先订阅或一次性小额付费"
    return "先验证影响力或流量，再决定是否转低价工具、模板或广告模式"


def derive_distribution_paths(tracks: list[str], source_ids: list[str], topic_ids: list[str]) -> list[str]:
    paths: list[str] = []
    if "search-intent-demand" in topic_ids:
        paths.append("SEO / 搜索意图页")
    if "ads" in tracks or "distribution-leverage" in topic_ids:
        paths.append("SEO / 搜索流量")
    if any(source_id in {"github-trending", "hacker-news", "lobsters"} for source_id in source_ids):
        paths.append("开源社区 / 开发者社区")
    if any(source_id in {"product-hunt", "x-public", "medium-devto", "indie-hackers"} for source_id in source_ids):
        paths.append("产品社区 / 社媒传播")
    if any(source_id in {"reddit-public", "v2ex", "buyer-intent-web", "emergent-public-web"} for source_id in source_ids):
        paths.append("论坛口碑 / 社区讨论")
    result: list[str] = []
    seen: set[str] = set()
    for item in paths:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result or ["待验证分发路径"]


def derive_success_indicators(tracks: list[str]) -> list[str]:
    if "cashflow" in tracks:
        return ["首批付费用户数", "试用到付费转化率", "首月收入是否覆盖基础 token / infra 成本"]
    if "ads" in tracks:
        return ["自然搜索流量", "广告展示量 / 点击率", "单页面收入是否覆盖维护成本"]
    if "oss_influence" in tracks:
        return ["GitHub stars / installs", "自然提及量", "开源流量是否转化为试用或订阅"]
    return ["是否形成稳定流量、留资或下一步付费验证信号"]


def derive_stop_conditions(text: str) -> list[str]:
    conditions = [
        "30~90 天内无法验证最小收入、流量或转化信号时降级为 watchlist",
        "若明显依赖重人工交付或高客服支持，则停止进入主线",
    ]
    if contains_any(text, ["consulting", "定制", "1对1", "implementation"]):
        conditions.append("若需求继续滑向重定制服务，则停止产品化投入")
    return conditions


def derive_unit_economics_assessment(unit_score: float, text: str) -> str:
    if unit_score >= 0.78:
        return "单位经济性偏好：更适合低价、广谱、自助购买或低维护分发。"
    if contains_any(text, ["consulting", "1对1", "定制"]):
        return "单位经济性偏弱：存在重服务或定制化风险，需谨慎投入。"
    return "单位经济性中等：需进一步验证 token / infra / 维护成本与价格空间。"


def derive_automation_assessment(automation_score: float, text: str) -> str:
    if automation_score >= 0.78:
        return "自动化适配较强：更像工具、模板、工作流或低触达产品，适合 agent 团队持续运营。"
    if contains_any(text, ["consulting", "1对1", "enterprise rollout", "定制"]):
        return "自动化适配偏弱：更接近项目制或重服务形态，不适合长期自养主线。"
    return "自动化适配中等：可继续验证是否能收敛为低维护产品。"


def derive_payment_hypothesis(tracks: list[str], text: str) -> str:
    if contains_any(text, ["template", "generator", "calculator", "download", "模板", "生成器", "计算器"]):
        return "用户会为明确节省时间的模板、生成器或计算器类产品付费，或先被免费流量吸引再转付费。"
    if contains_any(text, BROAD_AUDIENCE_TERMS):
        return "只要结果明确、省时显著、价格足够低，广谱用户愿意为高频小工具付费。"
    if "cashflow" in tracks:
        return "用户愿意为节省时间、减少往返、直接提高结果的工具型价值付费。"
    if "ads" in tracks:
        return "先用流量验证需求，再判断广告、affiliate 或导流是否能形成收入。"
    if "oss_influence" in tracks:
        return "先通过开源影响力获取用户，再用托管版、增强版或模板包实现付费转化。"
    if contains_any(text, ["workflow", "tool", "api", "agent"]):
        return "需验证用户是否愿意为更顺滑的工作流和自动化结果付费。"
    return "需先验证是否存在稳定付费意愿，再决定产品化深度。"


def derive_pricing_hypothesis(tracks: list[str]) -> str:
    if "cashflow" in tracks:
        return "优先低价广谱：一次性小额付费或轻量订阅。"
    if "ads" in tracks:
        return "优先免费获取流量，再看广告或导流收入。"
    if "oss_influence" in tracks:
        return "开源基础免费，增强版 / 托管版 / 模板集收费。"
    return "先小范围验证价格锚点，再决定收费模式。"


def derive_alignment_label(value: float) -> str:
    if value >= 0.72:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def derive_market_scope(topic_ids: list[str], source_ids: list[str], text: str) -> str:
    if is_broad_market(topic_ids, source_ids, text):
        return "broad"
    if is_dev_heavy(source_ids, text):
        return "developer"
    return "mixed"


def derive_market_angle(topic_ids: list[str], source_ids: list[str], text: str, tracks: list[str]) -> str:
    if "search-intent-demand" in topic_ids or contains_any(text, SEARCH_INTENT_TERMS):
        return "search-demand"
    if "broad-demand-pools" in topic_ids or contains_any(text, BROAD_AUDIENCE_TERMS):
        return "broad-demand"
    if "ads" in tracks or "distribution-leverage" in topic_ids:
        return "traffic-asset"
    if is_dev_heavy(source_ids, text):
        return "developer-tooling"
    return "mixed-opportunity"


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
            continue

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
    topics_data: dict[str, Any],
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
    profiles = topic_profile_map(topics_data)
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
        title = choose_title(group_signals)
        summary = choose_summary(group_signals)
        merged_tracks = tracks_from_profiles(topic_ids, profiles) + infer_tracks(topic_ids, source_ids)
        commercial_tracks: list[str] = []
        seen_tracks: set[str] = set()
        for track in merged_tracks:
            if track in seen_tracks:
                continue
            seen_tracks.add(track)
            commercial_tracks.append(track)
        content = text_blob(title, summary, keywords)
        topic_weight_value = topic_weight(topic_ids, profiles)
        north_star_topic_score = clamp(min(max(topic_weight_value / 1.4, 0.3), 0.95))
        market_signal_score = sum(signal_scores) / len(signal_scores)
        market_signal_score += min(source_diversity - 1, 2) * 0.06
        if signal_count >= 3:
            market_signal_score += 0.05
        if freshness_hours <= 24:
            market_signal_score += 0.05
        elif freshness_hours <= 72:
            market_signal_score += 0.02
        market_signal_score = clamp(market_signal_score)

        monetization = monetization_score(topic_ids, source_ids, content, has_official_source)
        distribution = distribution_score(topic_ids, source_ids, content)
        automation_fit = automation_fit_score(topic_ids, content)
        unit_economics = unit_economics_score(topic_ids, content)
        if is_dev_heavy(source_ids, content) and not is_broad_market(topic_ids, source_ids, content):
            market_signal_score = clamp(market_signal_score - 0.06)
        self_sustainability_score = clamp(
            monetization * 0.28
            + distribution * 0.22
            + automation_fit * 0.18
            + unit_economics * 0.18
            + north_star_topic_score * 0.14
        )
        score = clamp(market_signal_score * 0.48 + self_sustainability_score * 0.52)

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
        business_model_hypothesis = derive_business_model(commercial_tracks, topic_ids, content)
        distribution_paths = derive_distribution_paths(commercial_tracks, source_ids, topic_ids)
        success_indicators = derive_success_indicators(commercial_tracks)
        stop_conditions = derive_stop_conditions(content)
        unit_economics_assessment = derive_unit_economics_assessment(unit_economics, content)
        automation_fit_assessment = derive_automation_assessment(automation_fit, content)
        payment_hypothesis = derive_payment_hypothesis(commercial_tracks, content)
        pricing_hypothesis = derive_pricing_hypothesis(commercial_tracks)
        north_star_alignment = derive_alignment_label(self_sustainability_score)
        market_scope = derive_market_scope(topic_ids, source_ids, content)
        market_angle = derive_market_angle(topic_ids, source_ids, content, commercial_tracks)

        opportunity = {
            "opportunity_id": opp_id,
            "cluster_key": group_key,
            "title": title,
            "status": status,
            "priority": derive_priority(score),
            "score": score,
            "market_signal_score": market_signal_score,
            "self_sustainability_score": self_sustainability_score,
            "north_star_alignment": north_star_alignment,
            "market_scope": market_scope,
            "market_angle": market_angle,
            "confidence": confidence,
            "importance": importance,
            "topic_ids": topic_ids,
            "source_ids": source_ids,
            "commercial_tracks": commercial_tracks,
            "signal_ids": [str(item.get("signal_id")) for item in group_signals if str(item.get("signal_id", "")).strip()],
            "signal_count": signal_count,
            "source_diversity": source_diversity,
            "summary": summary,
            "recommended_action": recommendation,
            "keywords": keywords,
            "business_model_hypothesis": business_model_hypothesis,
            "distribution_paths": distribution_paths,
            "payment_hypothesis": payment_hypothesis,
            "pricing_hypothesis": pricing_hypothesis,
            "unit_economics_assessment": unit_economics_assessment,
            "automation_fit_assessment": automation_fit_assessment,
            "success_indicators": success_indicators,
            "stop_conditions": stop_conditions,
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
                f"- market_signal_score: {item.get('market_signal_score', '-')}",
                f"- self_sustainability_score: {item.get('self_sustainability_score', '-')}",
                f"- north_star_alignment: {item.get('north_star_alignment', '-')}",
                f"- market_scope: {item.get('market_scope', '-')}",
                f"- market_angle: {item.get('market_angle', '-')}",
                f"- commercial_tracks: {', '.join(TRACK_LABELS.get(track, track) for track in item.get('commercial_tracks', [])) or 'none'}",
                f"- business_model_hypothesis: {item.get('business_model_hypothesis', '-')}",
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

        opportunities = build_opportunities(
            existing_payload,
            signals,
            topics_data,
            args.candidate_threshold,
            args.ready_threshold,
        )
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

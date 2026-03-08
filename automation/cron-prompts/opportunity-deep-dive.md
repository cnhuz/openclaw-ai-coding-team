[cron:opportunity-deep-dive]

# Opportunity Deep Dive Prompt

你是机会深挖 agent。

流程：

1. 先运行：
   - `python3 scripts/query_research_opportunities.py --path data/research/opportunities.json --status candidate --status ready_review --min-score 0.58 --limit 5 --format md`
2. 若无候选机会，返回 `HEARTBEAT_OK`
3. 只选择一个最高价值机会继续深挖：
   - 优先选择没有 `card_path`、或证据仍偏单一的机会
4. 读取该机会已有证据链接，再使用 `web.fetch` / `web.search` 沿相同主题继续补证据
5. 如果发现新的高价值证据：
   - 用 `python3 scripts/record_research_signal.py ...` 继续写入新 signal，并尽量复用同一个 `cluster-key`
   - 然后重新运行 `python3 scripts/triage_research_signals.py --signals-root data/research/signals --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --lookback-hours 168`
6. 如果该机会已经足够进入审议：
   - 运行 `python3 scripts/promote_research_opportunity.py --path data/research/opportunities.json --opportunity-id ... --status ready_review --card-dir data/research/opportunity-cards`
7. 将本轮结果写入 `data/exec-logs/opportunity-deep-dive/`

规则：

- 本 job 只做深挖和固化 Opportunity Card，不直接创建正式交付任务
- 证据不足时宁可保持 `candidate`，不要过早晋升
- 执行日志必须包含：`- Status: ok`、`- opportunity_id: ...`、`- action: ...`

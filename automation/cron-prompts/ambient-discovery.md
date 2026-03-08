[cron:ambient-discovery]

# Ambient Discovery Prompt

你是持续探索 agent。

本轮目标：在公开网页范围内，持续发现新的用户痛点、竞品变化、社区热点与技术机会。

流程：

1. 先运行：
   - `python3 scripts/prepare_exploration_batch.py --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md --limit 6`
2. 从结果中最多选择 3 个探索目标
3. 使用 `web.search` / `web.fetch` 扫描公开来源；渠道不限定，可以在发现新线索后继续 pivot 到新的公开网页
4. 每当发现一个高价值信号，就运行：
   - `python3 scripts/record_research_signal.py --signals-root data/research/signals --source-id ... --source-label ... --channel ... --topic-id ... --title ... --summary ... --signal-type ... --query ... --keyword ... --cluster-key ... --evidence-url ...`
5. 每轮最多记录 6 条信号；每条必须至少满足：
   - 有明确 `topic-id`
   - 有 `title` 与 `summary`
   - 有 `signal-type`
   - 有至少一个 `evidence-url`
   - 有稳定 `cluster-key`，建议格式：`<topic-id>:<简短主题>`
6. 关键新信号首写当天日志 `memory/YYYY-MM-DD.md`
7. 将本轮结果写入 `data/exec-logs/ambient-discovery/`

规则：

- 公共网页优先；不要依赖登录态平台
- 不把普通资讯搬运当成研究信号
- 同一主题的多条信号尽量复用同一个 `cluster-key`
- 如果没有真正新的高价值信号，写日志并返回 `HEARTBEAT_OK`
- 执行日志必须包含一行：`- Status: ok` 或 `- Status: no-signal`

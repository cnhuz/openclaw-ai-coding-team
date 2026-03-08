[cron:ambient-discovery]

# Ambient Discovery Prompt

你是持续探索 agent。

本轮目标：在公开网页范围内，持续发现新的用户痛点、竞品变化、社区热点与技术机会。

流程：

1. 先运行：
   - `python3 scripts/prepare_exploration_batch.py --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md --limit 6`
   - `python3 scripts/prepare_site_frontier.py --site-profiles data/research/site_profiles.json --topic-profiles data/research/topic_profiles.json --inventory data/skills/inventory.json --format md --limit 8`
   - `python3 scripts/sync_skill_inventory.py --output data/skills/inventory.json --format md`
2. 优先从 `site_frontier` 中选择 2 个热门入口 / Feed，再从 exploration batch 中选择 1 个搜索型目标
3. 使用 `web.search` / `web.fetch` / `browser` / 命中 policy 的低风险 skill 进行持续探索；站点不限定，可以在发现高价值新站点后继续 pivot
4. 如果发现新的高质量站点、论坛、博客或社区：
   - 先运行 `python3 scripts/upsert_site_profile.py --path data/research/site_profiles.json --label ... --domain ... --channel ... --access ... --preferred-tool ... --fallback-tool ... --topic-tag ... --reason "discovered during ambient discovery"`
   - 再将其视为后续探索目标
5. 每次准备访问某个站点或 URL 前，先运行：
   - `python3 scripts/plan_tool_route.py --site-profiles data/research/site_profiles.json --tool-profiles data/research/tool_profiles.json --inventory data/skills/inventory.json --domain ... --url ... --target-kind hot_page|feed|query|article|post|timeline --format md`
6. 按 route 依次尝试工具；每尝试一次都记录：
   - `python3 scripts/record_tool_attempt.py --attempts-root data/research/tool_attempts --site-id ... --site-label ... --domain ... --tool-id ... --stage ambient-discovery --topic-id ... --query ... --url ... --target-kind hot_page|feed|query|article|post|timeline --outcome success|failure|partial|skipped --failure-kind ... --quality none|weak|medium|strong --note ...`
7. 若 `web.fetch` 失败、内容过弱、或站点明显依赖 JS/登录：
   - 优先切到 `browser`
   - 若目标是持续博客/Feed 监控或站点 API 访问存在明显能力缺口，优先考虑 `skill:blogwatcher`、站点专用 skill，或搜索并补位 skill 候选
8. 发现 skill 能力缺口时：
   - 先查 `openclaw skills list --json`
   - 再用 `npx --yes clawhub search "..."` 搜候选
   - 若发现可信低风险候选，运行 `python3 scripts/register_skill_candidate.py --path data/skills/catalog.json --source-type clawhub --slug ... --name ... --capability-gap ... --reason ... --install-method npx-clawhub --risk low|medium|high --review-status pending --status candidate`
9. 每当发现一个高价值信号，就运行：
   - `python3 scripts/record_research_signal.py --signals-root data/research/signals --source-id ... --source-label ... --channel ... --topic-id ... --title ... --summary ... --signal-type ... --query ... --keyword ... --cluster-key ... --evidence-url ...`
10. 每轮最多记录 6 条信号；每条必须至少满足：
   - 有明确 `topic-id`
   - 有 `title` 与 `summary`
   - 有 `signal-type`
   - 有至少一个 `evidence-url`
   - 有稳定 `cluster-key`，建议格式：`<topic-id>:<简短主题>`
11. 关键新信号首写当天日志 `memory/YYYY-MM-DD.md`
12. 将本轮结果写入 `data/exec-logs/ambient-discovery/`

规则：

- 公共网页优先；不要依赖登录态平台
- 热门入口 / Feed 优先；不要每轮都从宽泛搜索开始
- 对 `X`、强 JS 站点、热门流、评论区，优先考虑 `browser`
- 站点不受预置样例限制；发现高质量新域名时必须注册到 `site_profiles.json`
- 不把普通资讯搬运当成研究信号
- 同一主题的多条信号尽量复用同一个 `cluster-key`
- 如果没有真正新的高价值信号，写日志并返回 `HEARTBEAT_OK`
- 执行日志必须包含一行：`- Status: ok` 或 `- Status: no-signal`

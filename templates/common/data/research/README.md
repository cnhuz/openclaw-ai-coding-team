# Research Runtime Data

这个目录是持续探索系统的运行态数据区。

目标：

- 持续扫描公开来源中的用户、社区、竞品与技术信号
- 将碎片信号沉淀为可排序、可复盘、可晋升的机会池
- 让 `aic-researcher` 不只是“接单研究”，还能长期巡航外部世界

## 目录结构

- `sources.json`：信号源目录与搜索模板
- `topic_profiles.json`：当前探索主题、关键词、排除词、学习统计
- `source_scores.json`：来源质量评分与历史命中率
- `opportunities.json`：聚合后的机会池
- `signals/`：原始信号 JSONL
- `opportunity-cards/`：已固化的 Opportunity Card

## 设计边界

- `tasks/registry.json` 只承载正式交付任务，不承载弱信号与半成品机会
- `data/research/` 承载探索期情报、候选机会与自学习权重
- 只有当机会满足晋升条件时，才应写入正式任务真相源

## 机会状态

- `watchlist`：已捕获，但价值或证据不足
- `candidate`：具备继续深挖价值
- `ready_review`：证据较充分，适合交给 captain / planner 审议
- `promoted`：已晋升为正式任务或已形成正式推进动作
- `rejected`：确认暂不值得推进

## 自学习原则

- 高价值来源会提升 `source_scores.json` 中的权重
- 经常产出噪音的来源会被降权
- 被晋升、被否决、持续观察的机会都会回写到 `topic_profiles.json` 学习统计
- `exploration-learning` 还会反向生成 `query_expansions` 与 `blocked_terms`
- 第一版先学习“来源权重”和“主题热度”，后续再逐步学习查询模板与细分渠道

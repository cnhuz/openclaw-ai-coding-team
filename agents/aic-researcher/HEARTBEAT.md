# HEARTBEAT.md

此角色默认不依赖 heartbeat 持续探索；常态由 isolated cron sprint 或调度事件驱动。

若你被显式启用 heartbeat，收到 heartbeat 时：

1. 只检查是否存在待执行的研究 sprint 或新的探索目标
2. 若存在明确 sprint，扫描用户反馈、竞品变化、社区讨论、技术趋势
3. 将值得关注的信号整理成 Opportunity Card
4. 把高频新术语交给 `aic-curator`
5. 无事可做时返回 `HEARTBEAT_OK`

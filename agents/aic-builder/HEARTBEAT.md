# HEARTBEAT.md

此角色默认不依赖 heartbeat 持续生产；常态由任务触发或 backlog sprint 驱动。

若你被显式启用 heartbeat，收到 heartbeat 时：

1. 只检查已派发给自己的未完成实现任务
2. 若 backlog 未清，只决定是否继续下一轮实现 sprint
3. 若存在明确 blocker，整理成结构化交接回给 `aic-dispatcher`
4. 若无明确任务，不自行扩张需求
5. 无事可做时返回 `HEARTBEAT_OK`

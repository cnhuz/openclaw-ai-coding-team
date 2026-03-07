# HEARTBEAT.md

收到 heartbeat 时：

1. 检查是否有卡在 `Researching` / `Planned` / `Observing` 太久的任务
2. 若 backlog 失衡，要求重新排序优先级
3. 若发现值得研究的新方向，交给 `aic-researcher` 经 `aic-planner` 收敛
4. 没有需要处理的事项时，返回 `HEARTBEAT_OK`

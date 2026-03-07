# HEARTBEAT.md

收到 heartbeat 时：

1. 检查是否有待验证但未出报告的任务
2. 抽查近期实现是否缺少最小回归
3. 整理高频失败模式，交给 `aic-curator`
4. 无事可做时返回 `HEARTBEAT_OK`

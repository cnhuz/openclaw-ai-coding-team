# HEARTBEAT.md

收到 heartbeat 时：

1. 检查 staging / production 的待发布项
2. 检查是否存在发布后未观察完成的任务
3. 如存在异常，整理结果回给 `aic-dispatcher`
4. 无事可做时返回 `HEARTBEAT_OK`

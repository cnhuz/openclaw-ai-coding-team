# HEARTBEAT.md

收到 heartbeat 时：

1. 检查是否有长期停留在 `Building` / `Verifying` / `Observing` 的任务
2. 检查是否有无人接手的返工项
3. 将可归档的结果交给 `aic-curator`
4. 无事可做时返回 `HEARTBEAT_OK`

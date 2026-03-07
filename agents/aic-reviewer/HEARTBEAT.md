# HEARTBEAT.md

收到 heartbeat 时：

1. 检查是否有长期无人审议的 `Planned` / `Verifying` / `Staging` 任务
2. 抽查最近通过的任务是否存在“无证据放行”
3. 整理常见打回原因，交给 `aic-curator`
4. 无事可做时返回 `HEARTBEAT_OK`

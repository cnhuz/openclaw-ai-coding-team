[cron:core-memory-hourly]

你是记忆微同步 agent。

目标：

- 把新的高价值会话信号补进当天记忆
- 只把稳定事实提升到 `MEMORY.md`
- 保持记忆新鲜，不写入 cron 噪音

硬规则：

- 必须通过 `python3 scripts/scan_sessions_incremental.py --openclaw-dir __OPENCLAW_HOME__ --agent __AGENT_ID__ --state-file memory/_state/scan_sessions_hourly.json --format md --max-chars 4000` 读取增量
- 不总结任何 `memory-` 开头的 ok 消息
- 不把工具输出原样写入记忆

流程：

1. 运行增量扫描脚本
2. 若没有新内容：
   - 写执行日志到 `data/exec-logs/memory-hourly/`
   - 回复：
     - 第一行：`memory-hourly ok`
     - 第二行：`status: no new signals`
     - 第三行：`updated: none`
3. 若有新内容：
   - 追加到当天 `memory/YYYY-MM-DD.md`
   - 仅在出现稳定约束、长期偏好、关键决策时更新 `MEMORY.md`
   - 写执行日志到 `data/exec-logs/memory-hourly/`
   - 回复：
     - 第一行：`memory-hourly ok`
     - 第二行：`status: updated`
     - 第三行：`updated: <comma-separated file paths>`

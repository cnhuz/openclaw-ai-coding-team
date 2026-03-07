# Cron Prompt Source of Truth

这里的 `.md` 文件是 cron prompt 的源码。

原则：

- 不直接在运行时 job 配置里手改 prompt
- 先改这里的文件，再同步到运行时
- prompt 要匹配 isolated session 的工具边界
- 每个自动化 prompt 第一行都应以 `[cron:<job-name>]` 开头，便于防套娃过滤
- 如果 prompt 依赖脚本，优先使用 `scripts/scan_sessions_incremental.py`、`scripts/lockfile.py`、`scripts/weekly_gate.py`

推荐文件：

- `memory-hourly.md`
- `daily-backup.md`
- `daily-reflection.md`
- `daily-curation.md`
- `memory-weekly.md`
- `research-sprint.md`
- `build-sprint.md`
- `SYNC-PROTOCOL.md`

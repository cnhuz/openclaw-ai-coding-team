# BOOT.md - Core Agent Startup Check

启动后快速检查：

1. 当前 workspace 是否存在 `MEMORY.md`、`memory/`、`scripts/`
2. 今天的 `memory/YYYY-MM-DD.md` 是否已存在；没有则补建
3. 若启用了 qmd，检查最近一次 `qmd status` 是否可用
4. 若启用了 cron，确认 `memory-hourly`、`daily-reflection`、`memory-weekly` 至少已安装

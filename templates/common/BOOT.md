# BOOT.md - Optional `boot-md` Startup Checklist

这个文件对应 OpenClaw 原生 `boot-md` hook 的启动巡检语义。

注意：

- 它适用于网关启动后的主会话巡检
- 它**不保证**被每个子 agent、isolated cron、独立工具调用自动读取
- 因此关键规则必须仍然写在根 `AGENTS.md`，不能只写在这里

若当前会话确实由 `boot-md` hook 触发，或你被明确要求执行启动巡检，则先做以下轻量检查：

1. 先读取今天与昨天的 `memory/YYYY-MM-DD.md`
2. 先运行 `python3 scripts/validate_task_registry.py --path tasks/registry.json`
3. 再运行 `python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root ~/.openclaw/workspace-aic-researcher/data/research --skills-root ~/.openclaw/workspace-aic-researcher/data/skills --output data/dashboard.md`
4. 检查 `MEMORY.md` 是否有过时条目，以及任务真相源与记忆是否明显漂移
5. 检查是否存在卡住的活跃任务、待同步记忆、待升级事实、待处理 blocker
6. 若当前角色是 `aic-captain`，且入口会话已存在但任务盘为空，优先立一个 `Intake` 任务并交给 `aic-planner`
7. 若当前角色是 `aic-dispatcher`，且存在 `Approved` / `Building` / `Verifying` / `Staging` / `Observing` 任务，就继续推进到下一负责人
8. 检查 Git 备份与定时任务是否明显失效；若失效，记录待办并提醒负责人
9. 若是发布相关 Agent，检查环境是否可达
10. 若发现 cron、记忆同步、周级 gate 或 `MEMORY.md` 并发写入异常，先查看 `scripts/README.md`
11. 确认当前工作仍符合根 `AGENTS.md` 中的角色边界
12. 无需处理时保持安静，不做多余动作

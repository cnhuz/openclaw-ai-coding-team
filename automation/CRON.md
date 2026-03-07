# CRON.md - Team Automation Schedule

这份文件定义团队版 OpenClaw 的推荐定时策略。

原则：

- 精确定时任务用 cron
- heartbeat 只做粗粒度检查与调度
- 执行型 agent 靠任务触发、system event、isolated cron sprint 持续推进
- 默认时区显式写为 `Asia/Shanghai`

## 每日固定任务

- `00:00`：每个 workspace 做 Git 备份
- `00:10`：`aic-reflector` 做当日复盘
- `00:20`：`aic-curator` 做分类沉淀与长期记忆提升

建议都使用 isolated cron，避免把维护任务和主会话混在一起。

## 记忆同步叠层（推荐）

如果你希望把 `fusion` 的可靠记忆机制完整接进来，建议在固定任务之外再加一层记忆自动化：

- `memory-hourly`：每天多次微同步，只把增量高价值信号写入当天日志
- `daily-curation`：承担当天 canonical 整理与 A′ 滚动区维护
- `memory-weekly`：每天固定时间触发，但通过 gate 控制为“每周至少一次真正晋升”

推荐约束：

- `memory-hourly` 不依赖 `sessions_list` / `sessions_history`
- session 真相源用 `~/.openclaw/agents/<agent>/sessions/*.jsonl` 与 `*.jsonl.reset.*`
- 增量游标落到 `memory/_state/*.json`
- 所有写 `MEMORY.md` 的 job 共用 `memory/_state/MEMORY.lock`
- `memory-weekly` 建议放在 `00:40` 左右，并使用 `weekly_gate.py`

## 持续探索

`aic-researcher` 建议用 cron 跑固定 sprint，而不是靠 heartbeat 空转：

- 高频项目：每 `1h` 一轮
- 常规项目：每 `2h` 一轮
- 每轮只做一个研究 sprint，并输出 Opportunity Card 或研究摘要

## 持续实现

`aic-builder` 建议按 backlog 驱动：

- 有新任务时立即被调度唤醒
- backlog 未清时，每 `15m` 或 `30m` 续跑一轮实现 sprint
- backlog 清空时 no-op，等待下一次派发

## 心跳建议

默认启用 heartbeat 的角色：

- `aic-captain`
- `aic-dispatcher`

可按窗口期临时启用 heartbeat 的角色：

- `aic-releaser`

默认不依赖 heartbeat 驱动生产的角色：

- `aic-researcher`
- `aic-builder`
- `aic-tester`
- `aic-curator`
- `aic-reflector`

## 配置建议

- cron prompt 建议以 `.md` 文件作为源码，再同步到运行时
- 备份、复盘、沉淀拆成独立 job，便于重跑与排障
- 所有自动化结果都要能写回记忆或产生结构化通知，不能只“跑了但没痕迹”
- 共享文件写入前先拿锁；周级巩固任务建议使用 at-least-once gate
- isolated cron 若看不到主会话，可接入 session JSONL 扫描脚本
- 执行日志建议统一落到 `data/exec-logs/`
- 如需完整三层记忆自动化，优先复用 `automation/scripts/` 与 `automation/cron-prompts/`

如需具体 prompt，可先看 `automation/cron-prompts/`，再参考仓库中的 `openclaw-memory-fusion/docs/cron-prompts.md`。

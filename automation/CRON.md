# CRON.md - Team Automation Schedule

这份文件定义团队版 OpenClaw 的推荐定时策略。

原则：

- 精确定时任务用 cron
- heartbeat 只做粗粒度检查与调度
- 执行型 agent 靠任务触发、system event、isolated cron sprint 持续推进
- 默认时区显式写为 `Asia/Shanghai`
- 默认安装完成后，应至少具备一次点火动作：`boot-md` 启动巡检、`openclaw system event --mode now`，或两者同时启用

## 每日固定任务

- `每 10m`：`aic-captain` 刷新 `data/dashboard.md`
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

默认建议先给以下角色启用完整记忆层：

- `aic-captain`
- `aic-planner`
- `aic-dispatcher`

如需更强的长期上下文保鲜，再逐步扩到 `aic-researcher` / `aic-builder` 等执行角色。

## 持续探索

`aic-researcher` 建议用 cron 跑固定 sprint，而不是靠 heartbeat 空转：

- `ambient-discovery`：每 `30m` 一轮，持续巡公开来源
- `signal-triage`：每 `30m` 或 `45m` 一轮，对弱信号聚合打分
- `opportunity-deep-dive`：每 `2h` 一轮，对高分候选做深挖
- `opportunity-promotion`：每 `4h` 一轮，由 captain / planner 决定是否晋升正式任务
- `exploration-learning`：每 `6h` 一轮，学习高价值来源、query expansion 和噪音词
- `research-sprint`：继续保留，用于正式 `Researching` 任务的定向研究

推荐分层：

- 持续探索层：不直接创建交付任务，先进入 `data/research/`
- 正式研究层：进入 `tasks/registry.json` 后，再按 `Researching` 生命周期推进

推荐数据面：

- `data/research/signals/`
- `data/research/opportunities.json`
- `data/research/topic_profiles.json`
- `data/research/source_scores.json`
- `data/research/opportunity-cards/`

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

- 推荐用 `setup/install-openclaw-automation.sh` 或 `setup/install-openclaw-automation.ps1` 做 cron 安装与点火
- 安装完成后，推荐立刻触发一次 `openclaw system event --mode now`
- cron prompt 建议以 `.md` 文件作为源码，再同步到运行时
- 备份、复盘、沉淀拆成独立 job，便于重跑与排障
- 所有自动化结果都要能写回记忆或产生结构化通知，不能只“跑了但没痕迹”
- 共享文件写入前先拿锁；周级巩固任务建议使用 at-least-once gate
- isolated cron 若看不到主会话，可接入 session JSONL 扫描脚本
- 执行日志建议统一落到 `data/exec-logs/`
- 如需完整三层记忆自动化，优先复用 `automation/scripts/` 与 `automation/cron-prompts/`

如需具体 prompt，可先看 `automation/cron-prompts/`，再参考仓库中的 `openclaw-memory-fusion/docs/cron-prompts.md`。

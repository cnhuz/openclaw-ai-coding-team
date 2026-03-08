# Automation Helper Scripts

这个目录位于**团队设计包仓库**中，用来保存脚本源码。

它不是要求你把整个 `automation/` 目录复制进真实 workspace。

团队包现在已经内置这十四个 helper scripts：

- `scan_sessions_incremental.py`：增量扫描会话 JSONL
- `lockfile.py`：共享文件写锁
- `weekly_gate.py`：每周至少一次 gate
- `git_backup_health.py`：本地 Git / GitHub 远程 / pull-push 健康检查与自举
- `validate_task_registry.py`：本地任务真相源校验
- `query_task_registry.py`：本地任务真相源查询摘要
- `update_task_registry.py`：本地任务真相源更新器
- `create_handoff.py`：结构化交接生成器
- `refresh_dashboard.py`：运行看板刷新器
- `prepare_exploration_batch.py`：生成持续探索批次
- `record_research_signal.py`：记录结构化外部信号
- `triage_research_signals.py`：聚合 signals 并产出机会池
- `query_research_opportunities.py`：查询机会池
- `promote_research_opportunity.py`：固化 Opportunity Card 并可晋升正式任务
- `exploration_learning.py`：学习 query expansion、blocked terms 并清理陈旧候选

它们由本仓库持续维护，目前既包含原有记忆/任务协同脚本，也包含新加入的持续探索脚本。

## 推荐运行位置

在真实 workspace 中，建议把这九个脚本一起放到：

- `scripts/scan_sessions_incremental.py`
- `scripts/lockfile.py`
- `scripts/weekly_gate.py`
- `scripts/git_backup_health.py`
- `scripts/validate_task_registry.py`
- `scripts/query_task_registry.py`
- `scripts/update_task_registry.py`
- `scripts/create_handoff.py`
- `scripts/refresh_dashboard.py`
- `scripts/prepare_exploration_batch.py`
- `scripts/record_research_signal.py`
- `scripts/triage_research_signals.py`
- `scripts/query_research_opportunities.py`
- `scripts/promote_research_opportunity.py`
- `scripts/exploration_learning.py`

这样 cron prompt 可以直接使用相对路径，不必依赖当前仓库结构。

推荐再配一个运行态说明文件：

- `scripts/README.md`

让普通 agent 在非 cron 场景下，也知道这些脚本何时该用、何时不该用。

## 最小用法

- 增量扫描：
  - `python3 scripts/scan_sessions_incremental.py --state-file memory/_state/scan_sessions_hourly.json --format md --max-chars 4000`
- 获取写锁：
  - `python3 scripts/lockfile.py acquire --lock memory/_state/MEMORY.lock --timeout 120 --stale-seconds 7200`
- 释放写锁：
  - `python3 scripts/lockfile.py release --lock memory/_state/MEMORY.lock`
- weekly gate 检查：
  - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone Asia/Shanghai --mode check`
- weekly gate 标记成功：
  - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone Asia/Shanghai --mode mark`
- 备份自举与 GitHub 远程检查：
  - `python3 scripts/git_backup_health.py --workspace-root . --policy-path data/github-backup-policy.json --log-dir data/exec-logs/daily-backup`
- 校验任务真相源：
  - `python3 scripts/validate_task_registry.py --path tasks/registry.json`
- 读取 build backlog：
  - `python3 scripts/query_task_registry.py --path tasks/registry.json --view build_queue --format md`
- 读取 captain 摘要：
  - `python3 scripts/query_task_registry.py --path tasks/registry.json --view captain --blocked-only --format md`
- 创建或更新任务：
  - `python3 scripts/update_task_registry.py --path tasks/registry.json --task-id TASK-001 --title "重构任务源" --state Building --owner aic-builder --priority P1 --next-step "完成脚本改造" --append-evidence protocols/task-source-of-truth.md`
- 生成交接并同步真相源：
  - `python3 scripts/create_handoff.py --task-id TASK-001 --current-stage Building --goal "转交测试" --deliverable "实现 diff + 验证建议" --evidence src/app.ts --next-owner aic-tester --breakpoint "先准备 fixture" --sync-registry --sync-state Verifying --sync-owner aic-tester --sync-next-step "执行回归"`
- 刷新运行看板：
  - `python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root data/research --output data/dashboard.md`
- 生成探索批次：
  - `python3 scripts/prepare_exploration_batch.py --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md`
- 记录研究信号：
  - `python3 scripts/record_research_signal.py --signals-root data/research/signals --source-id reddit-public --source-label "Reddit Public" --channel community-forum --topic-id user-pain-demand --title "用户抱怨现有工具切换成本高" --summary "多个帖子提到流程中断和重复劳动" --signal-type user_pain --query "workflow pain reddit" --cluster-key user-pain-demand:workflow-friction --evidence-url https://example.com/thread`
- 聚合研究信号：
  - `python3 scripts/triage_research_signals.py --signals-root data/research/signals --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md`
- 查询机会池：
  - `python3 scripts/query_research_opportunities.py --path data/research/opportunities.json --status candidate --status ready_review --limit 5 --format md`
- 固化或晋升机会：
  - `python3 scripts/promote_research_opportunity.py --path data/research/opportunities.json --opportunity-id OPP-1234567890 --status ready_review --card-dir data/research/opportunity-cards`
- 探索结果自学习：
  - `python3 scripts/exploration_learning.py --topics data/research/topic_profiles.json --opportunities data/research/opportunities.json --stale-days 7 --format md`

原则：

- `memory-hourly` 不要再改回 `sessions_list` / `sessions_history`
- `daily-curation` 与 `memory-weekly` 写 `MEMORY.md` 时应共用 `memory/_state/MEMORY.lock`
- `memory/_state/` 下的游标、锁、gate 状态不要提交到远程仓库
- 若你升级了上游脚本版本，要同步更新本目录与相关 cron prompt

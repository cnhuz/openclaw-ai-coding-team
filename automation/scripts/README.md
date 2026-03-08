# Automation Helper Scripts

这个目录位于**团队设计包仓库**中，用来保存脚本源码。

它不是要求你把整个 `automation/` 目录复制进真实 workspace。

团队包现在已经内置这些 helper scripts：

- `scan_sessions_incremental.py`：增量扫描会话 JSONL
- `lockfile.py`：共享文件写锁
- `weekly_gate.py`：每周至少一次 gate
- `git_backup_health.py`：本地 Git / GitHub 远程 / pull-push 健康检查与自举
- `validate_task_registry.py`：本地任务真相源校验
- `query_task_registry.py`：本地任务真相源查询摘要
- `update_task_registry.py`：本地任务真相源更新器
- `create_handoff.py`：结构化交接生成器
- `refresh_dashboard.py`：运行看板刷新器
- `execution_target.py`：加载真实执行目标配置
- `verify_worktree_lifecycle.py`：在临时 git repo 中烟测 lifecycle 主闭环
- `prepare_exploration_batch.py`：生成持续探索批次
- `prepare_site_frontier.py`：生成站点热门入口、Feed 与搜索前沿
- `prepare_planner_intake.py`：从 captain 任务盘为 planner 生成 intake packet
- `prepare_builder_intake.py`：从 captain 任务盘为 builder 生成 intake packet，并附带真实 repo_root
- `prepare_tester_intake.py`：从 captain 任务盘为 tester 生成 verification intake packet
- `prepare_releaser_intake.py`：从 captain 任务盘为 releaser 生成 release intake packet
- `prepare_reflector_intake.py`：从 captain 任务盘为 reflector 生成 reflection intake packet，并补齐协议/模板绝对路径
- `validate_reflection_closeout.py`：校验 reflection 的 Observe Checks 结构与 knowledge proposal 字段
- `record_research_signal.py`：记录结构化外部信号
- `triage_research_signals.py`：聚合 signals 并产出机会池
- `query_research_opportunities.py`：查询机会池
- `promote_research_opportunity.py`：固化 Opportunity Card 并可晋升正式任务
- `bridge_ready_review_opportunity.py`：把 `ready_review` 机会确定性桥接成正式任务与 planner handoff
- `bridge_approved_task.py`：把 `Approved` 任务确定性推进到 builder 队列
- `exploration_learning.py`：学习 query expansion、blocked terms 并清理陈旧候选
- `upsert_site_profile.py`：记录或更新新发现站点画像
- `plan_tool_route.py`：按站点/域名规划工具回退链
- `record_tool_attempt.py`：记录一次站点-工具-结果尝试
- `tool_route_learning.py`：学习每个站点的更优工具路线
- `sync_skill_inventory.py`：同步当前 OpenClaw skills 库存
- `register_skill_candidate.py`：登记 skill 候选与审查状态
- `query_skill_catalog.py`：查询 skill 候选池
- `bootstrap_skill_dependency.py`：为 skill 安装缺失的 installer / toolchain 做本地自举
- `install_skill_candidate.py`：按 policy 自动安装可信低风险 skill
- `worktree_lifecycle.py`：为单个 agent 管理 git worktree 的 setup / status / cleanup 生命周期元数据与安全清理边界
- `compute_agent_kpi.py`：按证据计算 Daily / Weekly agent KPI scorecards

它们由本仓库持续维护，目前既包含原有记忆/任务协同脚本，也包含新加入的持续探索脚本。

## 推荐运行位置

在真实 workspace 中，建议把这些脚本一起放到：

- `scripts/scan_sessions_incremental.py`
- `scripts/lockfile.py`
- `scripts/weekly_gate.py`
- `scripts/git_backup_health.py`
- `scripts/validate_task_registry.py`
- `scripts/query_task_registry.py`
- `scripts/update_task_registry.py`
- `scripts/create_handoff.py`
- `scripts/refresh_dashboard.py`
- `scripts/execution_target.py`
- `scripts/verify_worktree_lifecycle.py`
- `scripts/prepare_exploration_batch.py`
- `scripts/prepare_site_frontier.py`
- `scripts/prepare_planner_intake.py`
- `scripts/prepare_builder_intake.py`
- `scripts/prepare_tester_intake.py`
- `scripts/prepare_releaser_intake.py`
- `scripts/prepare_reflector_intake.py`
- `scripts/validate_reflection_closeout.py`
- `scripts/record_research_signal.py`
- `scripts/triage_research_signals.py`
- `scripts/query_research_opportunities.py`
- `scripts/promote_research_opportunity.py`
- `scripts/bridge_ready_review_opportunity.py`
- `scripts/bridge_approved_task.py`
- `scripts/exploration_learning.py`
- `scripts/upsert_site_profile.py`
- `scripts/plan_tool_route.py`
- `scripts/record_tool_attempt.py`
- `scripts/tool_route_learning.py`
- `scripts/sync_skill_inventory.py`
- `scripts/register_skill_candidate.py`
- `scripts/query_skill_catalog.py`
- `scripts/bootstrap_skill_dependency.py`
- `scripts/install_skill_candidate.py`
- `scripts/worktree_lifecycle.py`
- `scripts/compute_agent_kpi.py`

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
  - `python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root data/research --skills-root data/skills --output data/dashboard.md`
- 生成探索批次：
  - `python3 scripts/prepare_exploration_batch.py --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md`
- 生成站点前沿：
  - `python3 scripts/prepare_site_frontier.py --site-profiles data/research/site_profiles.json --topic-profiles data/research/topic_profiles.json --inventory data/skills/inventory.json --format md --limit 8`
- 生成 planner intake packet：
  - `python3 scripts/prepare_planner_intake.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --packet-dir intake --owner aic-planner --state Intake --format md`
- 读取执行目标：
  - `PYTHONPATH=scripts python3 -c 'from pathlib import Path; from execution_target import load_execution_target; print(load_execution_target(Path("data/execution-target.json"))["repo_root"])'`
- 生成 builder intake packet：
  - `python3 scripts/prepare_builder_intake.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --execution-target-path ~/.openclaw/workspace-aic-captain/data/execution-target.json --packet-dir intake --owner aic-builder --state Building --format md`
- 生成 tester intake packet：
  - `python3 scripts/prepare_tester_intake.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --execution-target-path ~/.openclaw/workspace-aic-captain/data/execution-target.json --packet-dir verification-intake --owner aic-tester --state Verifying --format md`
- 生成 releaser intake packet：
  - `python3 scripts/prepare_releaser_intake.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --execution-target-path ~/.openclaw/workspace-aic-captain/data/execution-target.json --packet-dir release-intake --owner aic-releaser --state Staging --format md`
- 生成 reflector intake packet：
  - `python3 scripts/prepare_reflector_intake.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --execution-target-path ~/.openclaw/workspace-aic-captain/data/execution-target.json --packet-dir reflection-intake --owner aic-reflector --state Released --format md`
- 校验 reflection 收口产物：
  - `python3 scripts/validate_reflection_closeout.py --packet-path reflection-intake/<task-id>.md --reflection-path /path/to/reflection.md --proposal-path /path/to/proposal.json --format md`
- 说明：正式任务控制面默认以 `~/.openclaw/workspace-aic-captain/tasks/registry.json` 与 `~/.openclaw/workspace-aic-captain/handoffs/` 为准；执行角色不要只盯自己 workspace 的空任务盘
- 说明：真正写代码、跑测试、做 release gate 的目标仓库路径默认由 `data/execution-target.json` 声明；builder/tester/releaser 不应把自己的运行态 workspace 当成业务仓库
- 记录研究信号：
  - `python3 scripts/record_research_signal.py --signals-root data/research/signals --source-id reddit-public --source-label "Reddit Public" --channel community-forum --topic-id user-pain-demand --title "用户抱怨现有工具切换成本高" --summary "多个帖子提到流程中断和重复劳动" --signal-type user_pain --query "workflow pain reddit" --cluster-key user-pain-demand:workflow-friction --evidence-url https://example.com/thread`
- 聚合研究信号：
  - `python3 scripts/triage_research_signals.py --signals-root data/research/signals --sources data/research/sources.json --topics data/research/topic_profiles.json --source-scores data/research/source_scores.json --opportunities data/research/opportunities.json --format md`
- 查询机会池：
  - `python3 scripts/query_research_opportunities.py --path data/research/opportunities.json --status candidate --status ready_review --limit 5 --format md`
- 固化或晋升机会：
  - `python3 scripts/promote_research_opportunity.py --path data/research/opportunities.json --opportunity-id OPP-1234567890 --status ready_review --card-dir data/research/opportunity-cards`
- 把 ready_review 机会桥接成正式任务：
  - `python3 scripts/bridge_ready_review_opportunity.py --opportunities-path ~/.openclaw/workspace-aic-researcher/data/research/opportunities.json --task-registry-path tasks/registry.json --handoff-dir handoffs --task-owner aic-planner --task-state Intake --format md`
- 把 Approved 任务推进到 builder 队列：
  - `python3 scripts/bridge_approved_task.py --registry-path ~/.openclaw/workspace-aic-captain/tasks/registry.json --handoffs-dir ~/.openclaw/workspace-aic-captain/handoffs --task-owner aic-dispatcher --next-owner aic-builder --format md`
- 探索结果自学习：
  - `python3 scripts/exploration_learning.py --topics data/research/topic_profiles.json --opportunities data/research/opportunities.json --stale-days 7 --format md`
- 注册新站点画像：
  - `python3 scripts/upsert_site_profile.py --path data/research/site_profiles.json --label "Lobsters" --domain lobste.rs --channel developer-community --preferred-tool web.fetch --fallback-tool browser --topic-tag technical-enablers`
- 规划工具路线：
  - `python3 scripts/plan_tool_route.py --site-profiles data/research/site_profiles.json --tool-profiles data/research/tool_profiles.json --inventory data/skills/inventory.json --url https://x.com/explore --target-kind timeline --format md`
- 记录工具尝试：
  - `python3 scripts/record_tool_attempt.py --attempts-root data/research/tool_attempts --site-id x --tool-id browser --stage ambient-discovery --target-kind timeline --outcome success --quality strong --url https://x.com/explore`
- 学习工具路线：
  - `python3 scripts/tool_route_learning.py --site-profiles data/research/site_profiles.json --attempts-root data/research/tool_attempts --format md`
- 同步 skills 库存：
  - `python3 scripts/sync_skill_inventory.py --output data/skills/inventory.json --format md`
- 注册 skill 候选：
  - `python3 scripts/register_skill_candidate.py --path data/skills/catalog.json --source-type clawhub --slug blogwatcher --name "Blogwatcher" --capability-gap "持续博客订阅" --reason "连续出现官方博客跟踪缺口" --install-method npx-clawhub --risk low --review-status approved --status approved`
- 查询 skill 候选：
  - `python3 scripts/query_skill_catalog.py --path data/skills/catalog.json --status candidate --status approved --format md`
- 自举 skill 安装依赖：
  - `python3 scripts/bootstrap_skill_dependency.py --installer go --policy-path data/skills/dependency_policy.json --format md`
- 安装 skill 候选：
  - `python3 scripts/install_skill_candidate.py --catalog data/skills/catalog.json --policy data/skills/policy.json --dependency-policy data/skills/dependency_policy.json --candidate-id SKILL-1234567890 --format md`
- 管理 worktree 生命周期：
  - `python3 scripts/worktree_lifecycle.py setup --repo-root /path/to/repo --agent-id agent-001 --task-id TASK-001 --worktree-root /tmp/worktrees --branch agent/agent-001 --port-base 4100 --port-slots 32 --hook-config config/worktree-hooks.json`
  - `python3 scripts/worktree_lifecycle.py annotate --repo-root /path/to/repo --agent-id agent-001 --task-id TASK-001 --process-pid 12345 --temp-path /tmp/worktrees/agent-001--task-001/.cache --note "dev server started" --status in_use`
  - `python3 scripts/worktree_lifecycle.py status --repo-root /path/to/repo --agent-id agent-001 --task-id TASK-001`
  - `python3 scripts/worktree_lifecycle.py cleanup --repo-root /path/to/repo --agent-id agent-001 --task-id TASK-001`
- 烟测 lifecycle 工具：
  - `python3 scripts/verify_worktree_lifecycle.py --format md`
- 计算 Daily KPI：
  - `python3 scripts/compute_agent_kpi.py --openclaw-home ~/.openclaw --period daily --format md`
- 计算 Weekly KPI 并写入运行态：
  - `python3 scripts/compute_agent_kpi.py --openclaw-home ~/.openclaw --period weekly --write --format md`

原则：

- `memory-hourly` 不要再改回 `sessions_list` / `sessions_history`
- `daily-curation` 与 `memory-weekly` 写 `MEMORY.md` 时应共用 `memory/_state/MEMORY.lock`
- `memory/_state/` 下的游标、锁、gate 状态不要提交到远程仓库
- `.openclaw-runtime/` 这类 repo 本地 lifecycle 状态目录不要提交到远程仓库
- 若你升级了上游脚本版本，要同步更新本目录与相关 cron prompt

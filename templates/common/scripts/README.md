# Scripts Runtime Guide

这个目录属于**真实 workspace 的运行态工具区**。

与之相对：

- `automation/` 是团队设计包仓库里的源码与说明区
- `scripts/` 才是 agent 在真实 workspace 中实际调用的位置
- 根 `AGENTS.md` 应告诉 agent 什么时候查看这里

## 什么时候看这个文件

遇到以下情况时，先看这里：

- cron / heartbeat / system event 相关排障
- 记忆同步异常
- `MEMORY.md` 可能被多个 job 同时写入
- 周级任务需要判断“本周是否已跑过”

## 当前脚本

### `scripts/worktree_lifecycle.py`

用途：

- 为单个 agent 创建 / 查询 / 清理 git worktree 生命周期记录
- 把 worktree 路径、branch/ref、端口保留、env 文件、临时目录、hook 结果落盘到 repo 控制的状态目录
- 在 cleanup 时只清理该 agent 已登记资源，并输出可审计失败项

什么时候用：

- 多个 AI agent 需要并行操作同一仓库，但希望把 setup / cleanup 变成明确命令而不是人工步骤时
- 需要给 reviewer 说明“这个工具负责到哪一层、不会越界做什么”时

不要用于：

- 充当完整调度器、任务队列或沙箱平台
- 默认扫描并清理未知全局进程、未知 worktree、未知端口占用
- 自动执行来源不明的高风险 hook

### `scripts/verify_worktree_lifecycle.py`

用途：

- 在临时 git repo 中跑一遍 `setup -> annotate -> cleanup`
- 快速确认 lifecycle 工具没有结构性退化

什么时候用：

- `tester-gate`
- 修改 `worktree_lifecycle.py` 后想做最小烟测时

### `scripts/query_task_registry.py`

用途：

- 读取 `tasks/registry.json`
- 输出给 `captain`、`dispatcher`、cron prompt 用的任务摘要

什么时候用：

- `captain` 查看活跃任务与 blocker
- `dispatcher` 查看待派发、返工、阻塞任务
- `build-sprint` 读取 `Building` / `Rework` 队列
- `daily-reflection` 读取当前任务盘面

不要用于：

- 直接改写任务状态
- 绕过任务真相源，靠命令行输出当主记录

### `scripts/update_task_registry.py`

用途：

- 创建或更新 `tasks/registry.json` 中的任务项
- 在状态切换时同步写入 `state`、`owner`、`next_step`、`blocker`、`breakpoint`

什么时候用：

- `dispatcher` 派发任务
- `builder` 发现 blocker 或进入 `Building`
- `tester` 切到 `Verifying` 或打回
- `releaser` 切到 `Staging` / `Released` / `Observing`

不要用于：

- 替代 handoff
- 跳过审议流程私自改任务范围

### `scripts/create_handoff.py`

用途：

- 生成标准化 handoff Markdown 文件
- 可选同步 `tasks/registry.json`

什么时候用：

- 跨角色转手
- 本轮任务未闭合但需要留下恢复入口
- 需要把证据、风险、下一负责人一起固化时

不要用于：

- 用 handoff 代替任务真相源
- 没有证据时凑交接

### `scripts/refresh_dashboard.py`

用途：

- 汇总 `tasks/registry.json`、`handoffs/`、`data/exec-logs/`、OpenClaw `sessions`
- 刷新 `data/dashboard.md`

什么时候用：

- `captain` / `dispatcher` 做启动巡检
- 每日复盘前快速看盘面
- 想确认最近失败 job、阻塞任务、交接密度，以及八段闭环有没有真正启动时

不要用于：

- 替代底层真相源
- 在没有刷新数据的前提下把 dashboard 当唯一事实

### `scripts/prepare_exploration_batch.py`

用途：

- 从 `data/research/` 的主题画像、来源权重、机会池中，生成本轮最值得探索的公开来源与搜索 query

什么时候用：

- `ambient-discovery`
- 需要决定“这轮先去哪些论坛 / 社区 / 竞品站看什么”时

不要用于：

- 直接替代研究判断
- 把它生成的 query 当成唯一正确方向

### `scripts/prepare_site_frontier.py`

用途：

- 从 `site_profiles.json` 生成本轮优先浏览的热门入口、Feed 和站点前沿

什么时候用：

- `ambient-discovery`
- 想优先看“站点当前最热/最值得跟”的页面，而不是每轮都从宽泛搜索开始时

不要用于：

- 替代主题级探索批次
- 只盯一个站点连续刷，忽略覆盖率

### `scripts/prepare_planner_intake.py`

用途：

- 从 captain 任务盘里挑出 `owner=aic-planner` 的 `Intake / Replan` 任务
- 生成 planner 本地可直接消费的 intake packet

什么时候用：

- `planner-intake`
- 想把“任务已晋升”稳定推进到“planner 真正开工”时

### `scripts/prepare_builder_intake.py`

用途：

- 从 captain 控制面任务盘里挑出 `owner=aic-builder` 的 `Building / Rework` 任务
- 生成 builder 本地可直接消费的 intake packet
- 补上真实代码仓库目标 `repo_root`

什么时候用：

- `build-sprint`
- 想确认 builder 不是在自己的运行态 workspace 里“空转写代码”时

### `scripts/prepare_tester_intake.py`

用途：

- 从 captain 控制面任务盘里挑出 `owner=aic-tester` 的 `Verifying` 任务
- 生成 tester 本地 verification packet
- 带上统一测试命令与 acceptance

什么时候用：

- `tester-gate`
- 想把“实现完成”稳定推进到“测试验证”时

### `scripts/prepare_releaser_intake.py`

用途：

- 从 captain 控制面任务盘里挑出 `owner=aic-releaser` 的 `Staging` 任务
- 生成 releaser 本地 release packet
- 带上 `release_mode`、回滚命令与观察项

什么时候用：

- `releaser-gate`
- 想避免 releaser 在缺少发布上下文时空转时

## 控制面约定

- 当前团队默认以 `aic-captain` 工作区的 `tasks/registry.json` 作为正式任务控制面
- `aic-planner` / `aic-builder` / `aic-tester` / `aic-releaser` 的 cron 若需要读写正式任务，应优先使用 captain 工作区的绝对路径，而不是各自 workspace 中那份可能为空的本地副本
- 真正执行代码实现、测试与 release gate 的目标仓库默认以 `aic-captain/data/execution-target.json` 为准
- 若项目需要自定义 setup / cleanup hook，可显式提供 `data/worktree-hook-config.example.json` 的同结构文件，再由 `worktree_lifecycle.py --hook-config ...` 加载

### `scripts/bridge_approved_task.py`

用途：

- 从 dispatcher 队列中挑一个 `Approved` 任务
- 机械推进到 `Building`，并生成给 `aic-builder` 的 handoff

什么时候用：

- `dispatch-approved`
- 想避免 `Approved` 任务挂在 dispatcher 手里不往 builder 流动时

### `scripts/record_research_signal.py`

用途：

- 把外部世界发现的碎片信号写成结构化 JSONL

什么时候用：

- 发现新的用户痛点、竞品变化、社区热议、技术变化时
- 需要给 triage 提供可机器消费的原始信号时

不要用于：

- 直接创建正式任务
- 没有证据链接就硬凑 signal

### `scripts/triage_research_signals.py`

用途：

- 对 `signals/` 去重、聚类、打分，产出 `opportunities.json`
- 更新 `source_scores.json` 与 `topic_profiles.json` 的学习统计

什么时候用：

- `signal-triage`
- 想把持续探索从“很多碎片”收敛成“可排序机会池”时

不要用于：

- 直接把所有候选都晋升成立项
- 把短期噪音误当长期方向

### `scripts/query_research_opportunities.py`

用途：

- 查询机会池中的 `candidate / ready_review / promoted` 项

什么时候用：

- `opportunity-deep-dive`
- `opportunity-promotion`
- captain / planner 审议下一轮值得正式化的探索结果时

不要用于：

- 替代正式任务真相源
- 把 `ready_review` 直接等同于“已经立项”

### `scripts/promote_research_opportunity.py`

用途：

- 固化 Opportunity Card
- 可选把高价值机会晋升成正式任务

什么时候用：

- 机会已经有足够证据，准备交给 `captain` / `planner`
- 想把探索层和正式任务层可靠衔接时

不要用于：

- 证据不足时强行立项
- 绕过 `captain` / `planner` 的审议边界

### `scripts/bridge_ready_review_opportunity.py`

用途：

- 把 `ready_review` 机会确定性桥接成正式任务
- 同时生成给 `aic-planner` 的 handoff，减少机会晋升阶段对 prompt 临场判断的依赖

什么时候用：

- `opportunity-promotion`
- 想把“机会池里成熟机会”稳定推进到正式交付流时

不要用于：

- 直接替代 deep-dive
- 在证据仍明显不足时强行越过审议门

### `scripts/exploration_learning.py`

用途：

- 从 `opportunities.json` 学习更好的 query expansion 与 blocked terms
- 对长期无推进的 `candidate` 做轻量降级，避免机会池发霉

什么时候用：

- `exploration-learning`
- 想让探索链逐步学会“去哪找”和“什么是噪音”时

不要用于：

- 替代 deep-dive
- 把一次偶然命中的关键词永久固化

### `scripts/upsert_site_profile.py`

用途：

- 把新发现的站点、论坛、博客补进 `data/research/site_profiles.json`

什么时候用：

- 探索中发现预置样例之外的新域名，且后续值得继续追踪

### `scripts/plan_tool_route.py`

用途：

- 基于站点画像、技能库存、browser 可用性，给出当前最合理的工具回退链

什么时候用：

- 访问某站点或 URL 前，先决定是 `web.search`、`web.fetch`、`browser` 还是 skill
- 访问热门页、Feed、时间线、文章正文前，先按 `target-kind` 规划路线

### `scripts/record_tool_attempt.py`

用途：

- 记录一次“站点-工具-结果”尝试

什么时候用：

- 抓取失败、抓取成功、正文偏弱、切换工具时都应记录
- 记录时应带上 `target-kind`，让后续学习知道“热榜页、Feed、正文页”各自哪种工具更稳

### `scripts/tool_route_learning.py`

用途：

- 从 `tool_attempts/` 学每个站点的优先工具与避免工具
- 反向学习更适合的 `frontier kind`，并把明显的 `login-required` / `js-heavy` 信号写回站点画像

什么时候用：

- 周期性调优探索系统，不直接创建任务

### `scripts/sync_skill_inventory.py`

用途：

- 同步当前 OpenClaw 可见 skills 到 `data/skills/inventory.json`

什么时候用：

- 搜索新 skill 前，先知道已经有哪些可用能力

### `scripts/register_skill_candidate.py`

用途：

- 登记一个 skill 候选，包括能力缺口、风险、来源、安装方式

什么时候用：

- 发现明确能力缺口并找到可能补位的 skill

### `scripts/query_skill_catalog.py`

用途：

- 查询当前 skill 候选池

什么时候用：

- `skill-scout` / `skill-maintenance` / `reflector` 回看候选与安装状态

### `scripts/bootstrap_skill_dependency.py`

用途：

- 为 skill 安装缺失的 installer / toolchain 做本地自举

什么时候用：

- 已批准 skill 的安装被 `go`、本地 toolchain 等前置条件挡住时
- 想把“候选已批准”推进到“真正可安装”时

### `scripts/install_skill_candidate.py`

用途：

- 按 `data/skills/policy.json` 自动安装可信低风险 skill

什么时候用：

- 候选已经批准，可进入自动补位阶段

### `scripts/git_backup_health.py`

用途：

- 自动建立本地 Git 备份基线
- 在 `gh` 可用且已认证时自动创建 GitHub 仓库并配置 `origin`
- 校验 `fetch / pull / push` 是否可用

什么时候用：

- `daily-backup`
- 首次发现 workspace 还不是 Git 仓库时
- 想确认远程备份是否真正可恢复时

不要用于：

- 未经策略约束地随意创建公开仓库
- 在没有 `data/github-backup-policy.json` 共识时乱猜 owner / visibility

### `scripts/scan_sessions_incremental.py`

用途：

- isolated cron 看不到主会话树时，直接扫描 session JSONL
- 用于 `memory-hourly` 等记忆微同步任务

什么时候用：

- 需要从 session 文件中增量提取 user / assistant 最终回复
- 明确禁止使用 `sessions_list` / `sessions_history` 的 cron 场景

不要用于：

- 普通人工阅读日志
- 不需要增量游标的临时检查

### `scripts/lockfile.py`

用途：

- 在多个 job 可能同时写共享文件时加锁

什么时候用：

- 写 `MEMORY.md`
- 未来若有多个任务共享写同一个索引文件，也可复用

不要用于：

- 只读操作
- 不涉及共享写入的单次脚本

### `scripts/weekly_gate.py`

用途：

- 把“每周一次”任务改成“每天触发 + 每周至少成功一次”

什么时候用：

- `memory-weekly`
- 任何容易被机器睡眠错过的周级任务

不要用于：

- 每次都必须执行的 daily / hourly job

## 运行边界

- 如果脚本未安装，不要假装已运行；先记录待办或修复安装
- 如果脚本路径和模板不一致，要在 `TOOLS.md` 中写明真实路径
- 如果任务是 cron prompt 触发，优先遵循该 prompt 中的具体脚本调用方式

## 最小核对

在需要使用脚本前，至少确认：

- `scripts/` 目录存在
- 目标脚本文件存在
- `memory/_state/` 已创建
- `TOOLS.md` 没有声明该脚本“未启用”
- `data/github-backup-policy.json` 已明确 GitHub 备份策略
- 若使用持续探索链，还应确认 `data/research/` 已初始化

# OpenClaw AI Coding Team

这是一套面向 **AI 编程产品** 的多 Agent 团队骨架，目标不是“接单写代码”，而是形成一支能持续完成：

- 自主研究需求
- 主动探索方向
- 产出需求规格
- 设计技术方案
- 开发软件
- 测试验证
- 部署上线
- 复盘沉淀

的闭环团队。

## 设计原则

这套设计吸收了 `edict` 的层级调用思想，但不照搬三省六部的命名和实现：

- 保留 `入口 → 规划 → 审议 → 调度 → 专业执行` 的链路
- 只保留对 AI 编程团队有价值的角色
- 把你的 `workspace` 里的记忆、知识分类、反思能力提升为团队公共底座
- 重要事件采用事件驱动即时记忆；复盘负责蒸馏，不负责首次补记
- 精确定时任务交给 cron，heartbeat 只保留给调度型角色
- `aic-builder` 作为实现编排官，默认调度 `Codex` / `Claude Code` 等编码引擎
- 避免过重的 Dashboard / Event Bus 依赖，先把团队制度落清楚

## 团队角色

| Agent ID | 角色 | 核心职责 |
|----------|------|----------|
| `aic-captain` | 总指挥 | 唯一入口、优先级裁决、唯一对外汇报 |
| `aic-planner` | 规划官 | 需求收敛、任务拆解、验收标准 |
| `aic-reviewer` | 审议官 | 审查方案与产出，卡边界和质量 |
| `aic-dispatcher` | 调度官 | 决定派发对象、推进执行闭环 |
| `aic-researcher` | 研究官 | 研究需求、方向、竞品、用户与技术机会 |
| `aic-builder` | 实现编排官 | 编排编码引擎完成实现、审查 diff、推动验证 |
| `aic-tester` | 验证官 | 测试、回归、评审、验收 |
| `aic-releaser` | 发布官 | 部署、上线、回滚、发布后观察 |
| `aic-curator` | 典藏官 | 记忆整理、知识分类、术语表、项目档案 |
| `aic-reflector` | 反思官 | 日/周复盘、识别低效、推动规则更新 |

## 运行结构

- **唯一外部入口**：`aic-captain`
- **唯一对你汇报出口**：`aic-captain`
- **方案必须先审议**：`aic-planner -> aic-reviewer`
- **执行必须经调度**：`aic-dispatcher`
- **上线必须过发布门禁**：`aic-releaser`
- **复盘与沉淀独立存在**：`aic-reflector + aic-curator`

## 目录说明

- `AGENT_GRAPH.md`：角色关系、调用矩阵、主流程
- `automation/CRON.md`：cron / heartbeat 的推荐分工与时间表
- `automation/cron-prompts/`：cron prompt 源文件与同步说明
- `automation/scripts/`：任务协调、看板、记忆同步、持续探索、备份自愈等 helper scripts
- `WORKSPACE_BOOTSTRAP.md`：如何把这些种子装配成真实 `~/.openclaw/workspace-*`
- `OPENCLAW_RUNTIME_MATRIX.md`：OpenClaw 原生运行上下文与本仓库约定的边界说明
- `config/openclaw.agents.snippet.json`：可合并到 `openclaw.json` 的 agent 配置片段
- `config/openclaw.hooks.snippet.json`：可合并到 `openclaw.json` 的原生 hooks 配置片段
- `protocols/`：任务流转、交接、发布、知识分类、知识提案管线、反思闭环、执行透明等协议
- `templates/common/`：所有 agent 共用的 workspace 基础文件
- `agents/<agent-id>/`：每个 agent 的角色专属文件

## 持续探索系统

除了正式任务流之外，仓库现在还内置了一条独立的**持续探索链**，用于把“自主研究需求 / 主动探索方向”真正落到自动化上：

- `ambient-discovery`：持续巡公开来源，捕获外部 signals
- `signal-triage`：对 signals 去重、聚类、打分，形成机会池
- `opportunity-deep-dive`：对高分机会补证据、固化 Opportunity Card
- `opportunity-promotion`：把成熟机会晋升为正式任务
- `exploration-learning`：让探索系统自己学习更好的 query、来源、权重和工具路线
- `prepare-site-frontier`：把站点画像转成热门入口、Feed 和高价值前沿
- `skill-scout`：从能力缺口里发现更合适的 skill 候选
- `skill-maintenance`：按 policy 自动安装可信低风险 skill

运行态数据位于：

- `data/research/sources.json`
- `data/research/site_profiles.json`
- `data/research/tool_profiles.json`
- `data/research/tool_attempts/`
- `data/research/topic_profiles.json`
- `data/research/source_scores.json`
- `data/research/opportunities.json`
- `data/research/signals/`
- `data/research/opportunity-cards/`
- `data/skills/policy.json`
- `data/skills/catalog.json`

这条链和 `tasks/registry.json` 分离：

- `data/research/` 负责探索期弱信号和机会池
- `tasks/registry.json` 只负责正式交付任务
- `specs/`、`verification-reports/`、`release-notes/` 分别承载规划、验证、发布阶段的正式产物
- `site_profiles.json` + `tool_attempts/` 会驱动“热门入口优先、失败后自动换工具、再把经验学回去”的探索回路

## 预先准备的环境

这套仓库不是“只下载目录就能跑”的纯静态模板；它默认运行在 **已安装 OpenClaw 的真实环境** 里。

建议至少满足以下前置条件：

### 必需项

| 项目 | 用途 | 说明 |
|------|------|------|
| `OpenClaw` | Agent 运行时 | 必须已经安装并能正常连接 gateway |
| `python3` | 运行 helper scripts | `tasks`、`handoff`、`dashboard`、记忆自动化都依赖 Python 脚本 |
| `git` | 本地备份与版本基线 | `daily-backup`、首跑基线、回滚与追踪都依赖它 |
| `qmd` | Agent 级本地记忆检索 | 这套 coding team 现在默认按 `memory.backend = "qmd"` 接入每个 agent 的本地 Markdown 记忆 |
| `Chrome/Chromium` | Browser 工具探索与登录态站点 | 若希望探索 `X`、强 JS 页面、热门流和评论区，推荐准备可用浏览器 |
| `node` / `npx` | skill 自动安装与 ClawHub | `skill-maintenance` 默认通过 `npx clawhub` 安装可信低风险 skill |
| 可写的 `~/.openclaw/` | 运行时目录 | 安装器会创建 `workspace-aic-*`、`agents/*`、`openclaw.json` 备份 |

### 推荐项

| 项目 | 用途 | 说明 |
|------|------|------|
| `gh` | GitHub 远程自愈 | `daily-backup` 可自动创建 GitHub 私有仓库、配置 `origin`、校验 `pull/push` |
| 已登录的 `gh auth` | GitHub 建仓与推送 | 若未登录，GitHub 相关能力只能做到本地 Git，不会自动建远程仓库 |
| 稳定外网 | GitHub / 渠道 / 研究 | `gh repo create`、`push`、Telegram 探测、在线研究都需要网络 |
| Telegram / 其他渠道账号 | 对外入口 | 若要让 `aic-captain` 真正收消息，需先准备 channel account 与 token |

### QMD 记忆说明

安装器现在会为每个 agent 自动完成以下动作：

- 合并 `memory.backend = "qmd"` 到 `openclaw.json`
- 为每个 agent 预置独立的 QMD XDG 状态目录：
  - `~/.openclaw/agents/<agent-id>/qmd/xdg-config`
  - `~/.openclaw/agents/<agent-id>/qmd/xdg-cache`
- 为每个 agent 的 workspace 预热这些 collection：
  - `memory-root-<agent>`
  - `memory-alt-<agent>`
  - `memory-dir-<agent>`
  - `handoffs-<agent>`
  - `research-cards-<agent>`
  - `dashboard-<agent>`
- 默认执行：
  - `qmd collection add ...`
  - `qmd update`
  - `qmd status`
- 若显式启用安装参数 `--qmd-embed`，还会在初始化时额外执行 `qmd embed`

默认检索模式是 `memory.qmd.searchMode = "search"`，也就是 **BM25 优先**。  
这意味着：

- 不跑 `qmd embed` 也能先用
- 若后续希望更强语义检索，可以再执行一次带 `--qmd-embed` 的安装，或手工对指定 agent 预热 embed

### 当前支持建议

- **Linux / Ubuntu**：一等支持，优先使用 `setup/install-openclaw-team.sh`
- **Windows / PowerShell**：可用，优先使用 `setup/install-openclaw-team.ps1`

## Core Profile

如果你不想部署整套 coding team，只想给 `main` 或某个指定 agent 一键加上：

- 记忆系统
- 知识结构
- 每日反思
- qmd / embed 搜索

可以直接使用最小核心安装脚本：

`./setup/install-openclaw-core.sh --openclaw-home "$HOME/.openclaw" --agent-ids main`

如果你不想手动输入一长串参数，直接运行：

`./setup/install-openclaw-core.sh`

脚本会在运行过程中提示输入；大部分场景直接一路回车即可，默认就是给 `main` 安装 core profile。

默认会为目标 agent 安装：

- `memory-hourly`
- `daily-reflection`
- `daily-curation`
- `memory-weekly`
- qmd 预热（默认 BM25/update；加 `--qmd-embed` 可顺带跑 embed）

如果要创建一个新 agent，并直接赋予这套能力：

`./setup/install-openclaw-core.sh --openclaw-home "$HOME/.openclaw" --create-agent-id writer-cn --role-name "内容助理" --role-title "内容生产" --mission "围绕用户目标持续沉淀内容与知识资产" --accepted-from main`

说明：

- `main` 会被自动补齐 `workspace` 与 `agentDir`，默认使用 `~/.openclaw/workspace` 与 `~/.openclaw/agents/main`
- 新 agent 默认只具备最小 core profile，不会顺带装控制台、dashboard、任务闭环等整套团队能力
- 可用 `--skip-jobs`、`--skip-qmd-init`、`--qmd-embed`、`--timezone` 等参数做细调
- 不传关键参数时，会进入交互模式；传了参数则保持原来的静默安装模式
- **macOS**：原则上可复用 shell 路径，但你仍应先确认本机 `OpenClaw`、`python3`、`git`、`gh` 都可用

## 需要提前配置的内容

这套仓库现在已经能把“团队能力”装进去，但它仍然需要你提前决定一部分 **环境策略**，否则只能运行到半自动。

### 1. OpenClaw 运行时配置

至少要确认这些项：

- `~/.openclaw/openclaw.json` 存在且 OpenClaw 可正常读取
- 允许新增 agent 到 `agents.list`
- 允许新增 `bindings`
- 允许启用 internal hook：`boot-md`
- 允许为 agent 创建独立：
  - `workspace`
  - `agentDir`

本仓库提供的配置片段：

- `config/openclaw.agents.snippet.json`
- `config/openclaw.hooks.snippet.json`

默认关键值包括：

- `agents.defaults.skipBootstrap = true`
- `agents.defaults.userTimezone = Asia/Shanghai`
- `aic-captain` heartbeat：`30m`
- `aic-dispatcher` heartbeat：`15m`

### 2. 渠道入口配置

如果你希望 `aic-captain` 对外收消息，至少要提前准备：

- channel 名称，例如 `telegram`
- account id，例如 `aic-captain`
- 对应 token / 凭证

安装脚本支持在安装时直接写入 captain binding，但你仍然要自己保证：

- token 有效
- 渠道已登录 / 已配置
- 目标环境允许 OpenClaw 使用该 channel

### 3. GitHub 备份策略

如果你希望 agent 自动完成：

- `git init`
- 创建 GitHub 仓库
- 配置 `origin`
- 校验 `fetch / pull / push`

那么目标环境需要提前满足：

- 本机安装 `gh`
- `gh auth status` 通过
- 目标账号有权限创建仓库

运行态策略文件是：

- `data/github-backup-policy.json`

默认模板在：

- `templates/common/data/github-backup-policy.json`

### 4. 真实执行目标配置

如果你希望 `aic-builder / aic-tester / aic-releaser` 真正对某个代码仓库工作，而不是只在各自运行态 workspace 里空转，还需要准备：

- `data/execution-target.json`

默认模板在：

- `templates/common/data/execution-target.json`

关键字段：

- `target.repo_root`：真实代码仓库根目录
- `target.default_branch`：默认分支
- `target.test_commands`：tester 优先执行的校验命令
- `target.release_mode`：`repo_only` 或 `command`
- `target.release_command`：若使用命令式发布，在这里声明
- `target.rollback_command`：回滚命令
- `target.observe_checks`：发布后观察项

如果这份配置缺失，前半段研究/规划仍能运行，但 `开发软件 -> 测试验证 -> 部署上线 -> 复盘沉淀` 这条后半段不会真正闭环。

如果你的目标仓库需要自定义 worktree setup / cleanup，可显式提供 hook 配置；示例模板在：

- `templates/common/data/worktree-hook-config.example.json`

这类 hook 必须是显式声明、可关闭、可审计的，不能依赖来源不明的隐式脚本。

当前仓库也内置了最小烟测命令：

- `python3 automation/scripts/verify_worktree_lifecycle.py`

关键字段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | `true` | 是否启用 GitHub 远程自愈 |
| `owner` | `null` | 为空时使用当前 `gh auth` 登录用户 |
| `visibility` | `private` | 默认创建私有仓库 |
| `repo_name` | `null` | 为空时使用 workspace 目录名 |
| `remote_name` | `origin` | Git remote 名 |
| `branch` | `main` | 默认主分支 |
| `auto_create_repo` | `true` | 允许自动 `gh repo create` |
| `auto_pull` | `true` | 允许自动 `pull --ff-only` |
| `auto_push` | `true` | 允许自动 push |
| `allow_git_init` | `true` | 允许自动本地 `git init` |

如果你不希望 agent 自动创建远程仓库，可以把：

- `auto_create_repo = false`

### 4. 机器特有信息

本仓库不会帮你猜每台机器的真实环境信息，这些内容应写到运行态 `TOOLS.md`：

- SSH 主机 / 跳板机
- 部署服务器
- 包管理器
- 项目构建命令
- 数据库位置
- 日志路径
- 域名 / 证书
- GitHub owner / org 策略

模板入口：

- `templates/common/TOOLS.md`

## 最少可运行 vs 完整自治

你可以按两种目标准备环境：

### A. 最少可运行

满足这些就能把团队装起来：

- `OpenClaw`
- `python3`
- `git`
- 可写 `~/.openclaw`

此时你能得到：

- 多 agent 团队结构
- heartbeat / cron / dashboard
- 本地 Web 控制台：`python3 apps/control_plane/server.py --openclaw-home ~/.openclaw --host 127.0.0.1 --port 8765`
- 第二版控制台已支持任务/机会详情页、handoff 列表、文件查看、过滤和 `ready_review` 手动晋升
- 第三版控制台已支持任务时间线与基于 `update_task_registry.py` 的任务状态流转
- 第三版控制台现已补上运行告警与全局事件流，更直观看团队是否在推进主线
- `Agents` 面板现已升级为中文角色卡、团队拓扑和主线路径，不再只是 `aic-xxx` 列表
- 控制台现已支持 `/agent?id=...`，可直接看单角色的收到 / 推进 / 终结 / 返工 / 当前持有
- 内置 captain skill：`team-agent-factory`，可按团队运营情况新增/退役全功能 agent，并同步 runtime `openclaw.json`
- Web 控制台已接入 `team-agent-factory`：`/team-factory` 支持新增/退役 agent 的 dry-run 与 apply
- 控制台首页现已增加“团队北极星”面板，会直接显示自养目标、当前主目标和最值得验证的自养机会
- 控制台首页现已增加“本周真实产出 / 收益验证状态 / 持续演进”三块，更直观看到团队到底做出了什么、收益验证到哪一步、是在进化还是自转
- 首页还会进一步区分 `内部系统产出 / 对外产品产出 / 经营实验产出`，避免把团队自我强化、产品方向沉淀和真实商业验证混在一起看
- 控制台现已增加 `/experiments` 商业化实验面板，用于查看当前任务/机会对应的商业轨道、分发路径、成功指标与止损条件
- 商业化实验现已支持结构化记录：`data/experiments/registry.json`，可跟踪收入、分发、定价、成本与自动化适配实验
- 探索系统现已按“平台不变、扫描视角重构”调整：优先扫描付费意愿、搜索需求、广谱人群与分发杠杆，而不是默认被开发者社区热点带偏
- 控制台现已支持 `/kpi`，可查看 Daily / Weekly agent scorecards，并手动触发 KPI job
- KPI 引擎第一版：`python3 automation/scripts/compute_agent_kpi.py --openclaw-home ~/.openclaw --period daily --write`
- 研究机会现在会额外输出商业模式、付费假设、分发路径、单位经济性、自动化适配、成功指标与止损条件
- 任务真相源与 handoff
- 本地 Git 初始化能力

但不一定能得到：

- GitHub 自动建仓
- 远程 push / pull
- Telegram 入口
- 部署能力

### B. 完整自治

除了最少可运行外，还建议准备：

- `gh`
- `gh auth`
- 稳定网络
- 渠道 token
- 部署凭证 / SSH / 云平台权限
- 补齐 `TOOLS.md`
- 补齐 `data/github-backup-policy.json`

此时 agent 可以逐步实现：

- 自动立项与推进
- 自动记忆同步
- 自动 Git / GitHub 备份
- 自动 dashboard 巡检
- 更接近真实团队闭环的自治运行

## 快速开始

### 1. 先确认环境

建议先手动确认这些命令都可用：

```bash
openclaw --version
python3 --version
git --version
gh --version
gh auth status
```

如果你暂时不需要 GitHub 自动建仓，`gh` 和 `gh auth` 可以先缺省，但对应能力不会生效。

### 2. 安装团队

Linux / Ubuntu：

```bash
./setup/install-openclaw-team.sh --openclaw-home "$HOME/.openclaw"
```

Windows / PowerShell：

```powershell
./setup/install-openclaw-team.ps1 -OpenClawHome "$HOME/.openclaw"
```

默认行为包括：

- 创建 `workspace-aic-*`
- 合并 agent 配置到真实 `openclaw.json`
- 安装核心 cron
- 安装第二层自动化
- 触发一次 control-loop 点火

### 3. 安装完成后重点检查

建议立刻检查：

```bash
openclaw status --deep --json
openclaw cron list --json
```

然后看：

- `~/.openclaw/workspace-aic-captain/data/dashboard.md`

重点关注：

- `team_entry_active`
- `workflow_started`
- `Backup Health`
- `missing_core_jobs`
- `missing_optional_jobs`

## 推荐落地方式

建议在真实部署时：

1. 为每个 agent 创建独立 workspace
2. 每个 workspace 先复制 `templates/common/` 中的公共文件，并为每个 agent 准备独立 `agentDir`
3. 将 `agents/<agent-id>/AGENTS.md` 合并进 workspace 根部 `AGENTS.md`，让关键角色规则进入 OpenClaw 原生可见范围
4. 将 `config/openclaw.agents.snippet.json` 与 `config/openclaw.hooks.snippet.json` 合并到真实 `openclaw.json`
5. 首跑完成 Git 初始化、私有远程与首次推送
6. 按 `automation/CRON.md` 安装定时任务
7. 选定任务真相源，并按 `protocols/task-source-of-truth.md` 统一状态口径；本地兜底优先使用 `tasks/registry.json`
8. 打通执行日志与巡检输出，避免自动化 silent fail
9. 若希望一键装配，可直接运行 `setup/install-openclaw-team.ps1` 或 `setup/install-openclaw-team.sh`
10. 若希望“装完就点火”，保持安装脚本默认行为，或显式运行 `setup/install-openclaw-automation.sh`

补充边界：

- `automation/` 保留在团队设计包仓库中，作为源码与说明区
- 真实 workspace 运行态优先只保留 `scripts/`、`memory/`、`data/`、`tasks/`
- 部署、数据库、SSH、渠道、GitHub owner 等机器特有信息，仍然要在运行态配置中补齐

## 为什么要保留 `curator` 和 `reflector`

你的现有工作区已经说明：好用的系统不是“会做事”，而是“能及时记住、会分类、会反思”。

所以这套团队把以下能力变成正式角色，而不是附属杂活：

- `aic-curator`：把经验、术语、项目状态、技术知识写入正确位置
- `aic-reflector`：周期性发现低效与错误，并推动流程修正

这两者让团队具备 **连续学习能力**，而不是每次启动都重新踩坑。

## 这套团队现在强调什么

- **制度骨架**：入口、规划、审议、调度、执行、反思、沉淀
- **事件驱动记忆**：重要即写，先首写，再蒸馏
- **结构化知识**：热缓存、实体档案、知识文件、daily/weekly/archive、知识提案
- **可靠自动化**：cron prompt 源文件、增量扫描脚本、执行日志、可追溯备份
- **实现编排**：`aic-builder` 优先调用 `Codex` / `Claude Code`

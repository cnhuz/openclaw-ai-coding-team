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
- `automation/scripts/`：记忆同步、写锁、weekly gate 等 helper scripts
- `WORKSPACE_BOOTSTRAP.md`：如何把这些种子装配成真实 `~/.openclaw/workspace-*`
- `config/openclaw.agents.snippet.json`：可合并到 `openclaw.json` 的 agent 配置片段
- `protocols/`：任务流转、交接、发布、知识分类、知识提案管线、反思闭环、执行透明等协议
- `templates/common/`：所有 agent 共用的 workspace 基础文件
- `agents/<agent-id>/`：每个 agent 的角色专属文件

## 推荐落地方式

建议在真实部署时：

1. 为每个 agent 创建独立 workspace
2. 每个 workspace 先复制 `templates/common/` 中的公共文件
3. 将 `agents/<agent-id>/AGENTS.md` 复制为 workspace 根部 `ROLE.md`，其余角色文件正常复制
4. 将 `config/openclaw.agents.snippet.json` 合并到真实 `openclaw.json`
5. 首跑完成 Git 初始化、私有远程与首次推送
6. 按 `automation/CRON.md` 安装定时任务
7. 选定任务真相源，并按 `protocols/task-source-of-truth.md` 统一状态口径
8. 打通执行日志与巡检输出，避免自动化 silent fail
9. 若希望一键装配，可直接运行 `setup/install-openclaw-team.ps1`

补充边界：

- `automation/` 保留在团队设计包仓库中，作为源码与说明区
- 真实 workspace 运行态优先只保留 `scripts/`、`memory/`、`data/`、`tasks/`

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

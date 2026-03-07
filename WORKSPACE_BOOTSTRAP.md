# Workspace Bootstrap

这个目录里的文件是 **团队设计包**，不是直接替换你现有 `~/.openclaw` 的脚本。

建议你在真实部署时按下面方式装配每个 agent 的初始 workspace。

## 目录映射

真实 workspace 推荐命名：

- `~/.openclaw/workspace-aic-captain`
- `~/.openclaw/workspace-aic-planner`
- `~/.openclaw/workspace-aic-reviewer`
- `~/.openclaw/workspace-aic-dispatcher`
- `~/.openclaw/workspace-aic-researcher`
- `~/.openclaw/workspace-aic-builder`
- `~/.openclaw/workspace-aic-tester`
- `~/.openclaw/workspace-aic-releaser`
- `~/.openclaw/workspace-aic-curator`
- `~/.openclaw/workspace-aic-reflector`

## 每个 workspace 的建议初始文件

先复制公共模板：

- `templates/common/AGENTS.md`
- `templates/common/USER.md`
- `templates/common/TOOLS.md`
- `templates/common/BOOT.md`
- `templates/common/BOOTSTRAP.md`
- `templates/common/MEMORY.md`
- `templates/common/.gitignore`
- `templates/common/tasks/registry.md`
- `templates/common/data/dashboard.md`
- `templates/common/data/exec-logs/SPEC.md`
- `templates/common/data/knowledge-proposals/README.md`
- `templates/common/data/knowledge-proposals/TEMPLATE.json`
- `templates/common/scripts/README.md`
- `templates/common/memory/glossary.md`
- `templates/common/memory/context/environment.md`
- `templates/common/memory/daily/README.md`
- `templates/common/memory/daily/TEMPLATE.md`
- `templates/common/memory/people/README.md`
- `templates/common/memory/projects/README.md`
- `templates/common/memory/weekly/README.md`
- `templates/common/memory/weekly/TEMPLATE.md`
- `templates/common/memory/archive/README.md`
- `templates/common/memory/post-mortems.md`
- `templates/common/memory/knowledge/README.md`
- `templates/common/memory/knowledge/fw-design-decisions.md`
- `templates/common/memory/_state/README.md`

再复制角色文件：

- `agents/<agent-id>/AGENTS.md` → workspace 根部 `ROLE.md`
- `agents/<agent-id>/SOUL.md`
- `agents/<agent-id>/IDENTITY.md`
- `agents/<agent-id>/HEARTBEAT.md`
- `agents/<agent-id>/MEMORY.seed.md`

## 推荐覆盖顺序

1. 复制公共模板
2. 将角色专属 `AGENTS.md` 复制为 workspace 根部 `ROLE.md`
3. 复制其余角色文件
4. 将 `MEMORY.seed.md` 内容合并进 workspace 根部 `MEMORY.md`
5. 在 `USER.md` 中补齐你的真实信息与偏好
6. 在 `TOOLS.md` 中补齐机器、SSH、部署环境、账号等本地特有信息
7. 按 `config/openclaw.agents.snippet.json` 合并 agent 配置
8. 若当前 workspace 还不是 Git 仓库，执行 `git init`、检查 `.gitignore`、完成首个提交
9. 推荐为该 workspace 创建独立私有远程并完成首次推送
10. 将 `automation/scripts/*.py` 复制到真实 workspace 的 `scripts/`
11. 按 `automation/CRON.md` 安装定时备份、复盘、沉淀与 sprint 任务
12. 把 `automation/cron-prompts/` 中需要的 prompt 文件同步到运行时配置
13. 若启用完整记忆自动化，再额外安装 `memory-hourly` 与 `memory-weekly`
14. 选定任务真相源：优先外部任务系统；没有时至少使用 `tasks/registry.md`
15. 将首跑结果优先写入当天 `memory/daily/YYYY-MM/YYYY-MM-DD.md`
16. 完成验证后，移除或归档 `BOOTSTRAP.md`

## 为什么不直接生成真实 workspace

因为真实部署环境通常会有：

- 不同的 OpenClaw home 路径
- 不同的模型配置
- 不同的渠道账号
- 不同的服务器、SSH、密钥、部署环境

所以这里提供的是 **结构化种子**，让你可以稳妥地按设备环境装配，而不是用一套硬编码脚本去覆盖真实环境。

补充说明：

- `automation/` 目录是设计包里的源码区
- 真实 workspace 不必复制 `automation/`
- 真正进入运行态的是：
  - `scripts/`
  - `memory/`
  - `data/`
  - `tasks/`

## 首跑最低要求

每个 agent 的 workspace 首跑至少完成以下事项：

- 建立独立 Git 备份基线
- 显式设置时区为 `Asia/Shanghai`
- 安装每日 `00:00 / 00:10 / 00:20` 的 cron 任务
- 建立任务真相源与执行日志目录
- 将首跑结果写入记忆

其中：

- `00:00`：workspace Git 备份
- `00:10`：`aic-reflector` 日复盘
- `00:20`：`aic-curator` 分类沉淀

`heartbeat` 只默认用于调度型角色；执行型角色的持续推进靠任务触发与 cron sprint，不靠空转 heartbeat。

## 推荐额外目录

除记忆目录外，建议每个 workspace 还包含：

- `tasks/registry.md`：任务真相源的本地兜底
- `data/exec-logs/`：自动化执行日志
- `data/dashboard.md`：自动化巡检摘要
- `data/knowledge-proposals/`：待审核知识提案
- `memory/_state/`：cron 游标、锁与 gate 状态
- `memory/daily/`：分月每日日志
- `memory/weekly/`：周级巩固
- `memory/archive/`：历史归档
- `scripts/`：增量扫描、锁、weekly gate 等 helper scripts

`scripts/README.md` 应明确说明：

- 这些脚本在什么场景下使用
- 当前机器上的真实路径
- 哪些脚本已启用，哪些还未启用

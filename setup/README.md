# Setup

这里放的是**设计包安装脚本**，不是运行态 workspace 脚本。

如果你想看：

- 预先需要准备的环境
- `OpenClaw` / `git` / `gh` / 渠道 / GitHub 策略等前置条件
- 真实执行目标 `data/execution-target.json` 应如何配置
- 最少可运行 vs 完整自治的差异

请优先看根文档：

- `README.md`

推荐入口：

- `install-openclaw-team.ps1`
- `install-openclaw-team.sh`

用途：

- 在已安装 OpenClaw 的环境中创建 `workspace-aic-*`
- 复制公共模板与角色文件
- 将角色专属 `AGENTS.md` 合并进运行态根 `AGENTS.md`
- 合并 `config/openclaw.agents.snippet.json` 与 `config/openclaw.hooks.snippet.json` 到真实 `openclaw.json`
- 合并 `config/openclaw.memory.qmd.snippet.json`，把记忆后端切到 `qmd`
- 初始化结构化任务真相源 `tasks/registry.json`
- 初始化运行态阶段产物目录 `specs/`、`verification-reports/`、`release-notes/`
- 初始化 `data/execution-target.json`，让 builder / tester / releaser 知道真正的代码仓库目标
- 复制运行态 `scripts/`
- 可选地为每个 workspace 初始化本地 Git 仓库
- 默认为每个 agent 预热 qmd collection，并执行一次 `qmd update`
- 默认安装核心自动化 cron，并触发一次闭环点火
- 支持 Ubuntu / Linux 环境直接装配

自动化入口：

- `install-openclaw-automation.ps1`
- `install-openclaw-automation.sh`

与 qmd 相关的安装参数：

- `--skip-qmd-init`：跳过 qmd 预热
- `--qmd-embed`：安装阶段顺带跑一次 `qmd embed`

## 最小核心安装

如果只想给 `main` 或指定 agent 安装：

- 记忆系统
- 知识结构
- 每日反思
- qmd / embed 搜索

而不想部署完整 coding team，可使用：

`install-openclaw-core.sh`

典型用法：

- 给 `main` 安装 core profile：
  - `./setup/install-openclaw-core.sh --openclaw-home "$HOME/.openclaw" --agent-ids main`
- 创建新 agent 并直接赋予 core profile：
  - `./setup/install-openclaw-core.sh --openclaw-home "$HOME/.openclaw" --create-agent-id writer-cn --role-name "内容助理" --role-title "内容生产" --mission "围绕用户目标持续沉淀内容与知识资产" --accepted-from main`

这条安装链默认会安装的 job：

- `core-memory-hourly-<agent>`
- `core-daily-reflection-<agent>`
- `core-daily-curation-<agent>`
- `core-memory-weekly-<agent>`

建议理解方式：

- 根 `README.md`：说明“这套系统在什么环境下能跑、需要先配什么”
- `setup/README.md`：说明“安装脚本会做什么、不会做什么”

注意：

- 真实 workspace 不需要保留这里的 `setup/` 或 `automation/`
- 它们属于设计包仓库，不属于运行态目录
- 预装 workspace 若使用 `skipBootstrap=true`，运行态不应保留 `BOOTSTRAP.md`

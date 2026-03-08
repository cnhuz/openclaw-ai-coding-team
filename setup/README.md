# Setup

这里放的是**设计包安装脚本**，不是运行态 workspace 脚本。

如果你想看：

- 预先需要准备的环境
- `OpenClaw` / `git` / `gh` / 渠道 / GitHub 策略等前置条件
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
- 初始化结构化任务真相源 `tasks/registry.json`
- 复制运行态 `scripts/`
- 可选地为每个 workspace 初始化本地 Git 仓库
- 默认安装核心自动化 cron，并触发一次闭环点火
- 支持 Ubuntu / Linux 环境直接装配

自动化入口：

- `install-openclaw-automation.ps1`
- `install-openclaw-automation.sh`

建议理解方式：

- 根 `README.md`：说明“这套系统在什么环境下能跑、需要先配什么”
- `setup/README.md`：说明“安装脚本会做什么、不会做什么”

注意：

- 真实 workspace 不需要保留这里的 `setup/` 或 `automation/`
- 它们属于设计包仓库，不属于运行态目录
- 预装 workspace 若使用 `skipBootstrap=true`，运行态不应保留 `BOOTSTRAP.md`

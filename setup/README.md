# Setup

这里放的是**设计包安装脚本**，不是运行态 workspace 脚本。

推荐入口：

- `install-openclaw-team.ps1`
- `install-openclaw-team.sh`

用途：

- 在已安装 OpenClaw 的环境中创建 `workspace-aic-*`
- 复制公共模板与角色文件
- 将角色专属 `AGENTS.md` 安装为运行态 `ROLE.md`
- 合并 `config/openclaw.agents.snippet.json` 到真实 `openclaw.json`
- 复制运行态 `scripts/`
- 可选地为每个 workspace 初始化本地 Git 仓库
- 支持 Ubuntu / Linux 环境直接装配

注意：

- 真实 workspace 不需要保留这里的 `setup/` 或 `automation/`
- 它们属于设计包仓库，不属于运行态目录

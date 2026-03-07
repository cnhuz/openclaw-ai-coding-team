# TOOLS.md - 本地环境笔记

这个文件只记录每台机器独有的信息，不记录通用协议。

## 建议记录

- SSH 主机
- 部署服务器
- 包管理器
- 常用构建命令
- 云平台入口
- 数据库位置
- 日志路径
- 域名与证书说明

## Automation Scripts

如果当前 workspace 启用了运行态脚本，请在这里补齐真实路径与备注。

推荐记录：

- `scripts/scan_sessions_incremental.py`
  - 用途：isolated cron 做记忆微同步，看不到主会话时读取 session JSONL
- `scripts/lockfile.py`
  - 用途：多个 job 可能同时写 `MEMORY.md` 时加锁
- `scripts/weekly_gate.py`
  - 用途：周级任务采用“每天触发 + 每周至少成功一次” gate

使用边界：

- 真实 workspace 优先保留 `scripts/`，而不是复制整个 `automation/` 目录
- 若脚本路径与模板不同，必须在这里写明真实路径
- 若某个脚本尚未安装，也要写明“未启用”，避免 agent 误判

## Skill 源

安装任何新 skill 前，必须先做审查。

- skillsdirectory.com
- skillsmp.com
- agentskills.me
- skillstore.io
- skills.sh
- anthropics/skills
- vercel-labs/skills
- VoltAgent/awesome-openclaw-skills

## 约束

- 只把环境特有信息写这里
- 不把共享规则写这里
- 不把敏感信息写成会被轻易外发的形式

# BOOTSTRAP.md - Workspace First-Run Checklist

这是一次性首跑清单，不是闲聊仪式。

首跑优先目标是把 workspace 变成一个**可持续运行、可备份、可恢复、可沉淀**的工程系统。

## 首跑原则

1. 先完成工程初始化，再补人格化信息
2. 重要事实立即落盘，不等待夜间复盘补记
3. 首跑就要建立 Git 备份基线
4. 精确定时任务用 cron，不用 heartbeat 代替
5. 做不到的步骤要明确记为待办，不能假装已完成

## 第一步：创建基础结构

确保以下文件或目录存在：

- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `IDENTITY.md`
- `ROLE.md`
- `TOOLS.md`
- `BOOT.md`
- `MEMORY.md`
- `tasks/registry.md`
- `memory/`
- `memory/daily/`
- `memory/people/`
- `memory/knowledge/`
- `memory/projects/`
- `memory/weekly/`
- `memory/archive/`
- `memory/_state/`
- `memory/post-mortems.md`
- `memory/daily/YYYY-MM/YYYY-MM-DD.md`
- `data/exec-logs/`
- `data/dashboard.md`
- `data/knowledge-proposals/`
- `scripts/`
- `scripts/README.md`

然后把当前环境、用户硬规则、已知工具入口写进相应文件。

若是新部署，优先采用：

- `memory/daily/YYYY-MM/YYYY-MM-DD.md`
- `memory/weekly/YYYY-WXX.md`

而不是继续扩散扁平的根层日志。

注意：

- 真实 workspace 不需要保留 `automation/` 目录
- `automation/` 是团队设计包里的源码区
- 运行态只保留真正会被 agent 调用的 `scripts/`

## 第二步：初始化 Git 备份

如果当前 workspace 还不是 Git 仓库：

1. 执行 `git init`
2. 生成 `.gitignore`
3. 检查敏感项是否被忽略
4. 做首次提交

推荐忽略至少包括：

- `.env`
- `.env.*`
- `*.pem`
- `*.key`
- `secrets*`
- `credentials*`
- `tokens*`
- `sessions/`
- `*.jsonl`
- `*.jsonl.reset.*`
- `memory/_state/`
- `logs/`

## 第三步：创建私有远程并首推

推荐为每个 agent 的 workspace 建独立私有仓库。

标准动作：

1. 创建私有 GitHub 仓库
2. 添加 `origin`
3. 首次 `push`
4. 验证远程可见且最新提交已同步

如果当前环境没有 GitHub 凭证或用户尚未授权，必须把这件事记为待办，而不是跳过后假装已完成。

## 第四步：安装定时自动化

默认时区写死为 `Asia/Shanghai`，不要依赖机器本地时区猜测。

至少应配置：

- `00:00`：workspace 备份
- `00:10`：`aic-reflector` 复盘
- `00:20`：`aic-curator` 分类沉淀

执行型 agent 不靠 heartbeat 持续工作：

- `aic-researcher`：用 isolated cron 做 1h/2h sprint
- `aic-builder`：任务触发 + backlog 未清时 15m/30m 续跑
- `aic-tester`：在实现批次完成时被调度

heartbeat 只默认给调度型角色，例如 `aic-captain`、`aic-dispatcher`。

如果你启用完整记忆自动化，还应补上：

- `memory-hourly`：多次微同步，把新信号及时写入当天日志
- `memory-weekly`：通过 gate 做每周至少一次记忆晋升

此时需要把 `scan_sessions_incremental.py`、`lockfile.py`、`weekly_gate.py` 放进 `scripts/`，并把状态文件落到 `memory/_state/`。
同时应提供 `scripts/README.md`，明确说明这些脚本何时使用。

## 第五步：写入首跑记忆

至少记录以下内容：

- workspace 路径
- Git 是否已初始化
- 私有远程是否已建立
- cron 是否已安装
- 当前时区
- 当前待办和未完成的初始化项

首跑日志优先写入当天 `memory/daily/YYYY-MM/YYYY-MM-DD.md`，稳定事实再同步到 `MEMORY.md` 或 `TOOLS.md`；只有兼容旧工作区时才继续使用根层日志。
如果使用本地任务真相源，也要初始化 `tasks/registry.md`。

## 完成条件

只有同时满足以下条件，首跑才算完成：

- workspace 基础文件齐备
- Git 备份基线已建立
- 私有远程已验证，或明确记为待办
- cron 计划已安装，或明确记为待办
- 首跑信息已写入记忆

完成后再移除或归档本文件；如果当前安全规则要求先确认删除，就按规则确认后再删。

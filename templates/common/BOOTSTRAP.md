# BOOTSTRAP.md - Workspace First-Run Checklist

这是一次性首跑清单，不是闲聊仪式。

首跑优先目标是把 workspace 变成一个**可持续运行、可备份、可恢复、可沉淀**的 OpenClaw 原生工程系统。

## 首跑原则

1. 先完成工程初始化，再补人格化信息
2. 重要事实立即落盘，不等待夜间复盘补记
3. 首跑就要建立 Git 备份基线
4. 精确定时任务用 cron，不用 heartbeat 代替
5. 关键行为规则必须落在根 `AGENTS.md`
6. 做不到的步骤要明确记为待办，不能假装已完成

## 第一步：创建基础结构

确保以下文件或目录存在：

- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `IDENTITY.md`
- `TOOLS.md`
- `BOOT.md`
- `MEMORY.md`
- `tasks/registry.json`
- `tasks/registry.md`
- `specs/`
- `verification-reports/`
- `release-notes/`
- `memory/`
- `memory/people/`
- `memory/knowledge/`
- `memory/projects/`
- `memory/weekly/`
- `memory/archive/`
- `memory/_state/`
- `memory/post-mortems.md`
- `memory/YYYY-MM-DD.md`
- `data/exec-logs/`
- `data/dashboard.md`
- `data/knowledge-proposals/`
- `handoffs/`
- `scripts/`
- `scripts/README.md`

然后把当前环境、用户硬规则、已知工具入口写进相应文件。

注意：

- OpenClaw 原生子 agent 默认只保证拿到根 `AGENTS.md` 与 `TOOLS.md`
- 因此角色专属关键规则要并入根 `AGENTS.md`，不要只保留在额外文件
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

## 第三步：对齐 OpenClaw 原生配置

至少确认以下配置项已经落实：

1. 每个 agent 有独立 `workspace`
2. 每个 agent 有独立 `agentDir`
3. `agents.defaults.skipBootstrap` 已按你的安装方式配置
4. `userTimezone` 已显式设置
5. 如果需要启动巡检，已启用 `boot-md` hook

如果你使用本仓库的安装脚本，推荐合并：

- `config/openclaw.agents.snippet.json`
- `config/openclaw.hooks.snippet.json`

若你使用的是预装 runtime workspace，并且 `agents.defaults.skipBootstrap=true`，安装完成后不应继续保留 `BOOTSTRAP.md`；否则 OpenClaw `status` 会一直把它判定为 `bootstrapPending`。

## 第四步：安装定时自动化

默认时区写死为 `Asia/Shanghai`，不要依赖机器本地时区猜测。

至少应配置：

- `每 10m`：`aic-captain` 刷新 dashboard
- `00:00`：workspace 备份
- `00:10`：`aic-reflector` 复盘
- `00:20`：`aic-curator` 分类沉淀

执行型 agent 不靠 heartbeat 持续工作：

- `aic-researcher`：用 isolated cron 做 1h/2h sprint
- `aic-builder`：任务触发 + backlog 未清时 15m/30m 续跑
- `aic-tester`：在实现批次完成时被调度

heartbeat 只默认给调度型角色，例如 `aic-captain`、`aic-dispatcher`。

推荐安装完成后立刻触发一次 `openclaw system event --mode now`，把闭环从“已配置”推进到“已点火”。

如果你启用完整记忆自动化，还应补上：

- `memory-hourly`：多次微同步，把新信号及时写入当天日志
- `memory-weekly`：通过 gate 做每周至少一次记忆晋升

默认优先给 `aic-captain`、`aic-planner`、`aic-dispatcher` 启用；等运行稳定后，再决定是否扩到更多角色。

此时需要把 `scan_sessions_incremental.py`、`lockfile.py`、`weekly_gate.py` 放进 `scripts/`，并把状态文件落到 `memory/_state/`。
同时应提供 `scripts/README.md`，明确说明这些脚本何时使用。

## 第五步：写入首跑记忆

至少记录以下内容：

- workspace 路径
- agentDir 路径
- Git 是否已初始化
- 私有远程是否已建立
- cron 是否已安装
- 当前时区
- 当前待办和未完成的初始化项

首跑日志优先写入当天 `memory/YYYY-MM-DD.md`，稳定事实再同步到 `MEMORY.md` 或 `TOOLS.md`。
如果使用本地任务真相源，也要初始化 `tasks/registry.json`。

## 完成条件

只有同时满足以下条件，首跑才算完成：

- workspace 基础文件齐备
- Git 备份基线已建立
- OpenClaw 原生配置已对齐
- cron 计划已安装，或明确记为待办
- 首跑信息已写入记忆

完成后再移除或归档本文件；如果当前安全规则要求先确认删除，就按规则确认后再删。

# OpenClaw Runtime Matrix

这份矩阵用于区分：

- **OpenClaw 原生保证**
- **本仓库的团队约定**
- **不应假设的行为**

目标是避免把主会话里“看起来会发生”的事情，误当成所有运行上下文都成立。

## 1. 主会话

典型来源：

- 入口聊天
- 网关重连后的主 agent 会话

可以依赖：

- 根 `AGENTS.md`
- `TOOLS.md`
- 已配置的 workspace
- 若启用了 `boot-md`，启动时会额外跑 `BOOT.md`

不要假设：

- 所有补充文件都会被同样注入到每一轮上下文

## 2. 子 Agent 调用

典型来源：

- `allowAgents` 触发的 agent-to-agent 调用

可以依赖：

- 根 `AGENTS.md`
- `TOOLS.md`
- agent 自己的 `workspace`

必须把关键规则写在这里：

- 角色边界
- 完成条件
- 交接要求
- 安全红线

不要假设：

- `SOUL.md`
- `IDENTITY.md`
- `USER.md`
- `BOOT.md`
- 任意额外补充文件

会被稳定自动注入

## 3. `boot-md` 启动巡检

典型来源：

- 网关启动
- internal hooks 启用 `boot-md`

可以依赖：

- `BOOT.md` 会在启动时执行

不要假设：

- 子 agent
- isolated cron
- 普通脚本调用

也自动读过 `BOOT.md`

## 4. Heartbeat

典型来源：

- agent 配置中显式开启 `heartbeat`

适合：

- 调度
- 粗粒度巡检
- 节奏推进

不适合：

- 精确定时任务
- 替代 cron
- 执行型角色长期空转

本仓库约定：

- 默认只给 `aic-captain`、`aic-dispatcher`
- 其他角色优先靠任务触发或 cron sprint

## 5. Cron

典型来源：

- `openclaw cron add`
- 持久化 job

适合：

- 每日固定任务
- 延迟提醒
- 定期研究 / 构建 sprint
- 备份 / 复盘 / 记忆整理

不要假设：

- cron 会自动共享主会话上下文
- cron 能稳定看到主会话树

本仓库约定：

- isolated cron 优先
- 记忆微同步优先读 session JSONL，而不是 `sessions_list` / `sessions_history`

## 6. Session Memory Hook

典型来源：

- 启用 `session-memory`
- 触发 `/new`

原生输出更贴近：

- `memory/YYYY-MM-DD-slug.md`

本仓库当前策略：

- 运行态主日志统一收敛到 `memory/YYYY-MM-DD.md`
- 如果保留 `memory/daily/`，仅作为归档/迁移兼容结构

因此：

- 不建议同时依赖两套主日志路径
- 如启用 `session-memory`，应明确和本地日志策略怎么对齐

## 7. Bootstrap

典型来源：

- 新建 workspace
- `skipBootstrap = false`

原生语义：

- `BOOTSTRAP.md` 是一次性首跑清单

本仓库约定：

- 安装脚本默认把 `skipBootstrap` 设为 `true`
- 因为本仓库自行管理模板与首跑结构，不依赖默认 bootstrap 生成

## 8. 本仓库的硬约定

这些规则必须长期维持：

- 关键角色规则写在根 `AGENTS.md`
- `BOOT.md` 只是可选启动巡检，不是所有上下文都自动读取
- 本地任务真相源优先使用 `tasks/registry.json`
- 记忆主路径优先使用 `memory/YYYY-MM-DD.md`
- `memory/daily/` 仅作归档/兼容

## 9. 维护建议

当你准备新增规则时，先问自己：

1. 这是 OpenClaw 原生保证，还是本仓库约定？
2. 它在子 agent 中是否仍然可见？
3. 它在 cron / heartbeat / boot hook 中是否仍然成立？
4. 如果答案是否定的，这条规则是否应该迁回根 `AGENTS.md` 或 `TOOLS.md`？

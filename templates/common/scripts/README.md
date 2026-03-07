# Scripts Runtime Guide

这个目录属于**真实 workspace 的运行态工具区**。

与之相对：

- `automation/` 是团队设计包仓库里的源码与说明区
- `scripts/` 才是 agent 在真实 workspace 中实际调用的位置
- `ROLE.md` / `AGENTS.md` 应告诉 agent 什么时候查看这里

## 什么时候看这个文件

遇到以下情况时，先看这里：

- cron / heartbeat / system event 相关排障
- 记忆同步异常
- `MEMORY.md` 可能被多个 job 同时写入
- 周级任务需要判断“本周是否已跑过”

## 当前脚本

### `scripts/scan_sessions_incremental.py`

用途：

- isolated cron 看不到主会话树时，直接扫描 session JSONL
- 用于 `memory-hourly` 等记忆微同步任务

什么时候用：

- 需要从 session 文件中增量提取 user / assistant 最终回复
- 明确禁止使用 `sessions_list` / `sessions_history` 的 cron 场景

不要用于：

- 普通人工阅读日志
- 不需要增量游标的临时检查

### `scripts/lockfile.py`

用途：

- 在多个 job 可能同时写共享文件时加锁

什么时候用：

- 写 `MEMORY.md`
- 未来若有多个任务共享写同一个索引文件，也可复用

不要用于：

- 只读操作
- 不涉及共享写入的单次脚本

### `scripts/weekly_gate.py`

用途：

- 把“每周一次”任务改成“每天触发 + 每周至少成功一次”

什么时候用：

- `memory-weekly`
- 任何容易被机器睡眠错过的周级任务

不要用于：

- 每次都必须执行的 daily / hourly job

## 运行边界

- 如果脚本未安装，不要假装已运行；先记录待办或修复安装
- 如果脚本路径和模板不一致，要在 `TOOLS.md` 中写明真实路径
- 如果任务是 cron prompt 触发，优先遵循该 prompt 中的具体脚本调用方式

## 最小核对

在需要使用脚本前，至少确认：

- `scripts/` 目录存在
- 目标脚本文件存在
- `memory/_state/` 已创建
- `TOOLS.md` 没有声明该脚本“未启用”

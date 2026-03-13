# TOOLS.md - Core Agent Runtime Notes

这个文件只记录当前 agent 运行时的核心工具与目录约定。

## 核心脚本

- `scripts/scan_sessions_incremental.py`
  - 用途：增量提取高价值会话信号，供 `memory-hourly` 使用
- `scripts/lockfile.py`
  - 用途：写 `MEMORY.md` 时加锁，避免并发覆盖
- `scripts/weekly_gate.py`
  - 用途：控制周级记忆巩固节奏

## 运行时结构

- `MEMORY.md`
- `memory/`
- `data/knowledge-proposals/`
- `data/exec-logs/`
- `scripts/`

## qmd

- 推荐为当前 agent 保留独立 `agentDir`
- qmd 预热后，优先检索 `MEMORY.md` 与 `memory/**/*.md`
- 若启用了 embed，可用语义检索补强历史查询

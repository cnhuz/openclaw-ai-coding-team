# scripts/README.md - Core Profile

当前 core profile 只依赖最小脚本集：

- `scan_sessions_incremental.py`
  - 提取增量高价值会话，供 `memory-hourly` 使用
- `lockfile.py`
  - 给 `MEMORY.md` 写入加锁
- `weekly_gate.py`
  - 控制 `memory-weekly` 的每周节奏

## 默认作业

- `memory-hourly`
- `daily-reflection`
- `daily-curation`
- `memory-weekly`

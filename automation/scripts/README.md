# Automation Helper Scripts

这个目录位于**团队设计包仓库**中，用来保存脚本源码。

它不是要求你把整个 `automation/` 目录复制进真实 workspace。

团队包现在已经内置这三个 helper scripts：

- `scan_sessions_incremental.py`：增量扫描会话 JSONL
- `lockfile.py`：共享文件写锁
- `weekly_gate.py`：每周至少一次 gate

它们来自本仓库中的 `openclaw-memory-fusion/scripts/`，目前已同步到本目录。

## 推荐运行位置

在真实 workspace 中，建议把这三个脚本一起放到：

- `scripts/scan_sessions_incremental.py`
- `scripts/lockfile.py`
- `scripts/weekly_gate.py`

这样 cron prompt 可以直接使用相对路径，不必依赖当前仓库结构。

推荐再配一个运行态说明文件：

- `scripts/README.md`

让普通 agent 在非 cron 场景下，也知道这些脚本何时该用、何时不该用。

## 最小用法

- 增量扫描：
  - `python3 scripts/scan_sessions_incremental.py --state-file memory/_state/scan_sessions_hourly.json --format md --max-chars 4000`
- 获取写锁：
  - `python3 scripts/lockfile.py acquire --lock memory/_state/MEMORY.lock --timeout 120 --stale-seconds 7200`
- 释放写锁：
  - `python3 scripts/lockfile.py release --lock memory/_state/MEMORY.lock`
- weekly gate 检查：
  - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone Asia/Shanghai --mode check`
- weekly gate 标记成功：
  - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone Asia/Shanghai --mode mark`

原则：

- `memory-hourly` 不要再改回 `sessions_list` / `sessions_history`
- `daily-curation` 与 `memory-weekly` 写 `MEMORY.md` 时应共用 `memory/_state/MEMORY.lock`
- `memory/_state/` 下的游标、锁、gate 状态不要提交到远程仓库
- 若你升级了上游脚本版本，要同步更新本目录与相关 cron prompt

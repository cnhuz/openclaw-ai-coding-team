[cron:core-memory-weekly]

你是每周记忆巩固 agent。

前置步骤：

1. 先运行：
   - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone __TIMEZONE__ --mode check`
2. 如果返回 `shouldRun=false`：
   - 写执行日志到 `data/exec-logs/memory-weekly/`
   - 回复：
     - 第一行：`memory-weekly ok`
     - 第二行：`status: skipped by gate`
     - 第三行：`updated: none`
   - 结束
3. 如果返回 `shouldRun=true`：
   - 先获取写锁：
     - `python3 scripts/lockfile.py acquire --lock memory/_state/MEMORY.lock --timeout 120 --stale-seconds 7200`

流程：

1. 读取最近一周的日记忆、反思结果、知识提案
2. 将已证实且高复用的内容晋升到：
   - `MEMORY.md`
   - `memory/knowledge/`
   - `memory/people/`
   - `memory/projects/`
   - `memory/post-mortems.md`
3. 清理 `MEMORY.md` 的近期滚动区，只保留最近 7 天高价值条目
4. 成功后运行：
   - `python3 scripts/weekly_gate.py --state memory/_state/weekly_gate.json --timezone __TIMEZONE__ --mode mark`
5. 释放写锁：
   - `python3 scripts/lockfile.py release --lock memory/_state/MEMORY.lock`

回复格式：

- 第一行：`memory-weekly ok`
- 第二行：`status: consolidated`
- 第三行：`updated: <comma-separated file paths>`

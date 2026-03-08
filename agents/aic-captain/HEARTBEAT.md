# HEARTBEAT.md

收到 heartbeat 时：

1. 先运行 `python3 scripts/validate_task_registry.py --path tasks/registry.json`
2. 立刻刷新看板：`python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root ~/.openclaw/workspace-aic-researcher/data/research --skills-root ~/.openclaw/workspace-aic-researcher/data/skills --output data/dashboard.md`
3. 再运行 `python3 scripts/query_task_registry.py --path tasks/registry.json --view captain --format md`
4. 若当前会话或最近一轮 system / user 上下文里已经出现明确需求，但任务真相源里还没有对应活跃任务，立刻创建一个 `TASK-YYYYMMDD-HHMMSS`：
   - `state=Intake`
   - `owner=aic-planner`
   - `priority` 按用户影响判断，默认 `P1`
   - `next_step=收敛需求，必要时拉起研究`
   - `evidence_pointer` 至少包含 `conversation:<session-id>` 或可定位到本轮上下文的证据
5. 对 `Intake` / `Researching` / `Scoped` / `Planned` / `Replan` 的活跃任务，优先调用 `aic-planner`：
   - 若 `evidence_pointer` 里已有 Opportunity Card、research handoff 或 `opportunity:*` 标签，先把这些证据读清再下发给 `aic-planner`
   - 要求它决定是否需要先拉 `aic-researcher`
   - 要求它产出需求规格、验收标准、技术方案和下一负责人建议
6. 只要任务达到 `Approved` 且已经具备明确下一步，就调用 `aic-dispatcher`，把执行闭环正式点火
7. 若出现连续返工、方向错误、发布后异常或重复误解，再调用 `aic-reflector`
8. 只有在任务盘、看板和下一负责人都已对齐时，才返回 `HEARTBEAT_OK`

规则：

- 不把聊天当推进；没有任务就先立项
- 不把“已派发给 planner”说成“需求已收敛”
- 若没有任何新需求、活跃任务和系统异常，保持安静

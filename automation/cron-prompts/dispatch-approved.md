[cron:dispatch-approved]

# Dispatch Approved Prompt

你是 dispatch-approved agent。

流程：

1. 先运行：
   - `python3 scripts/bridge_approved_task.py --registry-path __OPENCLAW_HOME__/workspace-aic-captain/tasks/registry.json --handoffs-dir __OPENCLAW_HOME__/workspace-aic-captain/handoffs --lock __OPENCLAW_HOME__/workspace-aic-captain/tasks/_state/registry.lock --task-owner aic-dispatcher --next-owner aic-builder --format md`
2. 若没有 `Approved` 且 `owner=aic-dispatcher` 的任务：
   - 写执行日志到 `data/exec-logs/dispatch-approved/`
   - 日志包含：`- Status: no-op`
   - 返回 `HEARTBEAT_OK`
3. 若成功桥接：
   - 视为已把任务推进到 `Building`
   - 确认 handoff 已落到 captain 工作区
4. 将本轮结果写入 `data/exec-logs/dispatch-approved/`

规则：

- 不要跳过已批准任务不处理
- 不要丢失 spec 与 handoff 证据
- 执行日志必须包含：`- Status: ok`、`- decision: building|no-approved-task`、`- task_id: ...`

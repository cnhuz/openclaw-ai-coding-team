# HEARTBEAT.md

收到 heartbeat 时：

1. 先运行 `python3 scripts/validate_task_registry.py --path tasks/registry.json`
2. 刷新看板：`python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root ~/.openclaw/workspace-aic-researcher/data/research --skills-root ~/.openclaw/workspace-aic-researcher/data/skills --output data/dashboard.md`
3. 再运行 `python3 scripts/query_task_registry.py --path tasks/registry.json --view dispatcher --format md`
4. 对 `Approved` 任务：
   - 若已经具备明确实现边界，交给 `aic-builder`
   - 用 `python3 scripts/update_task_registry.py --path tasks/registry.json ...` 把状态推进到 `Building`
   - 用 `python3 scripts/create_handoff.py --task-id ... --next-owner aic-builder --sync-registry ...` 固化交接
5. 对 `Verifying` 任务：
   - 交给 `aic-tester`
   - 若验证失败，明确写回 `blocker`、`next_step`、`Rework` 或 `Replan`
6. 对 `Staging` / `Released` / `Observing` 任务：
   - 交给 `aic-releaser`
   - 需要沉淀的发布经验或上线观察，再转给 `aic-curator`
7. 对无人接手或长期停留在 `Building` / `Verifying` / `Observing` / `Rework` 的任务，先修正 `owner`、`state`、`next_step`，再继续派发
8. 只有当每个活跃执行任务都已有明确下一负责人，或确实无事可做时，才返回 `HEARTBEAT_OK`

规则：

- `tasks/registry.json` 是正式任务真相源；`data/dashboard.md` 只是最近观察摘要
- 若看板与 registry 冲突，以 registry 为准；必要时先刷新看板再继续
- 不把“已派发”说成“已完成”
- 任何状态切换都要同步 `tasks/registry.json`
- 任何跨角色转手都优先生成 handoff

[cron:reflect-release]

# Reflect Release Prompt

你是 release reflection agent。

流程：

1. 先运行：
   - `python3 scripts/query_task_registry.py --path __OPENCLAW_HOME__/workspace-aic-captain/tasks/registry.json --view active --owner aic-reflector --state Released --limit 5 --format md`
2. 若没有 `Released` 且 `owner=aic-reflector` 的任务：
   - 写执行日志到 `data/exec-logs/reflect-release/`
   - 日志包含：`- Status: no-op`
   - 返回 `HEARTBEAT_OK`
3. 只处理一个最高优先任务：
   - 找到 captain 工作区中最新的 `to-aic-reflector` handoff
   - 读取 handoff 中引用的 `__OPENCLAW_HOME__/workspace-aic-releaser/release-notes/<task-id>.md` 与 `__OPENCLAW_HOME__/workspace-aic-tester/verification-reports/<task-id>.md`
4. 生成 `reflections/<task-id>.md`，至少包含：
   - 本次交付是否符合原 spec
   - 哪些步骤顺畅，哪些步骤仍靠人工补位
   - 哪些经验值得沉淀为长期知识或流程修正
5. 生成 `data/knowledge-proposals/proposal-<task-id>.json`，最低字段遵循 `protocols/knowledge-pipeline.md`
6. 运行 `python3 scripts/update_task_registry.py --path __OPENCLAW_HOME__/workspace-aic-captain/tasks/registry.json --task-id ... --state Closed --owner aic-curator --clear-blocker --next-step "评估 reflection 与知识提案，完成长期沉淀" --append-evidence __OPENCLAW_HOME__/workspace-aic-reflector/reflections/<task-id>.md --append-evidence __OPENCLAW_HOME__/workspace-aic-reflector/data/knowledge-proposals/proposal-<task-id>.json`
7. 再运行 `python3 scripts/create_handoff.py --task-id ... --current-stage Closed --goal "把已闭环任务交给 curator 做长期沉淀" --deliverable "Reflection + Knowledge Proposal" --evidence __OPENCLAW_HOME__/workspace-aic-reflector/reflections/<task-id>.md --evidence __OPENCLAW_HOME__/workspace-aic-reflector/data/knowledge-proposals/proposal-<task-id>.json --next-owner aic-curator --breakpoint "评估 proposal 是否应落盘为长期知识或流程改造" --handoff-dir __OPENCLAW_HOME__/workspace-aic-captain/handoffs --sync-registry --registry-path __OPENCLAW_HOME__/workspace-aic-captain/tasks/registry.json --sync-state Closed --sync-owner aic-curator --sync-next-step "评估 reflection 与知识提案，完成长期沉淀"`
8. 将本轮结果写入 `data/exec-logs/reflect-release/`

规则：

- 不写空泛复盘；必须指出流程缺口与可复用经验
- 没有 release note 和 verification report，不允许关闭任务
- 执行日志必须包含：`- Status: ok`、`- decision: closed`、`- task_id: ...`、`- reflection: ...`

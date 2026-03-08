# AGENTS.md - aic-releaser Workspace Protocol

## Startup

1. 读 `SOUL.md`
2. 读 `IDENTITY.md`
3. 读 `USER.md`
4. 读 `MEMORY.md`
5. 看部署环境、发布门禁、回滚记录

## Memory Scope

- 重点记录：部署步骤、环境差异、回滚点、上线后异常
- 发布知识写入 `memory/knowledge/ref-*.md`
- 事故写入 `memory/post-mortems.md`

## Reflection Scope

- 反思发布前信息是否充分
- 反思门禁是否失效
- 反思观察窗口是否覆盖关键指标

## Collaboration

- 不主动调用其他 agent
- 输出必须包含：发布记录、回滚方案、观察结果
- 进入 `Staging`、`Released`、`Observing` 或发布受阻时，优先用 `python3 scripts/update_task_registry.py --path tasks/registry.json ...` 更新真相源
- 若发布受阻或完成发布交接，优先用 `python3 scripts/create_handoff.py --task-id ... --next-owner ... --sync-registry ...` 固化交接
- 若发布受阻，回交 `aic-dispatcher`

## Safety

- 不把“触发部署”说成“发布成功”
- 没过门禁不发布
- 高风险外部变更必须明确标注

## Completion Rule

- 只有发布结果和观察结论都明确后，才算完成

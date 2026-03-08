# AGENTS.md - aic-tester Workspace Protocol

## Startup

1. 读 `SOUL.md`
2. 读 `IDENTITY.md`
3. 读 `USER.md`
4. 读 `MEMORY.md`
5. 看历史失败模式、回归路径、验证门禁

## Memory Scope

- 重点记录：失败模式、边界漏洞、回归路径、未覆盖风险
- 可复用验证方法写入 `memory/knowledge/pat-*.md`
- 严重复盘写入 `memory/post-mortems.md`

## Reflection Scope

- 反思是否遗漏关键路径
- 反思哪些测试应该前移
- 高频失败模式交给 `aic-curator`

## Collaboration

- 不主动调用其他 agent
- 报告必须明确：通过、未覆盖、失败
- 进入 `Verifying`、发现 blocker、或建议打回时，优先用 `python3 scripts/update_task_registry.py --path tasks/registry.json ...` 更新真相源
- 若要打回 builder 或移交 releaser，优先用 `python3 scripts/create_handoff.py --task-id ... --next-owner ... --sync-registry ...` 生成交接
- 结论必须能交给 `aic-reviewer` 与 `aic-releaser`

## Safety

- 未运行测试不能写通过
- 未验证项必须显式列出

## Completion Rule

- 只有 Verification Report 完整产出，并明确下一步建议，才算完成

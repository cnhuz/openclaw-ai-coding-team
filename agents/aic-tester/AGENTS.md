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
- 结论必须能交给 `aic-reviewer` 与 `aic-releaser`

## Safety

- 未运行测试不能写通过
- 未验证项必须显式列出

## Completion Rule

- 只有 Verification Report 完整产出，并明确下一步建议，才算完成

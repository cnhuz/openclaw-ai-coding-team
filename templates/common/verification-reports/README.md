# Verification Reports

本目录用于保存 `aic-tester` 产出的验证报告。

推荐约定：

- 路径：`verification-reports/<task-id>.md`
- 内容结构：遵循 `protocols/verification-report.md`
- 角色边界：只放验证结论、覆盖范围、未验证项与证据，不放实现草稿

使用规则：

- 任务进入 `Verifying` 后，由 tester 在此落盘正式验证报告
- handoff 给 releaser / reflector 时，应把这里的报告作为核心证据之一
- 若验证失败并回到 `Rework`，应保留原报告，供 builder 按结论返工

# Specs

本目录用于保存 `aic-planner` 产出的正式规格文档。

推荐约定：

- 路径：`specs/<task-id>.md`
- 内容结构：遵循 `protocols/spec-template.md`
- 角色边界：只放可审议、可交接的规格，不放研究草稿或实现验证记录

使用规则：

- 正式任务进入 `Planned` 前后，应把可审议 Spec 固化到这里
- handoff、review、builder、tester 后续都应优先引用这里的绝对路径或稳定相对路径
- 若需要大幅改版，应保留 task_id 不变并原地更新，避免并行多份 Spec 漂移

# Release Notes

本目录用于保存 `aic-releaser` 产出的发布记录。

推荐约定：

- 路径：`release-notes/<task-id>.md`
- 内容应覆盖：发布模式、环境、执行结果、回滚点、上线后观察项
- 角色边界：只放发布门禁与发布结果，不替代验证报告或反思记录

使用规则：

- 任务进入 `Staging` 后，由 releaser 在此落盘正式 release record
- handoff 给 reflector 时，应附上这里的记录与 tester 的验证报告
- 若发布门禁失败，可保留当前记录作为回交 dispatcher / builder 的证据

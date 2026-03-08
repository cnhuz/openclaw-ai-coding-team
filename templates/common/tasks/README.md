# Tasks Registry

本目录用于保存**本地任务真相源**。

按 OpenClaw 原生规则，本地真相源应优先采用**结构化格式**，便于：

- 调度读取
- cron 巡检
- dashboard 汇总
- 断点恢复
- 脚本校验

## 推荐文件

- `tasks/registry.json`：机器可读的主真相源
- `tasks/registry.md`：可选的人类说明/入口索引

## `registry.json` 结构

根对象最低字段：

- `schemaVersion`
- `updatedAt`
- `sourceType`
- `externalSource`
- `tasks`

每个任务最低字段：

- `task_id`
- `title`
- `state`
- `owner`
- `priority`
- `updated_at`
- `blocker`
- `next_step`
- `evidence_pointer`

推荐补充字段：

- `breakpoint`
- `acceptance`
- `notes`
- `tags`

## `breakpoint` 结构

复杂任务建议使用对象，而不是一整段自由文本：

```json
{
  "completed": ["已完成事项"],
  "next": ["下一步动作"],
  "design_notes": ["设计备注"],
  "pending_confirmation": ["待确认项"]
}
```

## 推荐状态

与 `protocols/task-lifecycle.md` 保持一致：

- `Intake`
- `Researching`
- `Scoped`
- `Planned`
- `Approved`
- `Building`
- `Verifying`
- `Staging`
- `Released`
- `Observing`
- `Closed`
- `Replan`
- `Rework`

## 更新规则

- 任务状态更新优先写 `tasks/registry.json`
- `memory/` 只记录事件，不替代真相源
- 任务转手时要同步更新 `owner`、`next_step`、`breakpoint`
- 没有外部任务系统时，不要退回 Markdown 表格做主记录

# Task Registry

这是本地任务真相源的兜底版本。

若你已接入外部任务系统，此文件可以只保留索引说明与入口链接。

| Task ID | Title | State | Owner | Priority | Updated | Blocker | Next Step | Breakpoint | Evidence |
|--------|-------|-------|-------|----------|---------|---------|-----------|------------|----------|

## 使用规则

- 状态更新优先写这里或外部任务系统
- `memory/` 只记录事件，不替代这里
- 复杂任务应补 breakpoint 指针，便于下一次直接恢复
- 同一任务如果暂停或跨角色转手，必须更新 `Breakpoint`

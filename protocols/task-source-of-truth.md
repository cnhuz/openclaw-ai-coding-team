# Task Source of Truth

任务状态必须有且只有一个真相源。

## 原则

- 任务状态不能同时靠会话、记忆、口头交接、多个表格共同维护
- 记忆文件记录事件与摘要，不替代任务状态主记录
- 所有角色都以同一处状态为准，避免漂移

## 推荐顺序

1. 外部任务系统：Linear / Jira / GitHub Projects / 自建任务板
2. 若暂时没有外部系统，至少使用本地 `tasks/registry.md`

## 最低字段

无论任务真相源是什么，都应至少包含：

- `task_id`
- `title`
- `state`
- `owner`
- `priority`
- `updated_at`
- `blocker`
- `next_step`
- `evidence_pointer`

## 和记忆的分工

- 任务真相源：记录“当前状态是什么”
- `memory/daily/YYYY-MM/YYYY-MM-DD.md`：记录“发生了什么”
- `memory/YYYY-MM-DD.md`：仅兼容旧式工作区
- `MEMORY.md`：记录“哪些是高频长期事实”
- `memory/projects/`：记录项目级长期摘要与事实链

## 会话启动

每个新 session 启动时，先检查：

1. 是否有 `In Progress` / `Blocked` 任务
2. 是否有最新 breakpoint
3. 当前任务状态和记忆描述是否一致

如果状态和记忆冲突，以任务真相源为准，再修正记忆。

## Breakpoint 规范

复杂任务中断前，应留下结构化 breakpoint：

```md
任务ID: <task_id>
当前阶段: <state>
已完成:
- ...
下一步:
- ...
设计备注:
- ...
待确认:
- ...
```

## WIP 建议

- 非运维类角色：同一时间尽量只保持 1 个 `In Progress`
- 调度类角色：可以同时追踪多个任务，但每个任务都要有明确下一负责人

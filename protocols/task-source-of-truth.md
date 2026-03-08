# Task Source of Truth

任务状态必须有且只有一个真相源。

## 原则

- 任务状态不能同时靠会话、记忆、口头交接、多个表格共同维护
- 记忆文件记录事件与摘要，不替代任务状态主记录
- 所有角色都以同一处状态为准，避免漂移

## 推荐顺序

1. 外部任务系统：Linear / Jira / GitHub Projects / 自建任务板
2. 若暂时没有外部系统，至少使用本地 `tasks/registry.json`

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

若使用本地 JSON 真相源，推荐额外包含：

- `breakpoint`
- `acceptance`
- `notes`
- `tags`

推荐配套脚本：

- `scripts/validate_task_registry.py`
- `scripts/query_task_registry.py`
- `scripts/update_task_registry.py`

## 和记忆的分工

- 任务真相源：记录“当前状态是什么”
- `memory/YYYY-MM-DD.md`：记录“发生了什么”
- `memory/daily/YYYY-MM/YYYY-MM-DD.md`：可作为归档或旧式结构兼容
- `MEMORY.md`：记录“哪些是高频长期事实”
- `memory/projects/`：记录项目级长期摘要与事实链

## 会话启动

每个新 session 启动时，先检查：

1. 是否有 `In Progress` / `Blocked` 任务
2. 是否有最新 breakpoint
3. 当前任务状态和记忆描述是否一致

如果状态和记忆冲突，以任务真相源为准，再修正记忆。

## 状态更新建议

若使用本地 JSON 真相源，推荐通过脚本更新，而不是手工改多处：

```bash
python3 scripts/update_task_registry.py \
  --path tasks/registry.json \
  --task-id TASK-001 \
  --state Building \
  --owner aic-builder \
  --next-step "完成本轮 diff" \
  --append-evidence src/app.ts
```

进入新阶段时，应在同一轮完成三件事：

1. 更新 `tasks/registry.json`
2. 将关键事件写入 `memory/YYYY-MM-DD.md`
3. 若涉及跨角色，补上 handoff；推荐使用 `python3 scripts/create_handoff.py`

## 本地 JSON 推荐结构

推荐使用：

- `tasks/registry.json`：结构化主记录
- `tasks/registry.md`：人工备注与外部链接

示例根结构：

```json
{
  "schemaVersion": 1,
  "updatedAt": "2026-03-07T10:00:00+08:00",
  "sourceType": "local_registry",
  "externalSource": null,
  "tasks": []
}
```

单个任务示例：

```json
{
  "task_id": "TASK-001",
  "title": "重构本地任务真相源",
  "state": "Building",
  "owner": "aic-builder",
  "priority": "P1",
  "updated_at": "2026-03-07T10:00:00+08:00",
  "blocker": null,
  "next_step": "同步协议文档与模板",
  "evidence_pointer": [
    "protocols/task-source-of-truth.md",
    "templates/common/tasks/registry.json"
  ],
  "breakpoint": {
    "completed": [
      "已完成 schema 设计"
    ],
    "next": [
      "同步安装脚本与文档"
    ],
    "design_notes": [],
    "pending_confirmation": []
  }
}
```

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

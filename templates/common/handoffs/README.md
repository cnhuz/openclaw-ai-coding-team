# Handoffs

这个目录用于保存**跨角色交接产物**。

推荐结构：

```text
handoffs/YYYY-MM-DD/
└── HHMMSS-<task-id>-to-<next-owner>.md
```

## 原则

- handoff 是证据产物，不是聊天摘要
- 交接必须和 `protocols/handoff-contract.md` 保持一致
- 跨角色转手时，优先生成 handoff 文件
- 若 handoff 同时导致任务状态 / owner / next step 变化，应同步更新 `tasks/registry.json`

## 推荐文件

- `handoffs/README.md`：目录说明
- `handoffs/TEMPLATE.md`：手工填写模板
- `handoffs/YYYY-MM-DD/*.md`：实际交接产物

## 推荐入口

优先使用：

- `python3 scripts/create_handoff.py`

这样可以：

- 生成标准化 Markdown 交接文件
- 自动落到按日期分组的目录
- 可选同步 `tasks/registry.json`

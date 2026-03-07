# Project Profiles

推荐结构：

```text
memory/projects/<name>/
├── summary.md
└── items.json
```

可直接复制 `_template/` 作为第一个项目档案骨架。

## `summary.md`

记录项目当前快照：

- 当前状态
- 当前 owner
- 关键里程碑
- 最近 blocker
- 相关任务真相源入口

## `items.json`

记录项目事实链：

- `id`
- `fact`
- `category`
- `timestamp`
- `source`
- `status`
- `supersededBy`

项目 `category` 推荐值：

- `identity`
- `status`
- `milestone`
- `scope`
- `owner`
- `decision`
- `config`

`status` 推荐值：

- `active`
- `superseded`
- `historical`

`summary.md` 表示项目当前快照，`items.json` 表示长期事实链与 supersede 历史。

# People Profiles

推荐结构：

```text
memory/people/<name>/
├── summary.md
└── items.json
```

可直接复制 `_template/` 作为第一个人物档案骨架。

## `summary.md`

记录当前快照，面向人读：

- 这个人是谁
- 当前角色/关系
- 近期关键变化
- 指向相关项目或协议

## `items.json`

记录原子事实链，面向机器读：

- `id`
- `fact`
- `category`
- `timestamp`
- `source`
- `status`
- `supersededBy`（如有）

推荐补齐：

- `schemaVersion`
- `entity`
- `type`

人物 `category` 推荐值：

- `identity`
- `relationship`
- `status`
- `preference`
- `decision`
- `config`

`status` 推荐值：

- `active`
- `superseded`
- `historical`

`summary.md` 写当前快照，`items.json` 保留历史链；两者不要混用。

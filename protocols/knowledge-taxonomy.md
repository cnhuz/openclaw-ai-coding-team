# Knowledge Taxonomy

这套知识分类直接继承你当前工作区的长处：热缓存 + 深层分类 + 复盘沉淀。
同时吸收 `openclaw-memory-architecture` 的实体 schema 与 clerk pipeline 思路。

## 根层

- `MEMORY.md`：热缓存，记录高频事实和指针
- `memory/`：深层存储

## 深层分类

| 路径 | 内容 |
|------|------|
| `memory/glossary.md` | 术语、缩写、黑话 |
| `memory/people/<name>/summary.md` | 关键人物当前快照 |
| `memory/people/<name>/items.json` | 人物事实链与 supersede 历史 |
| `memory/projects/<name>/summary.md` | 项目当前状态与摘要 |
| `memory/projects/<name>/items.json` | 项目事实链与 supersede 历史 |
| `memory/knowledge/` | 可复用知识 |
| `memory/post-mortems.md` | 失败复盘 |
| `memory/YYYY-MM-DD.md` | 推荐的运行态每日日志路径 |
| `memory/daily/YYYY-MM/YYYY-MM-DD.md` | 可选的归档/兼容目录结构 |
| `memory/weekly/YYYY-WXX.md` | 周级巩固与归档摘要 |
| `memory/archive/` | 已退役但仍需保留的旧知识或快照 |
| `memory/context/environment.md` | 环境、部署、机器、基础设施 |
| `memory/_state/` | 游标、锁、gate 等运行态状态，不属于长期知识 |

## 非记忆但相关的数据区

| 路径 | 内容 |
|------|------|
| `data/knowledge-proposals/` | 待审核的知识提案 |
| `data/exec-logs/` | 自动化执行日志与证据 |

## `memory/knowledge/` 前缀约定

| 前缀 | 含义 | 示例 |
|------|------|------|
| `fw-` | 方法论 / 框架 | `fw-release-management.md` |
| `ref-` | 技术参考 | `ref-nextjs-deploy.md` |
| `pat-` | 模式与套路 | `pat-monorepo-build-cache.md` |
| `sys-` | 系统级反思 | `sys-team-bottlenecks.md` |

## 谁负责写什么

### `aic-curator`

- 术语表
- 人物档案
- 项目档案
- 知识文件
- 热缓存提升 / 降级
- post-mortem 归档

### `aic-reflector`

- 识别需要沉淀什么
- 指出哪些规则已过时
- 指出哪些知识该升级到长期记忆

### 其他执行角色

- 产生原始材料
- 不能把“应该沉淀什么”全部推给 `curator`

## 提升规则

- 一周内重复使用 3 次以上的信息，提升到 `MEMORY.md`
- 长期不用的信息，从 `MEMORY.md` 降级回深层文件
- 失败经验必须写 `memory/post-mortems.md`
- 能复用的技术知识才写入 `memory/knowledge/`

## 实体事实追踪

- 人物和项目尽量使用 `summary.md + items.json` 双文件结构
- `summary.md` 面向人读，记录当前快照
- `items.json` 面向机器读，记录原子事实、状态与 supersede 链
- 事实变化时，不直接覆盖旧事实；旧事实应标记为 `superseded`

### `items.json` 最低 schema

- `schemaVersion`
- `entity`
- `type`
- `items[]`

每个事实项至少包含：

- `id`
- `fact`
- `category`
- `timestamp`
- `source`
- `status`
- `supersededBy`

### 推荐取值

- `status`：`active` / `superseded` / `historical`
- 人物 `category`：`identity` / `relationship` / `status` / `preference` / `decision` / `config`
- 项目 `category`：`identity` / `status` / `milestone` / `scope` / `owner` / `decision` / `config`
- `source`：优先写成 `conversation:<session-id>` / `log:YYYY-MM-DD` / `cron:<job-name>` / `task:<task-id>` / `migration:<file>`

## 设计决策沉淀

- 重要设计决策统一汇入 `memory/knowledge/fw-design-decisions.md`
- 每条设计决策至少包含：日期、决策、理由、被放弃方案、来源

## 知识提案管线

- 原始材料先进入每日日志、执行日志、post-mortem、任务真相源
- `aic-reflector` 与 `aic-curator` 负责从原始材料中提出知识提案
- 有歧义、跨规则、可能影响长期记忆质量的内容先进入 `data/knowledge-proposals/`
- 经确认后再由 `aic-curator` 落入 `memory/`

详细流程见 `protocols/knowledge-pipeline.md`。

# Task Lifecycle

## 统一状态定义

| 状态 | 含义 | 主要 Owner |
|------|------|------------|
| `Intake` | 新想法 / 新需求进入团队 | `aic-captain` |
| `Researching` | 研究需求、方向、用户、技术、竞品 | `aic-researcher` |
| `Scoped` | 范围收敛，明确做什么与不做什么 | `aic-planner` |
| `Planned` | 已形成产品规格与技术方案 | `aic-planner` |
| `Approved` | 审议通过，可以进入实施 | `aic-reviewer` |
| `Building` | 开发与实现中 | `aic-builder` |
| `Verifying` | 测试、回归、验收中 | `aic-tester` |
| `Staging` | 已部署到预发布环境 | `aic-releaser` |
| `Released` | 正式上线 | `aic-releaser` |
| `Observing` | 上线后观测期 | `aic-releaser` |
| `Closed` | 完成归档 | `aic-captain` |
| `Replan` | 方案被打回，需要重做规划 | `aic-planner` |
| `Rework` | 实现/测试/发布不通过，需要返工 | `aic-dispatcher` |

## 标准流转

```text
Intake
→ Researching
→ Scoped
→ Planned
→ Approved
→ Building
→ Verifying
→ Staging
→ Released
→ Observing
→ Closed
```

任务状态本身必须写入单一真相源；本文件定义的是允许流转，不是状态存储位置。
详见：`protocols/task-source-of-truth.md`

## 回退规则

- 研究结论不足、目标不清、范围失控：回到 `Researching` 或 `Scoped`
- 方案被否决：进入 `Replan`
- 实现不达标、测试失败、发布失败：进入 `Rework`
- `Replan` 只能回到 `Planned`
- `Rework` 只能回到 `Building` 或 `Verifying`

## 状态切换即记忆

- 每次进入新状态或离开旧状态，当前 owner 都要在同一轮把关键变化写入 `memory/YYYY-MM-DD.md`
- 关键决策、用户纠正、blocker、事故、返工、上线、回滚，不得拖到任务关闭后再补记
- `aic-curator` 负责后续分类、提升、去重；不是首次捕获者
- `aic-reflector` 负责复盘制度问题；不是首次捕获者

## 每个状态必须有的产物

| 状态 | 最低产物要求 |
|------|--------------|
| `Researching` | Opportunity Card / 研究摘要 |
| `Scoped` | 范围边界、交付物定义 |
| `Planned` | Spec + Tech Plan |
| `Approved` | 审议结论、风险说明 |
| `Building` | 实现摘要、改动文件 |
| `Verifying` | Verification Report |
| `Staging` | Release Pack + 烟测结果 |
| `Released` | 发布记录、回滚点、上线时间 |
| `Observing` | 监控观察结果、异常记录 |
| `Closed` | 项目摘要、知识沉淀、必要 post-mortem |

## 关闭任务前必须完成

1. 当前 owner 已完成事件级首写，关键状态变化已进入 `memory/YYYY-MM-DD.md`
2. `aic-curator` 已完成需要长期保留内容的分类落盘
3. 需要沉淀的技术知识已写入 `memory/knowledge/`
4. 如有失败或返工，已更新 `memory/post-mortems.md`
5. `aic-captain` 已输出最终汇报

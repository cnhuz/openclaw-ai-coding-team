# Agent Graph

## 总体链路

```text
你
└─ aic-captain
   ├─ aic-planner
   │  ├─ aic-researcher
   │  └─ aic-reviewer
   ├─ aic-dispatcher
   │  ├─ aic-researcher
   │  ├─ aic-builder
   │  ├─ aic-tester
   │  ├─ aic-releaser
   │  └─ aic-curator
   └─ aic-reflector
      └─ aic-curator
```

## 调用矩阵

| Caller | Allowed Callees |
|--------|------------------|
| `aic-captain` | `aic-planner`, `aic-dispatcher`, `aic-reflector` |
| `aic-planner` | `aic-researcher`, `aic-reviewer` |
| `aic-reviewer` | 无 |
| `aic-dispatcher` | `aic-researcher`, `aic-builder`, `aic-tester`, `aic-releaser`, `aic-curator` |
| `aic-researcher` | 无 |
| `aic-builder` | 无 |
| `aic-tester` | 无 |
| `aic-releaser` | 无 |
| `aic-curator` | 无 |
| `aic-reflector` | `aic-curator` |

## 主流程

### 1. 你的想法进入团队

```text
aic-captain
→ aic-planner
→ aic-reviewer
→ aic-dispatcher
→ aic-builder
→ aic-tester
→ aic-releaser
→ aic-curator
→ aic-captain
```

### 2. 团队自主发现机会

```text
aic-captain (heartbeat / scheduled review)
→ aic-researcher
→ aic-planner
→ aic-reviewer
→ aic-dispatcher
→ 后续执行链
```

### 3. 上线后复盘

```text
aic-reflector
→ aic-curator
→ aic-captain
```

## 状态机

统一使用以下任务状态：

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

## 角色边界

- 只有 `aic-captain` 能直接承接外部消息与最终回报
- `aic-reviewer` 负责否决与补边界，不负责实际实现
- `aic-dispatcher` 负责派工，不自己写产品方案
- `aic-builder` 是产品工程，默认调度 `Codex` / `Claude Code` 等编码引擎完成实现，但不能单方面判定“可上线”
- `aic-releaser` 可以上线，但不能私自扩需求范围
- `aic-curator` 和 `aic-reflector` 负责系统持续学习，不直接承担核心交付
- 重要事件由当前 owner 立即首写记忆，`aic-curator` 负责后续分类，`aic-reflector` 负责制度复盘
- `heartbeat` 默认只给调度型角色；执行型角色通过任务触发或 cron sprint 持续推进
- 任务状态必须服从单一真相源；记忆记录事件，不替代任务状态主记录
- 自动化任务必须留下执行日志，不允许 silent fail

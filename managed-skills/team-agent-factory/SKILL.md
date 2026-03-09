---
name: team-agent-factory
description: 为 aic-captain 提供团队拓扑治理能力。用于根据任务负载、KPI、事件流和经营实验情况，新增全功能 agent、退役不必要 agent，并同步真实 openclaw.json、allowAgents、workspace、agentDir、cron 清理与 qmd 记忆初始化。
---

# team-agent-factory

这个 skill 只在 **团队拓扑需要调整** 时使用。

适用场景：

- 某个职责长期堆积，现有角色吃不下
- 某类能力缺口反复出现，现有团队没有合适 agent
- 某个 agent 长期无任务、无真实推进、只占运行资源
- 需要把实验型职责临时拆成独立 agent，再在验证结束后收回

不适用场景：

- 只是想修改单个任务 owner
- 只是想手动跑某个 cron
- 只是想给现有 agent 加一点提示词

## 工作流

1. 先看控制面：
   - `/agents`
   - `/agent?id=...`
   - `/kpi`
   - `/events`
   - `/experiments`
2. 明确这次是：
   - **新增 agent**
   - **退役 agent**
3. 所有拓扑变更都先 dry-run 一次：
   - `python3 scripts/manage_team_agent.py list --format md`
   - `python3 scripts/manage_team_agent.py add ... --dry-run --format md`
   - `python3 scripts/manage_team_agent.py retire ... --dry-run --format md`
4. 变更完成后，至少回验：
   - `openclaw status --deep --json`
   - `openclaw skills list --json`
   - `python3 scripts/refresh_dashboard.py ...`
5. 把“为什么新增/退役、预期解决什么问题、下一步观察什么”写进记忆或 handoff

## 新增 agent 时的最小要求

- 必须明确：
  - `agent_id`
  - 中文角色名
  - 角色职责
  - 输入
  - 输出
  - 协作边界
  - 上游是谁
  - 下游是谁
- 若没有充分理由，不要新增只会“看起来很忙”的角色
- 默认让 `aic-captain` 成为上游；只有确实需要，才扩到更多 caller

## 退役 agent 时的硬规则

- 若它仍持有活跃任务，必须先重分配，或显式传 `--reassign-active-tasks-to`
- 退役不是直接删干净，而是：
  - 从 `openclaw.json` 移除
  - 从别人的 `allowAgents` 中摘掉
  - 清理它的 cron jobs
  - 把 workspace / agentDir 归档

## 常用命令

### 1) 查看当前团队

```bash
python3 scripts/manage_team_agent.py list --format md
```

### 2) 新增一个全功能 agent

```bash
python3 scripts/manage_team_agent.py add \
  --agent-id aic-growth \
  --role-name 增长官 \
  --role-title 分发与增长实验 \
  --mission "围绕自养目标持续验证分发、转化与留存" \
  --accepted-from aic-captain \
  --allow-call aic-researcher \
  --core-responsibility "拆解增长实验并维护实验节奏" \
  --core-responsibility "把分发验证结果写回实验真相源" \
  --input "来自 captain 的增长目标与实验任务" \
  --input "现有 experiments 与 north-star 风险" \
  --output "增长实验记录、结果更新、下一步建议" \
  --boundary "不直接改产品路线，只验证分发与转化" \
  --memory-focus "记录高价值分发路径、转化信号与失败模式" \
  --reflection-focus "反思是不是在做高噪音低收益分发动作" \
  --emoji 📈 \
  --heartbeat-every 1h \
  --dry-run \
  --format md
```

### 3) 退役一个 agent

```bash
python3 scripts/manage_team_agent.py retire \
  --agent-id aic-growth \
  --reassign-active-tasks-to aic-captain \
  --dry-run \
  --format md
```

## 结果判断

只有同时满足下面几点，才算拓扑变更成功：

- 新/旧 agent 的 workspace 与 agentDir 状态正确
- `openclaw.json` 中 agent 列表已同步
- 上下游 `allowAgents` 已同步
- 若新增 agent，qmd 记忆已初始化
- 若退役 agent，遗留 cron job 已清掉
- 控制面刷新后，团队拓扑和角色面板能看到变化

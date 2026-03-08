# AGENTS.md - AI Coding Team Workspace Protocol

这个文件是当前 agent 的**根行为真相源**。

按 OpenClaw 原生规则，子 agent 默认只保证拿到根 `AGENTS.md` 与 `TOOLS.md`。
因此所有关键角色边界、升级路径、交接要求，都必须直接写在这里；不要把关键规则只放在 `ROLE.md`、`SOUL.md`、`IDENTITY.md` 之类补充文件中。

## 会话原则

1. 如果 `BOOTSTRAP.md` 仍存在，先完成首跑初始化，再进入日常工作
2. 先以当前 `AGENTS.md` 为准，再看 `TOOLS.md`
3. 主 workspace 会话中，若存在 `SOUL.md`、`IDENTITY.md`、`USER.md`、`MEMORY.md`，按需补读
4. 优先读取今天与昨天的 `memory/YYYY-MM-DD.md`
5. 若当前任务涉及 cron、备份、记忆同步、`MEMORY.md` 并发写入或定时任务排障，再读 `scripts/README.md`
6. `BOOT.md` 仅在启用 OpenClaw `boot-md` hook 或被显式要求做启动巡检时生效；不要假设每个子 agent / isolated cron 都自动读过它

## 记忆规则

- 重要信息**立即写入**，不允许依赖夜间复盘、`reflector` 或 `curator` 做首次补记
- 当前任务 owner 对自己看到的关键事件负首次落盘责任；先写对，再交给后续角色提炼
- 发生以下情况时，必须在同一轮写入当日日志：
  - 接到新任务或任务状态发生变化
  - 关键决策拍板、边界调整、优先级变化
  - 用户纠正偏好、规则、环境信息
  - 出现 blocker、事故、返工、上线、回滚
  - 学到新的入口、命令、路径、排障方法、可复用模式
- 运行态每日日志优先写入 `memory/YYYY-MM-DD.md`
- 若 workspace 仍保留 `memory/daily/` 分月目录，把它视为典藏/归档结构，而不是主运行写入入口
- 高频且稳定的长期事实进 `MEMORY.md`
- 可复用知识进 `memory/knowledge/`
- 项目或任务级持续状态进 `memory/projects/`
- 失败复盘进 `memory/post-mortems.md`
- 存在歧义、需要审核的长期沉淀候选先进入 `data/knowledge-proposals/`
- `aic-curator` 负责提升、去重、分类、降级，不替代首次捕获
- `aic-reflector` 负责发现制度问题与根因，不替代首次捕获

## 检索协议

### 确定性查找

1. `MEMORY.md`
2. `memory/YYYY-MM-DD.md`
3. `memory/glossary.md`
4. `memory/people/`
5. `memory/projects/`
6. `memory/knowledge/`
7. `memory/context/`
8. `memory/post-mortems.md`

### 模糊查找

如果问题是“之前是不是讨论过 X”“这件事以前怎么做过”，优先用语义搜索或等价检索，而不是遍历所有文件。

检索历史材料时，优先把 `memory/`、`memory/weekly/`、`memory/archive/`、`data/exec-logs/` 当作语料区。

### 先解码再执行

- 人名、缩写、项目代号、环境名，先解码再动作
- 对复杂问题，先走确定性查找，再补语义搜索
- 如果实体还没被确认，不要盲目执行

## 协作规则

- 只交付事实、证据、结论，不交付空话
- 必须明确写出下一负责人
- 不跳过层级调用
- 只有入口 Agent 可以直接对外汇报
- 若 workspace 存在 `scripts/README.md`，涉及自动化或记忆维护时先按其中入口执行，不要自己臆造脚本用法

## 安全

- 破坏性操作先确认
- 外发动作先确认
- 不泄露私人数据
- 不把猜测当结论

## 技能治理

- 发现 → 审查 → 安装，三步缺一不可
- 安装前必须先做安全审查
- 默认不自动安装未知来源 skill，不自动执行新写的高风险脚本
- 若 `data/skills/policy.json` 显式允许，并且命中“可信源 + 低风险 + 已审查”条件，可自动安装 skill

## 持续学习

- 有价值的信息立即写入记忆
- 反复踩坑必须写 `memory/post-mortems.md`
- 周期性复盘由 `reflector` 推动，`curator` 落盘

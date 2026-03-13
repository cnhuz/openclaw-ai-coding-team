# AGENTS.md - Core Agent Profile

这个文件是当前 agent 的根行为真相源。

## 会话原则

1. 先读 `AGENTS.md`，再读 `TOOLS.md`
2. 若存在 `SOUL.md`、`IDENTITY.md`、`MEMORY.md`，按需补读
3. 优先读取今天与昨天的 `memory/YYYY-MM-DD.md`
4. 涉及记忆同步、知识整理、反思或 qmd 检索时，先读 `scripts/README.md`
5. `BOOT.md` 仅在显式巡检或启用 `boot-md` hook 时使用

## 核心目标

- 围绕用户目标稳定工作，不自行扩展目标范围
- 及时记录关键信息，保持记忆新鲜
- 让知识结构持续可检索、可复用
- 每日反思执行方式，减少重复错误与噪音动作

## 记忆规则

- 重要信息立即写入，不依赖晚些时候补记
- 运行态每日日志优先写入 `memory/YYYY-MM-DD.md`
- 稳定、长期有效的事实再提升进 `MEMORY.md`
- 可复用方法、规则、模式写入 `memory/knowledge/`
- 失败经验写入 `memory/post-mortems.md`
- 人物与项目的持续事实分别写入 `memory/people/`、`memory/projects/`
- 暂不宜直接落盘的结论先写入 `data/knowledge-proposals/`

## 知识结构

- `MEMORY.md`：长期热缓存
- `memory/YYYY-MM-DD.md`：日记忆
- `memory/knowledge/`：方法、规则、经验
- `memory/people/`：人物事实链
- `memory/projects/`：项目事实链
- `memory/context/`：环境上下文
- `memory/post-mortems.md`：失败复盘
- `data/knowledge-proposals/`：待审的长期沉淀候选

## 反思规则

- 每日反思只回答三件事：
  - 今天发生了什么
  - 哪些做法有效或无效
  - 哪些知识应沉淀或修正
- 低置信度猜测不要直接写入长期记忆
- 需要人审的结构性变化先进入 `data/knowledge-proposals/`

## qmd 检索

- 确定性查找优先：
  - `MEMORY.md`
  - `memory/YYYY-MM-DD.md`
  - `memory/knowledge/`
  - `memory/people/`
  - `memory/projects/`
- 模糊历史问题再使用 qmd 搜索
- 若需要更强语义检索，可在安装或后续维护时执行 `qmd embed`

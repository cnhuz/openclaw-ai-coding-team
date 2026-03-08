# Knowledge Pipeline

知识沉淀不能只靠“想到就写”，也不能把所有分类判断都塞回执行热路径。

这套管线吸收 `openclaw-memory-architecture` 的 clerk model，但保留你要求的“重要事件立即首写”原则：

- **首次捕获** 仍由当前 owner 同轮写入每日日志
- **知识提案与分类治理** 由 `aic-reflector` / `aic-curator` 负责

## 目标

- 不让执行角色在热路径里承担过重的元认知负担
- 不让长期记忆被低质量、低置信度、一次性噪音污染
- 让重要知识有“原始材料 → 提案 → 落地”的清晰链路

## 原始材料来源

- `memory/YYYY-MM-DD.md`，必要时兼容 `memory/daily/YYYY-MM/YYYY-MM-DD.md`
- `memory/weekly/YYYY-WXX.md`
- `memory/post-mortems.md`
- `data/exec-logs/`
- `tasks/registry.json` 或外部任务系统
- handoff / verification / release / reflection 产物

## 五类高价值信号

| 信号 | 例子 | 目标位置 |
|------|------|----------|
| 设计决策 | 选择 A 而不是 B，因为 C | `memory/knowledge/fw-design-decisions.md` |
| 可复用经验 | 某种实现 / 验证套路反复有效 | `memory/knowledge/pat-*.md` / `ref-*.md` |
| 新术语 | 新代号、缩写、黑话 | `memory/glossary.md` |
| 实体变化 | 人物角色变化、项目状态变化 | `memory/people/` / `memory/projects/` |
| 重复模式 | 同类动作反复出现，值得工具化 | skill 候选 / 脚本候选 / `pat-*.md` |

## 流程

### 1. 首次捕获

- 当前 owner 在同一轮把事件写入每日日志
- 不等待 `aic-reflector` 或 `aic-curator` 补首次记录

### 2. 提案

- `aic-reflector` 或 `aic-curator` 扫描原始材料
- 对值得沉淀但暂不宜直接落盘的内容，生成知识提案到 `data/knowledge-proposals/`

### 3. 审核

以下情况默认先提案再确认：

- 置信度不高
- 结论依赖推断而非直接事实
- 会改动长期热缓存或规则
- 会覆盖已有实体事实
- 可能引发 skill / 自动化 / 协议调整

以下情况可由 `aic-curator` 直接落盘：

- 高置信度、低风险的术语补录
- 已明确证据链的实体状态更新
- 已重复验证的可复用经验整理
- 滚动区的新增、清理、降级

### 4. 落地

- `aic-curator` 负责将确认后的提案落入正确目录
- 对人物与项目事实，优先更新 `summary.md + items.json`
- 对 supersede 场景，保留历史，不直接抹平旧事实

### 5. 巩固与降级

- daily / curation 维护滚动区与当日 canonical
- weekly 负责长期提升、去重、降级和归档

## 提案文件建议

目录建议：

```text
data/knowledge-proposals/YYYY-MM-DD/
├── proposal-001.json
└── proposal-002.json
```

单个提案最低字段：

```json
{
  "type": "design_decision | reusable_experience | terminology | entity_change | repeated_pattern",
  "confidence": "high | medium | low",
  "source": "memory/YYYY-MM-DD.md",
  "destination": "memory/knowledge/fw-design-decisions.md",
  "action": "append | update | supersede | archive",
  "summary": "一句话摘要"
}
```

## 角色分工

### `aic-reflector`

- 识别系统问题、规则缺口、重复错误
- 提出需要沉淀或规则调整的候选项
- 不直接把低置信度结论写进长期记忆

### `aic-curator`

- 审核、合并、落地高置信度提案
- 维护 `MEMORY.md`、实体档案、知识文件、滚动区、归档
- 记录 supersede / 降级 / 提升动作

### 其他执行角色

- 负责写出足够清楚的原始材料
- 不需要在执行中承担复杂的知识分类判断

## 红线

- 没有原始材料支撑的内容，不进入长期记忆
- 不把随口猜测包装成设计决策
- 不因为“省事”跳过 supersede 历史
- 不让 `data/knowledge-proposals/` 变成长期垃圾堆；无效提案要标记结果或清理

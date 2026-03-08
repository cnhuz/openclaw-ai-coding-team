# Skills Runtime Data

这个目录是运行态的技能治理与安装状态区。

目标：

- 记录“当前缺什么能力”
- 记录“发现了哪些 skill 候选”
- 记录“哪些候选经过审查并允许自动安装”
- 记录“已经安装到运行态的 skills”

## 目录结构

- `policy.json`：自动安装与可信源策略
- `dependency_policy.json`：依赖安装器与本地 toolchain 自举策略
- `catalog.json`：skill 候选、审查、安装状态
- `inventory.json`：当前 OpenClaw 可见 skills 快照

## 自动安装边界

- 允许自动安装，不等于允许**无审查乱装**
- 只有命中 `policy.json` 的可信源、低风险、允许的安装方式时，才应自动安装
- 高风险或未知来源仍应保留为候选，等待后续审查

## 推荐流程

1. 同步当前 skills 库存
2. 从工具失败和能力缺口中提取 skill gap
3. 从可信源中搜索候选
4. 记录到 `catalog.json`
5. 审查后自动安装或继续观察

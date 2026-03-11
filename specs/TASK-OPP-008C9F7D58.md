# Spec

任务ID: TASK-OPP-008C9F7D58

## 背景
GitHub 在 Atlassian Marketplace 上架了 “GitHub Copilot for Jira (by GitHub)”，并在 GitHub Changelog 宣布其 “Copilot coding agent for Jira” 进入 public preview。根据公开页面描述，其核心工作流包括：
- 在 Jira 中通过 **Assignee 字段分配**给 Copilot，或在 issue 评论里 **@mention Copilot** 触发（Marketplace listing）
- agent 会 **拉取上下文**（issue 描述/评论等，按公开描述）并异步推进（GitHub Changelog）
- 进展/结果会以 **draft PR / PR updates** 的形式呈现，并在 Jira 内通过 agent panel 更新/提问（GitHub Changelog + Marketplace listing）
- 前置条件提到 **Jira Cloud + Rovo** 与 **已连接的 GitHub repo**；页面同时引用 **GitHub pre-release terms**，并提到 **Data Residency** 变体 App（Marketplace listing）

证据包（本仓库内可复核）：`research/TASK-OPP-008C9F7D58/EVIDENCE.md`

## 目标
1. 产出一份**可决策**的竞品深潜简报，明确：能力边界、触发方式、依赖条件、关键限制（含预发布条款/数据驻留）。
2. 形成一份“**对标能力清单 + 机会/威胁判断**”，用于后续 roadmap/产品定位讨论。
3. 给出我们是否需要跟进的**推荐动作**（继续观察 / PoC / 内容/SEO 抢占 / 规划集成能力）。
4. 建立一个**轻量监控机制**，用于捕捉该 App/Changelog 的后续关键变更（范围、定价、条款、能力）。

## 不做项
- 不在本任务内开发或发布任何 Jira Marketplace App。
- 不在本任务内实现完整的 “coding agent for Jira” 端到端能力。
- 不进行需要登录/付费/绕过限制的抓取或逆向；仅使用公开信息与合规手段。
- 不对 GitHub/Atlassian 的预发布条款做法律结论性解读（仅做风险提示 + 需要法务确认的点）。

## 交付物
1. 《竞品能力说明书（Copilot for Jira）》：
   - 触发方式（assignee / @mention）
   - agent 拉取的上下文范围（以公开描述为准）
   - 输出/呈现方式（draft PR、PR updates、agent panel 等）
   - 依赖与限制（Jira Cloud、Rovo、GitHub 连接、preview 条款）
   - 可能的用户价值点与适用场景
2. 《对标矩阵 + 差异化机会》：把竞品能力拆成可对标条目，并标注我们可做/不可做/成本高/需要外部前置条件。
3. 《风险清单》：合规/隐私/条款/数据驻留/平台依赖（Rovo）相关风险点与待确认问题。
4. 《建议与下一步》：
   - 单一推荐结论（watchlist / PoC / 内容切入 / 其它）
   - 止损条件 + 下一步责任人
5. 《监控方案》：列出要监控的页面/信号、频率、触发阈值（不依赖登录页）。

## 验收标准
1. 竞品说明书中**明确写清**：触发方式、输出物、依赖项、限制/条款提示；并附上对应公开证据链接（并在本仓库 Evidence Pack 中可复核）。
2. 对标矩阵至少覆盖 **10 条**可对标能力条目，并对每条给出“我们是否要跟 / 什么时候跟 / 代价”的一句话判断。
3. 风险清单至少包含：预发布条款风险、数据驻留/合规风险、平台依赖（Rovo/Jira Cloud）的锁定风险，并标注“需要进一步确认”的问题列表。
4. 建议部分给出**单一推荐结论**，并写出止损条件与下一步责任人。
5. 监控方案可执行：列出信号源、更新频率、触发条件；不依赖需要登录的页面。

## 技术约束
- 只使用公开可访问的材料；引用需可复查。
- 监控优先使用官方 changelog / marketplace 页面（或其可用的 RSS/JSON 端点）；避免高频抓取。
- 输出物以 Markdown 文档为主，便于进入后续任务链（review → builder/tester）。

## 实施建议
1. 材料收集：以 GitHub Changelog + Marketplace listing 为主，补充 GitHub Docs/terms（公开可访问）用于“限制/条款/集成步骤”校准。
2. 能力拆解：用“触发-上下文-计划-执行-反馈”五段式框架整理。
3. 对标矩阵：从用户价值出发（节省时间/减少切换/减少遗漏）映射到能力条目。
4. 风险核对：列出需要法务/合规确认的问题（不在本任务内给结论）。
5. 监控落地：建立低频监控（例如每周）并设定变更阈值；出现重大变化再升级为专项。

# 竞品深潜简报：GitHub Copilot for Jira（public preview）

任务ID: TASK-OPP-008C9F7D58

证据包：`research/TASK-OPP-008C9F7D58/EVIDENCE.md`

> 说明：下述内容严格基于公开页面描述 + 已固化证据摘录；对未公开细节不做推断。

---

## 1) 竞品能力说明书（Copilot for Jira）

### 1.1 触发方式（Triggers）
- **Assignee 字段分配给 Copilot coding agent**（Jira issue 层）
- **在 issue comments 中 @mention Copilot** 触发

证据：Atlassian Marketplace listing（More details 段落） `research/TASK-OPP-008C9F7D58/EVIDENCE.md` §B

### 1.2 上下文获取（Context）
- Copilot 会分析 Jira issue 的 **description 和 comments** 以收集上下文。

证据：GitHub Changelog `research/TASK-OPP-008C9F7D58/EVIDENCE.md` §A；Marketplace release notes `§B`

### 1.3 输出与呈现（Outputs / Surface）
- 在 GitHub 仓库侧：创建 **AI-generated draft pull request** / “open a draft pull request”。
- 在 Jira 侧：通过 **agent panel** 发布进度更新；必要时在 Jira 提出澄清问题。
- Marketplace listing 文案强调：**See updates as pull requests are generated**。

证据：GitHub Changelog `§A`；Marketplace listing（More details + release notes）`§B`

### 1.4 依赖与限制（Dependencies / Constraints）
- **Jira Cloud + Rovo enabled**
- **GitHub Copilot coding agent enabled**（面向 GitHub users）
- **Connected GitHub repository**
- 设置路径（公开描述）：安装 Atlassian Marketplace app + GitHub Marketplace app；连接 GitHub org；配置 agent 可访问的仓库。

证据：GitHub Changelog `§A`；Marketplace listing（More details）`§B`

### 1.5 条款/合规提示（公开页面可见）
- Marketplace listing 明确提示：使用该集成“signals agreement to GitHub pre-release terms”，并且是“an instruction to GitHub to send your organization's data to Atlassian”。
- Marketplace listing 同时提到 **Data Residency** 变体 app（GHEC with Data Residency）。

证据：Marketplace listing（More details）`§B`；pre-release terms 页面已本地固化 `§D`

---

## 2) 对标矩阵（>=10 条）+ 我方判断

> 口径：每条都给出 “是否跟 / 什么时候跟 / 代价/前置条件”。当前基于公开信息，因此“能否做到同等体验”需要后续 PoC 或更深证据确认。

| # | 能力条目 | 竞品状态（公开描述） | 我方是否跟 / 何时 | 代价 / 前置条件 |
|---:|---|---|---|---|
| 1 | Jira 内入口：Assignee 触发 | 支持 | **可跟（中期）** | 需要 Jira 侧集成面/权限模型；可能依赖 Atlassian 平台（Forge/Connect/其它） |
| 2 | Jira 内入口：@mention 触发 | 支持 | **可跟（中期）** | 需要 comment 事件处理 + 防滥用策略 |
| 3 | 从 Jira issue 获取上下文（desc/comments） | 支持 | **应跟（短期 PoC）** | 上下文映射/脱敏/合规；需要 Jira API scope |
| 4 | 在 GitHub 创建 draft PR 作为主要交付物 | 支持 | **选择性跟（视我们主战场）** | 需要 GitHub App 权限、repo 写入边界、审计 |
| 5 | Jira 内 agent panel 进度更新 | 支持（描述） | **可跟（中期）** | 需要在 Jira UI 有“状态面板”承载；否则体验落差 |
| 6 | Jira 内澄清提问（异步互动） | 支持（描述） | **可跟（中期）** | 需要对话历史、权限与噪音控制 |
| 7 | 保留现有 PR review/approval rules | 支持（描述） | **必须跟（若做 PR 写入）** | 关键在不绕过分支保护/审批；实现为 draft PR + 正常 review |
| 8 | Repo 级访问控制（配置哪些 repo 可访问） | 支持（描述） | **必须跟（若做集成）** | 安全要求高；需要配置 UI 与默认 deny |
| 9 | 预发布/条款提示在安装/使用路径可见 | 支持（描述） | **建议跟（短期）** | 文案与 UX 设计；需要法务确认触发点 |
|10 | Data Residency 变体（GHEC with Data Residency） | 有变体 app | **先观察（中期评估）** | 涉及产品策略/架构/数据驻留能力，不是纯工程问题 |
|11 | “减少 Jira↔GitHub context switching”主价值叙事 | 明确强调 | **可跟（短期内容/定位）** | 更偏叙事与产品定位，不一定要先做完功能 |
|12 | 安装路径：Atlassian Marketplace + GitHub Marketplace 双安装 | 明确描述 | **先研究（短期）** | 涉及分发与企业治理；决定我们是否走同类渠道 |

---

## 3) 风险清单（含待确认问题）

### 3.1 风险（至少覆盖：预发布条款 / 数据驻留 / 平台依赖）
1. **预发布条款风险**：Marketplace listing 明确指向 GitHub pre-release terms；我们若跟进需审视条款对数据处理、责任边界、SLA 的影响（需要法务确认）。
2. **数据传输/共享风险**：Marketplace listing 明确写“instruction to GitHub to send your organization's data to Atlassian”；这意味着跨平台数据流与责任划分对企业用户敏感。
3. **数据驻留（Data Residency）风险**：存在 “GHEC with Data Residency” 变体 app，提示部分客户对驻留有硬要求；若我们没有对应能力，企业市场会受限。
4. **平台依赖锁定（Rovo + Jira Cloud）**：要求 Jira Cloud + Rovo；如果 Rovo 是强前置，我们很难在 Server/DC 或不启用 Rovo 的客户中复制同路径。
5. **权限与写入边界风险**：draft PR 需要 repo 写入；如权限过大或审计不清，企业会拒绝安装。
6. **信息过期风险（preview 快速变化）**：public preview 阶段页面/能力描述可能快速变化；结论需绑定获取时间并建立监控。

证据：EVIDENCE.md §A/§B/§D

### 3.2 待确认问题（需要补证据或跨团队确认）
- Rovo 的具体前置含义：必须购买/启用哪些能力？是否对客户分层？
- “agent panel” 在 Jira 的具体承载形态与可扩展性（是否对第三方开放同类 surface）。
- Copilot coding agent enabled 的具体门槛（账号/计划/权限）与 org-level 控制。
- Data Residency 变体 app 与普通版的差异：仅部署区域/数据处理路径不同，还是权限/功能也不同。

---

## 4) 建议与下一步（单一推荐结论 + 止损条件）

### 推荐结论（单一）
**推荐：进入 watchlist + 轻量 PoC 预研（不立项开发 Jira App）**。

理由：
- 公开材料已足以证明“Jira 内触发 coding agent→draft PR”正在产品化，且分发面是 Atlassian Marketplace（企业治理/安装入口）。
- 但关键的可复制性取决于 Rovo/平台开放度、权限/合规路径、以及真实体验细节；当前证据仍主要是发布口径。

### 止损条件
- 连续 60–90 天监控无明显新增（能力/定价/条款/安装量）且内部无明确跟进需求，则降级为纯观察归档。

### 下一步责任人
- **aic-dispatcher / captain**：决定是否拆出后续任务（如：Jira 侧入口形态对我们产品的缺口分析；或内容/SEO 抢占任务）。
- **aic-researcher**（若要求升级）：补充 Rovo/Agents in Jira 的公开 docs 证据与约束，避免误判前置条件。

---

## 5) 监控方案（可执行、无需登录）

### 信号源（公开可抓取）
1. GitHub Changelog（文章/JSON）：
   - 页面：https://github.blog/changelog/2026-03-05-github-copilot-coding-agent-for-jira-is-now-in-public-preview/
   - JSON（WP）：https://github.blog/wp-json/wp/v2/changelogs/94331
2. Atlassian Marketplace listing：
   - https://marketplace.atlassian.com/apps/1582455624/github-copilot-for-jira-by-github
   - 变体 app（Data Residency）：https://marketplace.atlassian.com/apps/3637796809/github-copilot-for-jira-ghec-with-data-residency
3. GitHub Docs（集成说明）：
   - https://docs.github.com/copilot/how-tos/use-copilot-agents/coding-agent/integrate-coding-agent-with-jira
4. GitHub pre-release terms（条款页面）：
   - https://docs.github.com/en/site-policy/github-terms/github-pre-release-license-terms

### 频率
- 默认每周 1 次（足够捕获 preview 阶段变更）。

### 触发条件（升级为专项评审）
- Marketplace listing：payment model/price、requirements、moreDetails/releaseNotes、install count、scopes 等出现变化。
- GitHub Changelog/Docs：新增限制条件、权限/合规说明变化。
- 出现 GA/正式发布信号，或从 preview 转商业化定价。

---

## 附：引用位置说明
- 所有关键事实的原文摘录与本地固化路径：见 `research/TASK-OPP-008C9F7D58/EVIDENCE.md`。

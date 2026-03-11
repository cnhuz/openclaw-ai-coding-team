# Spec

任务ID: TASK-OPP-4F03F7856B

## 背景
Atlassian 在 Jira Cloud 推出 “Agents in Jira”（open beta），并明确把“第三方 agent”纳入 Jira 的协作面（assignee / 评论 @mention / workflow transition 等）；同时 GitHub 发布 “GitHub Copilot coding agent for Jira” 公共预览：以 Jira issue 为触发，让 Copilot coding agent 在 GitHub 仓库创建 AI draft PR，并把更新回写到 Jira。

这意味着「Issue Tracker → Agent → PR」不再只是 IDE/Chat 的个人能力，而被平台化、可治理化，并通过 Atlassian Marketplace 进入“管理员安装 + 组织治理”的分发路径；对 OpenClaw 的影响在于：是否需要把 Jira/Atlassian 生态纳入“可触发/可回写/可审计”的 agent orchestration 入口，以及是否存在可复用的平台接口（例如 external MCP server / 统一 agent surface）。

一手证据基于 Atlassian 社区公告、Atlassian Support 文档、GitHub Changelog。

## 目标
1. 产出一份可用于内部决策的竞争情报/机会评估：明确 Agents in Jira 与 Copilot for Jira 的能力边界、触发方式、可见性/治理口径与依赖条件。
2. 提炼对 OpenClaw 影响：
   - 是否需要规划 Jira/Atlassian 生态集成能力（Jira issue → agent run → PR/评论/状态回写）。
   - 是否存在“管理员治理/合规安装/Marketplace 分发”的可行路径与约束。
3. 给出下一步建议：Watch / Continue Research / Start PoC 三档建议与触发条件。

## 不做项
- 不在本任务内实现任何 Jira 插件、Atlassian Marketplace App、或生产级集成。
- 不承诺与 Copilot/Atlassian 完全对标的功能覆盖。
- 不做付费定价与财务模型细化（仅列出需要验证点）。
- 不做需要登录企业 Jira/Atlassian 管理后台的实测（除非后续明确提供测试环境/账号并完成合规许可）。

## 用户路径 / 使用场景
### 场景 1：Jira 内把 work item 交给 agent（平台侧）
- 在 Jira work item 上，通过 Assignee 下拉把任务分配给 agent（Rovo agent 或第三方 agent）。
- 在评论区通过 @mention 召唤 agent 做总结/改写/草拟等。
- 在 workflow transition / board column 上配置触发：当任务状态变化或进入某列时自动触发 agent。

### 场景 2：Jira issue 驱动 Copilot coding agent 产出 PR（合作方集成）
- 管理员从 Atlassian Marketplace 安装 “GitHub Copilot for Jira” 应用，同时安装 GitHub app。
- 在配置中连接 GitHub organization，并配置允许 agent 访问的 repositories。
- 用户将 Jira issue 分配给 GitHub Copilot（或在评论中 @mention）开始；agent 读取 issue 描述与评论，独立实现变更，创建 draft PR，并在 Jira 的 agent panel 更新进展/提问澄清。

## 交付物
1. 《竞争情报简报》（一页可读 + 细节附录）：
   - Agents in Jira：支持的协作 surface、可见性/分享机制、治理口径（permissions / audit trails）。
   - GitHub Copilot for Jira：触发方式、输入/输出、依赖条件（Rovo、GitHub app、repo 配置）、回写形态。
2. 《对比表》：触发方式、输入来源、输出形态、可见性、授权/安装依赖、治理能力、可扩展性（第三方 agent 接入路径）。
3. 《对我们意味着什么》（决策建议）：Watch / Continue Research / Start PoC 三档建议与触发条件。
4. 《待验证清单》：针对 A4/A6 明确列出缺失证据与建议查证入口（文档/开发者资源/权限 scope）。

## 验收标准
（每条需在 spec/简报里给出“结论 + 引用来源（链接）+ 关键摘录”。对缺失项必须明确标注“不确定”并列出待验证入口。）

1. A1（第三方 agent 支持边界）有可复核结论与摘录：
   - 至少包含 Atlassian 社区公告中对“third-party agents”的明确表述。
   - 若提到 external MCP server，需要标明这是“可扩展接口线索”，并列出待查证的官方开发者文档入口。
2. A2（触发方式）覆盖并可引用：assign / @mention / workflow transition（至少三种），并说明可选的 board column 触发（若适用）。
3. A3（Copilot for Jira 输出与回写）覆盖并可引用：draft PR、Jira agent panel 更新、在 Jira 内澄清提问（ask clarifying questions）。
4. A4（权限与授权）必须显式标注现阶段缺失点，并列出下一步应查证的“scope/permission 粒度”问题清单（Atlassian app scopes、GitHub app 权限、repo 访问配置粒度、数据驻留等）。
5. A5（治理能力口径）必须可引用：平台侧“respect your permissions… audit trails”、以及“输出仅对触发者可见、需显式 share/publish 才能共享”的机制。
6. A6（开发者 API / webhook / 接入文档）必须明确：当前证据不足以证明第三方 agent 的公开开发者平台能力；需给出待验证入口与判断标准（是否提供：事件订阅、work item 读取/写回 API、可注册第三方 agent、审计/权限模型）。
7. 必须给出“决策建议：Watch / Continue Research / Start PoC”三档结论，并为每档写出触发条件（至少各 2 条）。

## 技术约束
- 默认仅使用公开网页/官方文档/Marketplace listing 作为证据来源。
- 不进行未经许可的登录/抓取/绕过权限的测试。
- 输出需要带时间戳（open beta / public preview 期间能力与政策可能变化）。

## 风险
- open beta/public preview 期间接口与政策变化快，结论需要标注日期与不确定性。
- Atlassian “Agents in Jira 平台能力”与 GitHub “Copilot for Jira 合作伙伴集成”容易被混淆，导致把特例当通用能力。
- A4/A6 缺少开发者文档/权限 scope 级证据时，容易高估可接入性与治理可行性。

## 实施建议
### 1) 先把 A1/A2/A3/A5 用一手证据“钉死”
- Atlassian 社区公告明确写到：
  - “Agents in Jira works with both Rovo agents built by Atlassian and third-party agents like the GitHub Copilot coding agent …”
  - 触发方式包括：assignee 下拉选择 agent、评论 @mention、在 workflows 中触发。
  - “Because agents operate inside Jira's existing structures, they respect your permissions, project configurations, workflows, and audit trails.”
  - “You stay in control: Agent work is only visible to you until you choose to share it with your team.”
  证据：
  - https://community.atlassian.com/forums/Jira-articles/Introducing-Agents-in-Jira-now-in-open-beta/ba-p/3194583

- Atlassian Support 文档补充了：
  - 4 种协作/触发方式（含 board column）。
  - 输出可见性与 share/publish 路径：“Only you can view… When you’re happy… you can share the output as a comment or attachment …”
  - 以及“agents built by third parties”的表述与 external MCP server 线索（需进一步验证其开发者可用性）。
  证据：
  - https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/

- GitHub Changelog 明确写到 Copilot for Jira 的行为：
  - “Analyze the Jira issue’s description and comments … implement changes and open a draft pull request … post updates in Jira via the agent panel … ask clarifying questions in Jira …”
  - Get started 包含“Install Atlassian Marketplace app + GitHub app；connect org；configure repos；assign issue 或在 comments @mention”。
  - Requirements：Jira Cloud + Rovo enabled；Copilot coding agent enabled；connected repo。
  证据：
  - https://github.blog/changelog/2026-03-05-github-copilot-coding-agent-for-jira-is-now-in-public-preview/

### 2) A4/A6：把“不确定性”转成可执行的查证清单
- A4 待验证（建议继续 research）：
  - Atlassian Marketplace app 的权限 scope（读/写哪些 work item 字段？评论/附件？是否能读取跨项目数据？）。
  - GitHub app 的权限（repo contents/PR/issues/actions/secrets）与组织管理员安装要求。
  - “Configure which repositories Copilot coding agent can access” 的粒度：repo 级？branch 级？environment 级？
  - 数据驻留 / 审计日志：哪些事件进入 audit？是否导出？
- A6 待验证（建议继续 research）：
  - “Agents in Jira supports third-party agents” 是否意味着：提供公开 API/平台能力让任意第三方注册 agent？还是当前仅支持特定合作伙伴（如 Copilot）？
  - external MCP server（Support 文档提及）是否为第三方 agent 的正式扩展机制？
  - 是否存在 developer docs：事件订阅（issue assigned / transitioned / commented）、回写（comment/attachment/status/link）、权限/审计模型。

### 3) 决策建议（给 reviewer 审议）
- Watch（默认）：
  - 触发条件：未来 30-60 天内未出现公开可用的第三方接入开发者文档（A6 仍无法证实）；或 Marketplace/治理信息仍停留在营销层。
  - 触发条件：我们缺少 Jira Cloud + Rovo 的可用测试环境，短期无法验证。
- Continue Research（推荐）：
  - 触发条件：能找到/确认 external MCP server 或第三方 agent 注册的正式文档入口，并能回答 A6 的“可构建性”。
  - 触发条件：能拿到 Copilot for Jira 的权限/安装/审计细节（A4），用于对标“合规安装”门槛。
- Start PoC（条件满足后再发起）：
  - 触发条件：确认 Jira 侧可稳定获得事件（assign/transition/comment）并可安全回写（comment/link/attachment），且权限模型可控。
  - 触发条件：内部明确有“Jira issue 驱动 agent run”的真实需求（例如：自动产出 PR、自动同步状态）且能提供测试项目。

——

## 一手证据摘录（用于 reviewer 快速复核）
> Atlassian Community（Agents in Jira）：
> “You can now assign work items to AI agents … mention them in comments … add agents to workflow transitions … Agents in Jira works with … third-party agents like the GitHub Copilot coding agent … Because agents operate inside Jira's existing structures, they respect your permissions … and audit trails … Agent work is only visible to you until you choose to share it …”

> GitHub Changelog（Copilot coding agent for Jira）：
> “You can now assign Jira issues to GitHub Copilot coding agent … get AI-generated draft pull requests … Analyze … description and comments … open a draft pull request … Post updates in Jira via the agent panel … Ask clarifying questions in Jira …”

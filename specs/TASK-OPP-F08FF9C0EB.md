# Spec

任务ID: TASK-OPP-F08FF9C0EB

## 背景
近期出现两条关键官方信号，表明 Jira 正在把「AI agent」变成一等协作对象，并开放第三方接入；同时 GitHub 也把 Copilot coding agent 直接嵌入 Jira 的指派/评论/工作流触发链路。

- Atlassian Support 明确：在 work item 上与 agent 协作支持 4 个 surfaces：
  1) Assignee field 指派 agent
  2) 评论区 @mention agent
  3) workflow transition 触发 agent action
  4) board column 触发 agent
  并明确可协作对象包含 Atlassian 自带 Rovo agents、站点内创建的 agents、以及第三方 agents；agent 输出默认仅触发者可见，触发者可选择以 comment/attachment 发布给团队。
- GitHub Docs 明确：GitHub Copilot for Jira 集成为「Forge app + GitHub app」组合；可通过 assign / mention / workflow transition 触发；前置条件包括 Jira Cloud 组织启用 AI（Rovo activated + beta AI features on）；并提示“Jira 上下文会进入 PR，若 repo public 则对所有人可见”。
- Atlassian Admin 支持：从 Atlassian Administration 添加 External MCP server（含 Custom MCP server），用于在 Rovo/Studio 等体验中提供 tools/skills；部分 MCP server 还会提供可直接访问的预置 Rovo agent profile。

对 OpenClaw 而言，这是一个清晰的生态入口候选：通过「Rovo agent + 外部 MCP server」把我们的能力变成 Jira 内可被指派/召唤/自动触发的 agent（至少覆盖一个 surface），并在 Jira work item 内形成闭环。

## 目标
在“可落地验证”的粒度上收敛 MVP 规格，并给出 go/no-go 条件，确保后续 builder 可以直接做 PoC：

1) **MVP 定义**：OpenClaw/自有 agent 以何种形态进入 Jira work item 协作面（至少 1 个 surface），形成闭环：触发 → 执行 → 回写产出 → 可分享。
2) **实现路径对比并给出推荐**：
   - 路径 A（推荐）：Rovo agent + External MCP server（Custom MCP server）
   - 路径 B（备选）：Forge/Jira App（或 webhook）+ 外部服务回写（尽量不依赖 Rovo，但需评估是否可达/是否会引入上架与权限复杂度）
3) **技术接口/鉴权/权限模型落到可实现清单**：
   - MCP server 与 OpenClaw 服务之间的最小接口（工具列表、输入/输出、状态查询）
   - Atlassian 侧安装/权限/可见性策略
   - OpenClaw 侧鉴权、审计与最小权限
4) **验证步骤与 DoD（Definition of Done）**：明确 PoC 成功的可操作验证流程与通过标准。

## 不做项
- 不在本任务内实现生产级 Marketplace 上架/计费/分发（只做 PoC 规格与落地验证口径）。
- 不承诺获得 Atlassian 合作伙伴/白名单资格，也不推进商务谈判。
- 不在本任务内实现四种 surfaces 全覆盖（assignee + @mention + workflow + board column）。
- 不做 Copilot 的代码质量/成功率系统评测（只关注接入机制、触发面与风险边界）。
- 不尝试绕过 Atlassian 的 Rovo/AI/beta 权限控制。
- 不引入“自动创建 PR”作为 MVP 必达目标（可作为后续阶段扩展点）。

## 用户路径 / 使用场景
目标用户：使用 Jira Cloud 的研发/产品团队，希望“在 Jira 内发起并跟踪 agent 执行”，减少 Jira ↔ 代码仓库 ↔ Chat 工具之间的往返。

MVP 优先场景（建议优先）——**评论 @mention 触发**：
1) 用户在 work item 评论中 `@OpenClaw` 并给出指令（如：生成任务拆解、补齐验收标准、生成变更说明、生成测试要点、或把 issue 变成可执行的 OpenClaw 任务）。
2) agent 读取 work item 上下文（summary/description + 必要的 labels/comments 等）→ 调用外部工具执行（OpenClaw backend）→ 在 Agents 区域输出结果。
3) 触发者选择将输出发布为 comment/attachment 给团队。

备选场景（第二优先）——**workflow transition 触发**：
- 当 work item 进入特定状态（如 Ready for Dev / Ready for Review）自动触发 agent；适合批量流程化。

说明可行性但不纳入 MVP：
- Assignee 指派 agent
- Board column 触发 agent

## 交付物
1) `specs/TASK-OPP-F08FF9C0EB.md`（本 spec，含接口/鉴权/PoC/DoD）
2) 《MVP PoC 实现清单（可交给 builder）》：
   - Jira/Atlassian 管理侧配置步骤
   - MCP server 最小实现要求（部署与工具定义）
   - OpenClaw 侧最小接口与鉴权策略
3) 《实现路径对比与推荐结论》：路径 A vs 路径 B 的 trade-offs 与 go/no-go
4) 《风险与合规默认策略》：尤其是“上下文进入外部系统/PR”的泄漏风险

## 验收标准
1) **Surfaces 事实与范围声明**：spec 明确引用官方材料确认 4 个协作面（assignee/@mention/workflow/board column），并明确本 MVP 选择的触发面（至少 1 个，默认 @mention）。
2) **推荐路线可执行**：spec 明确推荐「Rovo agent + External MCP server（Custom MCP server）」并说明为何（门槛/体验/可维护性），同时给出备选路线（Forge/webhook）与采用条件。
3) **最小闭环定义明确**：写清楚触发 → 执行 → 回写 → 发布给团队的闭环；每一步的成功判定可操作。
4) **最小接口定义到字段级**：至少定义 2 个工具/接口（例如 create/run 与 status/get），并写清输入字段（work item id/url、summary/description、用户指令、可选 repo 标识）与输出字段（结果文本/附件引用、run_id、状态）。
5) **鉴权/权限/审计策略明确**：
   - Jira/Atlassian 侧：需要哪些管理员动作与权限（至少包括添加 external MCP server、启用 agent surface）。
   - OpenClaw 侧：MCP server → OpenClaw API 的鉴权方式（MVP 允许 API key/短期 token，但必须可轮换/可撤销）；审计日志包含触发者、work item、时间、请求摘要、结果状态。
6) **前置条件与 go/no-go 条件可执行**：至少包含并明确验证方式：
   - Jira Cloud 组织是否必须 AI-enabled（Rovo activated）+ Beta AI features on（若必须，写清目标用户限制）
   - 是否可添加 Custom external MCP server（若不可用：no-go 或降级到备选路线）
7) **风险默认策略落地**：对“Jira 上下文进入外部系统/PR（public repo 可见）”给出默认策略（例如：默认仅允许私有 repo；public repo 强提示/默认禁用；最小化传输字段）。
8) **PoC 验证步骤与 DoD**：提供可在 Jira UI 里复现的验证步骤，并给出通过口径（见实施建议中的 DoD）。

## 技术约束
- Jira 侧：Jira Cloud；且依据 GitHub/Atlassian 官方材料，AI 能力与 agent 协作体验处于 beta/rolling out，可能需要：
  - 组织启用 AI（Rovo activated / AI-enabled app）
  - 开启 Beta AI features
  - 对 workflow transition 触发：要求 Rovo enabled 且相关权限授予
- Atlassian 管理侧：添加 External MCP server 需要在 Atlassian Administration → Connected apps 操作，并需同意免责声明；需要可用的 Custom MCP server 入口。
- 可见性：agent 输出默认仅触发者可见；团队共享需要显式发布为 comment/attachment。
- 数据与合规：work item 的上下文可能包含敏感信息；任何发送到外部服务（MCP/OpenClaw）必须最小化字段并可审计；对 public repo 的上下文扩散需要默认规避。

## 风险
- **用户群门槛风险**：Rovo/AI-enabled/beta features 可能仅覆盖特定 plan 或需要管理员开启，导致可达用户群缩小。
- **生态位/接入机制不确定**：第三方 agent 的正式接入是否存在伙伴/白名单门槛需要持续验证；若 Custom MCP server 不可用则需降级路线。
- **数据泄漏与合规**：Jira 上下文进入外部系统或 PR，尤其 public repo 可见性风险，需要默认禁用或强提示。
- **权限与审计**：跨 Jira/外部工具授权设计不当会扩大 blast radius；必须最小权限、可撤销、可审计。
- **产品预期管理**：用户可能期待“自动开 PR”，但 MVP 可能先落在文档/拆解类产出；需要在范围与文案中写清楚。

## 实施建议
### 路线选择
- **推荐（MVP）**：Rovo agent + External MCP server（Custom MCP server）
  - 目标：把 OpenClaw 能力包装为 MCP tools/skills，供 Rovo agent 在 Jira work item 中被 @mention 触发。
- **备选**：Forge/Jira App 或 webhook + 外部服务回写
  - 采用条件：若 Custom MCP server 不可用，或 Rovo/AI 门槛导致覆盖过窄；代价是权限模型、上架/审核、交互体验与维护成本可能更高。

### 最小技术接口（MVP 级）
为避免过度绑定具体实现细节，本节仅定义“builder 必须实现/对接的最小契约”。

1) MCP Server 暴露给 Atlassian/Rovo 的 tools（示例命名，可调整）：
- `openclaw.run_from_jira`
  - 输入（最小字段）：
    - `jira_site` / `issue_key` 或 `work_item_url`
    - `instruction`（用户在评论中的指令）
    - `context`: `{summary, description, labels?, comments_excerpt?}`（明确只取必要字段）
    - `visibility`: `private|publishable`（是否允许产出被发布为 comment/attachment）
  - 输出：`{run_id, status, result_preview}`
- `openclaw.get_run_status`
  - 输入：`{run_id}`
  - 输出：`{status, progress?, result?, artifacts?}`

2) MCP Server → OpenClaw Backend API（建议 HTTP）：
- `POST /api/jira/runs` 创建运行：返回 `run_id`
- `GET /api/runs/{run_id}` 查询状态与结果
- （可选）`POST /api/jira/publish` 将结果以“可发布文本/附件”形式结构化输出（由触发者在 Jira UI 里发布）

> 注：Atlassian External MCP server 的网络/协议/认证细节以 Atlassian 官方文档与实际控制台为准；PoC 阶段以“可在组织内添加并可被 Rovo agent 调用”为 DoD。

### 鉴权与权限（最小可行方案）
- Atlassian 侧：
  - 由组织管理员添加 External MCP server（Custom），并在工具配置中启用相关 tools。
  - 创建/选择 Rovo agent，并在 Surfaces → Work item 打开开关，使其出现在 work item 协作面。
- OpenClaw 侧：
  - MCP Server 调用 OpenClaw API 使用 **可轮换、可撤销** 的凭据（MVP 可用 API key / short-lived token）。
  - 审计日志至少记录：触发者（若能获得）、work item 标识、时间、调用的 tool、输入摘要（脱敏）、输出状态、错误原因。

### 最小 PoC 实现清单（给 builder）
**Atlassian/Jira 配置（管理员/站点侧）**
1) 确认 Jira Cloud 组织满足前置条件：AI-enabled（Rovo activated）+ Beta AI features on（如官方要求）。
2) Atlassian Administration → Apps → Connected apps → Add external MCP server → 选择 Custom MCP server → 完成添加。
3) 在工具配置中启用 MCP server 的 tools；若提供预置 agent profile，确认可访问。
4) Studio → Agents：创建/选择 Rovo agent；在 Configuration → Surfaces → 打开 Work item。

**MCP Server（我们提供/部署）**
5) 提供一个可被 Atlassian 添加的可用 MCP server（PoC 环境即可）：
   - 具备基础可用性（可访问、稳定返回、错误可诊断）
   - 至少暴露 2 个 tools：run + status
6) MCP server 内实现 OpenClaw API 的调用与错误处理（超时、重试、幂等 key 可选）。

**OpenClaw Backend（PoC 环境即可）**
7) 提供最小 API：创建 run / 查询 run；执行内容先聚焦“文档类产出”（如：拆解、验收、测试要点），不要求自动改代码。
8) 输出结构化：返回可直接粘贴为 Jira comment 的文本（或附件内容/链接）。
9) 落审计日志（本地文件或可查询存储，PoC 级即可）。

### 验证步骤与 DoD（PoC 通过标准）
**验证步骤**（建议按 @mention 场景）：
1) 在 Jira 创建一个 work item，填入 summary/description（包含明确需求）。
2) 在评论中输入：`@OpenClaw <指令>`（例如“生成验收标准+测试要点”）。
3) 在 work item 的 Agents 区域观察到 agent 开始工作并产生输出（progress 或最终结果）。
4) 触发者可将输出发布为 comment 或 attachment（分享给团队）。
5) 验证审计：在 OpenClaw/MCP 侧可查到本次触发的 run 记录（含时间、work item 标识、状态）。

**DoD**：
- 至少 1 个 work item 上完成 1 次 @mention 触发闭环：触发成功、产出可读、可发布给团队。
- PoC 的最小接口与鉴权机制可重复使用（非一次性手工拼接）。
- 对“public repo 上下文泄漏”有默认策略文档化（PoC 可以先通过限制/提示实现）。

## References / Evidence
- Atlassian Support: Collaborate on work items with AI agents
  - https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/
- Atlassian Administration: Add an external MCP server from Atlassian Administration
  - https://support.atlassian.com/organization-administration/docs/add-an-external-mcp-server-from-atlassian-administration/
- GitHub Docs: Integrate Copilot coding agent with Jira
  - https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/integrate-coding-agent-with-jira

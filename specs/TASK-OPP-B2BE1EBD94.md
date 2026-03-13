# Spec

任务ID: TASK-OPP-B2BE1EBD94

## 背景
用户在选择「在线计算器/报价/测算」类工具（calculator/quote builder）时，经常需要处理潜在客户的联系信息、预算、财务数据等敏感信息，因此“安全 / 隐私 / 合规”往往是选型门槛。

来自一手证据的共识（需在内容中分清 Verified / Claim / Unknown）：
- 第三方对比文（involve.me）把 calculator 的关键安全要点总结为：**传输/存储加密、访问控制、持续维护（更新/补丁）**，并提到 SSL 用于保护 client data。（见 Evidence）
- vendor 官方页面的安全与合规声明（如“encryption in transit and at rest”“SOC 2 / GDPR”）大多属于 marketing claim；若无法获得审计报告/证书/信任中心细节，应在表格中标注 Claim/Unknown。
- 部分 vendor 的 security/privacy 入口可能返回 404 或不可用，需要在表格中显式标注，并给出替代核验路径（trust center、DPA、privacy policy、sitemap/robots 定位等）。

## 目标
产出一个可发布、可复用的“calculator builder 安全选型”内容规格，用于后续内容生产/页面生成：
1) 固化页面信息架构（IA）。
2) 定义 vendor 对比表 schema（结构化复用），并规定证据标注规则（Verified / Claim / Unknown）。
3) 提供可复制的安全采购问卷（checklist），并给出验收口径。

## 不做项
- 不开发任何 calculator builder 产品功能；不做落地页上线、埋点、A/B、投放。
- 不提供法律意见或合规背书；仅整理公开材料与可验证证据。
- 不承诺拿到 SOC2/ISO 等原始报告；若只能获得 marketing 声明，必须标注为 Claim。

## 用户路径 / 使用场景
1) SMB/独立站运营：希望用计算器/报价表单收集线索，担心隐私与数据泄露。
2) B2B 增长/市场团队：需要团队协作、权限控制、导出与共享治理。
3) Agency/实施方：为客户做工具选型，需要可复用的安全问卷与对比表。
4) 合规敏感行业周边：更关注加密、访问控制、数据删除、审计与供应商管理。

## 交付物

### 1) 页面信息架构（IA）
- H1: Secure Calculator Builder: Security Checklist & Vendor Comparison
- Section A: 为什么 calculator builder 的安全重要（敏感数据类型、风险场景）
- Section B: 一页式“安全选型结论”
  - 适用人群 / 不适用人群
  - 采购建议（按风险等级/团队规模/合规要求）
- Section C: Security checklist（采购问卷，≥15 问，按类别分组）
- Section D: Vendor comparison table（结构化表格 + 证据链接）
- Section E: FAQ（加密、权限、数据保留与删除、DPA/subprocessor、日志等）
- Section F: 免责声明
  - 非法律意见
  - claim/unknown 的标注规则与读者核验建议

### 2) Vendor 对比表 schema（可用于 CSV/JSON/Markdown）
字段建议（每个维度都要有 status + evidence）：
- vendor_name
- pricing_anchor (optional)
- official_security_url
- official_privacy_url
- encryption_in_transit
- encryption_at_rest
- access_control_rbac
- sso_saml
- audit_logs
- data_retention_deletion
- dpa_available
- subprocessor_list
- compliance_claims（GDPR/SOC2/ISO 等，必须标注 Claim/Verified）
- maintenance_security_testing
- last_checked_at
- notes（如页面 404、只有 marketing claim、证据抓取路径等）

仓库内 schema 文件位置：
- `research/TASK-OPP-B2BE1EBD94/vendor_comparison_schema.json`

### 3) Security checklist（≥15问，建议 18~24 问）
按以下 6 类组织，每题包含：Why it matters / How to verify / Evidence types。
- 传输/存储加密
- 身份与访问控制
- 审计与监控
- 数据生命周期（收集/保留/删除/备份）
- 合规与法务（DPA、subprocessor、数据跨境等）
- 运营与维护（漏洞管理、更新频率、第三方测试）

## 验收标准
1) 覆盖至少 5 个 vendor（建议：involve.me、Outgrow、ConvertCalculator、Calconic、Calculoid），并对每个 vendor 提供：security/privacy 入口、对比表中至少 10 个维度的状态（Verified/Claim/Unknown）。
2) Checklist ≥ 15 个问题，且分组覆盖上述 6 类；每题都有“如何验证/需要什么证据”。
3) 对比维度表 ≥ 10 个维度，其中安全相关维度 ≥ 5 个；每个维度都有统一定义与取值规范。
4) 每条关键结论必须有证据链接（URL + 摘录定位 / 本地抓取路径）；若只有声明或页面不可达（404/错误），必须标注 Claim 或 Unknown。
5) Opportunity Card 中主要证据链接完成“可访问性 + 描述匹配”核对；发现错位/404 时，页面与表格中显式标注并给出替代证据路径。

## 技术约束
- 优先使用 researcher 提供的离线抓取 HTML/摘录，并在内容中保留来源路径。
- 输出需结构化、稳定命名，便于后续自动生成页面、对比表和问卷。
- 证据分级：Official doc > Legal/Policy page > Trust center > Third-party comparison；并要求标注 Verified/Claim/Unknown。

## 风险
- 多数 vendor 安全能力无法从公开页面严格验证，容易只有 marketing claim；需明确标注与读者核验建议。
- 各家页面 URL 不稳定/返回 404，导致对比表需要维护；需记录 last_checked_at。

## Evidence（指向本地固化路径）
（本 spec 不重复贴长摘录，引用以本地 evidence pack 为准。）
- involve.me blog: `.../2026-03-13_150826_involve_best_builders.html`（Calculator Security 段落）
- involve.me security page: `.../2026-03-13_150928_involve_security.html`
- Outgrow pricing: `.../2026-03-13_150826_outgrow_pricing.html`
- Outgrow privacy policy: `.../2026-03-13_151235_outgrow_privacy_policy.html`
- ConvertCalculator privacy: `.../2026-03-13_150928_convert_privacy.html`
- Calconic privacy: `.../2026-03-13_151235_calconic_privacy.html`
- Calculoid TOS: `.../2026-03-13_151455_calculoid_terms_of_service.html`
- vendor security fetch summary: `.../2026-03-13_150928_vendor_security_fetch.md`
- sitemap probes: `.../2026-03-13_151051_sitemaps.md`

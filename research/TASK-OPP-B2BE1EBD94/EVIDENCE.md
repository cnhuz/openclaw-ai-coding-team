# Evidence Pack — Calculator Builder security selection criteria (encrypted transmission/storage + access controls + maintenance)

任务ID: TASK-OPP-B2BE1EBD94

> 目的：固化公开一手材料的原文抓取与关键摘录定位，用于支撑 spec 的“对比表维度 + checklist + Verified/Claim/Unknown 标注”。
> 
> 说明：本 Evidence Pack **不输出法律意见**；若仅有 marketing 文案或页面不可访问，需在产出中标注 Claim/Unknown。

## 0. 证据目录结构
- raw captures:
  - `research/TASK-OPP-B2BE1EBD94/raw/`

## 1. involve.me blog：Calculator Security（通用安全选型要点）
- URL: https://www.involve.me/blog/best-online-calculator-builders
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/involve_best_builders.html`

关键摘录定位：
- 章节：`Calculator Security`
- 该段落表达了三个核心点：
  - encrypted protocols for all data transmission and storage
  - access controls
  - regular updates and proactive maintenance

摘录（原文片段，做了最小换行规整，不改语义）：
```text
So what should you be looking for in a secure online calculator? Well, it should use encrypted protocols for all data transmission and storage, ensuring that information remains confidential and protected from unauthorized access. Top calculator builders implement access controls, so only authorized personnel can view or manage calculator results and user submissions. And here's the thing, regular updates and proactive maintenance are also essential!
```

## 2. involve.me：security page（SOC 2 / GDPR 等声明）
- URL: https://www.involve.me/security
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/involve_security.html`

备注：页面包含“SOC 2 compliant / fully GDPR compliant”等表述（通常属于 claim；若无报告/证书链接则按 Claim 标注）。

## 3. Outgrow：pricing（加密 in transit / at rest + security testing 声明）
- URL: https://outgrow.co/pricing/
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/outgrow_pricing.html`

摘录（FAQ：Is my data secure?）：
```text
We use industry benchmarked encryption for all sensitive data in transit and at rest. We also regularly run internal and third party security screening and tests.
```

## 4. Outgrow：privacy policy（数据删除 + 备份保留窗口）
- URL: https://outgrow.co/privacy-policy/
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/outgrow_privacy_policy.html`

摘录（Data Deletion Policy）：
- 数据删除：支持在账户内删除/邮件请求，承诺 15 business days 内完成
- 备份：可能仍保留在 back-up files，定期删除

## 5. ConvertCalculator：privacy policy（隐私与安全相关条款线索）
- URL: https://www.convertcalculator.com/privacy
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/convert_privacy.html`

备注：该页面为长 HTML（Framer），可用于提取 SSO、日志、删除、保留等条款线索；但需谨慎确认摘录位置与上下文。

## 6. Calconic：privacy policy（删除权等条款线索）
- URL: https://www.calconic.com/privacy
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/calconic_privacy.html`

备注：可用于提取 GDPR/删除权（Art. 17）、访问控制/权限等条款线索；同样需确认具体段落上下文。

## 7. Calculoid：Terms of Service（SSL 加密通信声明）
- URL: https://www.calculoid.com/terms-of-service
- 本地固化:
  - `research/TASK-OPP-B2BE1EBD94/raw/calculoid_terms_of_service.html`

摘录：
```text
All communication within the Service is encrypted by SSL protocol.
```

## 8. 404/入口不可用核对（security/privacy 页面可达性）
- 汇总：`research/TASK-OPP-B2BE1EBD94/raw/vendor_security_fetch.md`

包含示例：
- outgrow /security 与 /privacy 入口抓取返回 404（需在表格中标注 Unknown，并改用可用的 pricing / privacy-policy 等替代入口）
- convertcalculator /security 返回 404

## 9. sitemap/robots（替代证据入口定位）
- `research/TASK-OPP-B2BE1EBD94/raw/sitemaps.md`

用于在 security 页面不可用时定位隐私/条款/DPA/cookies 等页面入口。

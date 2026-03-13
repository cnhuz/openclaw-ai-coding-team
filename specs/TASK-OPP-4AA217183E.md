# Spec

任务ID: TASK-OPP-4AA217183E

## 背景
当前运行环境出现“DNS sinkhole / 透明劫持”现象：多个公共站点域名被解析到 `198.18.0.0/15`（RFC 2544 基准测试专用地址段），从而触发 OpenClaw 的 SSRF 防护（private/internal/special-use IP）并阻断访问，导致研究/持续探索几乎不可用。

关键一手证据（来自研究日志）：
- Host 使用 `systemd-resolved`，上游 DNS 为 `192.168.1.1`；但即便显式 `dig @1.1.1.1` / `dig @8.8.8.8`，返回仍为 `198.18.*`，说明 **UDP/TCP 53 出站在网络层被透明重写/拦截**（非单纯本机 resolver 配置问题）。
- DoH（DNS over HTTPS）通过 `https://dns.google/resolve` 可返回真实公网 IP（如 `github.com -> 140.82.114.3`；`www.reddit.com -> 151.101.*`），说明 HTTPs 出站可用且可绕开 53 端口劫持。
- Reddit：即便 pin 到正确公网 IP，访问页面仍返回 `HTTP/2 403`（疑似 Reddit “network security”/反爬策略），但 RSS 仍可用。

证据路径：
- /home/ubuntu/.openclaw/workspace-aic-researcher/data/exec-logs/research-sprint/20260313-052619-dns-diagnosis.txt
- /home/ubuntu/.openclaw/workspace-aic-researcher/data/exec-logs/research-sprint/20260313-052756-doh-tests.txt
- /home/ubuntu/.openclaw/workspace-aic-researcher/data/exec-logs/research-sprint/20260313-052907-reddit-doh.txt
- /home/ubuntu/.openclaw/workspace-aic-researcher/data/exec-logs/research-sprint/20260313-052919-reddit-pin.txt

## 目标
1) **恢复公共站点抓取能力**：至少让 `web_fetch` 可以稳定获取以下站点的正文（不触发 SSRF block）：
   - github.com
   - news.ycombinator.com
   - hnrss.org
   - entropicthoughts.com
2) 在不牺牲安全边界的前提下，提供可回滚、可审计的修复路径：
   - 路线 A：优先修复网络/DNS 出口（使系统 DNS 返回真实公网 IP）
   - 路线 B：当无法改网络策略时，在 OpenClaw fetch 层提供 DoH 解析 + 连接一致性校验（必要时配合受控 egress proxy）
3) 形成可复制的验收与回归（含 SSRF 回归）。

## 不做项
- 不通过“全局关闭 SSRF private/internal/special-use IP 拦截”解决问题。
- 不引入“仅凭 hostname allowlist 就绕过 private/internal IP blocking”的方案（该机制不能绕过 IP 层拦截）。
- 不在本任务内保证 Reddit 正文页可访问（Reddit 可能存在独立的 403 封锁/反爬策略）；只保证 RSS 继续可用，并将正文页访问作为 best-effort/后续任务。
- 不在本任务内解决 Brave Search 402 的采购/续费决策；仅提供技术侧 fallback 说明。

## 用户路径 / 使用场景
- 研究验证：researcher 用 `web_fetch` 拉取博客/仓库/讨论串正文，沉淀证据。
- 持续探索：自动化抓取 HN/RSS/博客更新并摘要。
- 交付核验：planner/reviewer 能复现打开来源链接核对事实。

## 交付物
1) **修复方案与配置落地**（至少实现路线 B；路线 A 作为推荐/首选但可由环境 owner 执行）：
   - 路线 A（Infra/DNS 修复）：给出明确的网络侧修复建议与回滚步骤（例如：改上游 DNS/关闭透明劫持策略/放行 53 到指定递归 DNS 等）。
   - 路线 B（OpenClaw fallback）：
     - 在 `web_fetch`（以及依赖同一 HTTP 客户端的抓取链路）增加可配置的 **DoH resolver**；
     - 支持“DoH endpoint + 直连 IP pin + SNI/证书校验”以避免 DoH 域名本身再次被 sinkhole；
     - 对 DoH 返回的 A/AAAA 做 **public-only 校验**（继续拦截 RFC1918/loopback/link-local/198.18/15 等），防止 SSRF 退化；
     - 输出诊断信息（当前环境是否疑似 53 劫持、DoH 可用性）。
     - （可选增强）为 `browser` 提供受控 HTTP(S) proxy 模式（由 proxy 完成 DNS 解析），以便浏览器不依赖本机 DNS。
2) **验收脚本/命令清单**（可复制粘贴）：
   - `getent`/`dig` 对比：system resolver vs DoH 解析结果；
   - `web_fetch` 对关键站点的 smoke；
   - SSRF 回归：访问 `127.0.0.1`/RFC1918/`198.18/15` 仍被阻断。
3) 文档：
   - 说明两条路线的适用条件、风险、回滚；
   - 说明 DoH 提供商的可配置性与默认值（合规提醒）。

## 验收标准
- [DNS 劫持识别] 能在目标环境中复现并识别：系统 DNS（含 `dig @1.1.1.1/@8.8.8.8`）返回 `198.18/15`，而 DoH 返回真实公网 IP。（提供日志或命令输出）
- [web_fetch 恢复] 在“系统 DNS 仍返回 198.18/15”的情况下，启用路线 B 后：
  - `web_fetch https://github.com/` 成功（非 SSRF Block），并能提取到 HTML/文本正文；
  - `web_fetch https://news.ycombinator.com/` 成功；
  - `web_fetch https://hnrss.org/frontpage` 成功；
  - `web_fetch https://entropicthoughts.com/no-swe-bench-improvement` 成功。
- [安全不退化] 启用路线 B 后：
  - `web_fetch http://127.0.0.1/`、`http://10.0.0.1/`、`http://198.18.0.1/` 仍被 SSRF 拦截（阻断原因明确）；
  - 不允许通过 DoH/代理把内网地址伪装成公网域名绕过（至少：对最终连接 IP 做二次校验）。
- [可回滚] 关闭 DoH/proxy 配置后系统行为恢复原状；且提供明确回滚步骤。
- [Reddit 边界明确] `https://www.reddit.com/r/programming/.rss` 仍可访问；Reddit 正文页若仍 403 不影响本任务验收（但需在报告中记录现状）。

## 技术约束
- 环境层面疑似存在对 UDP/TCP 53 的透明代理/重写，导致直接 DNS（含 @1.1.1.1/@8.8.8.8）不可用。
- DoH 可行性：`dns.google` pinned 到 `8.8.8.8:443` 可建立 TLS 并返回正确解析；Cloudflare/Quad9 在该环境下出现连接异常（需在实现中允许 provider 可配置）。
- SSRF 防护必须保持：继续拦截 loopback/RFC1918/link-local/special-use（含 `198.18/15`）。
- `browser`（Chromium/Playwright）默认依赖系统 DNS；若不修系统 DNS，则需要 proxy/远端浏览器等机制才能恢复浏览能力。

## 风险
- 合规/隐私：默认使用第三方 DoH（如 Google）可能触发合规要求；需可配置与可禁用。
- 代理/转发方案若设计不当会扩大 SSRF 攻击面或引入数据外泄风险（必须做“解析与连接一致性校验 + 目的地 allowlist + 二次校验”）。
- 仅修复 `web_fetch` 但 `browser` 仍不可用，用户仍可能感知“不完全恢复”（需在验收与沟通中明确）。

## 实施建议
1) 优先推进路线 A（若环境 owner 可改网络策略）：
   - 目标：让系统 DNS 解析回公网 IP；修复后 `browser` 与全部工具自然恢复。
   - 回滚：恢复原 DNS/网关策略。
2) 并行实现路线 B 作为“环境不可控时的自救方案”（建议作为本任务主要交付）：
   - 在 `web_fetch` 增加 DoH resolver（默认关闭，显式启用）；
   - 内置 provider 列表但允许配置；默认优先 `dns.google`，并支持直连 IP pin（例如 `dns.google -> 8.8.8.8:443`）+ SNI；
   - 解析后对最终连接 IP 做 public-only 校验；若解析结果落入 special-use 则明确报错（不降级到不安全路径）。
   - 为 `browser` 提供可选 proxy 模式（若实现成本过高，可拆为后续子任务，但需在 reviewer 审议时确认范围）。
3) 单独记录 Reddit 403：
   - 作为后续“站点特定策略/登录/cookie/UA/速率限制”的任务候选，不与本任务混在一起扩大范围。

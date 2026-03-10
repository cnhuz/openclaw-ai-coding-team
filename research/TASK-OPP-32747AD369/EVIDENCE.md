# Evidence Pack — Agent Safehouse (macOS sandbox-exec)

任务ID: TASK-OPP-32747AD369

统一获取时间（UTC）: 2026-03-10T17:06:57Z

> 注意：本 Evidence Pack 仅固化一手原文摘录与关键策略片段；macOS 实测用例需要在 macOS 上执行（见文末模板）。

---

## A. 官网（Home）关键摘录

URL: https://agent-safehouse.dev/
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/site-text-snippets.txt（researcher 抓取文本）

摘录（原文片段）：
- “macOS-native sandboxing for local agents. ... enforced by the kernel.”
- “Safehouse denies write access outside your project directory. The kernel blocks the syscall before any file is touched.”
- 示例拒绝：`rm: ~/: Operation not permitted`
- “Agents inherit your full user permissions. Safehouse flips this — nothing is accessible unless explicitly granted.”
- “Download a single shell script... No build step, no dependencies — just Bash and macOS.”
- “Safehouse automatically grants read/write access to the selected workdir (git root by default) ... SSH keys, other repos, personal files — is denied by the kernel.”
- 示例敏感读取被拒绝：`cat: /Users/you/.ssh/id_ed25519: Operation not permitted`

---

## B. Policy Builder 页面关键摘录

URL: https://agent-safehouse.dev/policy-builder
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/site-text-snippets.txt

摘录（原文片段）：
- “Pick your coding agents, optional capabilities, and file system access in plain language.”
- “View policy modules on GitHub”
- “Start with baseline paths, then add the smallest extra grants you need.”
- HOME token： “is supported and expands to your HOME_DIR value.”
- “Advanced override (optional) ... appended last and can override earlier rules.”
- 命令形态：`sandbox-exec -f my-safehouse.sb -- <command>`

---

## C. Docs：Default Assumptions（Allowed vs Opt-in）关键摘录

URL: https://agent-safehouse.dev/docs/default-assumptions.html
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/docs-default-assumptions.html

摘录（原文片段/要点）：
- Allowed by Default:
  - “Selected workdir read/write (git root above CWD, otherwise CWD).”
  - “Network access (open by default).”
  - “SSH metadata read support (~/.ssh/config, ~/.ssh/known_hosts) for git-over-ssh workflows.”
- Not granted by default:
  - “SSH private keys under ~/.ssh.”
  - “Browser profile/cookie/session data.”

---

## D. Docs：Policy Architecture（composable / ordering）关键摘录

URL: https://agent-safehouse.dev/docs/policy-architecture.html
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/docs-policy-architecture.html

摘录（原文片段/要点）：
- “safehouse composes a final sandbox policy from modular profiles, then runs your command under sandbox-exec.”
- Policy assembly order（层级清单）：`00-base.sb` → `10-system-runtime.sb` → `20-network.sb` → `30-toolchains/*` → ... → `--append-profile`（loaded last）
- “Later rules win.”
- HOME placeholder token：`__SAFEHOUSE_REPLACE_ME_WITH_ABSOLUTE_HOME_DIR__`

---

## E. GitHub README 关键摘录

URL: https://github.com/eugene1g/agent-safehouse
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/README-full.md

摘录（原文片段/要点）：
- “Agent Safehouse uses sandbox-exec with composable policy profiles and a deny-first model.”
- “It is a hardening layer, not a perfect security boundary against a determined attacker.”

---

## F. LICENSE（Apache 2.0）

URL: https://raw.githubusercontent.com/eugene1g/agent-safehouse/main/LICENSE
获取时间(UTC): 2026-03-10T17:06:57Z
来源文件: raw/LICENSE

摘录：
- “Apache License Version 2.0, January 2004”

---

## G. 策略模块片段要点（deny-first + network open + HOME token）

来源文件: raw/profiles-snippets.txt（researcher 摘录）
获取时间(UTC): 2026-03-10T17:06:57Z

摘录（原文片段）：
- `00-base.sb`：
  - `(define HOME_DIR "__SAFEHOUSE_REPLACE_ME_WITH_ABSOLUTE_HOME_DIR__")`
  - `(deny default)`
- `20-network.sb`：
  - Threat-model note: “blocking exfiltration/C2 is explicitly NOT a goal...”
  - `(allow network*)`

---

## H. macOS 最小复现实验记录模板（待补齐）

需要在 macOS 上执行，并把完整记录补到本文件或另存 `research/TASK-OPP-32747AD369/macos-repro.md`。

1) 环境信息：
- macOS: `sw_vers` 输出
- shell: `echo $SHELL`
- sandbox-exec 路径：`which sandbox-exec`

2) 用例 1（deny-first）：
- 目标：在 safehouse/sandbox-exec 下读取 `~/.ssh/id_ed25519`（或其它敏感文件）应被拒绝（Operation not permitted）
- 命令：
- profile（或 safehouse 生成参数）：
- 预期：
- 实际：

3) 用例 2（explicit allow）：
- 目标：对指定目录显式授权后可读写（证明“默认拒绝 + 最小授权”闭环）
- 命令：
- profile（或 safehouse 生成参数）：
- 预期：
- 实际：

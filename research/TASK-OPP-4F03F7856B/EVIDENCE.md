# Evidence Pack — Atlassian Agents in Jira (open beta) + GitHub Copilot coding agent for Jira

任务ID: TASK-OPP-4F03F7856B

> 本 Evidence Pack 固化公开一手材料的原文摘录（或可复核的本地抓取文件），用于支撑 Spec 中的 A1~A6。

## A. Atlassian Community announcement（Introducing Agents in Jira, open beta）

- URL: https://community.atlassian.com/forums/Jira-articles/Introducing-Agents-in-Jira-now-in-open-beta/ba-p/3194583
- 本地固化:
  - `research/TASK-OPP-4F03F7856B/raw/atlassian_community_agents_in_jira.html`

建议 reviewer 重点核对的要点（A1/A2/A5）：
- third-party agents 明确表述（包含 GitHub Copilot coding agent 作为例子）
- 触发方式：assignee / 评论 @mention / workflow transitions
- 治理口径：respect permissions / audit trails
- 可见性：默认仅触发者可见，需主动 share 才共享

## B. Atlassian Support（Collaborate on work items with AI agents）

- URL: https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/
- 本地固化:
  - `research/TASK-OPP-4F03F7856B/raw/atlassian_support_collaborate_ai_agents.html`

建议 reviewer 重点核对的要点（A2/A5/A6线索）：
- 触发/协作方式补充（可能包含 board column 等）
- 输出可见性与 share/publish 的机制描述
- third-party agents 表述与 external MCP server 线索（是否为公开接入机制尚不确定）

## C. GitHub Changelog（Copilot coding agent for Jira public preview）

- URL: https://github.blog/changelog/2026-03-05-github-copilot-coding-agent-for-jira-is-now-in-public-preview/
- 本地固化:
  - `research/TASK-OPP-4F03F7856B/raw/github_changelog_94331.json`

建议 reviewer 重点核对的要点（A3 + 触发/依赖）：
- draft PR 产出
- Jira 内 agent panel 回写更新 + 追问澄清
- Get started / Requirements（Rovo、连接 repo 等）

## D. Atlassian Marketplace listing（GitHub Copilot for Jira）

- URL: https://marketplace.atlassian.com/apps/1582455624/github-copilot-for-jira-by-github
- 本地固化:
  - `research/TASK-OPP-4F03F7856B/raw/marketplace_github-copilot-for-jira.html`

建议 reviewer 重点核对的要点（依赖/条款/权限线索）：
- 触发方式：assignee field / @mention
- Requirements: Jira Cloud + Rovo / Copilot coding agent enabled / connected repo
- pre-release terms 提示 + “send org data to Atlassian”表述
- （若页面包含 embedded state）可能包含 Atlassian app scopes（A4 线索）

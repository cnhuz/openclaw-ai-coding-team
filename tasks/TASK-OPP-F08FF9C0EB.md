# Task Brief

任务ID: TASK-OPP-F08FF9C0EB
标题: GitHub Copilot coding agent enters Jira assignment flow via public preview and Jira open beta

## 当前结论
- 本任务目标是把已批准 spec（PoC/MVP 规格）**落盘进 repo**，以便后续 builder/tester 在同一代码仓库内引用、验证与迭代。
- 本任务不实现生产级 Jira 插件或真实 MCP server 服务；只固化 spec 与最小 PoC 验证口径。

## 最小实现范围
- 在仓库内新增/同步：`specs/TASK-OPP-F08FF9C0EB.md`（来自 planner workspace 的已批准 spec）。
- 在仓库内新增任务 brief：`tasks/TASK-OPP-F08FF9C0EB.md`，包含：目标、边界、验收点、证据链接。

## 关键边界
- 仅同步已批准 spec，不引入范围外实现。
- 证据引用保持公开链接；不做需要登录/绕过权限的实测。

## 相关证据（公开链接）
- Atlassian Support: Collaborate on work items with AI agents
  - https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/
- Atlassian Administration: Add an external MCP server from Atlassian Administration
  - https://support.atlassian.com/organization-administration/docs/add-an-external-mcp-server-from-atlassian-administration/
- GitHub Docs: Integrate Copilot coding agent with Jira
  - https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/integrate-coding-agent-with-jira
- GitHub Changelog: Copilot coding agent for Jira public preview
  - https://github.blog/changelog/2026-03-05-github-copilot-coding-agent-for-jira-is-now-in-public-preview/
- Atlassian Community announcement: Agents in Jira open beta
  - https://community.atlassian.com/forums/Jira-articles/Introducing-Agents-in-Jira-now-in-open-beta/ba-p/3194583
- Atlassian Marketplace: GitHub Copilot for Jira
  - https://marketplace.atlassian.com/apps/1582455624/github-copilot-for-jira-by-github

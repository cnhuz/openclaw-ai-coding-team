# Evidence Pack — GitHub Copilot for Jira (Atlassian Marketplace listing + GitHub Changelog)

任务ID: TASK-OPP-008C9F7D58

> 本 Evidence Pack 固化公开一手材料的原文摘录（或可复核的本地抓取文件），用于支撑 Spec 中的“触发方式/输出物/依赖项/条款提示/监控信号”。

## A. GitHub Changelog（WP JSON）

- URL: https://github.blog/changelog/2026-03-05-github-copilot-coding-agent-for-jira-is-now-in-public-preview
- 获取时间(UTC): 2026-03-11T06:10:00Z
- 本地固化:
  - `research/TASK-OPP-008C9F7D58/raw/github_changelog_94331.json`

要点（用于定位证据段落）：
- Assign Jira issues to GitHub Copilot coding agent and get AI-generated draft pull requests
- When assigned, Copilot analyzes issue description/comments, works independently, posts updates in Jira via agent panel, asks clarifying questions
- Get started steps include installing Atlassian Marketplace app and a GitHub Marketplace app; connect GitHub org; configure repo access; assign issue or @mention
- Requirements include Jira Cloud with Rovo enabled and Copilot coding agent enabled; connected GitHub repository

摘录（原文片段，可能做了 HTML tag 去除/换行规整，不改语义）：
```text
You can now assign Jira issues to GitHub Copilot coding agent, our asynchronous, autonomous agent, and get AI-generated draft pull requests created in your GitHub repository. When you assign a Jira issue to Copilot, it will: Analyze the Jira issue&rsquo;s description and comments to gather relevant context. Work independently to implement changes and open a draft pull request. Post updates in Jira via the agent panel. Ask clarifying questions in Jira when more information is needed. Key benefits Accelerate repetitive tasks like bug fixes and documentation updates. Reduce context switching between Jira and GitHub while keeping existing workflows. Follow your existing review and approval rules for every pull request Copilot creates. Get started Install the GitHub Copilot for Jira app from the Atlassian Marketplace. You will also install a GitHub app as part of your setup. Connect your GitHub organization during setup. Configure which repositories Copilot coding agent can access. Assign a Jira issue to GitHub Copilot (or @mention it in issue comments) to begin. Requirements Jira Cloud with Rovo enabled GitHub Copilot coding agent enabled A connected GitHub repository This integration
```

## B. Atlassian Marketplace listing（embedded state: moreDetails + releaseNotes）

- URL: https://marketplace.atlassian.com/apps/1582455624/github-copilot-for-jira-by-github
- 获取时间(UTC): 2026-03-11T04:12:00Z
- 本地固化:
  - `research/TASK-OPP-008C9F7D58/raw/atlassian_marketplace_copilot_for_jira.html`

要点（用于定位证据段落）：
- Trigger: assign Copilot via assignee field; or mention it in issue comments
- Shows updates as pull requests are generated; agent fetches relevant context from Jira issues
- Requirements: Jira Cloud with Rovo; Copilot coding agent enabled; connected GitHub repository
- Pre-release terms: using integration signals agreement to GitHub pre-release terms and instruction to GitHub to send organization data to Atlassian
- Data Residency variant app mentioned for GHEC with Data Residency

摘录（原文片段，可能做了 HTML tag 去除/换行规整，不改语义）：
```text
MORE DETAILS:
GitHub Copilot for Jira can help teams reduce cycle times and increase throughput by automating coding tasks:&nbsp;Assign GitHub Copilot coding agent via the assignee field&nbsp;Trigger the agent by mentioning it in issue comments&nbsp;See updates as pull requests are generated&nbsp;The agent fetches relevant context from the Jira issues&nbsp;Use GitHub Copilot for Jira (GHEC with Data Residency) for GitHub Data Residency customersRequirements:&nbsp;Jira Cloud instance with Rovo&nbsp;GitHub users with Copilot coding agent enabled&nbsp;Connected GitHub repository&nbsp;&nbsp;Use of this integration signals agreement to GitHub's pre-release terms and an instruction to GitHub to send your organization's data to Atlassian.&nbsp;Get started:&nbsp;Install the apps from the Atlassian and GitHub Marketplaces&nbsp;Connect your GitHub organization&nbsp;Configure which repositories the agent can access&nbsp;Start assigning issues to GitHub CopilotWe welcome your feedback.

RELEASE NOTES:
GitHub Copilot coding agent for Jira is now available in public preview. Assign Jira issues to GitHub Copilot coding agent, which will analyze your issue details and open a draft pull request in your GitHub repository—ready for your review.Features:Copilot analyzes Jira issue descriptions and comments to gather contextWorks independently to implement changes and open a draft pull requestPosts progress updates and asks clarifying questions directly in JiraKeeps your existing review and approval rules for every pull request
```

## C. GitHub Docs（Integrating Copilot coding agent with Jira）

- URL: https://docs.github.com/copilot/how-tos/use-copilot-agents/coding-agent/integrate-coding-agent-with-jira
- 获取时间(UTC): 2026-03-11T06:10:00Z
- 本地固化:
  - `research/TASK-OPP-008C9F7D58/raw/github_docs_integrate_jira.html`

要点（用于定位证据段落）：
- 页面用于进一步细化集成步骤/权限/限制（后续 reviewer 若要求补细节可从该抓取中引用）

## D. GitHub pre-release license terms

- URL: https://docs.github.com/en/site-policy/github-terms/github-pre-release-license-terms
- 获取时间(UTC): 2026-03-11T06:10:00Z
- 本地固化:
  - `research/TASK-OPP-008C9F7D58/raw/github_pre_release_terms.html`

要点（用于定位证据段落）：
- Spec 只做风险提示与“需法务确认点”，不在本任务内输出法律结论

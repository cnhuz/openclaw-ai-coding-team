# Task Brief

任务ID: TASK-OPP-008C9F7D58
标题: Atlassian Marketplace listing: Copilot for Jira triggers via assignee/@mention, fetches context, generates PR updates; notes Rovo + pre-release terms

## 当前结论
- 本任务已从研究/规划进入实现链，但本轮落地目标仍是**固化已批准的竞品深潜简报**（竞品能力说明书 + 对标矩阵 + 风险清单 + 建议与下一步 + 监控方案），而不是实现任何 Jira/GitHub 集成功能。
- 正式规格见：`specs/TASK-OPP-008C9F7D58.md`

## 最小实现范围
- 在仓库内新增/补齐正式 spec 文件，保证后续 reviewer / builder / tester / releaser 引用的是稳定 repo 路径。
- 补齐证据固化路径（Evidence Pack），确保“触发方式/输出物/依赖项/条款提示/监控信号”均有可复核来源。

## 关键边界
- 只使用公开可访问材料；不登录、不付费、不逆向。
- 不对 GitHub/Atlassian 的预发布条款做法律结论性解读（仅提示风险 + 列出需法务确认点）。
- 关注链路聚焦：**Jira issue 触发 → coding agent 拉取上下文 → draft PR/PR updates → Jira 内进度/问题交互**。

## 相关证据
- evidence pack: `research/TASK-OPP-008C9F7D58/EVIDENCE.md`
- raw captures: `research/TASK-OPP-008C9F7D58/raw/`
- planner spec: `/home/ubuntu/.openclaw/workspace-aic-planner/specs/TASK-OPP-008C9F7D58.md`
- dispatcher handoff: `/home/ubuntu/.openclaw/workspace-aic-captain/handoffs/2026-03-11/052814-TASK-OPP-008C9F7D58-to-aic-builder.md`

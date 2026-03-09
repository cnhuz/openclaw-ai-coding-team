# KPI Runtime Data

这个目录用于保存团队 KPI 引擎的规则和输出。

## 文件

- `rules.v1.json`：KPI 规则模板
- `daily/YYYY-MM-DD.json`：按天输出的 agent scorecards
- `weekly/YYYY-WXX.json`：按周输出的 agent scorecards

## 原则

- KPI 是**证据驱动的运行分数**，不是 HR 绩效系统
- 正式任务仍以 `tasks/registry.json` 为真相源
- handoff、exec-log、verification、release、reflection、proposal 作为评分证据
- 没有值班义务、没有持单、没有相关输入的角色，允许记为 `n_a`

## 说明

- 第一版以 captain 工作区为中心输出分数文件
- Daily / Weekly 的统计时区默认应与自动化保持一致，建议 `Asia/Shanghai`
- 自养导向会作为补充质量指标进入评分，重点关注研究机会和主线任务是否贴近“可持续供血”的长期目标

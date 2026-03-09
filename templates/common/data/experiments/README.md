# Experiments Runtime Data

这个目录保存**商业化实验真相源**。

它不是从任务盘里“推断出来的观察结果”，而是团队对收入、分发、定价、成本、自动化适配等实验的结构化记录。

## 文件

- `registry.json`：实验主记录

## 设计原则

- `tasks/registry.json` 仍然是正式交付任务真相源
- `data/research/opportunities.json` 仍然是机会池真相源
- `data/experiments/registry.json` 只负责记录：
  - 具体在验证什么商业假设
  - 当前实验状态
  - 目标指标与当前结果
  - 证据、止损条件、下一步

## 常见实验类型

- `revenue`：收入/付费实验
- `distribution`：分发/获客实验
- `pricing`：定价实验
- `cost`：单位成本实验
- `automation_fit`：自动化适配实验
- `influence`：开源影响力转化实验

## 常见状态

- `planned`
- `running`
- `validated`
- `invalidated`
- `inconclusive`
- `paused`
- `stopped`
- `archived`

## 推荐用法

- 由 `captain` 或当前 owner 为主线任务/机会创建实验记录
- 在实验推进中持续更新：
  - `current_value`
  - `result_summary`
  - `evidence`
  - `stop_decision`
  - `next_step`
- 在 `daily-reflection` / `reflect-release` 中回看：
  - 这次动作是否更接近自养目标
  - 哪个实验已经可以继续放大
  - 哪个实验应该止损

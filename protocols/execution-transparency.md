# Execution Transparency

所有自动化任务都必须留下可见痕迹。

## 原则

- 不允许 silent fail
- 不允许“跑了但没人知道结果”
- 不允许只说成功，不给执行摘要与证据

## 执行日志

每个 cron / 自动化任务执行后，都应写入：

- `data/exec-logs/<job-name>/YYYY-MM-DD-HHMM.md`

日志最低结构：

```md
# <Task Name> | YYYY-MM-DD HH:MM

## Metadata
- Trigger: <cron / manual / event>
- Model: <model_name>
- Timeout: <seconds>

## Steps
### Step 1
- Input:
- Output:
- Duration:
- Status:

## Key Decisions
- ...

## Result Summary
- ...
```

## 报告要求

- 自动化结果必须带 `updated` 文件路径或明确说明 `none`
- 异常必须带错误摘要
- 如已生成执行日志，汇报里要带日志路径

## 运行规则

- 阻塞式执行，避免后台 silent fail
- 不要在进程结束前读取目标输出
- 并发写共享文件时先拿锁
- 长报告要分块发送，不要依赖平台自动截断

## 巡检面板

建议维护 `data/dashboard.md`，集中展示：

- 最近一次备份状态
- 最近一次反思状态
- 最近一次记忆整理状态
- 连续失败任务
- 最近执行日志索引

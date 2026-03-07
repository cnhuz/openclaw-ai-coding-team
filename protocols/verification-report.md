# Verification Report

`aic-tester` 输出统一使用以下结构。

```md
# Verification Report

任务ID: <task_id>

## 测试范围
- 路径 1
- 路径 2

## 执行方式
- 命令：
- 环境：
- 数据前提：

## 结果
- ✅ 通过：
- ⚠️ 未覆盖：
- ❌ 失败：

## 关键证据
- 文件路径 / 日志 / 截图 / 命令输出

## 风险判断
<可发布 / 需返工 / 建议暂缓>

## 建议下一步
<交给 aic-releaser / 回到 aic-builder / 回到 aic-planner>
```

## 红线

- 未运行测试不能写“通过”
- 未验证项必须显式列出
- 对线上风险不允许模糊表述

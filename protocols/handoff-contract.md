# Handoff Contract

所有 agent 之间的交接都必须使用同一份合同，避免“说了很多但没人能接着干”。

若使用本仓库的运行态模板，推荐：

- handoff 文件落到 `handoffs/YYYY-MM-DD/`
- 通过 `python3 scripts/create_handoff.py` 生成
- 若 handoff 改变了任务 owner / state / next step，同步更新 `tasks/registry.json`

## 必填字段

```md
任务ID: <task_id>
当前阶段: <Intake / Researching / ...>
目标: <一句话目标>
交付物: <本阶段完成后应该留下什么>
证据: <文件路径 / 命令结果 / 链接 / 观察结果>
风险/阻塞: <没有则写 无>
下一负责人: <agent_id>
Breakpoint: <若任务未闭合，写恢复入口；已闭合则写 无>
```

## 角色补充字段

### `aic-researcher`

补充：

- 研究问题
- 证据来源
- 可选方向
- 建议优先级

### `aic-planner`

补充：

- 范围边界
- 不做项
- 验收标准
- 关键里程碑

### `aic-reviewer`

补充：

- 通过 / 打回
- 打回原因
- 需要补强的点

### `aic-builder`

补充：

- 代码改动摘要
- 涉及模块
- 潜在技术债

### `aic-tester`

补充：

- 测试范围
- 覆盖到的关键路径
- 未验证项

### `aic-releaser`

补充：

- 环境
- 变更窗口
- 回滚点
- 上线后观察项

### `aic-curator`

补充：

- 更新了哪些记忆文件
- 新增了哪些知识分类
- 删除 / 降级了哪些过时信息

### `aic-reflector`

补充：

- 今天 / 本周的主要问题
- 根因
- 建议修改的规则 / 流程

## 交接红线

- 不允许只写“已完成”
- 不允许缺少证据
- 不允许下一负责人为空
- 不允许把“猜测”写成“结论”
- 任务未闭合时，不允许缺少 `Breakpoint`

## 推荐运行入口

示例：

```bash
python3 scripts/create_handoff.py \
  --task-id TASK-001 \
  --current-stage Building \
  --goal "完成实现并转给测试" \
  --deliverable "实现 diff + 验证建议" \
  --evidence src/app.ts \
  --evidence data/exec-logs/build-sprint/2026-03-07-1500.md \
  --risk "无" \
  --next-owner aic-tester \
  --breakpoint "测试需先准备 fixture" \
  --from-owner aic-builder \
  --extra-field "代码改动摘要=完成核心实现，剩余验证由 tester 承接" \
  --sync-registry \
  --registry-path tasks/registry.json \
  --sync-state Verifying \
  --sync-owner aic-tester \
  --sync-next-step "执行回归并补 fixture" \
  --sync-append-evidence verification-plan.md
```

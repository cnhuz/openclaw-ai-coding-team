# AGENTS.md - aic-dispatcher Workspace Protocol

## Startup

1. 读 `SOUL.md`
2. 读 `IDENTITY.md`
3. 读 `USER.md`
4. 读 `MEMORY.md`
5. 优先用 `python3 scripts/query_task_registry.py --path tasks/registry.json --view dispatcher --format md` 查看活跃任务；需要阻塞项时加 `--blocked-only`
6. 若存在 `data/dashboard.md`，优先看最近看板摘要；若已过时，可运行 `python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --sessions-root ~/.openclaw/agents --research-root ~/.openclaw/workspace-aic-researcher/data/research --skills-root ~/.openclaw/workspace-aic-researcher/data/skills --output data/dashboard.md`
7. 再看最近交接与记忆摘要

## Memory Scope

- 重点记录：任务路由、依赖关系、阻塞类型、返工模式
- 执行链经验写入 `memory/knowledge/pat-*.md`
- 活跃任务摘要写入 `memory/projects/`
- 任务状态主记录不写在记忆里；记忆只写路由事件与调度判断

## Reflection Scope

- 反思是不是把任务派给了错误角色
- 反思任务是否长时间卡在某一阶段
- 跨角色低效交给 `aic-reflector`

## Collaboration

- 只可调用：`aic-researcher`, `aic-builder`, `aic-tester`, `aic-releaser`, `aic-curator`
- 每次派发都必须指定下一负责人
- 任务进入新 owner 或新阶段时，优先用 `python3 scripts/update_task_registry.py --path tasks/registry.json ...` 同步真相源
- 跨角色转手时，优先用 `python3 scripts/create_handoff.py --task-id ... --next-owner ... --sync-registry ...` 固化交接
- 汇总完成后交给 `aic-captain`

## Safety

- 不越权定义需求
- 不把“已派发”说成“已完成”

## Completion Rule

- 只有当任务真正推进到下一个明确状态，或完整交接出去，才算完成

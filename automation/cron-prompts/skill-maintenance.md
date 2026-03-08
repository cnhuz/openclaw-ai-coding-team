[cron:skill-maintenance]

# Skill Maintenance Prompt

你是 skill maintenance agent。

流程：

1. 先运行：
   - `python3 scripts/sync_skill_inventory.py --output data/skills/inventory.json --format md`
   - `python3 scripts/query_skill_catalog.py --path data/skills/catalog.json --status approved --review-status approved --format md`
2. 读取 `data/skills/policy.json`
   - 读取 `data/skills/dependency_policy.json`
3. 若存在可信、低风险、允许自动安装的候选：
   - 运行 `python3 scripts/install_skill_candidate.py --catalog data/skills/catalog.json --policy data/skills/policy.json --dependency-policy data/skills/dependency_policy.json --candidate-id ... --format md`
4. 安装后再次运行：
   - `python3 scripts/sync_skill_inventory.py --output data/skills/inventory.json --format md`
5. 将本轮结果写入 `data/exec-logs/skill-maintenance/`

规则：

- 只安装命中 policy 的候选
- 安装失败要留下清晰原因，不要静默吞掉
- 不要批量乱装；每轮最多处理 2 个候选
- 执行日志必须包含一行：`- Status: ok` 或 `- Status: no-op`

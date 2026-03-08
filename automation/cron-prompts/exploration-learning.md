[cron:exploration-learning]

# Exploration Learning Prompt

你是探索学习 agent。

流程：

1. 运行：
   - `python3 scripts/exploration_learning.py --topics data/research/topic_profiles.json --opportunities data/research/opportunities.json --stale-days 7 --format md`
   - `python3 scripts/tool_route_learning.py --site-profiles data/research/site_profiles.json --attempts-root data/research/tool_attempts --format md`
   - `python3 scripts/query_skill_catalog.py --path data/skills/catalog.json --status candidate --status approved --format md`
2. 读取更新后的：
   - `data/research/topic_profiles.json`
   - `data/research/site_profiles.json`
3. 总结：
   - 哪些 query expansion 被学出来了
   - 哪些 blocked terms 被识别出来了
   - 是否有 stale candidate 被降级为 `watchlist`
   - 哪些站点已经学出了更合适的工具路线
   - 是否出现需要被自动安装的低风险 skill 候选
4. 将本轮结果写入 `data/exec-logs/exploration-learning/`

规则：

- 学习是“调优探索系统”，不是直接创建正式任务
- 不要把短期噪音直接学成长期偏好
- 工具学习要关注“站点-工具-结果”三元关系，而不是只学关键词
- 执行日志必须包含一行：`- Status: ok`

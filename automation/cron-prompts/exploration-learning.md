[cron:exploration-learning]

# Exploration Learning Prompt

你是探索学习 agent。

流程：

1. 运行：
   - `python3 scripts/exploration_learning.py --topics data/research/topic_profiles.json --opportunities data/research/opportunities.json --stale-days 7 --format md`
2. 读取更新后的 `data/research/topic_profiles.json`
3. 总结：
   - 哪些 query expansion 被学出来了
   - 哪些 blocked terms 被识别出来了
   - 是否有 stale candidate 被降级为 `watchlist`
4. 将本轮结果写入 `data/exec-logs/exploration-learning/`

规则：

- 学习是“调优探索系统”，不是直接创建正式任务
- 不要把短期噪音直接学成长期偏好
- 执行日志必须包含一行：`- Status: ok`

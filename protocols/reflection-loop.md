# Reflection Loop

反思不是写作文，而是系统调优闭环。

## 标准闭环

1. **备份**：先完成 workspace 备份
2. **回放**：读取当日日志、任务真相源（优先 `tasks/registry.json`）、最近执行日志
3. **诊断**：识别误解、返工、低效、用户纠正、制度缺口
4. **沉淀**：写入 `memory/post-mortems.md`、`memory/knowledge/sys-*.md`、必要时更新 `MEMORY.md`
5. **调优提案**：提出需要修改的 `AGENTS.md`、`TOOLS.md`、cron prompt、技能治理或脚本草稿
6. **汇报**：输出问题、根因、改进建议、是否需要人工确认

## 角色分工

- `aic-reflector`：负责诊断与提出规则修正
- `aic-curator`：负责分类、提升、去重、落盘
- `aic-captain`：决定是否把规则修正纳入团队主制度
- `aic-dispatcher`：必要时把流程改造派发为正式任务

## 可调项目

- `AGENTS.md`：行为规则、启动顺序、边界
- `TOOLS.md`：本机入口、技能源、部署信息
- `automation/cron-prompts/`：定时任务 prompt 源文件
- `automation/CRON.md`：时间表与角色分工
- `tasks/registry.json` 或外部任务系统流程

## 反思红线

- 不为了“看起来进化了”而乱改规则
- 不自动安装未知来源或高风险新 skill
- 不随意改 `SOUL.md`
- 不把一次偶发波动提升成长期制度

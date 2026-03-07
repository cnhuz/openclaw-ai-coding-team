# Cron Prompt Sync Protocol

1. 编辑 `automation/cron-prompts/*.md`
2. 确认第一行是否是 `[cron:<job-name>]`
3. 检查是否引用了当前环境存在的脚本与路径
4. 将文件内容同步到真实 cron job 的 message/payload
5. 记录同步时间、目标 job、版本说明
6. 下一次只继续修改源文件，不直接改运行时

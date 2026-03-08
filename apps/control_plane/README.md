# Web Control Plane

这是一个面向本地 `~/.openclaw` 运行态的轻量 Web 管理台。

目标不是替代 OpenClaw，也不是发明新的状态系统，而是把这些真实数据源整合成一个更直观的界面：

- `workspace-aic-captain/tasks/registry.json`
- `workspace-aic-captain/handoffs/`
- `workspace-aic-captain/data/dashboard.md`
- `workspace-aic-researcher/data/research/opportunities.json`
- `openclaw status --deep --json`
- `openclaw cron list --json`

## 特点

- 默认只绑定 `127.0.0.1`
- 不引入额外 Web 框架，直接使用 Python 标准库
- 对 `openclaw status` / `openclaw cron list` 做短 TTL 缓存，降低页面卡顿
- `registry` 仍然是正式任务真相源
- `dashboard` 仍然只是观察面
- 当前提供两个安全操作：
  - 刷新 captain dashboard
  - 手动触发某个 cron job
- 第二版已补：
  - 任务详情页
  - 机会详情页
  - Handoff 列表页
  - 文件查看页
  - 任务 / 机会过滤
  - `ready_review` 机会手动晋升
- 第三版已补：
  - 任务时间线
  - 基于 `update_task_registry.py` 的任务状态流转表单
  - 任务详情页内联查看 handoff / exec log / evidence 演进
  - 运行告警面板
  - 全局事件流页面
  - 团队拓扑、中文角色卡与主线路径

## 启动

```bash
python3 apps/control_plane/server.py --openclaw-home ~/.openclaw --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

## 页面

- `/`：总览
- `/tasks`：正式任务控制面
- `/opportunities`：机会池
- `/agents`：团队拓扑与角色状态
- `/cron`：cron 管理
- `/logs`：最近执行日志
- `/handoffs`：最近交接
- `/events`：全局事件流
- `/task?id=...`：任务详情
- `/opportunity?id=...`：机会详情
- `/file?path=...`：文件查看

## 管理动作

- 刷新 captain dashboard
- 手动触发 cron
- 手动晋升 `ready_review` 机会
- 更新任务的 `state / owner / priority / next_step / blocker`

## API

- `/api/summary`
- `/api/tasks`
- `/api/task?id=...`
- `/api/opportunities`
- `/api/opportunity?id=...`
- `/api/agents`
- `/api/events`
- `/api/alerts`
- `/api/cron`

## 注意

- 这是本地管理台，不带鉴权，不应该直接暴露到公网。
- 如果要远程访问，建议挂到反向代理后，再加你自己的鉴权层。

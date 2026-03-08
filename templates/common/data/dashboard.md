# Automation Dashboard

> Auto-updated
> Recommended generator: `python3 scripts/refresh_dashboard.py --registry-path tasks/registry.json --handoffs-dir handoffs --exec-logs-dir data/exec-logs --research-root data/research --skills-root data/skills --output data/dashboard.md`
> Control plane: task state, owner, blocker, next step, and closeout truth come from `tasks/registry.json`
> Dashboard role: derived observer; it may lag behind until refreshed

## Summary

- task_registry:
- task_registry_updated_at:
- task_state_source:
- dashboard_role:
- team_entry_active:
- workflow_started:
- tasks_total:
- active_tasks:
- blocked_tasks:
- recent_handoffs:
- exec_jobs_tracked:
- missing_core_jobs:
- missing_optional_jobs:

## Backup Health

- workspace_root:
- git_initialized:
- origin_configured:
- remote_url:
- branch:
- gh_available:
- gh_auth_ok:
- github_repo:
- last_backup_status:
- pull_ok:
- push_ok:
- latest_backup_log:

## Exploration Summary

- sources_enabled:
- active_topics:
- signals_last_24h:
- signal_sources_last_24h:
- latest_signal_at:
- opportunities_watchlist:
- opportunities_candidate:
- opportunities_ready_review:
- opportunities_promoted:
- top_opportunity:

## Capability Loop

| Capability | Status | Signal | Evidence |
|------------|--------|--------|----------|

## Agent Activity

| Agent | Sessions | Last Activity |
|-------|----------|---------------|

## Task State Counts

| State | Count |
|-------|-------|

## Priority Tasks

| Task ID | State | Owner | Priority | Blocker | Next Step |
|---------|-------|-------|----------|---------|-----------|

## Build Queue

| Task ID | Priority | Owner | Blocker | Next Step |
|---------|----------|-------|---------|-----------|

## Top Opportunities

| Opportunity | Status | Score | Topics | Action |
|-------------|--------|-------|--------|--------|

## Recent Handoffs

| Time | Task | From | To | File |
|------|------|------|----|------|

## Recent Execution Logs

| Job | Latest Log | Status | Consecutive Failures |
|-----|------------|--------|----------------------|

## Optional Automation

- missing_optional_jobs:

## Anomalies

- 暂无

#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
CONFIG_PATH=""
AGENT_IDS="main"
CREATE_AGENT_ID=""
ROLE_NAME=""
ROLE_TITLE="核心助理"
MISSION="围绕用户目标稳定积累记忆、整理知识并执行每日反思。"
ACCEPTED_FROM="main"
ALLOW_CALL=""
HEARTBEAT_EVERY=""
TIMEZONE="Asia/Shanghai"
MEMORY_HOURLY_EVERY="1h"
DAILY_REFLECTION_CRON="10 0 * * *"
DAILY_CURATION_CRON="20 0 * * *"
MEMORY_WEEKLY_CRON="40 0 * * *"
SKIP_JOBS=0
SKIP_QMD_INIT=0
QMD_EMBED=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  ./setup/install-openclaw-core.sh [options]

Options:
  --openclaw-home <path>         Target OpenClaw home directory
  --config-path <path>           Path to openclaw.json
  --agent-ids <csv>              Existing agents to apply core profile to, default main
  --create-agent-id <id>         Create one new agent and apply core profile
  --role-name <name>             Role display name for created/applied agent
  --role-title <title>           Role title, default 核心助理
  --mission <text>               Mission text
  --accepted-from <csv>          Which agents may call the created agent, default main
  --allow-call <csv>             Which agents the created agent may call
  --heartbeat-every <dur>        Optional heartbeat interval for created agent
  --timezone <iana>              Timezone for installed cron jobs, default Asia/Shanghai
  --memory-hourly-every <dur>    Memory-hourly interval, default 1h
  --daily-reflection-cron <exp>  Daily reflection cron, default 10 0 * * *
  --daily-curation-cron <exp>    Daily curation cron, default 20 0 * * *
  --memory-weekly-cron <exp>     Weekly memory consolidation cron, default 40 0 * * *
  --skip-jobs                    Do not install core cron jobs
  --skip-qmd-init                Do not prime qmd
  --qmd-embed                    Run qmd embed during priming
  --dry-run                      Print planned actions without writing files
  -h, --help                     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --openclaw-home) OPENCLAW_HOME="$2"; shift 2 ;;
    --config-path) CONFIG_PATH="$2"; shift 2 ;;
    --agent-ids) AGENT_IDS="$2"; shift 2 ;;
    --create-agent-id) CREATE_AGENT_ID="$2"; shift 2 ;;
    --role-name) ROLE_NAME="$2"; shift 2 ;;
    --role-title) ROLE_TITLE="$2"; shift 2 ;;
    --mission) MISSION="$2"; shift 2 ;;
    --accepted-from) ACCEPTED_FROM="$2"; shift 2 ;;
    --allow-call) ALLOW_CALL="$2"; shift 2 ;;
    --heartbeat-every) HEARTBEAT_EVERY="$2"; shift 2 ;;
    --timezone) TIMEZONE="$2"; shift 2 ;;
    --memory-hourly-every) MEMORY_HOURLY_EVERY="$2"; shift 2 ;;
    --daily-reflection-cron) DAILY_REFLECTION_CRON="$2"; shift 2 ;;
    --daily-curation-cron) DAILY_CURATION_CRON="$2"; shift 2 ;;
    --memory-weekly-cron) MEMORY_WEEKLY_CRON="$2"; shift 2 ;;
    --skip-jobs) SKIP_JOBS=1; shift ;;
    --skip-qmd-init) SKIP_QMD_INIT=1; shift ;;
    --qmd-embed) QMD_EMBED=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$CONFIG_PATH" ]]; then
  CONFIG_PATH="$OPENCLAW_HOME/openclaw.json"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANAGER="$PACKAGE_ROOT/automation/scripts/manage_core_agent.py"

COMMON_ARGS=(
  --openclaw-home "$OPENCLAW_HOME"
  --config-path "$CONFIG_PATH"
  --timezone "$TIMEZONE"
  --memory-hourly-every "$MEMORY_HOURLY_EVERY"
  --daily-reflection-cron "$DAILY_REFLECTION_CRON"
  --daily-curation-cron "$DAILY_CURATION_CRON"
  --memory-weekly-cron "$MEMORY_WEEKLY_CRON"
)

if [[ "$SKIP_JOBS" -eq 1 ]]; then
  COMMON_ARGS+=(--skip-jobs)
fi
if [[ "$SKIP_QMD_INIT" -eq 1 ]]; then
  COMMON_ARGS+=(--skip-qmd-init)
fi
if [[ "$QMD_EMBED" -eq 1 ]]; then
  COMMON_ARGS+=(--qmd-embed)
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  COMMON_ARGS+=(--dry-run)
fi

IFS=',' read -r -a AGENT_LIST <<< "$AGENT_IDS"
for agent_id in "${AGENT_LIST[@]}"; do
  [[ -z "$agent_id" ]] && continue
  cmd=(python3 "$MANAGER" "${COMMON_ARGS[@]}" apply --agent-id "$agent_id")
  if [[ -n "$ROLE_NAME" ]]; then
    cmd+=(--role-name "$ROLE_NAME")
  fi
  if [[ -n "$ROLE_TITLE" ]]; then
    cmd+=(--role-title "$ROLE_TITLE")
  fi
  if [[ -n "$MISSION" ]]; then
    cmd+=(--mission "$MISSION")
  fi
  if [[ -n "$ACCEPTED_FROM" ]]; then
    cmd+=(--accepted-from "$ACCEPTED_FROM")
  fi
  if [[ -n "$ALLOW_CALL" ]]; then
    cmd+=(--allow-call "$ALLOW_CALL")
  fi
  "${cmd[@]}"
done

if [[ -n "$CREATE_AGENT_ID" ]]; then
  cmd=(python3 "$MANAGER" "${COMMON_ARGS[@]}" create --agent-id "$CREATE_AGENT_ID")
  if [[ -n "$ROLE_NAME" ]]; then
    cmd+=(--role-name "$ROLE_NAME")
  fi
  if [[ -n "$ROLE_TITLE" ]]; then
    cmd+=(--role-title "$ROLE_TITLE")
  fi
  if [[ -n "$MISSION" ]]; then
    cmd+=(--mission "$MISSION")
  fi
  if [[ -n "$ACCEPTED_FROM" ]]; then
    cmd+=(--accepted-from "$ACCEPTED_FROM")
  fi
  if [[ -n "$ALLOW_CALL" ]]; then
    cmd+=(--allow-call "$ALLOW_CALL")
  fi
  if [[ -n "$HEARTBEAT_EVERY" ]]; then
    cmd+=(--heartbeat-every "$HEARTBEAT_EVERY")
  fi
  "${cmd[@]}"
fi

echo
echo "OpenClaw core profile install result:"
echo "- openclaw_home: $OPENCLAW_HOME"
echo "- config_path: $CONFIG_PATH"
echo "- agent_ids: ${AGENT_IDS:-none}"
if [[ -n "$CREATE_AGENT_ID" ]]; then
  echo "- created_agent: $CREATE_AGENT_ID"
fi
echo "- timezone: $TIMEZONE"
echo "- memory-hourly: $MEMORY_HOURLY_EVERY"
echo "- daily-reflection: $DAILY_REFLECTION_CRON"
echo "- daily-curation: $DAILY_CURATION_CRON"
echo "- memory-weekly: $MEMORY_WEEKLY_CRON"
if [[ "$SKIP_JOBS" -eq 1 ]]; then
  echo "- cron jobs: skipped"
fi
if [[ "$SKIP_QMD_INIT" -eq 1 ]]; then
  echo "- qmd: skipped"
elif [[ "$QMD_EMBED" -eq 1 ]]; then
  echo "- qmd: primed with embed"
else
  echo "- qmd: primed (BM25/update only)"
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "- dry-run mode: no files or cron jobs were written"
fi

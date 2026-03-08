#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
TIMEZONE="Asia/Shanghai"
RESEARCH_EVERY="1h"
BUILD_EVERY="15m"
DASHBOARD_EVERY="10m"
AMBIENT_DISCOVERY_EVERY="30m"
TRIAGE_EVERY="45m"
DEEP_DIVE_EVERY="2h"
PROMOTION_EVERY="4h"
EXPLORATION_LEARNING_EVERY="6h"
PLANNER_INTAKE_EVERY="10m"
REVIEWER_GATE_EVERY="15m"
DISPATCH_APPROVED_EVERY="10m"
TESTER_GATE_EVERY="15m"
RELEASER_GATE_EVERY="20m"
REFLECT_RELEASE_EVERY="30m"
SKILL_SCOUT_EVERY="12h"
SKILL_MAINTENANCE_EVERY="24h"
MEMORY_HOURLY_EVERY="1h"
MEMORY_AGENTS="aic-captain,aic-planner,aic-dispatcher"
SKIP_IGNITE=0
DRY_RUN=0

TEAM_AGENTS=(
  aic-captain
  aic-planner
  aic-reviewer
  aic-dispatcher
  aic-researcher
  aic-builder
  aic-tester
  aic-releaser
  aic-curator
  aic-reflector
)

usage() {
  cat <<'EOF'
Usage:
  ./install-openclaw-automation.sh [options]

Options:
  --openclaw-home <path>       OpenClaw home directory
  --timezone <iana>            Cron timezone, default Asia/Shanghai
  --research-every <duration>  Research sprint interval, default 1h
  --build-every <duration>     Build sprint interval, default 15m
  --dashboard-every <duration> Dashboard refresh interval, default 10m
  --ambient-every <duration>   Ambient discovery interval, default 30m
  --triage-every <duration>    Signal triage interval, default 45m
  --deep-dive-every <duration> Opportunity deep-dive interval, default 2h
  --promotion-every <duration> Opportunity promotion interval, default 4h
  --explore-learn-every <dur>  Exploration learning interval, default 6h
  --planner-intake-every <dur> Planner intake interval, default 10m
  --reviewer-gate-every <dur>  Reviewer gate interval, default 15m
  --dispatch-approved-every <dur> Dispatch-approved interval, default 10m
  --tester-gate-every <dur>     Tester gate interval, default 15m
  --releaser-gate-every <dur>   Releaser gate interval, default 20m
  --reflect-release-every <dur> Release reflection interval, default 30m
  --skill-scout-every <dur>    Skill scout interval, default 12h
  --skill-maint-every <dur>    Skill maintenance interval, default 24h
  --memory-hourly-every <dur>  Memory-hourly interval, default 1h
  --memory-agents <csv>        Agents for memory-hourly / memory-weekly
  --skip-ignite                Skip the final system-event ignition
  --dry-run                    Print planned actions without writing cron jobs
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --openclaw-home)
      OPENCLAW_HOME="$2"
      shift 2
      ;;
    --timezone)
      TIMEZONE="$2"
      shift 2
      ;;
    --research-every)
      RESEARCH_EVERY="$2"
      shift 2
      ;;
    --build-every)
      BUILD_EVERY="$2"
      shift 2
      ;;
    --dashboard-every)
      DASHBOARD_EVERY="$2"
      shift 2
      ;;
    --ambient-every)
      AMBIENT_DISCOVERY_EVERY="$2"
      shift 2
      ;;
    --triage-every)
      TRIAGE_EVERY="$2"
      shift 2
      ;;
    --deep-dive-every)
      DEEP_DIVE_EVERY="$2"
      shift 2
      ;;
    --promotion-every)
      PROMOTION_EVERY="$2"
      shift 2
      ;;
    --explore-learn-every)
      EXPLORATION_LEARNING_EVERY="$2"
      shift 2
      ;;
    --planner-intake-every)
      PLANNER_INTAKE_EVERY="$2"
      shift 2
      ;;
    --reviewer-gate-every)
      REVIEWER_GATE_EVERY="$2"
      shift 2
      ;;
    --dispatch-approved-every)
      DISPATCH_APPROVED_EVERY="$2"
      shift 2
      ;;
    --tester-gate-every)
      TESTER_GATE_EVERY="$2"
      shift 2
      ;;
    --releaser-gate-every)
      RELEASER_GATE_EVERY="$2"
      shift 2
      ;;
    --reflect-release-every)
      REFLECT_RELEASE_EVERY="$2"
      shift 2
      ;;
    --skill-scout-every)
      SKILL_SCOUT_EVERY="$2"
      shift 2
      ;;
    --skill-maint-every)
      SKILL_MAINTENANCE_EVERY="$2"
      shift 2
      ;;
    --memory-hourly-every)
      MEMORY_HOURLY_EVERY="$2"
      shift 2
      ;;
    --memory-agents)
      MEMORY_AGENTS="$2"
      shift 2
      ;;
    --skip-ignite)
      SKIP_IGNITE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw command not found" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 command not found" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROMPT_ROOT="$PACKAGE_ROOT/automation/cron-prompts"

IFS=',' read -r -a MEMORY_AGENT_LIST <<< "$MEMORY_AGENTS"

render_prompt() {
  local prompt_path="$1"
  local agent_id="$2"
  python3 -c '
import sys
from pathlib import Path

path = Path(sys.argv[1])
agent_id = sys.argv[2]
timezone = sys.argv[3]
openclaw_home = sys.argv[4]
text = path.read_text(encoding="utf-8")
text = text.replace("__AGENT_ID__", agent_id).replace("__TIMEZONE__", timezone).replace("__OPENCLAW_HOME__", openclaw_home)
sys.stdout.write(text)
' "$prompt_path" "$agent_id" "$TIMEZONE" "$OPENCLAW_HOME"
}

job_ids_by_name() {
  local job_name="$1"
  openclaw cron list --json | python3 -c '
import json
import sys

target = sys.argv[1]
data = json.load(sys.stdin)
for job in data.get("jobs", []):
    if isinstance(job, dict) and job.get("name") == target and job.get("id") is not None:
        print(job["id"])
' "$job_name"
}

remove_existing_jobs() {
  local job_name="$1"
  local job_id
  while IFS= read -r job_id; do
    [[ -z "$job_id" ]] && continue
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "DRY-RUN remove cron job: $job_name ($job_id)"
      continue
    fi
    openclaw cron remove "$job_id" >/dev/null
  done < <(job_ids_by_name "$job_name")
}

install_interval_job() {
  local name="$1"
  local agent_id="$2"
  local every="$3"
  local prompt_path="$4"
  local description="$5"
  local message
  message="$(render_prompt "$prompt_path" "$agent_id")"

  remove_existing_jobs "$name"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN add interval cron: $name agent=$agent_id every=$every prompt=$prompt_path"
    return
  fi

  openclaw cron add \
    --name "$name" \
    --description "$description" \
    --agent "$agent_id" \
    --session isolated \
    --light-context \
    --no-deliver \
    --timeout-seconds 1800 \
    --every "$every" \
    --message "$message" \
    >/dev/null
}

install_daily_job() {
  local name="$1"
  local agent_id="$2"
  local cron_expr="$3"
  local prompt_path="$4"
  local description="$5"
  local message
  message="$(render_prompt "$prompt_path" "$agent_id")"

  remove_existing_jobs "$name"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN add daily cron: $name agent=$agent_id cron=$cron_expr tz=$TIMEZONE prompt=$prompt_path"
    return
  fi

  openclaw cron add \
    --name "$name" \
    --description "$description" \
    --agent "$agent_id" \
    --session isolated \
    --light-context \
    --no-deliver \
    --timeout-seconds 1800 \
    --cron "$cron_expr" \
    --tz "$TIMEZONE" \
    --exact \
    --message "$message" \
    >/dev/null
}

install_interval_job \
  "dashboard-refresh" \
  "aic-captain" \
  "$DASHBOARD_EVERY" \
  "$PROMPT_ROOT/dashboard-refresh.md" \
  "Refresh the captain dashboard and expose ignition gaps."

install_interval_job \
  "ambient-discovery" \
  "aic-researcher" \
  "$AMBIENT_DISCOVERY_EVERY" \
  "$PROMPT_ROOT/ambient-discovery.md" \
  "Continuously scan public channels for new external signals."

install_interval_job \
  "signal-triage" \
  "aic-researcher" \
  "$TRIAGE_EVERY" \
  "$PROMPT_ROOT/signal-triage.md" \
  "Aggregate discovery signals into ranked opportunities."

install_interval_job \
  "opportunity-deep-dive" \
  "aic-researcher" \
  "$DEEP_DIVE_EVERY" \
  "$PROMPT_ROOT/opportunity-deep-dive.md" \
  "Deep dive the highest-value research opportunity."

install_interval_job \
  "opportunity-promotion" \
  "aic-captain" \
  "$PROMOTION_EVERY" \
  "$PROMPT_ROOT/opportunity-promotion.md" \
  "Promote mature opportunities into formal tasks."

install_interval_job \
  "exploration-learning" \
  "aic-researcher" \
  "$EXPLORATION_LEARNING_EVERY" \
  "$PROMPT_ROOT/exploration-learning.md" \
  "Learn better query expansions and blocked terms from exploration outcomes."

install_interval_job \
  "planner-intake" \
  "aic-planner" \
  "$PLANNER_INTAKE_EVERY" \
  "$PROMPT_ROOT/planner-intake.md" \
  "Consume Intake tasks and turn them into concrete specs."

install_interval_job \
  "reviewer-gate" \
  "aic-reviewer" \
  "$REVIEWER_GATE_EVERY" \
  "$PROMPT_ROOT/reviewer-gate.md" \
  "Review planned specs and turn them into Approved or Replan."

install_interval_job \
  "dispatch-approved" \
  "aic-dispatcher" \
  "$DISPATCH_APPROVED_EVERY" \
  "$PROMPT_ROOT/dispatch-approved.md" \
  "Move approved tasks into the builder queue."

install_interval_job \
  "tester-gate" \
  "aic-tester" \
  "$TESTER_GATE_EVERY" \
  "$PROMPT_ROOT/tester-gate.md" \
  "Verify build outputs and route them to releaser or back to builder."

install_interval_job \
  "releaser-gate" \
  "aic-releaser" \
  "$RELEASER_GATE_EVERY" \
  "$PROMPT_ROOT/releaser-gate.md" \
  "Apply the release gate and hand released tasks to reflector."

install_interval_job \
  "reflect-release" \
  "aic-reflector" \
  "$REFLECT_RELEASE_EVERY" \
  "$PROMPT_ROOT/reflect-release.md" \
  "Close released tasks with reflection and knowledge proposals."

install_interval_job \
  "skill-scout" \
  "aic-researcher" \
  "$SKILL_SCOUT_EVERY" \
  "$PROMPT_ROOT/skill-scout.md" \
  "Discover skill candidates from capability gaps."

install_interval_job \
  "skill-maintenance" \
  "aic-researcher" \
  "$SKILL_MAINTENANCE_EVERY" \
  "$PROMPT_ROOT/skill-maintenance.md" \
  "Auto-install trusted low-risk skills."

install_interval_job \
  "research-sprint" \
  "aic-researcher" \
  "$RESEARCH_EVERY" \
  "$PROMPT_ROOT/research-sprint.md" \
  "Run one research sprint and push the task toward scope."

install_interval_job \
  "build-sprint" \
  "aic-builder" \
  "$BUILD_EVERY" \
  "$PROMPT_ROOT/build-sprint.md" \
  "Run one implementation sprint from the build queue."

install_daily_job \
  "daily-reflection" \
  "aic-reflector" \
  "10 0 * * *" \
  "$PROMPT_ROOT/daily-reflection.md" \
  "Run the daily reflection loop."

install_daily_job \
  "daily-curation" \
  "aic-curator" \
  "20 0 * * *" \
  "$PROMPT_ROOT/daily-curation.md" \
  "Run the daily curation loop."

for agent_id in "${TEAM_AGENTS[@]}"; do
  install_daily_job \
    "daily-backup-$agent_id" \
    "$agent_id" \
    "0 0 * * *" \
    "$PROMPT_ROOT/daily-backup.md" \
    "Run the daily backup check for $agent_id."
done

for agent_id in "${MEMORY_AGENT_LIST[@]}"; do
  [[ -z "$agent_id" ]] && continue
  install_interval_job \
    "memory-hourly-$agent_id" \
    "$agent_id" \
    "$MEMORY_HOURLY_EVERY" \
    "$PROMPT_ROOT/memory-hourly.md" \
    "Run memory-hourly sync for $agent_id."

  install_daily_job \
    "memory-weekly-$agent_id" \
    "$agent_id" \
    "40 0 * * *" \
    "$PROMPT_ROOT/memory-weekly.md" \
    "Run gated weekly memory consolidation for $agent_id."
done

if [[ "$SKIP_IGNITE" -eq 0 ]]; then
  ignite_text="Initialize coding-team control loop. Refresh dashboards, scan external public signals, triage opportunities, and if the latest session contains a concrete but untracked request, create an Intake task and route it toward planning. If mature opportunities or delivery-stage tasks already exist, advance them to the next explicit owner. Stay quiet if nothing actionable exists."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN system event: $ignite_text"
  else
    openclaw system event --mode now --text "$ignite_text" >/dev/null
  fi
fi

echo
echo "OpenClaw automation install result:"
echo "- openclaw_home: $OPENCLAW_HOME"
echo "- timezone: $TIMEZONE"
echo "- dashboard-refresh: every $DASHBOARD_EVERY"
echo "- ambient-discovery: every $AMBIENT_DISCOVERY_EVERY"
echo "- signal-triage: every $TRIAGE_EVERY"
echo "- opportunity-deep-dive: every $DEEP_DIVE_EVERY"
echo "- opportunity-promotion: every $PROMOTION_EVERY"
echo "- exploration-learning: every $EXPLORATION_LEARNING_EVERY"
echo "- planner-intake: every $PLANNER_INTAKE_EVERY"
echo "- reviewer-gate: every $REVIEWER_GATE_EVERY"
echo "- dispatch-approved: every $DISPATCH_APPROVED_EVERY"
echo "- tester-gate: every $TESTER_GATE_EVERY"
echo "- releaser-gate: every $RELEASER_GATE_EVERY"
echo "- reflect-release: every $REFLECT_RELEASE_EVERY"
echo "- skill-scout: every $SKILL_SCOUT_EVERY"
echo "- skill-maintenance: every $SKILL_MAINTENANCE_EVERY"
echo "- research-sprint: every $RESEARCH_EVERY"
echo "- build-sprint: every $BUILD_EVERY"
echo "- memory-hourly agents: ${MEMORY_AGENTS:-none} every $MEMORY_HOURLY_EVERY"
echo "- daily-backup agents: ${#TEAM_AGENTS[@]}"
echo "- daily-reflection: 00:10"
echo "- daily-curation: 00:20"
echo "- memory-weekly agents: ${MEMORY_AGENTS:-none} at 00:40"
if [[ "$SKIP_IGNITE" -eq 1 ]]; then
  echo "- ignition: skipped"
else
  echo "- ignition: system event triggered"
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "- dry-run mode: no cron jobs were written"
fi

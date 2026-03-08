#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
CONFIG_PATH=""
CAPTAIN_CHANNEL=""
CAPTAIN_ACCOUNT_ID=""
SKIP_GIT_INIT=0
SKIP_CONFIG_MERGE=0
SKIP_AUTOMATION=0
SKIP_IGNITE=0
SKIP_QMD_INIT=0
QMD_EMBED=0
DRY_RUN=0
AUTOMATION_TIMEZONE="Asia/Shanghai"

usage() {
  cat <<'EOF'
Usage:
  ./install-openclaw-team.sh [options]

Options:
  --openclaw-home <path>       Target OpenClaw home directory
  --config-path <path>         Path to openclaw.json
  --captain-channel <name>     Optional captain binding channel
  --captain-account-id <id>    Optional captain binding account id
  --skip-git-init              Skip per-workspace git init
  --skip-config-merge          Skip openclaw.json merge
  --skip-automation            Skip cron install and control-loop ignition
  --skip-ignite                Install automation but skip final system event
  --skip-qmd-init              Skip per-agent qmd memory priming
  --qmd-embed                  Run qmd embed during install priming
  --automation-timezone <iana> Timezone for installed cron jobs
  --dry-run                    Print result without writing files
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --openclaw-home)
      OPENCLAW_HOME="$2"
      shift 2
      ;;
    --config-path)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --captain-channel)
      CAPTAIN_CHANNEL="$2"
      shift 2
      ;;
    --captain-account-id)
      CAPTAIN_ACCOUNT_ID="$2"
      shift 2
      ;;
    --skip-git-init)
      SKIP_GIT_INIT=1
      shift
      ;;
    --skip-config-merge)
      SKIP_CONFIG_MERGE=1
      shift
      ;;
    --skip-automation)
      SKIP_AUTOMATION=1
      shift
      ;;
    --skip-ignite)
      SKIP_IGNITE=1
      shift
      ;;
    --skip-qmd-init)
      SKIP_QMD_INIT=1
      shift
      ;;
    --qmd-embed)
      QMD_EMBED=1
      shift
      ;;
    --automation-timezone)
      AUTOMATION_TIMEZONE="$2"
      shift 2
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

if [[ -z "$CONFIG_PATH" ]]; then
  CONFIG_PATH="$OPENCLAW_HOME/openclaw.json"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMMON_ROOT="$PACKAGE_ROOT/templates/common"
AGENTS_ROOT="$PACKAGE_ROOT/agents"
RUNTIME_SCRIPTS_ROOT="$PACKAGE_ROOT/automation/scripts"
SNIPPET_PATH="$PACKAGE_ROOT/config/openclaw.agents.snippet.json"
HOOKS_SNIPPET_PATH="$PACKAGE_ROOT/config/openclaw.hooks.snippet.json"
MEMORY_SNIPPET_PATH="$PACKAGE_ROOT/config/openclaw.memory.qmd.snippet.json"
DAILY_TEMPLATE_PATH="$COMMON_ROOT/memory/daily/TEMPLATE.md"
QMD_PRIMER_PATH="$SCRIPT_DIR/prime_qmd_memory.py"
MERGE_DEFAULTS_PATH="$SCRIPT_DIR/merge_runtime_defaults.py"

ensure_dir() {
  local path="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  mkdir -p "$path"
}

copy_dir_content() {
  local source="$1"
  local destination="$2"
  ensure_dir "$destination"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  cp -a "$source"/. "$destination"/
}

preserve_runtime_state() {
  local workspace_path="$1"
  local stash_dir="$2"
  local rel_path
  for rel_path in MEMORY.md memory tasks specs verification-reports release-notes data/dashboard.md data/exec-logs data/knowledge-proposals data/github-backup-policy.json data/execution-target.json data/research data/skills data/kpi handoffs; do
    if [[ ! -e "$workspace_path/$rel_path" ]]; then
      continue
    fi
    ensure_dir "$(dirname "$stash_dir/$rel_path")"
    cp -a "$workspace_path/$rel_path" "$stash_dir/$rel_path"
  done
}

restore_runtime_state() {
  local workspace_path="$1"
  local stash_dir="$2"
  local rel_path
  for rel_path in MEMORY.md memory tasks specs verification-reports release-notes data/dashboard.md data/exec-logs data/knowledge-proposals data/github-backup-policy.json data/execution-target.json data/research data/skills data/kpi handoffs; do
    if [[ ! -e "$stash_dir/$rel_path" ]]; then
      continue
    fi
    rm -rf "$workspace_path/$rel_path"
    ensure_dir "$(dirname "$workspace_path/$rel_path")"
    cp -a "$stash_dir/$rel_path" "$workspace_path/$rel_path"
  done
}

remove_runtime_bootstrap() {
  local workspace_path="$1"
  local bootstrap_path="$workspace_path/BOOTSTRAP.md"
  if [[ ! -f "$bootstrap_path" || "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  rm -f "$bootstrap_path"
}

ensure_core_exec_log_dirs() {
  local workspace_path="$1"
  local job_name
  for job_name in dashboard-refresh ambient-discovery signal-triage opportunity-deep-dive opportunity-promotion exploration-learning planner-intake reviewer-gate dispatch-approved tester-gate releaser-gate reflect-release daily-kpi weekly-kpi skill-scout skill-maintenance research-sprint build-sprint daily-reflection daily-curation daily-backup memory-hourly memory-weekly; do
    ensure_dir "$workspace_path/data/exec-logs/$job_name"
  done
}

ensure_runtime_defaults() {
  local workspace_path="$1"
  local rel_path
  for rel_path in data/execution-target.json data/research/site_profiles.json data/research/tool_profiles.json data/skills/README.md data/skills/policy.json data/skills/dependency_policy.json data/skills/catalog.json data/kpi/README.md data/kpi/rules.v1.json; do
    if [[ -e "$workspace_path/$rel_path" || ! -e "$COMMON_ROOT/$rel_path" ]]; then
      continue
    fi
    ensure_dir "$(dirname "$workspace_path/$rel_path")"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      cp -a "$COMMON_ROOT/$rel_path" "$workspace_path/$rel_path"
    fi
  done
  if [[ "$DRY_RUN" -eq 0 ]]; then
    python3 "$MERGE_DEFAULTS_PATH" --workspace "$workspace_path" --common-root "$COMMON_ROOT" >/dev/null
  fi
}

render_execution_target() {
  local workspace_path="$1"
  local template_path="$COMMON_ROOT/data/execution-target.json"
  local target_path="$workspace_path/data/execution-target.json"
  if [[ ! -f "$template_path" || "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  python3 - "$template_path" "$target_path" "$PACKAGE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
package_root = sys.argv[3]

template = json.loads(template_path.read_text(encoding="utf-8"))
if target_path.exists():
    target = json.loads(target_path.read_text(encoding="utf-8"))
else:
    target = template

if not isinstance(target, dict):
    target = template
if not isinstance(template, dict):
    raise SystemExit("execution target template must be an object")

def deep_fill(dst, src):
    for key, value in src.items():
        if key not in dst:
            dst[key] = value
            continue
        current = dst[key]
        if isinstance(current, dict) and isinstance(value, dict):
            deep_fill(current, value)
            continue
        if isinstance(current, list) and isinstance(value, list):
            for item in value:
                if item not in current:
                    current.append(item)

deep_fill(target, template)
target_obj = target.setdefault("target", {})
if target_obj.get("repo_root") in {None, "", "__PACKAGE_ROOT__"}:
    target_obj["repo_root"] = package_root
if target_obj.get("build_entrypoint") is None:
    target_obj["build_entrypoint"] = ""
if target_obj.get("release_command") is None:
    target_obj["release_command"] = ""
if target_obj.get("rollback_command") is None:
    target_obj["rollback_command"] = "git revert <commit>"
target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

append_if_missing() {
  local path="$1"
  local block="$2"
  local existing=""
  if [[ -f "$path" ]]; then
    existing="$(cat "$path")"
  fi
  if [[ "$existing" == *"$block"* ]]; then
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  if [[ -n "$existing" && "${existing: -1}" != $'\n' ]]; then
    printf '\n' >> "$path"
  fi
  printf '%s\n' "$block" >> "$path"
}

ensure_today_daily_log() {
  local workspace_path="$1"
  local today weekday daily_path content
  today="$(date +%F)"
  weekday="$(date +%A)"
  daily_path="$workspace_path/memory/$today.md"
  if [[ -f "$daily_path" || "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  content="$(cat "$DAILY_TEMPLATE_PATH")"
  content="${content//YYYY-MM-DD/$today}"
  content="${content//(Day)/($weekday)}"
  printf '%s\n' "$content" > "$daily_path"
}

update_tools_runtime_section() {
  local tools_path="$1"
  local block
  block=$'## Installed Runtime Paths\n\n- `scripts/scan_sessions_incremental.py`: enabled\n- `scripts/lockfile.py`: enabled\n- `scripts/weekly_gate.py`: enabled\n- `scripts/git_backup_health.py`: enabled\n- `scripts/validate_task_registry.py`: enabled\n- `scripts/query_task_registry.py`: enabled\n- `scripts/update_task_registry.py`: enabled\n- `scripts/create_handoff.py`: enabled\n- `scripts/refresh_dashboard.py`: enabled\n- `scripts/execution_target.py`: enabled\n- `scripts/worktree_lifecycle.py`: enabled\n- `scripts/verify_worktree_lifecycle.py`: enabled\n- `scripts/compute_agent_kpi.py`: enabled\n- `scripts/prepare_exploration_batch.py`: enabled\n- `scripts/prepare_site_frontier.py`: enabled\n- `scripts/prepare_planner_intake.py`: enabled\n- `scripts/prepare_builder_intake.py`: enabled\n- `scripts/prepare_tester_intake.py`: enabled\n- `scripts/prepare_releaser_intake.py`: enabled\n- `scripts/prepare_reflector_intake.py`: enabled\n- `scripts/validate_reflection_closeout.py`: enabled\n- `scripts/record_research_signal.py`: enabled\n- `scripts/triage_research_signals.py`: enabled\n- `scripts/query_research_opportunities.py`: enabled\n- `scripts/promote_research_opportunity.py`: enabled\n- `scripts/bridge_ready_review_opportunity.py`: enabled\n- `scripts/bridge_approved_task.py`: enabled\n- `scripts/exploration_learning.py`: enabled\n- `scripts/upsert_site_profile.py`: enabled\n- `scripts/plan_tool_route.py`: enabled\n- `scripts/record_tool_attempt.py`: enabled\n- `scripts/tool_route_learning.py`: enabled\n- `scripts/sync_skill_inventory.py`: enabled\n- `scripts/register_skill_candidate.py`: enabled\n- `scripts/query_skill_catalog.py`: enabled\n- `scripts/bootstrap_skill_dependency.py`: enabled\n- `scripts/install_skill_candidate.py`: enabled\n- `AGENTS.md`: merged common + role rules\n- `BOOT.md`: optional `boot-md` startup checklist'
  append_if_missing "$tools_path" "$block"
}

merge_role_agents() {
  local workspace_path="$1"
  local role_agents_path="$2"
  local agent_id="$3"
  local agents_path="$workspace_path/AGENTS.md"
  local start_marker="<!-- OPENCLAW-ROLE:${agent_id}:BEGIN -->"
  local end_marker="<!-- OPENCLAW-ROLE:${agent_id}:END -->"

  if [[ ! -f "$role_agents_path" || ! -f "$agents_path" ]]; then
    return
  fi

  if grep -Fq "$start_marker" "$agents_path"; then
    return
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi

  {
    printf '\n%s\n\n' "$start_marker"
    cat "$role_agents_path"
    printf '\n%s\n' "$end_marker"
  } >> "$agents_path"
}

merge_memory_seed() {
  local workspace_path="$1"
  local memory_path="$workspace_path/MEMORY.md"
  local seed_path="$workspace_path/MEMORY.seed.md"
  if [[ ! -f "$seed_path" ]]; then
    return
  fi
  local seed
  seed="$(cat "$seed_path")"
  if [[ -z "${seed//[$'\t\r\n ']}" ]]; then
    return
  fi
  append_if_missing "$memory_path" "$seed"
}

ensure_git_repo() {
  local workspace_path="$1"
  local commit_message="$2"
  if [[ "$SKIP_GIT_INIT" -eq 1 ]]; then
    return
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "WARN: git not found; skipping Git init for $workspace_path" >&2
    return
  fi
  if [[ ! -d "$workspace_path/.git" && "$DRY_RUN" -eq 0 ]]; then
    git -C "$workspace_path" init >/dev/null
    git -C "$workspace_path" branch -M main >/dev/null
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  local user_name user_email
  user_name="$(git -C "$workspace_path" config user.name || true)"
  user_email="$(git -C "$workspace_path" config user.email || true)"
  if [[ -z "$user_name" || -z "$user_email" ]]; then
    echo "WARN: git user.name / user.email is missing; repo initialized but initial commit skipped for $workspace_path" >&2
    return
  fi
  git -C "$workspace_path" add . >/dev/null
  if [[ -n "$(git -C "$workspace_path" status --short)" ]]; then
    git -C "$workspace_path" commit -m "$commit_message" >/dev/null
  fi
}

merge_openclaw_config() {
  local target_config_path="$1"
  local resolved_openclaw_home="$2"
  local snippet_path="$3"
  local hooks_snippet_path="$4"
  local memory_snippet_path="$5"
  local channel="$6"
  local account_id="$7"

  if [[ "$DRY_RUN" -eq 0 && -f "$target_config_path" ]]; then
    cp "$target_config_path" "$target_config_path.$(date +%Y%m%d-%H%M%S).bak"
  fi

  OPENCLAW_TARGET_CONFIG="$target_config_path" \
  OPENCLAW_HOME_RESOLVED="$resolved_openclaw_home" \
  OPENCLAW_SNIPPET_PATH="$snippet_path" \
  OPENCLAW_HOOKS_SNIPPET_PATH="$hooks_snippet_path" \
  OPENCLAW_MEMORY_SNIPPET_PATH="$memory_snippet_path" \
  OPENCLAW_CAPTAIN_CHANNEL="$channel" \
  OPENCLAW_CAPTAIN_ACCOUNT_ID="$account_id" \
  OPENCLAW_DRY_RUN="$DRY_RUN" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

target_config_path = Path(os.environ["OPENCLAW_TARGET_CONFIG"])
snippet_path = Path(os.environ["OPENCLAW_SNIPPET_PATH"])
hooks_snippet_path = Path(os.environ["OPENCLAW_HOOKS_SNIPPET_PATH"])
memory_snippet_path = Path(os.environ["OPENCLAW_MEMORY_SNIPPET_PATH"])
openclaw_home = os.environ["OPENCLAW_HOME_RESOLVED"]
channel = os.environ.get("OPENCLAW_CAPTAIN_CHANNEL", "")
account_id = os.environ.get("OPENCLAW_CAPTAIN_ACCOUNT_ID", "")
dry_run = os.environ.get("OPENCLAW_DRY_RUN", "0") == "1"

snippet = json.loads(snippet_path.read_text(encoding="utf-8"))
hooks_snippet = json.loads(hooks_snippet_path.read_text(encoding="utf-8")) if hooks_snippet_path.exists() else {}
memory_snippet = json.loads(memory_snippet_path.read_text(encoding="utf-8")) if memory_snippet_path.exists() else {}
if target_config_path.exists():
    config = json.loads(target_config_path.read_text(encoding="utf-8"))
else:
    config = {}

def deep_merge(target, source):
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            deep_merge(existing, value)
        else:
            target[key] = value

agents = config.setdefault("agents", {})
defaults = agents.setdefault("defaults", {})
snippet_defaults = snippet["agents"].get("defaults", {})
for key, value in snippet_defaults.items():
    if key == "subagents":
        defaults.setdefault("subagents", {})
        defaults["subagents"]["maxConcurrent"] = value["maxConcurrent"]
    else:
        defaults[key] = value

agent_list = list(agents.get("list", []))
for agent_def in snippet["agents"]["list"]:
    new_agent = json.loads(json.dumps(agent_def))
    new_agent["workspace"] = str(Path(openclaw_home) / f"workspace-{new_agent['id']}")
    new_agent["agentDir"] = str(Path(openclaw_home) / "agents" / new_agent["id"])
    replaced = False
    for index, existing in enumerate(agent_list):
        if existing.get("id") == new_agent["id"]:
            agent_list[index] = new_agent
            replaced = True
            break
    if not replaced:
        agent_list.append(new_agent)
agents["list"] = agent_list

if channel and account_id:
    bindings = list(config.get("bindings", []))
    new_binding = {
        "agentId": "aic-captain",
        "match": {
            "channel": channel,
            "accountId": account_id,
        },
    }
    replaced = False
    for index, existing in enumerate(bindings):
        if existing.get("agentId") == "aic-captain":
            bindings[index] = new_binding
            replaced = True
            break
    if not replaced:
        bindings.append(new_binding)
    config["bindings"] = bindings

memory_root = memory_snippet.get("memory")
if isinstance(memory_root, dict):
    existing_memory = config.get("memory")
    if not isinstance(existing_memory, dict):
        existing_memory = {}
    deep_merge(existing_memory, memory_root)
    config["memory"] = existing_memory

hook_root = hooks_snippet.get("hooks", {})
if hook_root:
    config_hooks = config.setdefault("hooks", {})
    for scope_name, scope_value in hook_root.items():
        target_scope = config_hooks.setdefault(scope_name, {})
        if "enabled" in scope_value:
            target_scope["enabled"] = scope_value["enabled"]
        existing_entries = target_scope.get("entries", {})
        if not isinstance(existing_entries, dict):
            if isinstance(existing_entries, list):
                converted_entries = {}
                for entry in existing_entries:
                    if isinstance(entry, dict) and entry.get("hookName"):
                        converted_entries[entry["hookName"]] = {
                            key: value for key, value in entry.items() if key != "hookName"
                        } or {"enabled": True}
                existing_entries = converted_entries
            else:
                existing_entries = {}
        for hook_name, hook_config in scope_value.get("entries", {}).items():
            existing_entries[hook_name] = hook_config
        if existing_entries:
            target_scope["entries"] = existing_entries

if not dry_run:
    target_config_path.parent.mkdir(parents=True, exist_ok=True)
    target_config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
PY
}

prime_qmd_memory() {
  local agent_id="$1"
  local workspace_path="$2"
  local runtime_agent_dir="$3"
  if [[ "$SKIP_QMD_INIT" -eq 1 ]]; then
    return
  fi
  if ! command -v qmd >/dev/null 2>&1; then
    echo "WARN: qmd not found; qmd memory priming skipped for $agent_id" >&2
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    local dry_run_cmd=(python3 "$QMD_PRIMER_PATH" --agent-id "$agent_id" --workspace "$workspace_path" --agent-dir "$runtime_agent_dir" --dry-run)
    if [[ "$QMD_EMBED" -eq 1 ]]; then
      dry_run_cmd+=(--embed)
    fi
    "${dry_run_cmd[@]}" >/dev/null
    return
  fi
  local cmd=(python3 "$QMD_PRIMER_PATH" --agent-id "$agent_id" --workspace "$workspace_path" --agent-dir "$runtime_agent_dir")
  if [[ "$QMD_EMBED" -eq 1 ]]; then
    cmd+=(--embed)
  fi
  "${cmd[@]}" >/dev/null
}

ensure_dir "$OPENCLAW_HOME"

created_workspaces=()
while IFS= read -r -d '' agent_dir; do
  agent_id="$(basename "$agent_dir")"
  workspace_path="$OPENCLAW_HOME/workspace-$agent_id"
  runtime_agent_dir="$OPENCLAW_HOME/agents/$agent_id"
  workspace_exists=0
  state_stash_dir=""

  if [[ -e "$workspace_path" ]]; then
    workspace_exists=1
  fi

  ensure_dir "$workspace_path"
  ensure_dir "$runtime_agent_dir"
  if [[ "$workspace_exists" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
    state_stash_dir="$(mktemp -d)"
    preserve_runtime_state "$workspace_path" "$state_stash_dir"
  fi
  copy_dir_content "$COMMON_ROOT" "$workspace_path"
  if [[ "$workspace_exists" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
    restore_runtime_state "$workspace_path" "$state_stash_dir"
    rm -rf "$state_stash_dir"
  fi
  ensure_runtime_defaults "$workspace_path"
  render_execution_target "$workspace_path"
  remove_runtime_bootstrap "$workspace_path"
  ensure_core_exec_log_dirs "$workspace_path"

  merge_role_agents "$workspace_path" "$agent_dir/AGENTS.md" "$agent_id"

  for role_file in SOUL.md IDENTITY.md HEARTBEAT.md MEMORY.seed.md; do
    if [[ -f "$agent_dir/$role_file" && "$DRY_RUN" -eq 0 ]]; then
      cp "$agent_dir/$role_file" "$workspace_path/$role_file"
    fi
  done

  ensure_dir "$workspace_path/scripts"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    find "$RUNTIME_SCRIPTS_ROOT" -maxdepth 1 -type f -name '*.py' -exec cp {} "$workspace_path/scripts/" \;
  fi

  ensure_today_daily_log "$workspace_path"
  merge_memory_seed "$workspace_path"
  update_tools_runtime_section "$workspace_path/TOOLS.md"
  ensure_git_repo "$workspace_path" "chore: bootstrap $agent_id workspace"
  prime_qmd_memory "$agent_id" "$workspace_path" "$runtime_agent_dir"

  created_workspaces+=("$agent_id -> $workspace_path")
done < <(find "$AGENTS_ROOT" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

if [[ "$SKIP_CONFIG_MERGE" -eq 0 ]]; then
  merge_openclaw_config "$CONFIG_PATH" "$OPENCLAW_HOME" "$SNIPPET_PATH" "$HOOKS_SNIPPET_PATH" "$MEMORY_SNIPPET_PATH" "$CAPTAIN_CHANNEL" "$CAPTAIN_ACCOUNT_ID"
fi

automation_status="skipped"
if [[ "$SKIP_AUTOMATION" -eq 0 ]]; then
  if command -v openclaw >/dev/null 2>&1; then
    automation_cmd=("$SCRIPT_DIR/install-openclaw-automation.sh" "--openclaw-home" "$OPENCLAW_HOME" "--timezone" "$AUTOMATION_TIMEZONE")
    if [[ "$SKIP_IGNITE" -eq 1 ]]; then
      automation_cmd+=("--skip-ignite")
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
      automation_cmd+=("--dry-run")
    fi
    "${automation_cmd[@]}"
    automation_status="installed"
    if [[ "$SKIP_IGNITE" -eq 0 ]]; then
      automation_status="installed + ignited"
    fi
  else
    echo "WARN: openclaw not found; skipping automation install" >&2
    automation_status="skipped (openclaw missing)"
  fi
fi

echo
echo "OpenClaw AI Coding Team install result:"
for item in "${created_workspaces[@]}"; do
  echo "- $item"
done
if [[ "$SKIP_CONFIG_MERGE" -eq 1 ]]; then
  echo "- openclaw.json merge skipped"
else
  echo "- config updated: $CONFIG_PATH"
fi
if [[ -n "$CAPTAIN_CHANNEL" && -n "$CAPTAIN_ACCOUNT_ID" ]]; then
  echo "- captain binding configured: $CAPTAIN_CHANNEL / $CAPTAIN_ACCOUNT_ID"
else
  echo "- captain binding not provided; keeping existing binding or leaving it empty"
fi
echo "- automation: $automation_status"
if [[ "$SKIP_GIT_INIT" -eq 1 ]]; then
  echo "- workspace Git init skipped"
fi
if [[ "$SKIP_QMD_INIT" -eq 1 ]]; then
  echo "- qmd memory priming skipped"
elif [[ "$QMD_EMBED" -eq 1 ]]; then
  echo "- qmd memory primed with embed"
else
  echo "- qmd memory primed (BM25/update only)"
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "- dry-run mode: no files were written"
fi

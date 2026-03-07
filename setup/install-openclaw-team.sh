#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
CONFIG_PATH=""
CAPTAIN_CHANNEL=""
CAPTAIN_ACCOUNT_ID=""
SKIP_GIT_INIT=0
SKIP_CONFIG_MERGE=0
DRY_RUN=0

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
DAILY_TEMPLATE_PATH="$COMMON_ROOT/memory/daily/TEMPLATE.md"

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
  local today month weekday daily_dir daily_path content
  today="$(date +%F)"
  month="$(date +%Y-%m)"
  weekday="$(date +%A)"
  daily_dir="$workspace_path/memory/daily/$month"
  daily_path="$daily_dir/$today.md"
  ensure_dir "$daily_dir"
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
  block=$'## Installed Runtime Paths\n\n- `scripts/scan_sessions_incremental.py`: enabled\n- `scripts/lockfile.py`: enabled\n- `scripts/weekly_gate.py`: enabled\n- `ROLE.md`: enabled'
  append_if_missing "$tools_path" "$block"
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
  local channel="$4"
  local account_id="$5"

  if [[ "$DRY_RUN" -eq 0 && -f "$target_config_path" ]]; then
    cp "$target_config_path" "$target_config_path.$(date +%Y%m%d-%H%M%S).bak"
  fi

  OPENCLAW_TARGET_CONFIG="$target_config_path" \
  OPENCLAW_HOME_RESOLVED="$resolved_openclaw_home" \
  OPENCLAW_SNIPPET_PATH="$snippet_path" \
  OPENCLAW_CAPTAIN_CHANNEL="$channel" \
  OPENCLAW_CAPTAIN_ACCOUNT_ID="$account_id" \
  OPENCLAW_DRY_RUN="$DRY_RUN" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

target_config_path = Path(os.environ["OPENCLAW_TARGET_CONFIG"])
snippet_path = Path(os.environ["OPENCLAW_SNIPPET_PATH"])
openclaw_home = os.environ["OPENCLAW_HOME_RESOLVED"]
channel = os.environ.get("OPENCLAW_CAPTAIN_CHANNEL", "")
account_id = os.environ.get("OPENCLAW_CAPTAIN_ACCOUNT_ID", "")
dry_run = os.environ.get("OPENCLAW_DRY_RUN", "0") == "1"

snippet = json.loads(snippet_path.read_text(encoding="utf-8"))
if target_config_path.exists():
    config = json.loads(target_config_path.read_text(encoding="utf-8"))
else:
    config = {}

agents = config.setdefault("agents", {})
defaults = agents.setdefault("defaults", {})
defaults.setdefault("subagents", {})
defaults["subagents"]["maxConcurrent"] = snippet["agents"]["defaults"]["subagents"]["maxConcurrent"]

agent_list = list(agents.get("list", []))
for agent_def in snippet["agents"]["list"]:
    new_agent = json.loads(json.dumps(agent_def))
    new_agent["workspace"] = str(Path(openclaw_home) / f"workspace-{new_agent['id']}")
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

if not dry_run:
    target_config_path.parent.mkdir(parents=True, exist_ok=True)
    target_config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
PY
}

ensure_dir "$OPENCLAW_HOME"

created_workspaces=()
while IFS= read -r -d '' agent_dir; do
  agent_id="$(basename "$agent_dir")"
  workspace_path="$OPENCLAW_HOME/workspace-$agent_id"

  ensure_dir "$workspace_path"
  copy_dir_content "$COMMON_ROOT" "$workspace_path"

  if [[ -f "$agent_dir/AGENTS.md" && "$DRY_RUN" -eq 0 ]]; then
    cp "$agent_dir/AGENTS.md" "$workspace_path/ROLE.md"
  fi

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

  created_workspaces+=("$agent_id -> $workspace_path")
done < <(find "$AGENTS_ROOT" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

if [[ "$SKIP_CONFIG_MERGE" -eq 0 ]]; then
  merge_openclaw_config "$CONFIG_PATH" "$OPENCLAW_HOME" "$SNIPPET_PATH" "$CAPTAIN_CHANNEL" "$CAPTAIN_ACCOUNT_ID"
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
if [[ "$SKIP_GIT_INIT" -eq 1 ]]; then
  echo "- workspace Git init skipped"
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "- dry-run mode: no files were written"
fi

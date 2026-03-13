#!/usr/bin/env bash
set -euo pipefail

# Smoke test for TASK-OPP-4AA217183E: DNS sinkhole -> DoH fallback path.
#
# This repo ships patch scripts for the OpenClaw installation (global npm dist):
#   - setup/patch_openclaw_web_fetch_doh.py
#   - setup/patch_openclaw_web_fetch_doh_schema.py
#
# After patching, enable DoH in ~/.openclaw/openclaw.json:
#   tools.web.fetch.doh.enabled=true
#   tools.web.fetch.doh.endpointUrl="https://dns.google/resolve"
#   tools.web.fetch.doh.pinnedIp="8.8.8.8"
#   tools.web.fetch.doh.timeoutMs=5000
#
# This script drives the *web_fetch tool* via openclaw agent (no dedicated CLI
# subcommand). It prints JSON summaries for manual verification.

AGENT_ID=${AGENT_ID:-aic-builder}

say() { printf '\n==> %s\n' "$*"; }

say "Config validate"
openclaw config validate

say "DNS baseline (system resolver)"
getent ahosts github.com | head -n 5 || true

say "web_fetch smoke (public sites)"
openclaw agent --agent "$AGENT_ID" --message $'Run ONLY the web_fetch tool with extractMode=text and maxChars=2000 for each URL below. Return a short JSON summary with url->status.\n\n1) https://github.com/\n2) https://news.ycombinator.com/\n3) https://hnrss.org/frontpage\n4) https://entropicthoughts.com/no-swe-bench-improvement\n' --timeout 300

say "SSRF regression (should be blocked)"
openclaw agent --agent "$AGENT_ID" --message $'Run ONLY the web_fetch tool with extractMode=text and maxChars=200 for each URL below. For each, return JSON with url -> {ok:boolean, status?:number, error?:string}.\n\n1) http://127.0.0.1/\n2) http://10.0.0.1/\n3) http://198.18.0.1/\n' --timeout 300

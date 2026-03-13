#!/usr/bin/env bash
set -euo pipefail

# Smoke test for TASK-OPP-4AA217183E: DNS sinkhole -> DoH fallback path.
#
# Assumes you've applied both patches to your OpenClaw installation:
#   - setup/patch_openclaw_web_fetch_doh.py
#   - setup/patch_openclaw_web_fetch_doh_schema.py
# And enabled DoH in your OpenClaw config (default path shown):
#   ~/.openclaw/openclaw.json
#     tools.web.fetch.doh.enabled=true
#
# Verifies:
#   - web_fetch works for public sites
#   - SSRF guard still blocks loopback/RFC1918/198.18/15

OPENCLAW_CONFIG_PATH=${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}

say() { printf '\n==> %s\n' "$*"; }

say "Config: $OPENCLAW_CONFIG_PATH"
openclaw config validate >/dev/null

say "DNS baseline (system resolver)"
getent ahosts github.com | head -n 5 || true

say "web_fetch smoke (public sites)"
openclaw tools web_fetch --url https://github.com/ --maxChars 2000 --extractMode text >/dev/null
openclaw tools web_fetch --url https://news.ycombinator.com/ --maxChars 2000 --extractMode text >/dev/null
openclaw tools web_fetch --url https://hnrss.org/frontpage --maxChars 2000 --extractMode text >/dev/null
openclaw tools web_fetch --url https://entropicthoughts.com/no-swe-bench-improvement --maxChars 2000 --extractMode text >/dev/null

echo "OK: web_fetch public sites"

say "SSRF regression (should FAIL)"
set +e
openclaw tools web_fetch --url http://127.0.0.1/ --maxChars 200 --extractMode text >/dev/null
rc1=$?
openclaw tools web_fetch --url http://10.0.0.1/ --maxChars 200 --extractMode text >/dev/null
rc2=$?
openclaw tools web_fetch --url http://198.18.0.1/ --maxChars 200 --extractMode text >/dev/null
rc3=$?
set -e

echo "Return codes: 127.0.0.1=$rc1 10.0.0.1=$rc2 198.18.0.1=$rc3"
if [[ "$rc1" -eq 0 || "$rc2" -eq 0 || "$rc3" -eq 0 ]]; then
  echo "ERROR: SSRF regression failed (one of the internal targets unexpectedly succeeded)" >&2
  exit 2
fi

echo "OK: SSRF guard still blocks internal/special-use IPs"

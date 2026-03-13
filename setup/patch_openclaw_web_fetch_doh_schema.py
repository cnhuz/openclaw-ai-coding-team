#!/usr/bin/env python3
"""Patch OpenClaw config schema to allow tools.web.fetch.doh.

Context:
- We already patch the web_fetch runtime implementation to *use* an opt-in DoH
  lookupFn (see patch_openclaw_web_fetch_doh.py).
- However OpenClaw's config schema is strict; without this patch, adding
  tools.web.fetch.doh to openclaw.json fails validation and may prevent the
  gateway from loading.

This patch extends ToolsWebFetchSchema in the built dist bundles to accept:

  tools.web.fetch.doh = {
    enabled?: boolean,
    endpointUrl?: string,
    pinnedIp?: string,
    timeoutMs?: number
  }

Rollback:
- Remove the doh key from openclaw.json.
- Reinstall OpenClaw (or restore backups if you run without --no-backup).

Safety:
- This patch only relaxes config validation to accept the doh config object.
  SSRF enforcement remains in the runtime (resolvePinnedHostnameWithPolicy).
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

TARGET_FILES = [
    # main CLI / gateway schema bundles
    "dist/daemon-cli.js",
    # auth profile schema bundle
    "dist/auth-profiles-CNyDTsy4.js",
    # model selection schema bundles (hashes vary across releases)
    "dist/model-selection-ikt2OC4j.js",
    "dist/model-selection-CjMYMtR0.js",
    "dist/model-selection-Zb7eBzSY.js",
    # plugin sdk schema bundle
    "dist/plugin-sdk/config-GHoFNNPc.js",
]

TOOLS_WEB_FETCH_MARKER = "const ToolsWebFetchSchema = z.object({"

DOH_INSERTION = (
    "userAgent: z.string().optional(),\n\t"
    "doh: z.object({\n\t\t"
    "enabled: z.boolean().optional(),\n\t\t"
    "endpointUrl: z.string().optional(),\n\t\t"
    "pinnedIp: z.string().optional(),\n\t\t"
    "timeoutMs: z.number().int().positive().optional()\n\t"
    "}).strict().optional()"
)


def patch_tools_web_fetch_schema(src: str) -> tuple[bool, str]:
    """Return (changed, newSrcOrReason)."""
    if TOOLS_WEB_FETCH_MARKER not in src:
        return False, "marker not found"

    start = src.index(TOOLS_WEB_FETCH_MARKER)
    end_marker = "}).strict().optional();"
    end = src.find(end_marker, start)
    if end == -1:
        return False, "end marker not found"
    end += len(end_marker)

    block = src[start:end]
    if "doh:" in block:
        return False, "already patched"

    needle = "userAgent: z.string().optional()"
    if needle not in block:
        return False, f"needle not found: {needle}"

    block2 = block.replace(needle, DOH_INSERTION, 1)
    return True, src[:start] + block2 + src[end:]


def patch_file(path: Path, *, backup: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"

    src = path.read_text(encoding="utf-8")
    changed, out = patch_tools_web_fetch_schema(src)
    if not changed:
        return False, f"{out}: {path}"

    if backup:
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = path.with_suffix(path.suffix + f".bak.{ts}")
        bak.write_text(src, encoding="utf-8")

    path.write_text(out, encoding="utf-8")
    return True, f"patched: {path}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--openclaw-root",
        default=str(Path.home() / ".npm-global/lib/node_modules/openclaw"),
        help="OpenClaw install root (default matches this host's global npm prefix)",
    )
    ap.add_argument("--no-backup", action="store_true", help="Do not write .bak.* backups")
    args = ap.parse_args()

    root = Path(args.openclaw_root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"OpenClaw root not found: {root}")

    changed = 0
    for rel in TARGET_FILES:
        ok, msg = patch_file(root / rel, backup=not args.no_backup)
        print(msg)
        if ok:
            changed += 1

    if changed == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

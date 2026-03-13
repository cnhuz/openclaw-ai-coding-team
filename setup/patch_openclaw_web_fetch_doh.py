#!/usr/bin/env python3
"""Patch OpenClaw's web_fetch to support a DoH-based DNS fallback.

Why: some networks transparently rewrite UDP/TCP 53 DNS to RFC2544 (198.18/15),
which triggers OpenClaw SSRF blocking and breaks web_fetch. This patch adds an
*opt-in* DoH resolver that is used as lookupFn for SSRF-pinned DNS.

- Opt-in via openclaw.json:
  tools.web.fetch.doh = {
    enabled: true,
    endpointUrl: "https://dns.google/resolve",  # default
    pinnedIp: "8.8.8.8",                       # default
    timeoutMs: 5000                            # default
  }

Rollback: set tools.web.fetch.doh.enabled=false (or unset the doh object).

Safety: SSRF public/private checks remain enforced by resolvePinnedHostnameWithPolicy.
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

TARGET_FILES = [
    "dist/pi-embedded-CtM2Mrrj.js",
    "dist/pi-embedded-DgYXShcG.js",
    "dist/reply-DhtejUNZ.js",
    "dist/subagent-registry-CkqrXKq4.js",
    "dist/plugin-sdk/reply-DFFRlayb.js",
]

INSERT_BEFORE = "async function runWebFetch(params) {"

DOH_HELPERS = r'''// --- web_fetch DoH patch (opt-in) ---
const DEFAULT_WEB_FETCH_DOH_ENDPOINT = "https://dns.google/resolve";
const DEFAULT_WEB_FETCH_DOH_PINNED_IP = "8.8.8.8";
function resolveWebFetchDohConfig(fetch) {
\tif (!fetch || typeof fetch !== "object") return;
\tconst doh = "doh" in fetch ? fetch.doh : void 0;
\tif (!doh || typeof doh !== "object") return;
\tconst enabled = "enabled" in doh ? doh.enabled === true : false;
\tif (!enabled) return { enabled: false };
\tconst endpointUrl = typeof doh.endpointUrl === "string" && doh.endpointUrl.trim() ? doh.endpointUrl.trim() : DEFAULT_WEB_FETCH_DOH_ENDPOINT;
\tconst pinnedIp = typeof doh.pinnedIp === "string" && doh.pinnedIp.trim() ? doh.pinnedIp.trim() : DEFAULT_WEB_FETCH_DOH_PINNED_IP;
\tconst timeoutMs = typeof doh.timeoutMs === "number" && Number.isFinite(doh.timeoutMs) ? Math.max(100, Math.floor(doh.timeoutMs)) : 5e3;
\treturn { enabled: true, endpointUrl, pinnedIp, timeoutMs };
}
function _normalizeHostForLookup(host) {
\treturn String(host || "").trim().toLowerCase().replace(/\.$/, "");
}
function _isCanonicalIpv4(value) {
\tif (typeof value !== "string") return false;
\tconst s = value.trim();
\tif (!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(s)) return false;
\tconst parts = s.split(".");
\tfor (const part of parts) {
\t\tconst n = Number(part);
\t\tif (!Number.isInteger(n) || n < 0 || n > 255) return false;
\t}
\treturn true;
}
async function _webFetchResolveViaGoogleDoh(hostname, type, doh) {
\tconst endpointUrl = doh.endpointUrl;
\tconst pinnedIp = doh.pinnedIp;
\tconst endpointHost = _normalizeHostForLookup(new URL(endpointUrl).hostname);
\tconst endpointLookupFn = async (host, options) => {
\t\tconst normalized = _normalizeHostForLookup(host);
\t\tif (normalized !== endpointHost) {
\t\t\tthrow new Error(`DoH bootstrap lookup called for unexpected host: ${host}`);
\t\t}
\t\tconst family = pinnedIp.includes(":") ? 6 : 4;
\t\tconst record = { address: pinnedIp, family };
\t\tif (typeof options === "object" && options && options.all === true) return [record];
\t\treturn record;
\t};
\tconst url = `${endpointUrl}?name=${encodeURIComponent(hostname)}&type=${encodeURIComponent(type)}`;
\tconst res = await fetchWithSsrFGuard({
\t\turl,
\t\tmaxRedirects: 0,
\t\ttimeoutMs: doh.timeoutMs,
\t\tlookupFn: endpointLookupFn,
\t\tinit: { headers: { Accept: "application/dns-json" } },
\t\tauditContext: "web-fetch-doh"
\t});
\ttry {
\t\tconst text = await res.response.text();
\t\tlet json;
\t\ttry {
\t\t\tjson = JSON.parse(text);
\t\t} catch {
\t\t\tthrow new Error(`DoH parse failed: ${text?.slice?.(0, 300) ?? ""}`);
\t\t}
\t\tif (!json || typeof json !== "object") throw new Error("DoH response invalid");
\t\tif (json.Status !== 0) throw new Error(`DoH status=${json.Status}`);
\t\tconst answers = Array.isArray(json.Answer) ? json.Answer : [];
\t\tconst out = [];
\t\tfor (const ans of answers) {
\t\t\tconst data = ans && typeof ans === "object" ? ans.data : void 0;
\t\t\tif (_isCanonicalIpv4(data)) out.push({ address: data.trim(), family: 4 });
\t\t}
\t\treturn out;
\t} finally {
\t\tawait res.release();
\t}
}
function resolveWebFetchLookupFn(doh) {
\tif (!doh || typeof doh !== "object") return;
\tif (doh.enabled !== true) return;
\treturn async (hostname, options) => {
\t\tconst all = typeof options === "object" && options && options.all === true;
\t\tconst wantFamily = typeof options === "object" && options && typeof options.family === "number" ? options.family : 0;
\t\tconst host = _normalizeHostForLookup(hostname);
\t\tif (!host) throw new Error("Invalid hostname");
\t\t// Prefer IPv4; fetch-guard will still enforce SSRF restrictions.
\t\tlet records = await _webFetchResolveViaGoogleDoh(host, "A", doh);
\t\tif ((wantFamily === 6 || wantFamily === 0) && records.length === 0) {
\t\t\t// We currently only return canonical IPv4 records; keep behavior explicit.
\t\t\t// (IPv6-only sites may still fail until we add AAAA parsing.)
\t\t}
\t\tif (records.length === 0) throw new Error(`DoH: unable to resolve hostname: ${hostname}`);
\t\tif (all) return records;
\t\treturn records[0];
\t};
}
// --- end web_fetch DoH patch ---

'''


def patch_file(path: Path, *, backup: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"

    src = path.read_text(encoding="utf-8")

    if "web_fetch DoH patch" in src:
        return False, f"already patched: {path}"

    if INSERT_BEFORE not in src:
        return False, f"marker not found: {path}"

    # 1) Inject helper functions before runWebFetch
    src2 = src.replace(INSERT_BEFORE, DOH_HELPERS + INSERT_BEFORE, 1)

    # 2) Pass lookupFn into fetchWithWebToolsNetworkGuard inside runWebFetch
    needle = "timeoutSeconds: params.timeoutSeconds,\n\t\t\tinit: { headers: {"
    if needle not in src2:
        return False, f"needle not found (lookupFn insert): {path}"
    src3 = src2.replace(
        needle,
        "timeoutSeconds: params.timeoutSeconds,\n\t\t\tlookupFn: resolveWebFetchLookupFn(params.doh),\n\t\t\tinit: { headers: {",
        1,
    )

    # 3) Pass doh config into runWebFetch call site
    # 3) Pass doh config into runWebFetch call site
    # Note: dist bundling sometimes shifts indentation (tabs). Match both variants.
    needle2_variants = [
        # older builds
        "firecrawlStoreInCache: true,\n\t\t\tfirecrawlTimeoutSeconds\n\t\t}));",
        # current builds (one more level of indentation)
        "firecrawlStoreInCache: true,\n\t\t\t\tfirecrawlTimeoutSeconds\n\t\t\t}));",
    ]
    for needle2 in needle2_variants:
        if needle2 in src3:
            src4 = src3.replace(
                needle2,
                needle2.replace(
                    "firecrawlTimeoutSeconds\n",
                    "firecrawlTimeoutSeconds,\n\t\t\t\tdoh: resolveWebFetchDohConfig(fetch)\n",
                ),
                1,
            )
            break
    else:
        return False, f"needle not found (doh config insert): {path}"

    if backup:
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = path.with_suffix(path.suffix + f".bak.{ts}")
        bak.write_text(src, encoding="utf-8")

    path.write_text(src4, encoding="utf-8")
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

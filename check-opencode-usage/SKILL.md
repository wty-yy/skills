---
name: check-opencode-usage
description: Query opencode.ai workspace usage and cost with the local Chrome login, and generate or publish the HTML dashboard. Use when the user asks for opencode usage, daily token/cost totals, per-API-key or per-model breakdowns, cache hit rate, remaining OpenCode Go membership quota, or to refresh the hosted report at opencode-usage.wty-yy.top.
---

# Check opencode usage

## When To Use

- daily token/cost totals for the last N days
- breakdown by API key (`wt` vs all other keys) or by model
- cache hit rate, model token prices, remaining OpenCode Go quota (5h / weekly / monthly)
- generate the detailed HTML dashboard, or publish it to `opencode-usage.wty-yy.top`

## Quick Start

```bash
cd <skill>/scripts

uv run opencode_usage.py --days 7 --by-key   # terminal table
uv run opencode_usage.py --days 7 --json     # machine-readable summary
uv run usage_report.py --days 14             # writes usage_report.html (~1 min)
uv run usage_report.py --days 14 --push      # publish to Cloudflare KV
```

PEP 723 inline dependencies; `uv run` resolves `cryptography` and `secretstorage` automatically. Do not run with plain `python`.

| Script | Options |
| --- | --- |
| `opencode_usage.py` | `--days` (default 7), `--by-model`, `--by-key`, `--json`, `--workspace`, `--profile`, `--max-pages` |
| `usage_report.py` | `--days` (default 14), `--out`, `--push`, `--workspace`, `--profile`, `--max-pages` |

API keys are grouped by display name: keys ending in `- wt` are `wt`, all others are counted as `yy` (other keys).

## Implementation Details

### Auth (Chrome cookie decryption)

1. Read cookies for `opencode.ai` from `~/.config/google-chrome/<profile>/Cookies` (SQLite, `encrypted_value`); override the root with `CHROME_CONFIG_DIR`. The profile with opencode cookies is auto-detected.
2. Get the keyring secret for Chrome: `search_items({"application": "chrome"})` on the default collection. `get_all_items()` can raise `ItemNotFoundException` on gnome-keyring; `application=chromium` may hold a different secret and produces garbage plaintext. Fallback is `peanuts` (keyring-less Chrome).
3. Decrypt `v10`/`v11`: `PBKDF2-HMAC-SHA1(secret, b"saltysalt", 1, 16)` + AES-128-CBC with a fixed 16-space IV; `v11` plaintext starts with a 32-byte `SHA256(host_key)` prefix that must be stripped.
4. Only the `auth` cookie matters (iron-session `Fe26.2**...`). If login is stale the fix is to re-login to opencode.ai in Chrome; there is no token fallback.

### opencode.ai RPC

No public API; the scripts call the SolidStart RPC `POST https://opencode.ai/_server` with `X-Server-Id` content hashes.

| Function | ID constant | Args | Returns |
| --- | --- | --- | --- |
| `usage.list` | `USAGE_LIST_FN` | `workspace, page` | 50 records/page: model, provider, tokens, `cost`, `keyID` |
| `getCosts` | `GET_COSTS_FN` | `workspace, year, month(0-based), tz` | daily cost rows + `keys` (id -> displayName, deleted) |
| `lite.subscription.get` | `LITE_GET_FN` | `workspace` | rolling/weekly/monthly quota windows |
| `lite.subscription.usage` | `LITE_USAGE_FN` | `workspace, scope` | per-model quota rows |

- Request bodies are seroval node JSON: array nodes must include the `l` (length) field or the server silently misparses args (symptom: `actor of type "account" is not associated with a workspace`). Use `seroval_args()`.
- Responses are JS expressions (`;0x<len>;` prefix, `$R[n]=` refs, `new Date(...)`, `!0`/`!1`); server errors arrive as HTTP 200 with `Object.assign(new Error("..."))`. `parse_solid_response()` handles both.
- `cost`/`totalCost`/quota `usage`/`limit` are in 1e-8 USD (`COST_SCALE`). Go windows: 5h = 20% of monthly, weekly = 50%, monthly = 100%. The Go plan is internally `lite`.
- `usage.list` pages 50 records and a busy workspace generates ~1500 records/day; `fetch_records()` paginates until a short page or cutoff. Concurrent calls occasionally hit TLS EOF; keep the retry/backoff in `call_server()`.

### Publish (Cloudflare KV)

- `--push` uploads keys `report` (HTML) and `report-meta` (JSON) via the KV REST API; env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit), optional `CF_KV_KEY` (default `report`).
- `references/cloudflare-worker.js` serves those keys from the `USAGE_KV` binding; deploy it with a KV binding and a custom domain, and keep the domain behind Cloudflare Access.
- Auto-publish runs as a systemd user timer (`opencode-usage-push.timer`, every 10 min) reading `~/.config/opencode-usage/env`; logs via `journalctl --user -u opencode-usage-push.service`. It needs the user's gnome-keyring session.

## Function Hash Recovery

`X-Server-Id` hashes are content-hashed and change when opencode.ai redeploys. Recover them by fetching the workspace page HTML, finding the `index-*.js` chunk under `/_build/assets/`, and grepping for `createServerReference("<hash>")` next to `query(..., "usage.list" | "getCosts" | "lite.subscription.get" | "lite.subscription.usage")`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no 'auth' cookie for opencode.ai` | Log in to opencode.ai in Chrome; rerun |
| `actor of type "account" is not associated with a workspace` | Seroval array node missing `l`, or wrong workspace ID |
| `unsupported cookie encryption` / unreadable plaintext | Wrong keyring item; use `search_items({"application": "chrome"})` |
| `Invalid time value` from `getCosts` | Pass a 0-based JS month (`9 月` -> `8`) |
| Truncated token totals, `complete: false` | Raise `--max-pages` |
| TLS EOF / `SSLEOFError` under load | Transient; retries are built in, lower parallelism if persistent |

## Notes

- The `auth` cookie is a full account credential; it never leaves the local machine for the query/report path.
- The HTML report is self-contained (Chart.js and data inlined) and includes an inline-generated Chart.js copy; a network failure only degrades it to a CDN fallback.
- Report date bucketing uses the system-local timezone; `--days` includes today.

---
name: check-opencode-usage
description: Query opencode.ai console usage/cost and Go membership quota with a service API key or the local Chrome login, and generate or publish the HTML dashboard. Use when the user asks for opencode usage, daily token/cost totals, per-API-key or per-model breakdowns, cache hit rate, remaining OpenCode Go quota, or to refresh the hosted report at opencode-usage.wty-yy.top.
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
| `usage_report.py` | `--days` (default 14), `--out`, `--push`, `--history`, `--workspace`, `--profile`, `--max-pages` |

API keys are grouped by display name: keys ending in `wt` are `wt`, all others are counted as `yy`.

## Implementation Details

### Auth

1. Preferred: `OPENCODE_API_KEY` holding a console service API key (`oc_sk_...`), sent as `Authorization: Bearer`. Create one with `POST /console/api/service-accounts` (`{name}`) and `POST /console/api/service-accounts/<id>/keys` (`{name, permissions: "all", expiresAt: null}`); the token is returned once.
2. Fallback: the Chrome console session cookie `__Host-console_session` plus an `x-org-id` header (the workspace ID is now the org ID). Cookies are read from `~/.config/google-chrome` (override `CHROME_CONFIG_DIR`); the profile is auto-detected.
3. Cookie decryption: `v10`/`v11` prefix, AES-128-CBC with `PBKDF2-HMAC-SHA1(secret, "saltysalt", 1, 16)` and a fixed 16-space IV; v11 plaintext carries a 32-byte `SHA256(host_key)` prefix to strip. The keyring item must be `application=chrome`; a `chromium` item may hold a different secret and silently produces garbage.
4. If the session is stale, log in again at https://opencode.ai/console/login in Chrome.

### Console API

Base `https://opencode.ai/console/api` (the pre-2026-09-22 SolidStart `/_server` RPC with `X-Server-Id` hashes is gone).

| Endpoint | Purpose |
| --- | --- |
| `/usage/rows` | per-request records; cursor pagination via `nextCursor`, `pageSize` max 100, accepts `since=<ISO>` or `range=24h\|7d\|30d` |
| `/usage/cost-by-day` | daily or hourly aggregates (`bucket=day\|hour`) |
| `/usage/summary` | range totals |
| `/service-accounts` | service accounts and their keys (`id -> name`, `permissions`, `status`) |
| `/go/status` | Go quota meters: `access.meters.{fiveHour,week,month}` with `usedMicroCents`, `limitMicroCents`, `resetsAt`; the month window resets at `access.endsAt` (subscription period end) |

- `costMicroCents` and quota `usedMicroCents`/`limitMicroCents` are in 1e-8 USD.
- A service key resolves the org itself; cookie auth needs `x-org-id`.
- Usage history starts at 2026-09-22 (console migration); older usage is absent from the API but still counted in the Go quota meters. The optional `history.json` (`--history`) backfills earlier days from cached old reports and marks them `backfilled: true`.
- Concurrent requests occasionally fail with TLS EOF; keep the retry/backoff in `call_api`.

### Publish (Cloudflare KV)

- `--push` uploads keys `report` (HTML) and `report-meta` (JSON) via env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit), optional `CF_KV_KEY` (default `report`).
- `references/cloudflare-worker.js` serves those keys from the `USAGE_KV` binding; keep the custom domain behind Cloudflare Access.
- Auto-publish example: a systemd user timer every 10 min with an `EnvironmentFile` holding `OPENCODE_API_KEY` and `CF_*`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HTTP 401 `Unauthorized` | Key revoked or stale console session; re-login or create an `all` service key |
| HTTP 403 `Forbidden` | Service key is `inference-only`; use a key with `all` permission |
| HTTP 400 `x-org-id is required` | Cookie auth needs the header; Bearer keys do not |
| HTTP 400 on `pageSize` | Maximum is 100 |
| TLS EOF / `SSLEOFError` under load | Transient; retries are built in |
| Days before 2026-09-22 are empty | Expected without `history.json`; the API has no pre-migration rows |
| `unsupported cookie encryption` / unreadable plaintext | Wrong keyring item; use `search_items({"application": "chrome"})` |

## Notes

- API key names come from `/service-accounts`; usage rows only carry `serviceApiKeyId`.
- The HTML report is self-contained (Chart.js inlined at generation time with a CDN fallback).
- `history.json` contains personal usage data; keep it out of public repositories.
- The `auth` cookie and service keys are account credentials; never write them to disk, logs or repositories.

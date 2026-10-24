---
name: opencode-tools
description: Query opencode.ai console usage/cost and OpenCode Go membership quota with a service API key plus the local Chrome login, generate or publish the HTML dashboard, switch billing periods and refresh the hosted report. Use when the user asks for opencode usage, daily token/cost totals, per-API-key or per-model breakdowns, cache hit rate, remaining Go quota, or to refresh/publish the report at opencode-usage.wty-yy.top.
---

# OpenCode Tools

## When To Use

- daily token/cost totals for the last N days
- breakdown by API key (`wt` vs all other keys) or by model
- cache hit rate, model token prices, remaining OpenCode Go quota (5h / weekly / monthly)
- generate the detailed HTML dashboard, switch its billing period, or publish it to `opencode-usage.wty-yy.top`
- turn Go auto-renewal off or back on (billing action; only on explicit request)

## Quick Start

```bash
cd <skill>/scripts

uv run opencode_usage.py --days 7 --by-key --by-model   # terminal table
uv run opencode_usage.py --days 7 --json                # machine-readable summary
uv run usage_report.py                                  # current Go period + previous period
uv run usage_report.py --days 14                        # fixed recent window
uv run usage_report.py --push                           # publish to Cloudflare KV
```

PEP 723 inline dependencies; `uv run` resolves `cryptography` and `secretstorage` automatically. Do not run with plain `python`. A warm run takes ~1 min; the first per-key backfill adds up to `KEY_FETCH_BUDGET` (4) days per run.

| Script | Options |
| --- | --- |
| `opencode_usage.py` | `--days` (default 7, max 90), `--by-model`, `--by-key`, `--json`, `--workspace`, `--profile` |
| `usage_report.py` | `--days` (optional; default current Go period plus the previous period, capped at 90 days), `--out`, `--push`, `--workspace`, `--profile` |

API keys ending in `wt` are grouped as `wt`, all others as `yy`.

## Implementation Details

### Auth

1. Preferred: `OPENCODE_API_KEY` holding a console service API key (`oc_sk_...`), sent as `Authorization: Bearer`. Create one with `POST /console/api/service-accounts` (`{name}`) and `POST /console/api/service-accounts/<id>/keys` (`{name, permissions: "all", expiresAt: null}`). The token is returned once.
2. Request logs reject service keys (403), so `auth_header_sets()` also returns the Chrome console session cookie `__Host-console_session` plus `x-org-id`, and `call_api()` switches auth on 401/403. Cookies need the user's gnome-keyring session and are read from `~/.config/google-chrome` (override `CHROME_CONFIG_DIR`).
3. Cookie decryption: `v10`/`v11` prefix, AES-128-CBC with `PBKDF2-HMAC-SHA1(secret, "saltysalt", 1, 16)` and a fixed 16-space IV; v11 plaintext carries a 32-byte `SHA256(host_key)` prefix to strip. The keyring item must be `application=chrome`; a `chromium` item may hold a different secret and silently produces garbage.
4. If the session is stale, log in again at https://opencode.ai/console/login in Chrome.

### Console API

Base `https://opencode.ai/console/api`. The workspace ID is the org ID.

| Endpoint | Purpose |
| --- | --- |
| `/v2/usage/export?range=7d\|30d\|90d` | CSV at day × model × user: `requests`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_micro_cents`; covers 2026-09-13 onward and matches request-log sums exactly |
| `/request-logs?day=YYYY-MM-DD&category=inference&limit=100` | per-request rows with `serviceAPIKeyID`, token counts, dollar `cost`; cursor pagination (`nextCursor` must be URL-encoded), 30-day retention, data from 2026-09-22 |
| `/service-accounts` | service accounts and their keys (`id -> name`) |
| `/go/status` | Go quota meters: `access.meters.{fiveHour,week,month}`; the month window resets at `access.endsAt` (subscription period end); also returns `startsAt`, `endsAt`, `cancelAtPeriodEnd`, `resumability` |
| `POST /go/subscription/cancel` | stop Go auto-renewal; sets `cancelAtPeriodEnd=true`, access remains until `access.endsAt` |
| `POST /go/subscription/resume` | undo cancellation and restore renewal |

- The request-log backend is slow (5-30 s per page) and intermittently returns 500; `/request-logs/export` and `/request-logs/groups` are currently broken. `fetch_key_stats()` therefore caches one day at a time in `key_cache.json`, backfills at most `KEY_FETCH_BUDGET` days per run, and always re-fetches today.
- The report shows per-day `wt` / `yy` totals: 2026-09-22+ from the key cache, 2026-09-13..09-21 from the optional `history.json` next to the scripts (recovered from cached old reports). Splits are scaled proportionally so `wt + yy` equals the official daily total; days without either source fall back to `—` in the split columns.
- `/usage/rows` was removed in the 2026-09-27 redeploy; per-key data comes only from request logs.
- `cost_micro_cents`, request-log `cost` (USD float) and quota `usedMicroCents`/`limitMicroCents` are in 1e-8 USD.
- Concurrent requests occasionally fail with TLS EOF or 500; keep the retry/backoff in `call_api`.

### Go subscription changes

`POST /go/subscription/cancel` and `POST /go/subscription/resume` use the Chrome console session (the same session as the Console UI). Send `Origin: https://opencode.ai`, `Referer: https://opencode.ai/console/go`, `x-org-id`, and no body. Cancelling stops the next renewal but does not refund the current period; access continues until `access.endsAt`. Verify the result with `/go/status` (`cancelAtPeriodEnd`, `resumability`, `renewalStopReason`). Only perform these calls when the user explicitly asks to change billing.

### Report UI

- Default view is the current Go period (`startsAt` → today). The top-right selector also offers previous monthly periods back to 2026-09-13, capped at 90 days.
- The `刷新` button re-fetches the published URL with a `_refresh` cache-buster and `cache: "no-store"`, parses the embedded `<script type="application/json" id="reportData">` snapshot, swaps `DATA` in place and re-renders. The selected period, theme and scroll position survive; opening via `file://` falls back to `location.reload()`.
- Header meta is intentionally short: `套餐周期 <startsAt> ~ <endsAt> · 生成于 <timestamp>`. The quota footnote only describes the 5h / weekly / monthly windows.
- The period selector reserves space for its date range and becomes full-width on small screens; keep that behavior when changing the header layout.
- The report contains personal usage data. Do not commit generated `usage_report.html`, `key_cache.json` or `history.json`.

### Publish (Cloudflare KV)

- `--push` uploads keys `report` (HTML) and `report-meta` (JSON) via env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit), optional `CF_KV_KEY` (default `report`).
- `references/cloudflare-worker.js` serves those keys from the `USAGE_KV` binding; keep the custom domain behind Cloudflare Access.
- Auto-publish: copy `references/opencode-usage-push.service` and `references/opencode-usage-push.timer` to `~/.config/systemd/user/`, adjust `WorkingDirectory` and the `uv` path, create `~/.config/opencode-usage/env` from `references/env.example` (mode 600), then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now opencode-usage-push.timer
```

The timer runs every 10 minutes with `TimeoutStartSec=600` to cover slow request-log pages; logs go to `journalctl --user -u opencode-usage-push.service`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HTTP 401 `Unauthorized` | Key revoked or stale console session; re-login or create an `all` service key |
| HTTP 403 on `/request-logs` | Expected for service keys; cookie fallback handles it |
| HTTP 403 on other paths | Service key is `inference-only`; use a key with `all` permission |
| HTTP 500 on request logs | Transient ClickHouse backend; retries are built in, the day cache keeps the last good data |
| HTTP 400 `x-org-id is required` | Cookie auth needs the header; Bearer keys do not |
| Empty per-key table | `key_cache.json` is still backfilling, or the day is before 2026-09-22 |
| `unsupported cookie encryption` / unreadable plaintext | Wrong keyring item; use `search_items({"application": "chrome"})` |
| Report still shows an older period or renewal state | Click `刷新`; it only sees the last KV publish, and quota is a snapshot from generation time (timer every 10 min) |
| Period selector text is clipped | Keep the right padding for the native arrow and the full-width rule in the `max-width: 760px` media query |

## Notes

- `key_cache.json` holds per-day per-key aggregates (`fetchedAt` + `keys`); entries are kept for `KEY_CACHE_MAX_AGE` (365) days. Deleting it forces a full backfill.
- `history.json` contains personal pre-2026-09-22 usage totals; keep it out of public repositories.
- The HTML report is self-contained (Chart.js inlined at generation time with a CDN fallback). The refresh button fetches the full HTML (~250 KB); there is no separate JSON endpoint.
- Service keys and session cookies are account credentials; never write them to disk, logs or repositories.

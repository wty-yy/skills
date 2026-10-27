---
name: opencode-tools
description: Query opencode.ai usage/cost and OpenCode Go quota across accounts, generate or publish the HTML dashboard, and switch accounts or billing periods. Use for OpenCode daily token/cost totals, per-key or per-model breakdowns, cache hit rate, remaining Go quota, or maintaining the report at opencode-usage.wty-yy.top.
---

# OpenCode Tools

## When To Use

- daily token/cost totals for the last N days
- breakdown by API key (`wt` vs all other keys) or by model
- cache hit rate, model token prices, remaining OpenCode Go quota (5h / weekly / monthly)
- generate the detailed HTML dashboard, switch Google/GitHub accounts or billing periods, or publish it to `opencode-usage.wty-yy.top`
- turn Go auto-renewal off or back on (billing action; only on explicit request)

## Quick Start

```bash
cd <skill>/scripts

uv run opencode_usage.py --days 7 --by-key --by-model   # terminal table
uv run opencode_usage.py --days 7 --json                # machine-readable summary
uv run usage_report.py                                  # current Go period + previous period
uv run usage_report.py --days 14                        # fixed recent window
uv run usage_report.py --accounts ~/.config/opencode-usage/accounts.json  # account switcher
uv run usage_report.py --push                           # publish to Cloudflare KV
```

PEP 723 inline dependencies; `uv run` resolves `cryptography` and `secretstorage` automatically. Do not run with plain `python`. A warm run takes ~1 min; the first per-key backfill adds up to `KEY_FETCH_BUDGET` (4) days per run.

| Script | Options |
| --- | --- |
| `opencode_usage.py` | `--days` (default 7, max 90), `--by-model`, `--by-key`, `--json`, `--workspace`, `--profile` |
| `usage_report.py` | `--days` (optional; default current Go period plus the previous period, capped at 90 days), `--accounts`, `--out`, `--push`, `--workspace`, `--profile` |

API keys ending in `wt` are grouped as `wt`, all others as `yy`.

### Multiple accounts

Copy [references/accounts.example.json](references/accounts.example.json) to `~/.config/opencode-usage/accounts.json` and replace the workspace IDs with each account's Console org ID. Use the actual ID, including its `org_` or legacy `wrk_` prefix. The first entry is the default account; `id` must be unique and `name` is the display label.

- `apiKeyEnv` names that account's service-key environment variable; when omitted, the account uses its Chrome or saved session without inheriting another account's key. Load those variables into the process, for example with `uv run --env-file ~/.config/opencode-usage/env usage_report.py`.
- Optional `profile` is an absolute or `~`-expanded Chrome profile directory. `--workspace` or `--profile` selects single-workspace mode instead of loading the accounts list. The terminal script remains a single-workspace command.
- The browser session is checked against `/go/status` for the target workspace before saving it as `session-<workspace>.json` beside the accounts config (mode 600). A saved session lets the other account remain readable after switching the browser login, until that session expires.
- Usage caches are separate: the original `DEFAULT_WORKSPACE` retains `key_cache.json` and optional `history.json`; other workspaces use `key_cache-<workspace>.json` and do not inherit that history. `account_reports.json` keeps the last successful snapshot per workspace; read failures show its original timestamp and a history-snapshot warning. An account without any successful snapshot fails generation instead of publishing incomplete data.
- Existing service keys keep totals and Go quota available while that account is logged out. Per-key request logs still need a valid session for the same account; otherwise its existing key cache is retained.

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

- The request-log backend is slow (5-30 s per page) and intermittently returns 500; `/request-logs/export` and `/request-logs/groups` are currently broken. `fetch_key_stats()` therefore caches one day at a time in the workspace's key cache, backfills at most `KEY_FETCH_BUDGET` days per account per run, and always re-fetches today.
- The report shows per-day `wt` / `yy` totals: 2026-09-22+ from the key cache, 2026-09-13..09-21 from the optional `history.json` next to the scripts (recovered from cached old reports). Splits are scaled proportionally so `wt + yy` equals the official daily total; days without either source fall back to `—` in the split columns.
- `/usage/rows` was removed in the 2026-09-27 redeploy; per-key data comes only from request logs.
- `cost_micro_cents`, request-log `cost` (USD float) and quota `usedMicroCents`/`limitMicroCents` are in 1e-8 USD.
- Concurrent requests occasionally fail with TLS EOF or 500; keep the retry/backoff in `call_api`.

### Go subscription changes

`POST /go/subscription/cancel` and `POST /go/subscription/resume` use the Chrome console session (the same session as the Console UI). Send `Origin: https://opencode.ai`, `Referer: https://opencode.ai/console/go`, `x-org-id`, and no body. Cancelling stops the next renewal but does not refund the current period; access continues until `access.endsAt`. Verify the result with `/go/status` (`cancelAtPeriodEnd`, `resumability`, `renewalStopReason`). Only perform these calls when the user explicitly asks to change billing.

### Report UI

- The account selector switches each account's totals, charts, tables and live quota together. The last selected account is saved in `localStorage`; each account's selected period is retained during the page session. A single-account report hides the account selector.
- Default view is the selected account's current Go period (`startsAt` → today). Its period selector also offers previous monthly periods back to 2026-09-13, capped at 90 days. Quota always describes that account's current plan, including when viewing a historical period.
- The `刷新` button re-fetches the published URL with a `_refresh` cache-buster and `cache: "no-store"`, parses the embedded `<script type="application/json" id="reportData">` snapshot, replaces `REPORT` and selects the matching account's `DATA`. The selected account, period, theme and scroll position survive; opening via `file://` falls back to `location.reload()`.
- The snapshot contains `accounts`, `defaultAccount` and a publication `generatedAt`; each account has its own `generatedAt`, `periods`, `days`, `dayModels`, `keyDays`, `keysMeta` and `quota`.
- Header meta is intentionally short: `<account name> · 套餐周期 <startsAt> ~ <endsAt> · 生成于 <timestamp>`. Failed accounts show a warning and mark quota as a historical snapshot.
- The period selector reserves space for its date range and becomes full-width on small screens; keep that behavior when changing the header layout.
- The report contains personal usage data. Keep generated HTML, `key_cache*.json`, `history.json` and `account_reports.json` outside version control; keep real account configs and saved sessions in the private config directory.

### Publish (Cloudflare KV)

- `--push` sends HTML and KV metadata (`generatedAt`, SHA-256 `etag`, UTF-8 `bytes`) together in one multipart write to `report` via env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit), optional `CF_KV_KEY` (default `report`). The old `report-meta` key may remain for rollback but is neither written nor read. Keep the 10-minute timer: normal publishing uses 144 writes/day per site.
- [references/cloudflare-worker.js](references/cloudflare-worker.js) serves `/` through GET/HEAD from the `USAGE_KV` binding using `getWithMetadata`. It ignores query cache-busters and reuses the result for 60 seconds within a warm Worker instance, isolated by KV binding. Cold instances still read KV.
- Keep the custom domain behind Cloudflare Access. The normal Cache API is unavailable behind Access; the Worker uses memory caching and `Cache-Control: private, max-age=60`, supports ETag and Last-Modified/304, and does not cache credentials or personalized responses. Cloudflare HTML transforms may strip ETag.
- Update the deployed Worker when changing its source; publishing Python-generated HTML alone does not update Worker code. Preserve the existing KV binding, domains and Access rules. The supplied Worker reads `report`; if changing `CF_KV_KEY`, update the Worker key to match.
- Auto-publish: copy `references/opencode-usage-push.service` and `references/opencode-usage-push.timer` to `~/.config/systemd/user/`, adjust `WorkingDirectory` and the `uv` path, create `~/.config/opencode-usage/env` from `references/env.example` (mode 600), then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now opencode-usage-push.timer
```

The timer runs every 10 minutes with `TimeoutStartSec=600` to cover slow request-log pages; logs go to `journalctl --user -u opencode-usage-push.service`.

### Validation

```bash
cd <skill>
uvx ruff check --target-version py310 scripts/opencode_usage.py scripts/usage_report.py
uvx ruff format --check scripts/opencode_usage.py scripts/usage_report.py
node --test references/cloudflare-worker.test.mjs
```

When modifying publication code, mock `urllib.request.urlopen` and check that one successful publication sends exactly one multipart PUT containing both the HTML and metadata, including UTF-8 byte length and SHA-256 ETag. The Worker tests cover memory-cache reuse/expiry, isolation by KV binding, conditional GET, HEAD, and unavailable KV. For account changes, verify separate caches and histories, snapshot fallback, and account/period selection across refreshes.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HTTP 401 `Unauthorized` | Key revoked or stale console session; re-login or create an `all` service key |
| HTTP 403 on `/request-logs` | Expected for service keys; use a valid browser or saved session for the same account; otherwise existing key-cache data remains |
| HTTP 403 on other paths | Service key is `inference-only`; use a key with `all` permission |
| HTTP 500 on request logs | Transient ClickHouse backend; retries are built in, the day cache keeps the last good data |
| HTTP 400 `x-org-id is required` | Cookie auth needs the header; Bearer keys do not |
| Empty per-key table | `key_cache.json` is still backfilling, or the day is before 2026-09-22 |
| `unsupported cookie encryption` / unreadable plaintext | Wrong keyring item; use `search_items({"application": "chrome"})` |
| Report still shows an older period or renewal state | Click `刷新`; it only sees the last KV publish (timer every 10 min), with up to 60 seconds of Worker caching. Quota is a snapshot from that account's generation time |
| One account shows a history-snapshot warning | Restore that account's service key or log into its Console in Chrome, then regenerate the report to refresh the saved session |
| Period selector text is clipped | Keep the right padding for the native arrow and the full-width rule in the `max-width: 760px` media query |

## Notes

- Each workspace's key cache holds per-day per-key aggregates (`fetchedAt` + `keys`); entries are kept for `KEY_CACHE_MAX_AGE` (365) days. Deleting it forces a full backfill for that workspace.
- `history.json` contains personal pre-2026-09-22 usage totals; keep it out of public repositories.
- The HTML report is self-contained (Chart.js inlined at generation time with a CDN fallback). The refresh button fetches the full HTML (~250 KB); there is no separate JSON endpoint.
- Service keys and session cookies are account credentials. Store them only in private local config files with owner-only permissions; never embed them in the report, logs, examples or repositories.

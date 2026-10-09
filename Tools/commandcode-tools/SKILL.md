---
name: commandcode-tools
description: Query commandcode.ai current billing-period usage, credits and quota with the local Chrome login, generate or publish the HTML dashboard to Cloudflare KV, and wire the Command Code GOAT provider into opencode with all 62 models and reasoning-effort variants. Use for Command Code usage, per-model stats, cache hit rate, remaining credits or 5h/weekly limits, hosted report updates, or Command Code provider setup in opencode.
---

# Command Code tools

Two capabilities: usage reporting from the commandcode.ai console API, and opencode provider setup for the GOAT plan.

## When To Use

- current billing-period token/credit totals, daily buckets, per-model stats and cache hit rate
- remaining monthly credits, 5-hour/weekly window limits, subscription period
- generate the HTML dashboard or publish it to Cloudflare KV
- add the Command Code provider to opencode with every GOAT model and reasoning-effort variants

## Quick Start

### Usage report

```bash
cd <skill>/scripts

uv run commandcode_usage.py --by-model    # current billing period, terminal table
uv run commandcode_usage.py --json        # machine-readable summary
uv run usage_report.py                   # writes usage_report.html
uv run usage_report.py --push            # publish to Cloudflare KV
```

PEP 723 inline dependencies; `uv run` resolves `cryptography` and `secretstorage`. Do not run with plain `python`.

| Script | Options |
| --- | --- |
| `commandcode_usage.py` | `--by-model`, `--json`, `--profile` |
| `usage_report.py` | `--out`, `--push`, `--profile` |

Both scripts use the current subscription's `currentPeriodStart/End`; there is no `--days` option. JSON contains `{generatedAt, site, range, days, totals, models, requests, keys, quota, billing}`.

### opencode provider

Choose one credential source: use `/connect` with provider ID `commandcode` and omit `provider.commandcode.options.apiKey`, or use the template's environment-variable reference and export the key before starting opencode. An unset environment reference can override a valid saved credential and cause HTTP 401.

```bash
export COMMANDCODE_API_KEY=<cmd_api_key>   # environment mode only; create at https://commandcode.ai/settings/keys

# merge references/commandcode_provider.json into ~/.config/opencode/opencode.json
# remove options.apiKey from the merged provider when using /connect
# (merge script in references/add_commandcode_to_opencode.md)

opencode models commandcode | wc -l   # 62
```

Full setup, model table, and option mapping: `references/add_commandcode_to_opencode.md`.

## Implementation Details

### Auth

- Cookie-only: `__Secure-commandcode_prod_.session_data` + `__Secure-commandcode_prod_.session_token`, read from `~/.config/google-chrome` (override `CHROME_CONFIG_DIR`); Bearer API keys do not work on `/internal/*`.
- Cookie host key is `.commandcode.ai`; v11 plaintext carries a 32-byte `SHA256(host_key)` prefix that `decrypt_cookie` strips for both `.commandcode.ai` and `commandcode.ai`.
- Stale session: log in again at https://commandcode.ai in Chrome.

### Console API

Base `https://api.commandcode.ai`, cookie auth. Console routes live under `/internal/*`.

| Endpoint | Purpose |
| --- | --- |
| `GET /internal/usage/charts?from=YYYY-MM-DD&to=YYYY-MM-DD&granularity=day` | rows per day × model × provider: `requests`, `tokensIn/Out/Total`, `cacheReadInputTokens`, `totalCost` (raw API price), `consumedTotal` (plan credits), `cacheSavings`; `from` inclusive, `to` exclusive, UTC days |
| `GET /internal/usage/summary` | billing-period totals; `totalCost`/`totalCredits` are credits consumed with plan multipliers |
| `GET /internal/billing/credits` | `credits.monthlyCredits` (remaining) and `monthlyCreditsGranted`; `windowLimits.{fiveHour,weekly}` carry `used`/`cap`/`resetAt` (ms epoch) |
| `GET /internal/billing/subscriptions` | `planId`, `status`, `currentPeriodStart/End`; the month window resets at `currentPeriodEnd` |
| `GET /internal/usage?limit=100` | last 24 h only with cursor pagination; rows carry `tokensIn/Out`, `durationTotal`, `meta.{model,totalCost,traceId}` |
| `POST /internal/api-keys/list` with `{"orgId": null}` | key `id`/`name`/`createdAt`/`ownerUserId`/`ownerOrgId`; no usage fields |
| `GET /internal/orgs/{orgId}/analytics?from=...&to=...` | official frontend displays member spending for organization owners/admins; per-member tokens are unverified |

- Inspected personal-account usage APIs cannot split historical usage by key: request rows have no user/key identifier, charts aggregate by day/model/provider, and real or nonexistent `apiKeyId` filters return identical account totals from usage and summary. This does not establish that additional private logs are unavailable.
- The inspected account's keys share one `ownerUserId`, and `/internal/orgs` is empty for that account. Separate organization members differ from people sharing a personal account's keys. The report groups key names (`wty*` → `wty`, `wt*` → `wt`, others → `xfy`) in the key table only.
- `cacheReadInputTokens` is a subset of `tokensIn`; `tokensTotal = tokensIn + tokensOut`.
- Credits vs raw cost: the plan meters `consumedTotal` (deals and multipliers applied), while `totalCost` is the raw API price; the two differ.

### Billing-period totals

- Cards and core totals come from `/internal/usage/summary`. Read the summary before and after charts; retry if requests/input/output/total tokens/credits change. Missing subscription bounds or a summary without `periodBasis: billing-period` are errors.
- Chart buckets are UTC days from the period's start date through today. For a partial first day, derive its requests/input/output/total tokens/credits by subtracting later days from the stable billing summary. Daily and model core totals must match that summary.
- The partial first day's cache and raw API-price fields are unavailable and emitted as `null`. Attribute the first-day slice to a model only when the entire UTC start day has one model; otherwise retain an explicit unallocated first-day row. Do not proportionally distribute usage.
- The cache hit-rate card uses only `DATA.days` with non-null `cacheRead` and `tokensIn`: `sum(cacheRead) / sum(tokensIn)` over that same set. Show `0%` for zero cache reads with positive input; show `—` when no eligible days exist or their input sum is zero. Its subtitle states the actual covered UTC dates and identifies an excluded partial first day whose cache is unknown. Do not divide by full-period input or fill unavailable full-period cache totals; they remain `null`.
- The dashboard uses M units on the daily Token axis and six summary cards in a responsive 3/2/1-column layout. Unknown fields display `—`.

### Publish (Cloudflare KV)

- `--push` uploads keys `report` (HTML) and `report-meta` (JSON) with env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit); optional `CF_KV_KEY` (default `report`).
- `references/cloudflare-worker.js` serves fixed keys `report` and `report-meta` from the `USAGE_KV` binding. Leave `CF_KV_KEY=report` unless the Worker keys are also changed. Cloudflare Access is optional.
- Auto-publish example: `references/systemd/commandcode-usage-push.{service,timer}` runs `uv run usage_report.py --push` every 10 min with an `EnvironmentFile` holding the `CF_*` vars; adjust `WorkingDirectory` to the scripts directory. Installed units live at `~/.config/systemd/user/`; credentials at `~/.config/commandcode-usage/env`. Inspect logs with `journalctl --user -u commandcode-usage-push.service`.
- Automatic publishing requires the computer to remain on and connected, with valid Chrome session cookies. Refresh an open report page manually to see uploaded data.

### Provider API and opencode

- Base `https://api.commandcode.ai/provider/v1`; create keys at https://commandcode.ai/settings/keys.
- `/chat/completions` takes `reasoning_effort` (`off`, `low`, `medium`, `high`, `xhigh`, `max`); Claude `/messages` takes `output_config.effort` (`low`, `medium`, `high`, `xhigh`, `max`).
- GOAT allows every `opensource` model (62); premium models return `MODEL_NOT_IN_PLAN` (403).
- Provider config: one `commandcode` provider on `@ai-sdk/openai-compatible`, with `claude-sonnet-5-5` overriding per-model `provider.npm` to `@ai-sdk/anthropic`; variants carry `reasoningEffort` per model, or `effort` for Claude.
- The template uses `{env:COMMANDCODE_API_KEY}` so the key stays out of the config file. For credentials saved with `/connect`, omit `options.apiKey`; see the credential-source setup and troubleshooting in `references/add_commandcode_to_opencode.md`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no Chrome profile with commandcode.ai cookies` | log in at https://commandcode.ai in Chrome |
| HTTP 401/403 on `/internal/*` | stale session; re-login in Chrome |
| `Invalid 'Authorization' header or token.` / HTTP 401 on `/provider/v1/*` | check the credential source: an unset `{env:COMMANDCODE_API_KEY}` can override a valid `/connect` key. Remove `provider.commandcode.options.apiKey` to use the saved key, or export the variable before launching opencode; restart and smoke-test. If it still fails, check key validity. |
| Missing day in charts | `from` must include the day and `to` must be exclusive; pass tomorrow to include today |
| HTTP 400 on `reasoning_effort` | use `off` instead of `none` |
| `MODEL_NOT_IN_PLAN` | premium model; GOAT only includes `opensource` models |
| `opencode models commandcode` prints nothing | invalid JSON or wrong config path; re-run the merge script |
| Claude requests fail on `/chat/completions` | keep `claude-sonnet-5-5` on `@ai-sdk/anthropic`; Claude only serves `/messages` |

## Notes

- Chart buckets use UTC days; the request table shows local time in the dashboard. Recent-request APIs retain only the last 24 h and ignore `from`/`to`.
- The HTML report is self-contained; Chart.js is inlined at generation time with a CDN fallback.
- API keys and session cookies are account credentials; never commit them to a repository.

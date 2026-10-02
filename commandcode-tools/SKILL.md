---
name: commandcode-tools
description: Query commandcode.ai usage, credits and quota with the local Chrome login, generate or publish the HTML dashboard to Cloudflare KV, and wire the Command Code GOAT provider into opencode with all 62 models and reasoning-effort variants. Use when the user asks for Command Code usage, daily token/cost totals, per-model stats, cache hit rate, remaining credits or 5h/weekly limits, to refresh the hosted report, or to add Command Code models to opencode on a machine.
---

# Command Code tools

Two capabilities: usage reporting from the commandcode.ai console API, and opencode provider setup for the GOAT plan.

## When To Use

- daily token/cost totals for the last N days, per-model stats, cache hit rate
- remaining monthly credits, 5-hour/weekly window limits, subscription period
- generate the HTML dashboard or publish it to Cloudflare KV
- add the Command Code provider to opencode with every GOAT model and reasoning-effort variants

## Quick Start

### Usage report

```bash
cd <skill>/scripts

uv run commandcode_usage.py --days 7 --by-model    # terminal table
uv run commandcode_usage.py --days 7 --json        # machine-readable summary
uv run usage_report.py --days 14                   # writes usage_report.html
uv run usage_report.py --days 14 --push            # publish to Cloudflare KV
```

PEP 723 inline dependencies; `uv run` resolves `cryptography` and `secretstorage`. Do not run with plain `python`.

| Script | Options |
| --- | --- |
| `commandcode_usage.py` | `--days` (default 7), `--by-model`, `--json`, `--profile` |
| `usage_report.py` | `--days` (default 14), `--out`, `--push`, `--profile` |

### opencode provider

```bash
export COMMANDCODE_API_KEY=<cmd_api_key>   # create at https://commandcode.ai/settings/keys

# merge references/commandcode_provider.json into ~/.config/opencode/opencode.json
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
| `POST /internal/api-keys/list` with `{"orgId": null}` | key `id`/`name`/`createdAt`; no usage fields |

- The API exposes no per-key usage: charts, summary, usage list and billing endpoints return account-level data only, and `/alpha/*` with a Bearer key behaves the same. The report groups key names (`wty*` → `wty`, `wt*` → `wt`, others → `xfy`) in the key table only.
- `cacheReadInputTokens` is a subset of `tokensIn`; `tokensTotal = tokensIn + tokensOut`.
- Credits vs raw cost: the plan meters `consumedTotal` (deals and multipliers applied), while `totalCost` is the raw API price; the two differ.
- `/internal/orgs` is empty for personal accounts.

### Publish (Cloudflare KV)

- `--push` uploads keys `report` (HTML) and `report-meta` (JSON) with env vars `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN` (scope: Workers KV Storage Edit); optional `CF_KV_KEY` (default `report`).
- `references/cloudflare-worker.js` serves those keys from the `USAGE_KV` binding; keep the custom domain behind Cloudflare Access.
- Auto-publish example: `references/systemd/commandcode-usage-push.{service,timer}` runs every 10 min with an `EnvironmentFile` holding the `CF_*` vars; adjust `WorkingDirectory` to the directory that holds the scripts.

### Provider API and opencode

- Base `https://api.commandcode.ai/provider/v1`; create keys at https://commandcode.ai/settings/keys.
- `/chat/completions` takes `reasoning_effort` (`off`, `low`, `medium`, `high`, `xhigh`, `max`); Claude `/messages` takes `output_config.effort` (`low`, `medium`, `high`, `xhigh`, `max`).
- GOAT allows every `opensource` model (62); premium models return `MODEL_NOT_IN_PLAN` (403).
- Provider config: one `commandcode` provider on `@ai-sdk/openai-compatible`, with `claude-sonnet-5-5` overriding per-model `provider.npm` to `@ai-sdk/anthropic`; variants carry `reasoningEffort` per model, or `effort` for Claude.
- The config uses `{env:COMMANDCODE_API_KEY}` so the key stays out of the config file.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no Chrome profile with commandcode.ai cookies` | log in at https://commandcode.ai in Chrome |
| HTTP 401/403 on `/internal/*` | stale session; re-login in Chrome |
| Missing day in charts | `from` must include the day and `to` must be exclusive; pass tomorrow to include today |
| HTTP 400 on `reasoning_effort` | use `off` instead of `none` |
| `MODEL_NOT_IN_PLAN` | premium model; GOAT only includes `opensource` models |
| `opencode models commandcode` prints nothing | invalid JSON or wrong config path; re-run the merge script |
| Claude requests fail on `/chat/completions` | keep `claude-sonnet-5-5` on `@ai-sdk/anthropic`; Claude only serves `/messages` |

## Notes

- Charts buckets and `--days` use UTC days; the request table shows local time in the dashboard.
- The HTML report is self-contained; Chart.js is inlined at generation time with a CDN fallback.
- API keys and session cookies are account credentials; never commit them to a repository.

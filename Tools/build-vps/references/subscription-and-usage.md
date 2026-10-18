# RackNerd usage and subscription deployment

## Account and API

Use the current provider interface. RackNerd's ctrl panel superseded older
SolusVM workflows; do not assume an old API host still applies. Open the matching
VPS by its address and inspect its API tab.

- Reuse valid enabled credentials. Generate and enable them only within the
  user's authorized scope and applicable browser confirmation requirements.
  Do not regenerate an existing key just to obtain a copy.
- These per-VPS credentials also permit power operations. They are not read-only
  and must remain separate from the subscription token and downloaded profile.
- Store local credentials in the task directory, server credentials in a
  restricted configuration directory, and use mode `600` for both.

The observed API endpoint is:

```text
https://ctrl.racknerd.com/api/client/command.php
```

POST `key`, `hash`, `action=info`, `bw=1`, and `rdtype=json`. Verify both HTTP
success and JSON `status=success`; provider errors can also use HTTP 200. Confirm
the returned `ipaddress` matches `<SERVER_IPV4>` before using the counters.

The `bw` field is CSV:

```text
total_bytes,used_bytes,free_bytes,percent_used
```

The observed official meter updates about every five minutes and resets on the
first day of each month at midnight UTC. Reconfirm the panel's current policy.
These are provider-wide billed counters, not guest interface counters or per-node
3x-ui totals. Preserve byte units instead of guessing from rounded GB/TB labels.

Use HTTPS verification and POST bodies, not credential-bearing URLs. A normal
curl-style User-Agent resolved an observed HTTP 403 from this API; if a request
is challenged or rejected, inspect the response rather than disabling TLS or
attempting to solve a challenge through unsupported automation.

## Bundled implementation

Resources:
- `scripts/subscription_server.py`: standard-library HTTPS server and usage CLI.
- `assets/subscription-settings.json.template`: configuration to populate outside
  this skill, including the expected server address and strong random token.
- `assets/racknerd-subscription.service`: adaptable systemd unit.

Install populated operational files at these paths, or adapt the unit and
environment variables consistently:

| File | Destination | Mode |
| --- | --- | --- |
| Python program | `/usr/local/lib/racknerd-subscription/subscription_server.py` | 644 |
| Populated settings | `/etc/racknerd-subscription/settings.json` | 600 |
| API key/hash JSON | `/etc/racknerd-subscription/api.json` | 600 |
| Complete client YAML | `/etc/racknerd-subscription/clash.yaml` | 600 |
| Service unit | `/etc/systemd/system/racknerd-subscription.service` | 644 |

Use mode `700` for the configuration directory. The API JSON has exactly `key`
and `hash` fields. Generate at least 128 bits of randomness for the subscription
token and keep its URL private. Use the actual domain certificate/key paths.
An empty `listen_host` uses the wildcard listener; choose a loopback hostname
instead when placing a local reverse proxy in front.

The bundled unit runs as root to read root-only API/certificate files, restricts
filesystem writes to its state directory, and drops capabilities. Its suggested
subscription port is above the privileged-port range. Adapt permissions if using
a dedicated account; do not make API credentials or private keys world-readable.

After placement, daemon-reload, enable/start, and inspect the service. Ensure
the certificate renewal reload command restarts both the panel and subscription
service. A running Python SSL context otherwise retains its old certificate.

Query official counters from inside the VPS:

```bash
python3 /usr/local/lib/racknerd-subscription/subscription_server.py --usage
```

The script also accepts `RACKNERD_SUB_CONFIG` and `RACKNERD_SUB_DATA` directory
overrides. Those paths contain task-specific data, not skill resources.

## Download semantics

The token-protected endpoint is:

```text
https://<NODE_DOMAIN>:<SUBSCRIPTION_PORT>/sub/<SUBSCRIPTION_TOKEN>/clash.yaml
```

Every authorized download obtains official usage, with a short 15-second cache
for repeated GET/HEAD requests. Provider outages can use a same-month result up
to one hour old, marked stale with its check timestamp. Never reuse a previous
month's result after reset; return 503 if no usable counters exist.

Send these response headers:

```text
Subscription-Userinfo: upload=0; download=<USED_BYTES>; total=<TOTAL_BYTES>
Content-Disposition: attachment; filename=racknerd_<SERVER_IPV4>.yaml
Profile-Title: racknerd_<SERVER_IPV4>
Profile-Update-Interval: 1
Cache-Control: private, no-store, no-cache, max-age=0
CDN-Cache-Control: no-store
Cloudflare-CDN-Cache-Control: no-store
```

RackNerd exposes combined usage, so `download` carries the combined total and
`upload=0` is not a claim that no upload occurred. All nodes share the same VPS
quota, including its non-proxy traffic. Do not represent monthly reset as a
subscription expiration date. The profile update interval is an hourly client
hint; actual automatic behavior depends on the application.

## Optional server expiry display

When requested, set `expires_at` in the populated settings JSON to a positive
integer Unix timestamp in seconds. Omit it or leave it `null` when unverified.
The bundled service appends this field to both GET and HEAD responses:

```text
Subscription-Userinfo: upload=0; download=<USED_BYTES>; total=<TOTAL_BYTES>; expire=<EXPIRY_UNIX_SECONDS>
```

Clash Verge reads `expire` as subscription metadata. Putting a date only in a
YAML comment does not populate its subscription card. Refresh/import the remote
subscription to receive the header; preserve the user's active proxy/TUN state.
Distinguish verified response headers from a display actually observed in the UI.

### Source and renewal maintenance

Inspect the current API documentation and actual `action=info` response before
claiming expiry comes from the API. The observed ctrl response, including all
documented info flags (`status`, `ipaddr`, `bw`, `hdd`, `mem`), had no expiry or
billing-date field. Do not invent a field, derive expiry from the monthly traffic
reset, or assume that a future API has the same limitations.

When the API lacks expiry, use the matching VPS's billing product page and its
next due date, or a date explicitly supplied by the user. Match the service to
the target IP and hostname. Record the source, check time, date precision, and
timestamp convention in task artifacts. For a date-only source, UTC midnight
can represent the calendar date; verify the displayed date in the intended
client timezone and do not describe it as an exact shutdown time.

Official usage continues to refresh through the API; a manually configured
expiry does not. After renewal, recheck the billing date, update the operational
settings and its local source, restart the subscription service, fetch GET/HEAD,
and refresh the client subscription. State this maintenance requirement at
delivery. Do not schedule future checks unless requested.

## Imported profile names

Use the filename exactly as shown without surrounding quotes or escape
characters. Already imported profile names may require manual renaming or
re-importing even after the response header is corrected.

## Verify before delivery

Test populated GET and HEAD requests with normal TLS validation. Check:
- YAML parses, contains only intended nodes, and passes the intended Mihomo core.
- Wrong tokens return 404 without calling the provider API.
- API keys/hashes do not occur in response bodies, headers, or subscription URLs.
- Counters match the target VPS and units; CDN responses are not stale cache hits.
- Filename/title contain the complete server address and no quotes/backslashes.
- If expiry is configured, GET/HEAD contain the verified `expire` timestamp and
  it renders as the intended calendar date; report any UI verification limits.
- Renewal reloads every certificate consumer and services are enabled/running.

Run the bundled behavior tests without contacting a real provider:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
```

Sources:
- https://www.racknerd.com/ctrl-control-panel
- https://blog.racknerd.com/racknerd-launches-ctrl-a-proprietary-platform-built-for-the-ai-era/
- https://github.com/clash-verge-rev/clash-verge-rev/blob/dev/src-tauri/src/config/prfitem.rs

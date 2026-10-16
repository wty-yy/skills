# Domain proxying and nodes

## Cloudflare

Obtain the user's full hostname. Query public DNS if the local resolver returns
synthetic proxy addresses. Check Cloudflare response headers as well as DNS.

Standard HTTPS proxy ports currently include `443`, `2053`, `2083`, `2087`,
`2096`, and `8443`; verify the current official list. A random panel port will
not become reachable merely by enabling the DNS proxy.

An adaptable allocation, subject to existing listeners:

| Service | HTTPS port |
| --- | --- |
| Management panel | 443 |
| VMess WS | 8443 |
| VLESS XHTTP | 2053 |
| Subscription | 2087 |

Use a certificate matching `<NODE_DOMAIN>`. Full (strict) validates origin
identity; an address-only certificate is not a hostname certificate. Preserve
strict origin validation instead of silently changing zone-wide SSL settings.

HTTP-01 can work through Cloudflare if challenge requests reach the standalone
origin listener on port `80`. Check challenge routing and redirects before
retrying issuance. Account for occupied ports. Do not force renewals just to test
the schedule. Renewal must reload every service using the certificate.

Diagnose layers independently: 521 can indicate no usable origin listener; 526
can indicate origin certificate validation failure. A working panel is not proof
that a node transport works.

## Node parameters

Each node needs its own UUID, path, listener, and matching client configuration.

VMess WS TLS:
- Client: `type: vmess`, `alterId: 0`, `cipher: auto`, `network: ws`, `tls: true`.
- Set SNI and WS Host to the owned hostname, match the WS path, and verify TLS.
- Use `alpn: [http/1.1]`; maintain accurate clocks and test reconnect behavior.
- This is a compatibility option. Check release notices before upgrading a core
  that may deprecate VMess or WS.

VLESS XHTTP TLS:
- Client: `type: vless`, `network: xhttp`, `tls: true`, `packet-encoding: xudp`.
- Start with `alpn: [h2]` and `mode: packet-up`; match host and path on both sides.
- Use ordinary VLESS `decryption: none` on the TLS-backed server. Do not add
  Vision flow to this setup or stack traditional mux over XHTTP multiplexing.
- Streaming modes can require additional CDN configuration; test them separately.

Cloudflare terminates outer TLS. Ordinary VLESS without extra Encryption has a
different trust boundary from VMess's protocol-level payload encryption. Explain
that tradeoff; neither newer transport nor CDN routing guarantees higher speed.

## REALITY boundary

REALITY is excluded from the default workflow. It was abandoned after actual
client compatibility failures and the user selected two domain-based options.
Reassess exact versions if explicitly requested in a future task. Do not silently
lower protocol requirements, install another engine, or move the management panel
to pursue an unrequested fallback.

## Test actual traffic

Populate the client template and run `mihomo -t`. Use an isolated core bound to
a loopback address with a separate home directory and unused diagnostic ports;
disable TUN in the diagnostic copy and do not change system proxy settings.
Inspect the installed client's actual core version. Testing a separate newer
binary does not establish compatibility with the installed client.

An existing active proxy can return Fake-IP addresses through the system
resolver. The isolated core does not share that core's Fake-IP mapping. If node
or destination DNS returns synthetic addresses, give the diagnostic copy its
own DNS resolver, including `proxy-server-nameserver` for the node hostname.
For example, after checking that the loopback port and upstream are usable:

```yaml
dns:
  enable: true
  listen: 127.0.0.1:10553
  enhanced-mode: redir-host
  nameserver:
    - https://1.1.1.1/dns-query
  proxy-server-nameserver:
    - https://1.1.1.1/dns-query
```

This is a diagnostic override, not a change to the served profile or the user's
system resolver. Confirm real node resolution in the diagnostic logs; do not
silently change the transport or disable certificate verification after a generic
TLS EOF. Preserve logs before deleting a failed test's temporary directory.

First prove node connectivity without rule providers when needed, using a
temporary `MATCH,PROXY` diagnostic copy. Then test the downloaded full profile
with its intended rules restored. When providers are enabled, follow
[automatic-rules.md](automatic-rules.md) for readiness checks before routing
probes. Select each node explicitly, request a small HTTPS endpoint through the
local proxy, and confirm both the selected chain and returned server address.
Stop the diagnostic core in a cleanup path even if an assertion fails, and
confirm its listeners have closed. Record untested UDP applications and
performance separately.

Sources:
- https://developers.cloudflare.com/fundamentals/reference/network-ports/
- https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/
- https://developers.cloudflare.com/network/websockets/
- https://wiki.metacubex.one/config/proxies/vmess/
- https://wiki.metacubex.one/config/proxies/vless/
- https://wiki.metacubex.one/config/proxies/transport/
- https://wiki.metacubex.one/config/proxies/tls/
- https://wiki.metacubex.one/config/dns/

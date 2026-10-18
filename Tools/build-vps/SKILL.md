---
name: build-vps
description: Bootstrap a user-owned VPS with key-only SSH, 3x-ui, optional Cloudflare domain proxying, VMess and VLESS XHTTP nodes, and Clash Verge subscriptions with RackNerd bandwidth usage. Use for this provisioning workflow or its maintenance, not unrelated server administration.
---

# Build VPS

Follow the requested stages and reuse facts already established in the session.
This workflow does not itself authorize changes to another server or account.

## Inputs and artifacts

Collect only missing inputs: provider, server address, SSH port and user,
bootstrap authentication, key name and host alias, working directory, owned
domain availability, and intended Clash Verge/Mihomo version.

- Keep operational scripts, notes, subscription profiles, API credentials, and
  access information in the current task directory or the user's output directory.
  Restrict secret files to mode `600` and exclude them from version control.
- Use `~/.ssh` for SSH identity files, known hosts, and SSH configuration only.
- Keep this skill free of deployment-specific addresses, domains, credentials,
  UUIDs, and subscription tokens. Use placeholders such as `<SERVER_IPV4>`,
  `<NODE_DOMAIN>`, and `<SSH_ALIAS>` in reusable instructions.
- Record actual actions, backups, versions, effective settings, and verification
  outside the skill. Distinguish completed work from instructions only.
- Preserve existing identities, services, and clients. Do not regenerate working
  credentials, change ports, or reinstall software without a task-specific reason.

## Six-stage workflow

### 1. Request IPv6 when applicable

Confirm whether the provider is RackNerd unless already known. If IPv6 is already
allocated, inspect that VPS's Network tab and guest configuration; skip the
allocation request. Otherwise, give RackNerd users the path
`Customer area -> Submit Ticket -> Support -> matching VPS`.

**Subject:** Request for IPv6 Address Allocation

```text
Hello RackNerd Support,

Please allocate IPv6 addresses to my VPS with IPv4 address <SERVER_IPV4>.
I would like the maximum number of IPv6 addresses available for this VPS
under your allocation policy.

Thank you!
```

Let the user submit unless they explicitly request submission on their behalf.
A ticket request is not an assigned or configured address. Record the provider's
reply and network parameters before applying network changes. Other providers
require their own process. For an assigned address that needs guest configuration,
read [references/ipv6.md](references/ipv6.md); allocation alone does not prove
IPv6 connectivity.

### 2. Establish key-only SSH

Read [references/ssh-and-panel.md](references/ssh-and-panel.md). Generate the
requested local identity, deploy only its public key, and configure the host
alias. Test a fresh key-only connection before disabling passwords. Preserve a
recovery connection, back up the configuration, inspect effective settings, and
reload SSH. A reused multiplexed session does not prove that key login works.
For an IP replacement, follow the migration section in the same reference;
preserve existing subscription URLs when the hostname and service continue.

### 3. Install 3x-ui

Use the official installer and current upstream documentation. For Debian/Ubuntu:

```bash
apt update -y && apt install -y curl socat
```

Inspect this official script before executing the exact downloaded snapshot:

`https://raw.githubusercontent.com/MHSanaei/3x-ui/master/install.sh`

Record its digest and resolved release. Prefer SQLite for a small single-server
setup, random credentials and paths, trusted HTTPS, and automatic renewal.
An initial IP certificate is an option when supported; use a matching hostname
certificate after domain migration. If the owned hostname already points to this
VPS and HTTP-01 reaches it, install with domain TLS directly. Keep installer logs
and credentials restricted.
Verify autostart, HTTPS, and authenticated login with normal session/CSRF handling.
Implementation details are in the SSH/panel reference.

### 4. Bind an optional Cloudflare domain

Ask whether the user owns a domain unless already established. If not, skip
Cloudflare and leave the domain-dependent node stages pending. Do not silently
deploy REALITY as a substitute; it is excluded from this workflow's defaults.

Have the user onboard an owned domain if necessary. Inspect an existing `A`
record before creating one; reuse a matching server address, automatic TTL, and
enabled proxy. Obtain the full hostname or URL from the user when not yet known.

Read [references/domain-and-nodes.md](references/domain-and-nodes.md). Validate
public DNS, Cloudflare responses, a supported origin port, and a matching origin
certificate. A saved orange-cloud DNS record alone does not prove connectivity.

### 5. Review the node plan

| Option | Intended use | Essential parameters |
| --- | --- | --- |
| VMess + WS + TLS | Compatibility option | AEAD, `alterId: 0`, separate UUID and WS path |
| VLESS + XHTTP + TLS | Upgrade candidate | H2, `packet-up` initially, separate UUID and path |

Both can share an owned hostname through Cloudflare with distinct supported
HTTPS ports. Neither is universally faster. Check the actual client core version;
documented protocol support is not an end-to-end test.

If the user requests review first, stop before creating listeners. Otherwise,
continue within the authorized scope using the node reference and
[assets/clash-nodes.yaml.template](assets/clash-nodes.yaml.template).
Honor the requested protocol, node names, count, and default selection. For
multiple dedicated IPv6 exits, configure every allocated address using the IPv6
reference, then follow the node reference's IPv6 routing and IPv4 fallback plan.

### 6. Deploy nodes, subscription downloads, and official traffic usage

Back up the panel database with SQLite's online backup API. Inspect existing
inbounds and ports. Use supported panel APIs, preserve unrelated listeners,
reuse matching managed inbounds, and reject conflicting identities or ports.
Inspect the generated runtime configuration after applying changes.

Read [references/subscription-and-usage.md](references/subscription-and-usage.md)
for API credentials, subscription deployment, response headers, caching, and
certificate reloads. The bundled service and systemd template are reusable
implementation resources. API credentials must never enter the client profile.
When expiry display is requested, use the reference's optional `expires_at`
setting with a verified source and renewal-update procedure.

Generate a complete profile with a selection group and explicit routing. When
automatic regional split routing is requested, merge
[assets/clash-rules.yaml](assets/clash-rules.yaml) following
[references/automatic-rules.md](references/automatic-rules.md). A final `MATCH`
rule alone is not regional split routing.

Apply the selected routing policy to both the generation workflow and the actual
server-served profile. Updating only this skill's templates does not update an
existing subscription. Fetch the public subscription URL after deployment and
assert that its `rule-providers` and ordered `rules` match the intended policy.

Derive names from the actual server address:

```text
Content-Disposition: attachment; filename=racknerd_<SERVER_IPV4>.yaml
Profile-Title: racknerd_<SERVER_IPV4>
```

Use an unquoted ASCII filename. Quotes or backslashes must not become part of
the downloaded filename or imported profile name.

## Completion evidence

- Fresh SSH key login succeeds, password login is rejected, and the alias uses
  the intended server and identity.
- Panel and subscription services run and autostart. Renewal reload commands
  cover every service consuming the certificates.
- The downloaded profile passes `mihomo -t`. Select and test each retained node
  in an isolated local core, confirming the actual outbound server address.
  Isolate diagnostic DNS when the system resolver returns another core's Fake-IP
  addresses. Do not change the user's active proxy/TUN settings just to test.
- Verify GET/HEAD, filename/title, usage headers, wrong-token rejection, and
  absence of provider credentials from subscription responses.
- If rule providers are enabled, check formats, initial downloads, refresh
  settings, and representative routing decisions. Wait for provider readiness
  before testing the full routing profile; a responding controller is insufficient.
- Stop task-only diagnostic processes. Report final URLs, paths, usage semantics,
  and untested scope. Do not claim speed or UDP validation from a TCP-only check.

After changing the bundled subscription service, run its tests and the
skill-creator package validator.

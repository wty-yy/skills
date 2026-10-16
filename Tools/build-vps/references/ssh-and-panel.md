# SSH and panel implementation

## SSH bootstrap

Inspect existing identities and effective SSH settings. Back up the local config;
never overwrite an existing identity. Connect using the supplied bootstrap method
and normal host-key verification. Create the requested Ed25519 identity locally,
choosing passphrase handling for the user's interactive/unattended requirements.
Deploy only its public key. Preserve existing authorized keys, line boundaries,
and ownership; avoid duplicate entries. Use mode `700` for SSH directories and
`600` for private keys, authorized keys, and client configuration.

Add a specific alias before broader matching blocks when necessary:

```sshconfig
Host <SSH_ALIAS>
  HostName <SERVER_IPV4>
  User <SSH_USER>
  Port <SSH_PORT>
  IdentityFile ~/.ssh/<KEY_NAME>
  IdentitiesOnly yes
  PubkeyAuthentication yes
  PreferredAuthentications publickey
  PasswordAuthentication no
  KbdInteractiveAuthentication no
```

`IdentityFile` can accumulate. Inspect `ssh -G <SSH_ALIAS>` instead of assuming
`IdentitiesOnly` alone selects exactly the intended identity.

Verify without connection reuse:

```bash
ssh -S none -o ControlMaster=no -o BatchMode=yes <SSH_ALIAS> 'id -un; hostname'
```

Before disabling passwords, retain a recovery session and back up server config.
Inspect the main file, included files, and `Match` blocks. OpenSSH commonly uses
the first obtained value: a late `99-` file may not override earlier cloud-init
settings. Choose a drop-in position based on the actual include order.

```text
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
```

Apply the root directive only when root key access is intended. Validate with
`sshd -t` and `sshd -T -C` for the intended user and peer. Reload the correct
service. A short scheduled rollback can protect remote-only changes; cancel it
after fresh login verification. Never leave a success-invalidating rollback armed.

Finally, test a fresh key connection and a new batch-mode connection with public
keys disabled and password/keyboard-interactive preferred. Expect rejection with
only public-key authentication offered; do not submit repeated password guesses.

## Official 3x-ui installation

Inspect installed software, ports, architecture, disk, and memory. Do not blindly
reinstall a panel or perform an unrelated full-system package upgrade.

Fetch, inspect, and record the digest of the official installer before running
that snapshot. The observed installer supported `XUI_NONINTERACTIVE=1`,
`XUI_DB_TYPE=sqlite`, `XUI_SSL_MODE=ip`, and domain mode with
`XUI_SSL_MODE=domain` plus `XUI_DOMAIN=<NODE_DOMAIN>`. It also supported
`XUI_PANEL_PORT` and `XUI_SERVER_IP`. Verify these in the downloaded script
rather than assuming a moving branch has the same interface. If DNS and HTTP-01
already reach the intended VPS, use domain TLS directly and choose an available
Cloudflare-supported panel port. Otherwise, use the appropriate initial setup
and verify TLS before treating it as complete. Confirm the actual incoming
address before IP certificate issuance: outbound detection can report another
NAT/routed address.

Record releases, service units, database, port, base path, certificate paths, and
renewal commands. Installer logs can contain passwords/tokens: restrict them and
keep secrets out of general notes. Initial result files may become stale after
URL changes; maintain current access metadata in the task directory.

For a session-authenticated API, GET the login page, retain cookies, read the
CSRF meta token, and POST credentials with matching Origin/Referer. Refresh the
authenticated page/token before mutations. A missing CSRF token can cause 403;
do not disable CSRF or certificate verification to make requests work.

Observed routes, relative to the configured base path:

```text
panel/api/inbounds/list
panel/api/inbounds/add
panel/api/inbounds/update/<INBOUND_ID>
panel/api/server/restartXrayService
```

Confirm these against the installed release. Wire responses may decode
`settings`, `streamSettings`, and `sniffing` as objects while writes expect JSON
strings. Decode conditionally. Verify actual runtime configuration and traffic.

Sources:
- https://github.com/MHSanaei/3x-ui
- https://github.com/MHSanaei/3x-ui/blob/master/install.sh

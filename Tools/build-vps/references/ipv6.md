# Configure an allocated IPv6 address

Use this reference only when the VPS has an assigned IPv6 address and guest
network configuration needs attention. Keep an existing working setup.

## Establish the parameters

Select the provider instance by the requested IPv4 address. Record its assigned
IPv6 address, prefix length and gateway from that instance's Network tab or a
provider reply that identifies the same VPS. A ticket about another instance or
a generic setup article is not evidence for this server. Do not derive a gateway
or an allocation size from an example.

Compare the allocation with `ip -6 address`, `ip -6 route`, and the configuration
owned by the guest's network manager. A global address listed in the control
panel may still be absent from the guest. A link-local address alone does not
establish public IPv6 access.

## Apply and verify

For a Netplan guest:

1. Back up the active configuration and identify whether cloud-init or the
   provider manages it. Preserve the working IPv4 address, routes, DNS and renderer.
2. Add the confirmed IPv6 address/prefix and IPv6 default route without replacing
   existing entries or appending duplicates. Keep Netplan files restricted.
3. Run `netplan generate` before applying. Preserve an SSH recovery session and
   use `netplan try` or a short scheduled restore when remote access could be lost.
   Verify the actual restored state if a trial expires or is canceled.
4. Inspect the resulting address and route. Wait for an address marked
   `tentative` to finish Duplicate Address Detection before interpreting an early
   failed probe. A persistent `tentative` state or `dadfailed` requires diagnosis;
   do not disable DAD to force success.
5. Check the gateway and a public IPv6 destination, then make an HTTPS request
   with IPv6 forced and inspect the returned source address. Also verify a fresh
   IPv4 SSH connection. A gateway response alone does not prove public routing;
   an ICMP timeout alone does not prove HTTPS is unavailable.
6. Cancel any scheduled rollback after connectivity is verified. If verification
   fails, restore the known configuration and check access instead of repeatedly
   applying guessed parameters. Record any provider/cloud-init overwrite risk;
   do not reboot solely to test persistence without a task-specific reason.

Use the equivalent validation and recovery steps for other network managers.
Configuring server IPv6 does not itself require changing client DNS, enabling
IPv6 in a Clash profile, or adding a Cloudflare AAAA record.

Sources:
- https://netplan.readthedocs.io/en/stable/netplan-try/
- https://docs.kernel.org/networking/ip-sysctl.html

# Automatically updated Clash routing

Use Mihomo HTTP `rule-providers` when the user wants rule-based regional split
routing. The providers download public routing lists; they are separate from
the private subscription profile and provider usage API.

Use MetaCubeX's `meta-rules-dat` repository, `meta` branch. The accompanying
`assets/clash-rules.yaml` is a merge fragment, not a complete subscription. Keep
the populated node definitions and the `PROXY` selection group from the client
template. Confirm URLs and file availability when using the skill.

The fragment implements this ordered policy:
1. Private domains and private networks go direct.
2. Chinese domains go direct.
3. Known non-Chinese domains use `PROXY`.
4. Other Chinese destination addresses go direct.
5. Unmatched traffic uses `PROXY`.

Rules are first-match wins. Keep explicit user overrides before broad regional
rules. This baseline does not claim a separate classification for every service.
Ask for service-specific exceptions only when they matter to the user's task.

Each provider uses `type: http`, `format: mrs`, and `interval: 86400` for daily
refresh. Domain lists use `behavior: domain`; address lists use `behavior:
ipcidr`. MRS does not support `classical` behavior. Relative cache paths must stay
inside the core's allowed home directory.

The fragment uses `proxy: PROXY` for downloading rules through a configured node,
which can help when the rule source is not directly reachable. Confirm that the
selected node and hostname resolution work without those rule files first.

Advertising blocking is optional and can break application functionality. When
requested, add a domain provider using this URL and place its REJECT rule before
broad direct/proxy matches:

```text
https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/category-ads-all.mrs
```

Do not send the private node subscription URL to a public subscription converter
to obtain these rules. They can be merged locally or generated directly by the
subscription service's configuration workflow.

Verify the complete profile with the user's actual core, initial provider
downloads, and representative private, domestic, foreign, and fallback routing.
Keep provider refresh distinct from full-subscription refresh and quota updates.

Start the full-profile test from an empty provider cache. A responding
`/version` endpoint only proves controller readiness; provider downloads may
still be running. Poll `/providers/rules` with a bounded deadline and require
every expected provider to be loaded, with a nonzero `ruleCount` for these
bundled lists, before switching nodes or making routing assertions. Keep the
bootstrap selection stable during initial downloads. On timeout, preserve logs
and inspect DNS, transport and download errors rather than treating an empty
rule set or a temporary `MATCH` configuration as a successful split-routing test.

For an existing subscription, back up and update the served profile atomically,
and update its generator so future regeneration preserves the rule providers.
Fetch the public URL and inspect the returned configuration; a changed local
template alone is not evidence that a subscribed client receives the new rules.
Verify an empty-cache core can download providers through the configured node.
In the client, confirm rule mode and refresh/reselect the subscribed profile.
`RULE-SET` entries reference many downloaded matches rather than expanding every
domain into the profile's top-level rule list. If old rules persist, inspect any
local merge or script that replaces the subscription's `rules` section.

Sources:
- https://wiki.metacubex.one/config/rule-providers/
- https://wiki.metacubex.one/config/rules/
- https://github.com/MetaCubeX/meta-rules-dat
- https://wiki.metacubex.one/api/

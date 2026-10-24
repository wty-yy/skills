# OpenCode Go for DSH

## Route and credentials

The bundled [opencode-go.patch.yml](opencode-go.patch.yml) adds DeepSeek models to DSH `0.2.1-rc.2` and dsh-tui `0.17.0`, verified on 2026-10-24. It adds a provider without changing the existing default.

| Route ID | Resolved API | Base URL | Credential reference |
| --- | --- | --- | --- |
| `opencode-go` | `openai-completions` from the native catalog | `https://opencode.ai/zen/go/v1` | `OPENCODE_GO_API_KEY` |

Store the provided key in the managed credential document with mode `600`; merge this shape with existing references and records:

```yaml
version: 1
refs:
  OPENCODE_GO_API_KEY: <user-provided-key>
```

Use the credentials service or a masked input and atomic file replacement. Keep the key out of command arguments, logs, and repository files. Redacting only `sk-...` misses OpenCode's `oc_sk_...` keys; avoid displaying credential documents at all.

When the user asks to reuse OpenCode's DeepSeek configuration, inspect its active provider endpoint and model IDs without printing credentials. Reuse the user's supplied key in preference to an older stored key. Distinguish Go subscription routes from pay-as-you-go and free-tier routes; the same model name does not establish entitlement.

## Preserve native session handling

Use the exact route ID **`opencode-go`** and **omit `api`** from its configuration. In the verified DSH adapter, an installed catalog route without `api` reuses the native provider implementation. The native OpenCode Go provider wraps requests with `x-opencode-session` using the actual conversation's `sessionId`.

An explicit `api: openai-completions` selects a generic protocol factory in this version and bypasses that wrapper. Renaming the route to a custom ID also loses native provider dispatch. Do not work around this with a fixed session header shared by every conversation.

Inspect the installed `dsh-llm-pi-ai` and pi-ai provider implementation before applying this seed to another version. Confirm that the native `opencode-go` provider exists and carries session headers. If it is unavailable, identify a compatible supported release or adapter before claiming a working connection.

The native model catalog supplies the API, input modalities, output limits, DeepSeek thinking format, and assistant `reasoning_content` replay rules. The seed intentionally declares only model IDs and the verified endpoint. Do not copy Command Code's compatibility or Responses settings into this route.

## Merge and refresh models

1. Read the saved key without printing it and fetch `GET {baseURL}/models` with Bearer authentication and a `deepseek-harness/<installed-version>` User-Agent. Keep TLS verification enabled. Start with the existing working OpenCode Go endpoint; verify any replacement endpoint before saving it.
2. Reconcile requested DeepSeek IDs with the live list and installed native model catalog. The verified list exposed `deepseek-v4.1-flash` and `deepseek-v4-pro`; OpenCode's older local configuration still named `deepseek-v4-flash`. For a generic request to add DeepSeek, offer the current listed models. If an explicitly selected model is unavailable, ask before substituting it. A successful listing does not prove inference access.
3. Back up each target `cordis.patch.yml` and merge the seed into `llm-pi-ai.config.providers` for `web`, `dsh-tui`, and the verification `headless` profile. Preserve other providers and user settings; update the existing route instead of duplicating it.
4. Preserve the saved default when adding this provider. For a new installation or an explicit default change, use the following selection after confirming the model remains available. For verification only, save it as a temporary `route-check.yml` and pass `--patch` as shown in `SKILL.md`.

```yaml
- id: agent-default-model
  config:
    provider: opencode-go
    model: deepseek-v4.1-flash
    reasoningEffort: high
```

5. Enable `credentials` in headless when needed, as described in `SKILL.md`. Dump all target profiles and confirm the provider key, endpoint, model IDs, credential reference, and omitted `api`. The effective API comes from the native catalog.

## Verify and select

Run the short reply and sequential tool checks from `SKILL.md` through the temporary selection overlay. The verified V4.1 Flash route returned `OK`, completed four sequential `bash` calls, replayed their history, and produced a final answer. V4 Pro was listed and configured; it was not exercised end to end. Do not describe catalog presence or a successful config dump as a tested inference request.

Use `dsh web` or `dsh-tui`, then select **OpenCode Go** and the desired model; TUI uses `/model`. Existing sessions retain their selected route. New sessions use the saved default, which remains unchanged when only adding a provider.

For failures, distinguish missing credentials, HTTP 401, plan or privacy restrictions on HTTP 403, incorrect endpoint paths on HTTP 404, and missing session headers. Inspect the response and installed adapter before changing the key or protocol. OpenCode's documentation notes that DeepSeek access can depend on the workspace's allowed regions; report that restriction without changing account privacy settings automatically. Keep retries bounded.

## Sources

- [OpenCode Go](https://opencode.ai/docs/go/): model availability, workspace restrictions, client identity, and session requirements.
- [OpenCode harness integration](https://opencode.ai/v2/docs/console/harnesses/): API keys, plan-specific endpoints, and session headers. Endpoint documentation may change; use a verified working URL for the installed client.
- Installed `@deepseek-ai/dsh-llm-pi-ai/lib/index.js` and `@earendil-works/pi-ai/dist/providers/opencode-go.js`, `opencode-headers.js`, and `opencode-go.models.js`: native dispatch, per-conversation headers, and model metadata for the installed version.

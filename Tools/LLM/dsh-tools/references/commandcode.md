# Command Code GOAT for DSH

## Routes and credentials

The bundled [commandcode.patch.yml](commandcode.patch.yml) is a configuration seed verified with DSH `0.2.1-rc.2` and dsh-tui `0.16.1` on 2026-10-24. Its catalog contains 60 distinct model IDs and an additional Responses route for the default DeepSeek model. Treat this as a snapshot, not a promised plan entitlement or a permanently complete model list.

| Route ID | API | Base URL | Purpose |
| --- | --- | --- | --- |
| `commandcode-responses` | `openai-responses` | `https://api.commandcode.ai/provider/v1` | Default DeepSeek V4.1 Flash, with `high` reasoning |
| `commandcode` | `openai-completions` | `https://api.commandcode.ai/provider/v1` | Other compatible GOAT models |
| `commandcode-claude` | `anthropic-messages` | `https://api.commandcode.ai/provider` | Claude models included in the plan |

All routes reference `COMMANDCODE_API_KEY`. Keys are created at [Command Code API keys](https://commandcode.ai/settings/keys). The Anthropic SDK appends `/v1/messages`; giving its route a base URL ending in `/v1` produced a doubled version segment and HTTP 404 in the tested setup. Do not use `/chat/completions` for Claude-only models.

The managed credential document uses this shape; merge the reference into the existing document instead of replacing other keys or records:

```yaml
version: 1
refs:
  COMMANDCODE_API_KEY: <user-provided-key>
```

Use the credentials service when available. Otherwise edit with a round-trip YAML parser, use an atomic replacement with owner-only permissions, and avoid concurrent credential writes. Store the key only in the managed credential file. Do not pass it in `curl -H ...` arguments or print it through `cat`, environment dumps, debugging, or session logs. Regexes that only redact `sk-...` do not protect Command Code's `user_...` keys or stored OAuth grants.

## Merge configuration

1. Back up each existing target `cordis.patch.yml`. Inspect the composed tree for the `llm-pi-ai`, `agent-default-model`, and `credentials` IDs.
2. In `llm-pi-ai.config.providers`, merge the three named routes from the seed. Keep other routes. Preserve custom models and compatibility changes unless updating them is required for the requested connection; reconcile rather than blindly replacing an existing provider definition.
3. Set `agent-default-model.config` to the chosen provider, model, and effort. The seed selects `commandcode-responses`, `deepseek/deepseek-v4.1-flash`, and `high`.
4. Repeat for `web`, `dsh-tui`, and the verification `headless` profile. Initialize a shipped headless profile with `dsh headless --dump-config` if needed. To use the managed store there, merge this separate override:

```yaml
- id: credentials
  disabled: false
```

5. Parse the resulting files and dump each profile. The seed is a top-level list of Loader patches, not a legacy `llm-pi-ai:` section. Do not duplicate entry IDs or overwrite user plugin settings.

`apiKeyEnv` is a **reference name**, not a literal API key. Current DSH resolves it per request from the managed credentials file, then launch environment and `.env` fallbacks. Saving a managed credential is sufficient; no shell-profile export is needed. Old releases may behave differently, so use the installed credential plugin documentation when adapting this workflow.

## Refresh the model catalog

Use `GET https://api.commandcode.ai/provider/v1/models` with the user's saved Bearer credential. Use a client identifying itself with a normal User-Agent; the default Python urllib User-Agent received Cloudflare `403 / 1010` during verification, while a normal browser-style User-Agent succeeded. Never bypass a challenge or disable TLS verification.

- Compare exact model IDs, context lengths, and `supported_endpoints` with the seed. Retain the user's selected model when it is still served.
- A successful model listing does **not** prove GOAT plan access. In the verified account the endpoint listed premium models too. Use current plan/category evidence from Command Code, an existing verified GOAT catalog, or a small request for a selected model; do not import every listed model as entitled or probe all models with billed requests.
- Skip removed IDs; do not silently map them to a differently named model. If the requested default has disappeared, choose a currently supported model with the user instead of leaving a broken default.
- Keep Chat Completions on `commandcode`, Anthropic on `commandcode-claude`, and only Responses-capable models on `commandcode-responses`. DSH's route-level `api` applies to every model on that route.
- Carry forward known input modalities and output caps; `/models` context length alone does not establish image support or maximum output. The seed carries recorded catalog capabilities; only selected models were exercised end to end. Verify an image request before claiming a particular route's vision support works.
- Translate offered thinking levels through model `reasoningEfforts`, for example `{off: off, low: low, high: high, max: max}`. Quote `off` in YAML; YAML 1.1 parsers may otherwise turn it into a boolean. Preserve `requiresReasoningContentOnAssistantMessages` for Chat Completions models that replay `reasoning_content`; it does not belong on Responses models.
- Map the gateway's `reasoning_effort` wire values directly. Avoid provider-specific thinking formats or unsupported effort names unless the endpoint requires them and a request verifies them.

The sibling `commandcode-tools` skill can supply console-side plan/category evidence when installed, but is not required to apply this seed. Its opencode JSON cannot be pasted directly into DSH.

## Transport failures

In the verified setup, Chat Completions intermittently closed an HTTP 200 SSE response roughly three seconds into generation. Direct Node `fetch` outside DSH also failed with `terminated`, `cause: other side closed`, and `UND_ERR_SOCKET`, including on the `-fast` alias. The DSH log showed `TRANSPORT` and exhausted five retries. This evidence indicates a broken upstream stream on those attempts; it does not establish whether the gateway, its upstream, or the network path caused the close.

The same model's Responses route completed direct longer requests and a DSH run with four sequential tools followed by a long answer. This is the reason for the seed's preferred route. It is a tested mitigation, not a guarantee that every future `TRANSPORT` failure has the same cause or that all Responses endpoints are more reliable.

When a failure recurs:

1. Inspect the latest failed session's `turn/end`, `assistant/attempt`, and `llm/retry` events. Protect credentials and unrelated task content when reading logs. Session `.jsonl.zstd` files contain concatenated frames: `zstd -dc` reads the complete log; Node's one-shot decoder may show only the header frame.
2. Distinguish `AUTH` / HTTP 401, `MODEL_NOT_IN_PLAN` / HTTP 403, HTTP 404 route errors, `RATE_LIMIT`, and `TRANSPORT`. Do not rotate a working key or blame authentication based on `terminated` alone.
3. Compare a small direct provider request with the same model and protocol; record response status, elapsed time, stream completion, and nested transport cause, excluding the key and full request body.
4. For the observed Chat Completions failure, test the Responses-capable route with a temporary overlay before changing defaults. Retain the original route for other models. Existing sessions must explicitly switch to the new route through `/model`.
5. Keep retries finite (`normal`, five retries in the seed). Stop after the configured budget and report persistent failures. Increasing timeouts or enabling unlimited retries does not repair an upstream socket close.

`dsh-tui doctor` may report a missing `DEEPSEEK_API_KEY` even though this custom provider uses a valid `COMMANDCODE_API_KEY`. Check the configured route's own reference before treating that generic diagnostic as a connection failure.

## Sources

- [DeepSeek Harness repository and installed package references](https://github.com/deepseek-ai/deepseek-harness): inspect the installed `dsh-llm-pi-ai`, `dsh-credentials-local`, `dsh-headless`, and `dsh-settings` READMEs for the active version.
- [dsh-tui repository](https://github.com/ccch1mneyyy/dsh-TUI): profile initialization, CLI commands, and `/model` behavior.
- [Command Code](https://commandcode.ai): live provider catalog, plan access, and user API keys.

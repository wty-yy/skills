# Add Command Code (GOAT) to opencode

Wire the Command Code Provider API into opencode as provider `commandcode`: 62 GOAT-plan models with reasoning-effort variants where the model supports them.

## API

- Base URL: `https://api.commandcode.ai/provider/v1`
- Auth: `Authorization: Bearer <CMD_API_KEY>`; Claude endpoints also accept `x-api-key`
- Endpoints: `/chat/completions` (OpenAI-compatible, most models), `/messages` (Claude only), `/responses`, `/models`
- Model list: `GET https://api.commandcode.ai/provider/v1/models` (public, no auth)
- API key: create at https://commandcode.ai/settings/keys; the same key authenticates the CLI and the API

Reasoning effort fields:

| Endpoint | Request field | Allowed values |
| --- | --- | --- |
| `/chat/completions` | `reasoning_effort` | `off`, `low`, `medium`, `high`, `xhigh`, `max` (not `none`) |
| `/messages` (Claude) | `output_config.effort` | `low`, `medium`, `high`, `xhigh`, `max` |

## Plan Gating

`individual-goat` allows every model in category `opensource`. The 23 `premium` models need Pro/Max or extra usage and are excluded from the config:

```
claude-fable-5
claude-fable-5-1
claude-haiku-4-5-20251001
claude-opus-4-7
claude-opus-4-8
claude-opus-5
claude-opus-5-5
claude-sonnet-4-6
claude-sonnet-5
google/gemini-3.1-flash-lite
google/gemini-3.5-flash
google/gemini-3.5-flash-lite
google/gemini-3.6-flash
gpt-5.3-codex
gpt-5.4
gpt-5.4-mini
gpt-5.5
gpt-5.6-terra
gpt-6-astra
gpt-6-sol
gpt-6.1-sol
meta/muse-spark-1.1
sakana/fugu-ultra
```

## Configure opencode

1. Set the API key in the environment used by opencode:

```bash
export COMMANDCODE_API_KEY=<cmd_api_key>   # add to the shell profile
```

2. Merge `references/commandcode_provider.json` into `~/.config/opencode/opencode.json`:

```python
#!/usr/bin/env python3
import json
from pathlib import Path

cfg_path = Path.home() / ".config/opencode/opencode.json"
provider_path = Path(__file__).parent / "commandcode_provider.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
provider = json.loads(provider_path.read_text(encoding="utf-8"))
cfg.setdefault("provider", {})["commandcode"] = provider
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("providers:", list(cfg["provider"]))
```

The provider uses `@ai-sdk/openai-compatible`; `claude-sonnet-5-5` overrides `provider.npm` to `@ai-sdk/anthropic` because it only serves `/messages`. The API key uses opencode `{env:COMMANDCODE_API_KEY}` substitution, so no secret is stored in the config.

3. Verify and smoke-test:

```bash
opencode models commandcode | wc -l   # 62
opencode run --model commandcode/deepseek/deepseek-v4.1-flash --variant off "Reply with exactly: ok"
opencode run --model commandcode/claude-sonnet-5-5 --variant max --thinking "What is 17*23?"
```

## Model Table

| Model ID | Name | Context | Max output | Variants | Vision |
| --- | --- | ---: | ---: | --- | :---: |
| `claude-sonnet-5-5` | Claude Sonnet 5.5 | 1,000,000 | 64,000 | `low`, `medium`, `high`, `xhigh`, `max` | Y |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash (latest) | 1,000,000 | 64,000 | `off`, `high`, `max` |  |
| `deepseek/deepseek-v4-flash-fast` | DeepSeek V4 Flash Fast | 1,000,000 | 64,000 | `low`, `high`, `max` |  |
| `deepseek/deepseek-v4-flash-vision-exp` | DeepSeek V4 Flash Vision (exp) | 1,000,000 | 64,000 | `off`, `high`, `max` | Y |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro (latest) | 1,000,000 | 64,000 | `off`, `high`, `max` |  |
| `deepseek/deepseek-v4.1-flash` | DeepSeek V4.1 Flash | 1,000,000 | 64,000 | `off`, `low`, `high`, `max` | Y |
| `deepseek/deepseek-v4.1-flash-fast` | DeepSeek V4.1 Flash Fast | 1,000,000 | 64,000 | `off`, `low`, `high`, `max` | Y |
| `google/gemini-3.7-flash` | Gemini 3.7 Flash | 1,048,576 | 64,000 | `low`, `medium`, `high` | Y |
| `google/gemini-3.8-flash` | Gemini 3.8 Flash | 1,000,000 | 64,000 | `low`, `medium`, `high` | Y |
| `gpt-5.6-luna` | GPT-5.6 Luna | 1,050,000 | 64,000 | `low`, `medium`, `high`, `xhigh`, `max` | Y |
| `gpt-5.6-sol` | GPT-5.6 Sol | 1,050,000 | 64,000 | `low`, `medium`, `high`, `xhigh`, `max` | Y |
| `gpt-6-luna` | GPT-6 Luna | 1,050,000 | 64,000 | `low`, `medium`, `high`, `xhigh`, `max` | Y |
| `inclusionai/ling-3.0-flash-sante:free` | Ling 3.0 Flash Sante | 262,144 | 32,768 | — |  |
| `inclusionai/ling-3.1-flash:free` | Ling 3.1 Flash | 262,144 | 32,768 | `low`, `medium`, `high` |  |
| `meituan/LongCat-2.0` | LongCat 2.0 | 1,048,576 | 64,000 | — |  |
| `meta/muse-spark-1.2` | Muse Spark 1.2 | 1,048,576 | 64,000 | `low`, `medium`, `high`, `xhigh` | Y |
| `meta/muse-spark-1.2-contributor` | Muse Spark 1.2 Contributor | 1,048,576 | 64,000 | `low`, `medium`, `high`, `xhigh` | Y |
| `meta/muse-spark-1.3` | Muse Spark 1.3 | 1,048,576 | 64,000 | `low`, `medium`, `high`, `xhigh`, `max` | Y |
| `meta/muse-spark-1.3-contributor` | Muse Spark 1.3 Contributor | 1,048,576 | 64,000 | `low`, `medium`, `high`, `xhigh` | Y |
| `MiniMaxAI/MiniMax-M2.5` | MiniMax M2.5 | 200,000 | 64,000 | — |  |
| `MiniMaxAI/MiniMax-M2.7` | MiniMax M2.7 | 200,000 | 64,000 | — |  |
| `MiniMaxAI/MiniMax-M3` | MiniMax M3 | 1,000,000 | 64,000 | `low`, `medium`, `high` | Y |
| `moonshotai/Kimi-K2.5` | Kimi K2.5 | 256,000 | 64,000 | — | Y |
| `moonshotai/Kimi-K2.6` | Kimi K2.6 | 256,000 | 64,000 | — | Y |
| `moonshotai/Kimi-K2.7-Code` | Kimi K2.7 Code | 256,000 | 64,000 | — | Y |
| `moonshotai/Kimi-K2.7-Code-Highspeed` | Kimi K2.7 Code HighSpeed | 262,000 | 64,000 | — | Y |
| `moonshotai/Kimi-K3` | Kimi K3 | 1,000,000 | 64,000 | `low`, `high`, `max` | Y |
| `nvidia/nemotron-3-ultra-550b-a55b` | Nemotron 3 Ultra | 1,000,000 | 64,000 | — |  |
| `poolside/laguna-s-2.1-free` | Laguna S 2.1 | 256,000 | 32,768 | — |  |
| `Qwen/Qwen3.6-Max-Preview` | Qwen 3.6 Max Preview | 200,000 | 64,000 | — |  |
| `Qwen/Qwen3.6-Plus` | Qwen 3.6 Plus | 200,000 | 64,000 | — | Y |
| `Qwen/Qwen3.7-Flash` | Qwen 3.7 Flash | 1,000,000 | 64,000 | — | Y |
| `Qwen/Qwen3.7-Max` | Qwen 3.7 Max | 1,000,000 | 64,000 | — |  |
| `Qwen/Qwen3.7-Plus` | Qwen 3.7 Plus | 1,000,000 | 64,000 | — | Y |
| `Qwen/Qwen3.8-27B` | Qwen 3.8 27B | 262,144 | 32,768 | `low`, `medium`, `xhigh` | Y |
| `Qwen/Qwen3.8-Flash` | Qwen 3.8 Flash | 1,000,000 | 64,000 | `low`, `medium`, `xhigh` | Y |
| `Qwen/Qwen3.8-Max` | Qwen 3.8 Max | 1,000,000 | 64,000 | `low`, `medium`, `xhigh` | Y |
| `Qwen/Qwen3.8-Max-0902` | Qwen 3.8 Max 0902 | 1,000,000 | 64,000 | `low`, `medium`, `xhigh` | Y |
| `Qwen/Qwen3.8-Omni-Flash` | Qwen 3.8 Omni Flash | 1,000,000 | 131,072 | `low`, `medium`, `xhigh` | Y |
| `stealth/space-bunny-alpha` | Space Bunny Alpha | 1,000,000 | 524,288 | `low`, `medium`, `high`, `max` | Y |
| `stepfun/Step-3.5-Flash` | Step 3.5 Flash | 262,144 | 64,000 | — |  |
| `stepfun/Step-3.7-Flash` | Step 3.7 Flash | 256,000 | 64,000 | — | Y |
| `stepfun/Step-5-Preview` | Step 5 Preview | 1,000,000 | 64,000 | `low`, `medium`, `high` | Y |
| `tencent/hy3-paid` | Tencent Hy3 | 262,144 | 64,000 | — |  |
| `tencent/hy4-preview` | Tencent Hy4 Preview | 1,048,576 | 64,000 | `low`, `medium`, `high` |  |
| `thinkingmachines/inkling` | Inkling | 256,000 | 64,000 | — | Y |
| `thinkingmachines/inkling-small` | Inkling Small | 1,000,000 | 64,000 | — | Y |
| `xai/grok-4.5` | Grok 4.5 | 500,000 | 64,000 | `low`, `medium`, `high` | Y |
| `xai/grok-4.6` | Grok 4.6 | 500,000 | 64,000 | `low`, `medium`, `high`, `xhigh` | Y |
| `xai/grok-4.7` | Grok 4.7 | 500,000 | 64,000 | `low`, `medium`, `high`, `xhigh` | Y |
| `xiaomi/mimo-v2.5` | MiMo V2.5 | 1,000,000 | 64,000 | — | Y |
| `xiaomi/mimo-v2.5-pro` | MiMo V2.5 Pro | 1,000,000 | 64,000 | — |  |
| `xiaomi/mimo-v2.6-flash` | MiMo V2.6 Flash | 1,048,576 | 64,000 | — | Y |
| `xiaomi/mimo-v2.6-pro` | MiMo V2.6 Pro | 1,048,576 | 64,000 | — | Y |
| `xiaomi/mimo-v2.6-pro-ultraspeed` | MiMo V2.6 Pro UltraSpeed | 1,048,576 | 64,000 | — | Y |
| `z-ai/glm-5.3-flash` | GLM-5.3 Flash | 1,048,576 | 131,072 | `low`, `high`, `max` | Y |
| `z-ai/glm-5.3-flashx` | GLM-5.3 FlashX | 1,000,000 | 131,072 | `low`, `high`, `max` | Y |
| `zai-org/GLM-5` | GLM-5 | 200,000 | 64,000 | — |  |
| `zai-org/GLM-5.1` | GLM-5.1 | 200,000 | 64,000 | — |  |
| `zai-org/GLM-5.2` | GLM-5.2 | 1,000,000 | 64,000 | `high`, `max` |  |
| `zai-org/GLM-5.2-Fast` | GLM-5.2 Fast | 1,000,000 | 64,000 | — |  |
| `zai-org/GLM-5.3` | GLM-5.3 | 1,000,000 | 64,000 | `low`, `high`, `max` |  |

## Notes

- opencode maps variant `reasoningEffort` to the request body `reasoning_effort`, and variant `effort` to `output_config.effort` for `@ai-sdk/anthropic`.
- `interleaved: {field: "reasoning_content"}` on reasoning models lets opencode send thinking back in multi-turn conversations.
- `limit.output` defaults to `64000` (Command Code CLI default); models with a smaller documented limit carry it (for example Qwen 3.8 27B uses `32768`).
- Refresh the list when Command Code ships new models: compare `GET /provider/v1/models` with `GET /internal/models` (cookie auth, see the usage scripts) and update `commandcode_provider.json`.

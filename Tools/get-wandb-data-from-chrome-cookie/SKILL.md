---
name: get-wandb-data-from-chrome-cookie
description: Download Weights & Biases (wandb.ai) run data - metadata, files, full metric history/curves and output artifacts - with the Chrome login session instead of a W&B API key. Use when the user asks to fetch, export or download a wandb run that the local API key cannot access, when a GraphQL query returns a null project although the run page opens in Chrome, or when the user asks to read wandb cookies from Chrome on Linux.
---

# Get W&B Data From Chrome Cookie

## When To Use

Extract the wandb.ai cookies from a locally logged-in Chrome profile and download any run the browser session can access:

- run metadata: `config`, `summaryMetrics`, `historyKeys`, state
- full metric history (`history`): every logged step and key
- run files: `config.yaml`, `wandb-metadata.json`, `wandb-summary.json`, `*.diff`, requirements
- output artifacts: history/events parquet and other artifact files

Use it when the run belongs to another account than the local API key, or when the user has no API key at all.

## Quick Start

```bash
pip install pycryptodome secretstorage

python scripts/download_wandb_run.py --url https://wandb.ai/<entity>/<project>/runs/<run_id> --output <dir>
```

Output layout:

```
<dir>/
├── run_info.json          # run metadata: config, summary, historyKeys, state
├── history.json / .csv    # full metric history, one row per step
├── artifact_info.json
├── files/                 # run files
└── artifacts/<seq>/       # output artifact files (parquet)
```

## Implementation Details

### Chrome cookie decryption (Linux, Chrome 127+)

1. Linux Chrome no longer stores `os_crypt.encrypted_key` in `Local State`; the key lives in gnome-keyring as an item with `application=chrome` and `xdg:schema=chrome_libsecret_os_crypt_password_v2`, read through `secretstorage`.
2. Derive the AES key with `PBKDF2-HMAC-SHA1(secret, b"saltysalt", 1, 16)`.
3. Cookie prefixes `v10` and `v11` both use AES-128-CBC with a 16-space-byte IV; `v11` plaintext starts with a 32-byte domain hash that must be stripped.
4. Cookies are stored in `~/.config/google-chrome/<profile>/Cookies` (SQLite, `encrypted_value` column); copy the database before reading to avoid lock contention.

### Authentication

- Set `session.trust_env = False`. Otherwise requests reads `~/.netrc` and adds Basic auth automatically, silently replacing the cookie session with the API key account; the symptom is `project` returning `null` even though the run page opens in Chrome.
- Verify the identity with `query { viewer { username email } }` before downloading.

### W&B endpoints

| Data | Endpoint |
| --- | --- |
| GraphQL | `POST https://api.wandb.ai/graphql` with the cookie session |
| Full history | `run { historyLineCount history(samples: N) }`; pass `N` greater than `historyLineCount` to get every row as JSON lines |
| Run files | GraphQL `run { files { edges { node { name directUrl } } } }`; fall back to `https://api.wandb.ai/files/<entity>/<project>/<run_id>/<name>` |
| Output artifacts | `run { outputArtifacts { ... files { directUrl } } }`; `directUrl` is a signed GCS URL, download directly |
| Optional system metrics | `run { events(samples: N) }` via `--system-metrics`; rows use `_runtime` instead of `_step` |

- Send `x-origin: https://wandb.ai` with GraphQL requests to match the frontend.
- `history` and `events` return arrays of JSON strings, one per row.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Chrome Safe Storage key not found` | Keyring is locked, or the item is not registered under `application=chrome`; enumerate items with `secretstorage` to check |
| `project` returns `null` | Ensure `trust_env` is disabled, the Chrome account has access, and the profile is listed in `CHROME_PROFILES` |
| File download returns 404 | Newer runs do not store `output.log` or `wandb-history.jsonl`; this is expected |
| History has fewer rows than `historyLineCount` | `samples` is too small; pass a value greater than `historyLineCount` |

### Fallback: headless Chrome + CDP

If cookie decryption breaks, copy the Chrome profile and launch headless Chrome with `--remote-debugging-port`, then read the app's own GraphQL responses with `Network.getResponseBody` or run `fetch` in the page context. This is independent of the cookie encryption format but requires starting a browser.

## Notes

- Only the profiles in `CHROME_PROFILES` are scanned; extend the list for more profiles.
- Session cookies are account credentials. Do not write them to disk, logs or repositories.
- Self-hosted W&B instances expose different GraphQL and file URLs; adjust the `GRAPHQL` constant and path templates.

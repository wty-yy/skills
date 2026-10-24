---
name: dsh-tools
description: Check and install npm-based DeepSeek Harness prerequisites (dsh, dsh-tui, and pnpm), then connect Command Code GOAT or OpenCode Go APIs across DSH Web and TUI profiles. Includes credentials, model discovery, protocol routing, and connection verification. Use for DSH setup and API configuration, not provider billing reports or configuring the OpenCode app itself.
---

# DSH Tools

Configure DeepSeek Harness and its terminal interface together. Reuse the user's provider, key, model preference, and existing installation when already known. Ask for the API provider only if unspecified; continue prerequisite checks while waiting. Supported providers: **Command Code GOAT** and **OpenCode Go**. For another provider, inspect available configuration before requesting missing endpoint, protocol, or model details.

## 1. Check and install prerequisites

Run the read-only check:

```bash
bash <skill>/scripts/check_environment.sh
```

It checks `node`, `npm`, `pnpm`, `dsh`, and `dsh-tui` on PATH and their npm global packages. Exit `1` means something is missing or failed; it does not install anything. A usable local installation, version-manager shim, or Corepack-managed pnpm may not appear in the global package list; inspect that case before reinstalling.

On Windows without Bash, use PowerShell `Get-Command node,npm,pnpm,dsh,dsh-tui` and `npm list --global --depth=0` for the same inventory, then run the available version commands. Use `dsh-tui version` rather than starting its interactive UI.

If Node/npm is absent, use the user's existing Node version manager or the official Node installer. Check the selected packages' current `engines` before choosing a Node version. Install only missing or incompatible dependencies; do not upgrade working packages merely to run this skill.

```bash
# Check current registry metadata; respect explicit version pins.
npm view @deepseek-ai/dsh version engines --json
npm view @deepseek-harness-tui/dsh-tui version engines --json
npm view pnpm version engines --json

# When pnpm is missing, install it before initializing the TUI profile.
npm install --global pnpm
# Include only missing packages in the actual install command.
npm install --global @deepseek-ai/dsh @deepseek-harness-tui/dsh-tui
```

Resolve npm permission errors using the existing user-owned Node installation or npm prefix. Do not introduce `sudo`, replace an installed Node manager, or force dependency build approvals as a routine setup step. Re-run the prerequisite check after installation.

## 2. Inspect DSH profiles

Resolve the home from `DSH_HOME`, falling back to `~/.dsh`. Inspect installed package documentation and composed configuration because DSH is changing rapidly.

```bash
dsh --version
dsh web --dump-config
dsh-tui version
# Initialize only if the TUI profile is absent.
dsh plugin --profile dsh-tui add @deepseek-harness-tui/dsh-tui
dsh --profile dsh-tui --dump-config
```

For the profile-based configuration verified on DSH `0.2.1-rc.2`, overrides live in `$DSH_HOME/profiles/<profile>/cordis.patch.yml`; do not write the old `settings.yaml` layout. The installer normally initializes `web` when its configuration is inspected. Configure **web and dsh-tui** by default, plus **headless** for verification and command-line use unless the user limits the targets. Do not launch the TUI with `dsh dsh-tui --help`; use `dsh-tui help` for launcher help.

Preserve unrelated plugin entries, providers, model preferences explicitly chosen by the user, comments, and `!!js` tags. Use a YAML round-trip editor or targeted edits; a plain safe-load/dump can reject or corrupt DSH's tagged expressions. Back up each changed file before editing. Repeated setup should update the same provider keys and entry IDs without creating duplicates.

### Disable the TUI first-run guide by default

As part of setup, skip the automatic first-run wizard unless the user requests it. In dsh-tui `0.16.1`, merge the following state into `~/.dsh-tui/onboarding.json`, creating its parent directory if necessary:

```json
{
  "completed": true,
  "version": 1
}
```

This is per-user TUI state, separate from `DSH_HOME` and Cordis profile settings. Back up an existing file, preserve unrelated fields and any higher existing revision, and write the merged JSON atomically. For another installed version, inspect its `onboardingPrefs` module for the current `ONBOARDING_VERSION` and boot predicate before writing; do not stamp an arbitrarily large version. Re-read the file and confirm that the installed version's wizard predicate no longer offers onboarding. Keep the launchpad preference unchanged. The user can still run `/setup` manually.

## 3. Connect the selected provider

Read only the selected provider's reference and reconcile its credential-free seed with the current catalog:

- **Command Code GOAT:** [references/commandcode.md](references/commandcode.md) and [references/commandcode.patch.yml](references/commandcode.patch.yml); credential reference `COMMANDCODE_API_KEY`.
- **OpenCode Go:** [references/opencode-go.md](references/opencode-go.md) and [references/opencode-go.patch.yml](references/opencode-go.patch.yml); credential reference `OPENCODE_GO_API_KEY`. Use the native `opencode-go` route without an explicit `api` to preserve its per-conversation session header.

Merge the relevant entries into each target profile rather than replacing entire patch files. Keep API keys in DSH's managed `$DSH_HOME/.credentials.yaml`, under the selected `refs` name, with POSIX mode `600`. Merge with existing `version`, `refs`, and `records`; preserve other credentials. Write changes atomically and never display the original document or any key value. Use a provided key, an existing stored reference, or a masked input; keep keys out of command-line arguments, shell history, skill files, and examples. If a key is still missing, prepare the non-secret configuration and ask for it; do not claim a connection was verified.

When adding a provider, preserve the existing default unless the user asks to switch it. For a new setup without a chosen default, the Command Code seed selects `commandcode-responses` / `deepseek/deepseek-v4.1-flash` / `high`; OpenCode Go uses `opencode-go` / `deepseek-v4.1-flash` / `high` after confirming catalog availability. Keep the providers' protocol and reasoning settings separate. Do not change existing permissions, sandbox, or approval policy as part of provider setup.

## 4. Verify both interfaces

1. Dump `web`, `dsh-tui`, and any configured `headless` profile; confirm the provider routes, model, API protocol, and credential reference. Check the key's presence and file permissions without printing it. Confirm that the TUI first-run guide is marked complete at the installed wizard revision unless the user requested onboarding.
2. Headless disables the managed credential plugin in the tested version. Add `- id: credentials` with `disabled: false` to **headless only** when it must use the saved key. Other profiles already mount the store. For older versions inspect their credential format and activation behavior first.
3. Run one short real request, then a bounded multi-step tool test in a scratch directory through the newly configured route. If the existing default differs, use a temporary `--patch` overlay for `agent-default-model` rather than changing the saved default. The latter test must show completed tool results and a completed final answer; a short `OK` alone does not verify tool-history replay. Stop after successful checks; avoid testing every catalog model or retrying indefinitely.

```bash
# Runs small, billed requests; route-check.yml selects the provider being verified.
dsh headless --patch ./route-check.yml --json 'Reply only OK. Do not call tools.'
dsh headless --patch ./route-check.yml --json 'Call bash four times sequentially, running pwd each time; wait for each result. Then explain merge sort briefly. Do not read or write any other files.'
```

For the final response report configured profiles, available models/protocol, whether the default changed, and actual checks performed. Start with `dsh web` or `dsh-tui`. An already-running app may need a restart; an existing conversation keeps its selected route, so use `/model` to select the added provider's model. A new session uses the saved default. Do not silently kill user processes, edit their session logs, or claim TUI interaction was checked when only its composed configuration was inspected.

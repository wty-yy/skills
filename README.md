# SKILLS

Skills I use for coding, writing, and everyday tasks.

English | [简体中文](README.zh-CN.md)

## Usage

Clone once and keep the checkout; installed skills link to it.

```bash
git clone https://github.com/wty-yy/skills.git
cd skills
```

### Linux / macOS

Requires Bash 3.2+; macOS's bundled Bash is supported.

```bash
# Select skills for Codex
./install.sh -i codex

# Install all skills for all agents
./install.sh -i all --yes

# Install all Codex skills and replace its global instructions with a symlink
./install.sh -i codex --yes --global-instructions

# Uninstall repository links
./install.sh -r all
```

Use `-i` / `--install` to install and `-r` / `--remove` to uninstall. Use arrow keys to move, Space to select, Enter to apply, or q to cancel.

### Windows

Requires PowerShell 5.1+ and a local filesystem that supports directory junctions. Global instruction file symlinks also require Developer Mode or an elevated terminal. Run in CMD or PowerShell:

```powershell
# Select skills for Codex
.\install.cmd install codex

# Install all skills for all agents
.\install.cmd install all -Yes

# Install all Codex skills and replace its global instructions with a symlink
.\install.cmd install codex -Yes -GlobalInstructions

# Uninstall repository links
.\install.cmd uninstall all
```

Enter a number to select a skill or category, Enter to apply, or q to cancel.

### Options

Choose `claude`, `codex`, `opencode`, or `all`. Omit the agent to select all three.

| Agent | Default skills directory | Global instructions | Configuration override |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `~/.config/opencode/AGENTS.md` | `XDG_CONFIG_HOME` |

On Windows, `~` means `%USERPROFILE%`. Set `SKILLS_INSTALL_HOME` to change the default home directory.

The checklist starts with a standalone **AGENTS.md** item, linking the agent's global file to this repository's [AGENTS.md](AGENTS.md). It contains the four English principles from [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills): Think Before Coding, Simplicity First, Surgical Changes, and Goal-Driven Execution. Selecting this item replaces the existing file without a backup; repository updates take effect through the link.

Use `--global-instructions` (PowerShell: `-GlobalInstructions`) to preselect this item. Combine with `--yes` / `-Yes` to install it without the checklist. `--yes` / `-Yes` alone leaves global instructions unchanged. An existing repository instruction link is selected by default; deselecting or uninstalling removes that link without restoring the previous file.

Installation replaces same-named items. Deselecting or uninstalling removes only this repository's links. Update with `git pull`, then rerun the installer for new or moved skills.

## Skills

Categories follow `<category>/<skill>/SKILL.md`; the installers discover them automatically.

### Coding

- `code-simplifier`: simplify code without changing behavior.
- `no-ai-slop`: edit writing to remove AI patterns.
- `python-docstring-standard`: standardize Python docstrings.
- `writing-a-project-proposal`: draft Chinese project proposals.
- `wty-markdown-standards`: format Markdown documentation and changelogs.

### Tools

- `build-vps`: set up VPS access, proxy nodes, and Clash Verge subscriptions with bandwidth usage and automatic rules.
- `check-opencode-usage`: check OpenCode usage and costs.
- `cloud189-download`: download Tianyi Cloud folders with resumable ranges and MD5 verification.
- `commandcode-tools`: check Command Code usage and configure its provider.
- `get-wandb-data-from-chrome-cookie`: download W&B run data.
- `wechat_get_data`: read local Linux WeChat records and recover emoji.
- `youtube-download`: download videos, audio, and bilingual subtitles.
- `yuketang-background`: manage Yuketang course tasks.

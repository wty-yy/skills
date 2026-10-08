# SKILLS

Skills I use for coding, writing, and everyday tasks.

## Usage

Clone once and keep the checkout; installed skills link to it.

```bash
git clone https://github.com/wty-yy/skills.git
cd skills
```

### Linux / macOS

```bash
# Select skills for Codex
./install.sh install codex

# Install all skills for all agents
./install.sh install all --yes

# Uninstall repository links
./install.sh uninstall all
```

Use arrow keys to move, Space to select, Enter to apply, or q to cancel.

### Windows

Requires PowerShell 5.1+ and a local filesystem that supports directory junctions. Run in CMD or PowerShell:

```powershell
# Select skills for Codex
.\install.cmd install codex

# Install all skills for all agents
.\install.cmd install all -Yes

# Uninstall repository links
.\install.cmd uninstall all
```

Enter a number to select a skill or category, Enter to apply, or q to cancel.

### Options

Choose `claude`, `codex`, `opencode`, or `all`. Omit the agent to select all three.

| Agent | Default skills directory | Configuration override |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `XDG_CONFIG_HOME` |

On Windows, `~` means `%USERPROFILE%`. Set `SKILLS_INSTALL_HOME` to change the default home directory.

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

- `check-opencode-usage`: check OpenCode usage and costs.
- `commandcode-tools`: check Command Code usage and configure its provider.
- `get-wandb-data-from-chrome-cookie`: download W&B run data.
- `wechat_get_data`: read local Linux WeChat records and recover emoji.
- `youtube-download`: download videos, audio, and bilingual subtitles.
- `yuketang-background`: manage Yuketang course tasks.

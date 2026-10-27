# SKILLS

Skills I use for coding, writing, and everyday tasks.

English | [简体中文](README.zh-CN.md)

## Skills

Categories follow `<category>/<skill>/SKILL.md`; the installers discover them automatically.

### Coding

- [code-simplifier](Coding/code-simplifier/): simplify code without changing behavior.
- [no-ai-slop](Coding/no-ai-slop/): edit writing to remove AI patterns.
- [python-docstring-standard](Coding/python-docstring-standard/): standardize Python docstrings.
- [writing-a-project-proposal](Coding/writing-a-project-proposal/): draft Chinese project proposals.
- [wty-markdown-standards](Coding/wty-markdown-standards/): format Markdown documentation and changelogs.

### Tools

- [build-vps](Tools/build-vps/): set up VPS access, proxy nodes, and Clash Verge subscriptions with bandwidth usage and automatic rules.
- [cloud189-download](Tools/Downloader/cloud189-download/): download Tianyi Cloud folders with resumable ranges and MD5 verification.
- [data-collection](Tools/data-collection/): deploy a Docker service that reserves GPU memory for one host user.
- [get-wandb-data-from-chrome-cookie](Tools/Downloader/get-wandb-data-from-chrome-cookie/): download W&B run data.
- [wechat-get-data](Tools/Downloader/wechat-get-data/): read local Linux WeChat records and recover emoji.
- [youtube-download](Tools/Downloader/youtube-download/): download videos, audio, and bilingual subtitles.
- [yuketang-background](Tools/yuketang-background/): manage Yuketang course tasks.

#### LLM

- [commandcode-tools](Tools/LLM/commandcode-tools/): check Command Code usage and configure its provider.
- [dsh-tools](Tools/LLM/dsh-tools/): check DSH prerequisites and configure API access for Web and TUI.
- [opencode-tools](Tools/LLM/opencode-tools/): check OpenCode usage and costs.
- [token-usage](Tools/LLM/token-usage/): deploy and maintain the Token usage dashboard and collectors.

## Usage

Clone once and keep the checkout; installed skills link to it.

```bash
git clone https://github.com/wty-yy/skills.git
cd skills
```

### Linux / macOS

Requires Bash 3.2+; macOS's bundled Bash is supported.

```bash
# Choose AI tools, then skills
./install.sh -i

# Preselect Codex in the AI tool checklist
./install.sh -i codex

# Select skills for DSH
./install.sh -i dsh

# Install all skills for all agents
./install.sh -i all --yes

# Install all Codex skills and replace its global instructions with a symlink
./install.sh -i codex --yes --global-instructions

# Choose AI tools and skills to uninstall
./install.sh -r

# Uninstall all repository links without the checklists
./install.sh -r all --yes
```

Use `-i` / `--install` to install and `-r` / `--remove` to uninstall. First select AI tools, then skills for each selected tool. Use arrow keys to move, Space to select, Enter to continue or apply, or q to cancel. Uninstall lists only installed repository links and removes only checked items; its checkboxes start empty.

### Windows

Requires PowerShell 5.1+ and a local filesystem that supports directory junctions. Global instruction file symlinks also require Developer Mode or an elevated terminal. Run in CMD or PowerShell:

```powershell
# Choose AI tools, then skills
.\install.cmd install

# Preselect Codex in the AI tool checklist
.\install.cmd install codex

# Install all skills for all agents
.\install.cmd install all -Yes

# Install all Codex skills and replace its global instructions with a symlink
.\install.cmd install codex -Yes -GlobalInstructions

# Choose AI tools and skills to uninstall
.\install.cmd uninstall
```

Enter a number to toggle an AI tool, skill, or category, Enter to continue or apply, or q to cancel.

### Options

Choose `claude`, `codex`, `opencode`, `dsh`, or `all`. Named tools are preselected in the first checklist. `--yes` / `-Yes` skips both checklists; without a tool argument it selects all four.

| Agent | Default skills directory | Global instructions | Configuration override |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `~/.config/opencode/AGENTS.md` | `XDG_CONFIG_HOME` |
| DSH | `~/.dsh/skills` | `~/.dsh/AGENTS.md` | `DSH_HOME` |

On Windows, `~` means `%USERPROFILE%`. Set `SKILLS_INSTALL_HOME` to change the default home directory.

The skill checklist starts with a standalone **AGENTS.md** item, linking the agent's global file to this repository's [AGENTS.md](AGENTS.md). It contains the four English principles from [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills): Think Before Coding, Simplicity First, Surgical Changes, and Goal-Driven Execution. Selecting this item replaces the existing file without a backup; repository updates take effect through the link.

Use `--global-instructions` (PowerShell: `-GlobalInstructions`) to preselect this item. Combine with `--yes` / `-Yes` to install it without the checklist. During installation, `--yes` / `-Yes` alone leaves global instructions unchanged. An existing repository instruction link is selected by default; deselecting or uninstalling removes that link without restoring the previous file.

Installation replaces same-named items. Deselecting or uninstalling removes only this repository's links. Update with `git pull`, then rerun the installer for new or moved skills.

Installing `opencode-tools`, `token-usage`, or `wechat-get-data` also removes this repository's corresponding old `check-opencode-usage`, `token_usage`, or `wechat_get_data` links. Existing old-name installations preselect their replacements; unrelated files, directories, and links are preserved.

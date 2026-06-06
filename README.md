# SKILLS

This repository stores some skills that I have used.

## Usage

Almost every CLI agent has each agent skills directory in user's HOME, for example:

- codex: Linux/Mac `~/.codex/skills`, Win: `%APPDATA%\codex\skills`
- claude code: Linux/Mac `~/.claude/skills`, Win: `%APPDATA%\claude\skills`
- gemini/antigravity: Linux/Mac `~/.gemini/skills`, Win: `%APPDATA%\gemini\skills`

Use git clone to clone this repository and don't delete deafult skills in the directory.

```bash
# If there is no skills directory
git clone --no-checkout https://github.com/wty-yy/skills.git

# If there is already a skills directory
# For codex (Linux/Mac)
cd ~/.codex/skills
git clone --no-checkout https://github.com/wty-yy/skills.git temp_skills && mv temp_skills/.git skills/ && rm -rf temp_skills && cd skills && git reset --hard HEAD

# For codex (Win CMD)
cd %APPDATA%\codex\skills
git clone --no-checkout https://github.com/wty-yy/skills.git temp_skills && move temp_skills\.git skills\ && rmdir /s /q temp_skills && cd skills && git reset --hard HEAD
```

## Introduction

Each skill is packaged as a directory with a `SKILL.md` file that defines when the skill should be used, the expected output style, and any workflow or formatting rules.

Current custom skills in this repository:

- `python-docstring-standard`: standardizes Python docstrings to a consistent team format.
- `writing-a-project-proposal`: writes and rewrites Chinese project proposal materials in a formal proposal style.
- `wty-readme-generator`: generates or rewrites README files in a concise documentation style.

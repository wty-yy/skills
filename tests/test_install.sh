#!/usr/bin/env bash
set -euo pipefail

test_bash="${1:-bash}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-install-test.XXXXXX")"
trap 'rm -rf -- "$test_root"' EXIT

test_repo="$test_root/repository with spaces"
export SKILLS_INSTALL_HOME="$test_root/profile with spaces"
unset CLAUDE_CONFIG_DIR CODEX_HOME XDG_CONFIG_HOME
mkdir -p -- "$test_repo/Coding/demo skill" "$SKILLS_INSTALL_HOME/.codex"
cp -- "$repo_root/install.sh" "$repo_root/AGENTS.md" "$test_repo/"
printf 'fixture\n' > "$test_repo/Coding/demo skill/SKILL.md"
printf 'original\n' > "$SKILLS_INSTALL_HOME/.codex/AGENTS.md"

# A fresh installation starts with an empty discovery array.
"$test_bash" "$test_repo/install.sh" -i all --yes --global-instructions > /dev/null
for config in .claude .codex .config/opencode; do
    destination="$SKILLS_INSTALL_HOME/$config"
    name=AGENTS.md
    [[ "$config" != .claude ]] || name=CLAUDE.md
    [[ -L "$destination/skills/demo skill" && "$destination/skills/demo skill" -ef "$test_repo/Coding/demo skill" ]]
    [[ -L "$destination/$name" && "$destination/$name" -ef "$test_repo/AGENTS.md" ]]
done

"$test_bash" "$test_repo/install.sh" --remove > /dev/null
for config in .claude .codex .config/opencode; do
    destination="$SKILLS_INSTALL_HOME/$config"
    name=AGENTS.md
    [[ "$config" != .claude ]] || name=CLAUDE.md
    [[ ! -e "$destination/skills/demo skill" && ! -L "$destination/skills/demo skill" ]]
    [[ ! -e "$destination/$name" && ! -L "$destination/$name" ]]
done

# An instructions-only checkout has no skills; flags default to all agents.
rm -rf -- "$test_repo/Coding"
"$test_bash" "$test_repo/install.sh" --install --yes --global-instructions > /dev/null
[[ "$SKILLS_INSTALL_HOME/.claude/CLAUDE.md" -ef "$test_repo/AGENTS.md" ]]
[[ "$SKILLS_INSTALL_HOME/.codex/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
[[ "$SKILLS_INSTALL_HOME/.config/opencode/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
"$test_bash" "$test_repo/install.sh" -r all > /dev/null
[[ -f "$test_repo/AGENTS.md" ]]

printf 'Installer regression checks passed (%s).\n' "$test_bash"

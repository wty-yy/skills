#!/usr/bin/env bash
set -euo pipefail

test_bash="${1:-bash}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-install-test.XXXXXX")"
trap 'rm -rf -- "$test_root"' EXIT

test_repo="$test_root/repository with spaces"
export SKILLS_INSTALL_HOME="$test_root/profile with spaces"
unset CLAUDE_CONFIG_DIR CODEX_HOME XDG_CONFIG_HOME DSH_HOME
mkdir -p -- "$test_repo/Coding/demo skill" "$SKILLS_INSTALL_HOME/.codex"
cp -- "$repo_root/install.sh" "$repo_root/AGENTS.md" "$test_repo/"
printf 'fixture\n' > "$test_repo/Coding/demo skill/SKILL.md"
printf 'original\n' > "$SKILLS_INSTALL_HOME/.codex/AGENTS.md"

# A fresh installation starts with an empty discovery array.
"$test_bash" "$test_repo/install.sh" -i all --yes --global-instructions > /dev/null
for config in .claude .codex .config/opencode .dsh; do
    destination="$SKILLS_INSTALL_HOME/$config"
    name=AGENTS.md
    [[ "$config" != .claude ]] || name=CLAUDE.md
    [[ -L "$destination/skills/demo skill" && "$destination/skills/demo skill" -ef "$test_repo/Coding/demo skill" ]]
    [[ -L "$destination/$name" && "$destination/$name" -ef "$test_repo/AGENTS.md" ]]
done

"$test_bash" "$test_repo/install.sh" --remove --yes > /dev/null
for config in .claude .codex .config/opencode .dsh; do
    destination="$SKILLS_INSTALL_HOME/$config"
    name=AGENTS.md
    [[ "$config" != .claude ]] || name=CLAUDE.md
    [[ ! -e "$destination/skills/demo skill" && ! -L "$destination/skills/demo skill" ]]
    [[ ! -e "$destination/$name" && ! -L "$destination/$name" ]]
done

# Moving skills into Tools/LLM repairs old paths and migrates renamed links.
for name in commandcode-tools dsh-tools opencode-tools token-usage; do
    mkdir -p -- "$test_repo/Tools/LLM/$name"
    printf 'fixture\n' > "$test_repo/Tools/LLM/$name/SKILL.md"
done
mkdir -p -- "$test_repo/Tools/Downloader/wechat-get-data"
printf 'fixture\n' > "$test_repo/Tools/Downloader/wechat-get-data/SKILL.md"
for config in .claude .codex .config/opencode .dsh; do
    destination="$SKILLS_INSTALL_HOME/$config/skills"
    mkdir -p -- "$destination"
    for name in commandcode-tools dsh-tools check-opencode-usage token_usage wechat_get_data; do
        ln -s -- "$test_repo/Tools/$name" "$destination/$name"
    done
done
"$test_bash" "$test_repo/install.sh" -i all --yes > /dev/null
for config in .claude .codex .config/opencode .dsh; do
    destination="$SKILLS_INSTALL_HOME/$config/skills"
    for name in commandcode-tools dsh-tools opencode-tools token-usage; do
        [[ "$destination/$name" -ef "$test_repo/Tools/LLM/$name" ]]
    done
    [[ ! -L "$destination/check-opencode-usage" && ! -L "$destination/token_usage" ]]
    [[ "$destination/wechat-get-data" -ef "$test_repo/Tools/Downloader/wechat-get-data" ]]
    [[ ! -L "$destination/wechat_get_data" ]]
    # An already-installed replacement must still clean up a restored old link.
    ln -s -- "$test_repo/Tools/token_usage" "$destination/token_usage"
done
"$test_bash" "$test_repo/install.sh" -i all --yes > /dev/null
for config in .claude .codex .config/opencode .dsh; do
    [[ ! -L "$SKILLS_INSTALL_HOME/$config/skills/token_usage" ]]
done

# Foreign old-name links and ordinary directories are not migration targets.
mkdir -p -- "$test_root/foreign/check-opencode-usage" "$SKILLS_INSTALL_HOME/.codex/skills/token_usage"
printf 'keep\n' > "$SKILLS_INSTALL_HOME/.codex/skills/token_usage/keep.txt"
ln -s -- "$test_root/foreign/check-opencode-usage" "$SKILLS_INSTALL_HOME/.codex/skills/check-opencode-usage"
"$test_bash" "$test_repo/install.sh" -i codex --yes > /dev/null
[[ "$SKILLS_INSTALL_HOME/.codex/skills/check-opencode-usage" -ef "$test_root/foreign/check-opencode-usage" ]]
[[ -f "$SKILLS_INSTALL_HOME/.codex/skills/token_usage/keep.txt" ]]
"$test_bash" "$test_repo/install.sh" -r all --yes > /dev/null
[[ -d "$test_repo/Tools/LLM/token-usage" ]]
[[ -f "$SKILLS_INSTALL_HOME/.codex/skills/token_usage/keep.txt" ]]

# A legacy link is retained when its replacement is not in this checkout.
rm -rf -- "$test_repo/Tools/LLM/opencode-tools"
rm -- "$SKILLS_INSTALL_HOME/.codex/skills/check-opencode-usage"
ln -s -- "$test_repo/Tools/check-opencode-usage" "$SKILLS_INSTALL_HOME/.codex/skills/check-opencode-usage"
"$test_bash" "$test_repo/install.sh" -i codex --yes > /dev/null
[[ -L "$SKILLS_INSTALL_HOME/.codex/skills/check-opencode-usage" ]]

# An explicit DSH target honors DSH_HOME for skills and global instructions.
DSH_HOME="$test_root/custom dsh home" "$test_bash" "$test_repo/install.sh" -i dsh --yes --global-instructions > /dev/null
[[ "$test_root/custom dsh home/skills/token-usage" -ef "$test_repo/Tools/LLM/token-usage" ]]
[[ "$test_root/custom dsh home/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
DSH_HOME="$test_root/custom dsh home" "$test_bash" "$test_repo/install.sh" -r dsh --yes > /dev/null
[[ ! -L "$test_root/custom dsh home/skills/token-usage" ]]
[[ ! -L "$test_root/custom dsh home/AGENTS.md" ]]

# An instructions-only checkout has no skills; flags default to all agents.
rm -rf -- "$test_repo/Coding" "$test_repo/Tools"
"$test_bash" "$test_repo/install.sh" --install --yes --global-instructions > /dev/null
[[ "$SKILLS_INSTALL_HOME/.claude/CLAUDE.md" -ef "$test_repo/AGENTS.md" ]]
[[ "$SKILLS_INSTALL_HOME/.codex/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
[[ "$SKILLS_INSTALL_HOME/.config/opencode/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
[[ "$SKILLS_INSTALL_HOME/.dsh/AGENTS.md" -ef "$test_repo/AGENTS.md" ]]
"$test_bash" "$test_repo/install.sh" -r all --yes > /dev/null
[[ -f "$test_repo/AGENTS.md" ]]

printf 'Installer regression checks passed (%s).\n' "$test_bash"

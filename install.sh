#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./install.sh <install|uninstall> [claude|codex|opencode|all ...] [--yes]

Manage all skill directories containing SKILL.md next to this script.
If no agent is specified, all three agents are selected.
Install opens a checklist with this repository's installed skills selected.
Press Space to toggle a skill and Enter to install selected skills and remove
deselected repository links. Press q or Escape to cancel without applying.
Use --yes to install all skills without opening the checklist.

Examples:
  ./install.sh install codex
  ./install.sh install claude opencode
  ./install.sh install all
  ./install.sh install codex --yes
  ./install.sh uninstall all

Default destinations:
  claude    ~/.claude/skills
  codex     ~/.codex/skills
  opencode  ~/.config/opencode/skills

Environment:
  SKILLS_INSTALL_HOME  Override the home directory for default destinations.
  CLAUDE_CONFIG_DIR    Override Claude's configuration directory.
  CODEX_HOME          Override Codex's configuration directory.
  XDG_CONFIG_HOME     Override the configuration root used by OpenCode.

Install replaces existing files, directories, and symlinks with the same name.
Uninstall removes only symlinks pointing to this repository, including broken
links for skills that have been removed from the repository.
EOF
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

skills_dir() {
    case "$1" in
        claude) printf '%s/skills\n' "${CLAUDE_CONFIG_DIR:-$install_home/.claude}" ;;
        codex) printf '%s/skills\n' "${CODEX_HOME:-$install_home/.codex}" ;;
        opencode) printf '%s/opencode/skills\n' "${XDG_CONFIG_HOME:-$install_home/.config}" ;;
    esac
}

is_repo_link() {
    local destination="$1"
    local source="$repo_root/${destination##*/}"
    [[ -L "$destination" ]] || return 1
    [[ "$(readlink -- "$destination")" == "$source" || "$destination" -ef "$source" ]]
}

is_source_directory() {
    [[ ! -L "$1" && "$1" -ef "$2" ]]
}

collect_selection() {
    local target_dir="$1"
    local source destination
    items=()
    selected=()
    statuses=()

    for source in "${skills[@]}"; do
        items+=("$source")
        destination="$target_dir/${source##*/}"
        if is_source_directory "$destination" "$source"; then
            selected+=(1)
            statuses+=(source)
        elif is_repo_link "$destination"; then
            selected+=(1)
            statuses+=(installed)
        elif [[ -e "$destination" || -L "$destination" ]]; then
            selected+=(0)
            statuses+=(conflict)
        else
            selected+=(0)
            statuses+=(available)
        fi
    done

    # Include owned links whose source skill has been removed from the checkout.
    for destination in "$target_dir"/*; do
        is_repo_link "$destination" || continue
        source="$repo_root/${destination##*/}"
        [[ -d "$source" && -f "$source/SKILL.md" ]] && continue
        items+=("$source")
        selected+=(1)
        statuses+=(stale)
    done
}

restore_terminal() {
    printf '\033[0m\033[?25h\033[?1049l'
}

choose_skills() {
    local agent="$1" target_dir="$2"
    local cursor=0 start=0 end index checked marker label key sequence
    local terminal_rows terminal_columns page_size

    read -r terminal_rows terminal_columns < <(stty size 2>/dev/null || printf '24 80\n')
    [[ "$terminal_rows" =~ ^[0-9]+$ ]] || terminal_rows=24
    page_size=$((terminal_rows - 10))
    [[ "$page_size" -gt 0 ]] || page_size=1

    trap restore_terminal EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    printf '\033[?1049h\033[?25l'

    while true; do
        if [[ "$cursor" -lt "$start" ]]; then
            start="$cursor"
        elif [[ "$cursor" -ge $((start + page_size)) ]]; then
            start=$((cursor - page_size + 1))
        fi
        end=$((start + page_size))
        [[ "$end" -le ${#items[@]} ]] || end=${#items[@]}
        checked=0
        for index in "${!items[@]}"; do
            checked=$((checked + selected[index]))
        done

        printf '\033[H\033[2J'
        printf 'Skill 选择 — %s\n目录：%s\n\n' "$agent" "$target_dir"
        printf '↑/↓ 或 j/k 移动 · 空格切换 · a 全选 · n 全不选\n'
        printf 'Enter 应用选择 · q/Esc 取消\n\n'
        printf '已勾选 %d/%d，显示 %d-%d\n' "$checked" "${#items[@]}" "$((start + 1))" "$end"

        for ((index = start; index < end; index++)); do
            marker=' '
            [[ ${selected[index]} -eq 0 ]] || marker=x
            case "${statuses[index]}" in
                installed) label='已安装' ;;
                available) label='未安装' ;;
                conflict) label='同名项，选中后覆盖' ;;
                stale) label='已安装，源 skill 已删除' ;;
                source) label='源目录，保留且不可卸载' ;;
            esac
            [[ "$index" -ne "$cursor" ]] || printf '\033[7m'
            printf ' [%s] %s  (%s)\033[0m\n' "$marker" "${items[index]##*/}" "$label"
        done
        printf '\n勾选项会安装；取消勾选的本仓库链接会删除。\n'

        key=''
        if ! IFS= read -rsn1 key; then
            restore_terminal
            trap - EXIT INT TERM HUP
            return 1
        fi
        if [[ "$key" == $'\033' ]]; then
            sequence=''
            IFS= read -rsn1 -t 1 sequence || true
            if [[ "$sequence" == '[' || "$sequence" == 'O' ]]; then
                key=''
                IFS= read -rsn1 -t 1 key || true
                case "$key" in
                    A) key=k ;;
                    B) key=j ;;
                    *) continue ;;
                esac
            else
                key=q
            fi
        fi

        case "$key" in
            k) cursor=$(((cursor + ${#items[@]} - 1) % ${#items[@]})) ;;
            j) cursor=$(((cursor + 1) % ${#items[@]})) ;;
            ' ')
                [[ ${statuses[cursor]} == source ]] || selected[cursor]=$((1 - selected[cursor]))
                ;;
            a|n)
                for index in "${!items[@]}"; do
                    [[ ${statuses[index]} == source ]] && continue
                    if [[ "$key" == a ]]; then selected[index]=1; else selected[index]=0; fi
                done
                ;;
            ''|q)
                restore_terminal
                trap - EXIT INT TERM HUP
                [[ "$key" != q ]]
                return
                ;;
        esac
    done
}

case "${1:-}" in
    ''|-h|--help) usage; exit 0 ;;
    install|uninstall) action="$1"; shift ;;
    *) usage >&2; die "Unknown action: $1" ;;
esac

if [[ $# -eq 0 ]]; then
    set -- all
fi

# Validate every agent before making any changes.
agents=()
non_interactive=false
for agent in "$@"; do
    case "$agent" in
        all) agents+=(claude codex opencode) ;;
        claude|codex|opencode) agents+=("$agent") ;;
        -y|--yes) non_interactive=true ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown agent: $agent (supported: claude, codex, opencode, all)" ;;
    esac
done
if [[ ${#agents[@]} -eq 0 ]]; then
    agents=(claude codex opencode)
fi
if [[ "$action" == install && "$non_interactive" == false ]]; then
    [[ -t 0 && -t 1 ]] || die "Interactive install requires a terminal. Use --yes to install all skills without a checklist."
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
install_home="${SKILLS_INSTALL_HOME:-${HOME:?HOME must be set}}"
shopt -s nullglob

skills=()
if [[ "$action" == install ]]; then
    for source in "$repo_root"/*; do
        [[ -d "$source" && -f "$source/SKILL.md" ]] || continue
        skills+=("$source")
    done
fi

for agent in "${agents[@]}"; do
    target_dir="$(skills_dir "$agent")"
    if [[ "$action" == uninstall && ! -d "$target_dir" ]]; then
        printf '[%s] Nothing to uninstall: %s\n' "$agent" "$target_dir"
        continue
    fi
    if [[ -d "$target_dir" ]]; then
        target_dir="$(cd -- "$target_dir" && pwd -P)"
    fi
    count=0

    if [[ "$action" == install ]]; then
        collect_selection "$target_dir"
        [[ ${#items[@]} -gt 0 ]] || die "No repository skills found to manage in $repo_root or $target_dir"
        if [[ "$non_interactive" == true ]]; then
            for index in "${!items[@]}"; do
                selected[index]=1
            done
        elif ! choose_skills "$agent" "$target_dir"; then
            printf '[%s] Cancelled; no changes applied to this agent.\n' "$agent"
            exit 0
        fi

        removed=0
        for index in "${!items[@]}"; do
            source="${items[index]}"
            name="${source##*/}"
            destination="$target_dir/$name"

            if [[ ${selected[index]} -eq 0 ]]; then
                if is_repo_link "$destination"; then
                    rm -- "$destination"
                    printf '[%s] Removed: %s\n' "$agent" "$destination"
                    removed=$((removed + 1))
                fi
                continue
            fi
            [[ -d "$source" && -f "$source/SKILL.md" ]] || continue

            # A checkout inside an agent's skills directory is already usable.
            if is_source_directory "$destination" "$source"; then
                printf '[%s] Already present: %s\n' "$agent" "$name"
                continue
            fi
            if is_repo_link "$destination"; then
                printf '[%s] Already linked: %s\n' "$agent" "$name"
                continue
            fi
            case "$repo_root/" in
                "$destination/"*) die "Refusing to replace the repository or its parent: $destination" ;;
            esac

            mkdir -p -- "$target_dir"
            if [[ -e "$destination" || -L "$destination" ]]; then
                rm -rf -- "$destination"
            fi
            ln -s -- "$source" "$destination"
            printf '[%s] Linked: %s -> %s\n' "$agent" "$destination" "$source"
            count=$((count + 1))
        done
        printf '[%s] Installed %d skill(s), removed %d skill(s) in %s\n' "$agent" "$count" "$removed" "$target_dir"
    else
        for destination in "$target_dir"/*; do
            is_repo_link "$destination" || continue
            rm -- "$destination"
            printf '[%s] Removed: %s\n' "$agent" "$destination"
            count=$((count + 1))
        done
        printf '[%s] Uninstalled %d skill(s) from %s\n' "$agent" "$count" "$target_dir"
    fi
done

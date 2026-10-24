#!/usr/bin/env bash
set -euo pipefail

ui_language=en
case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    zh|zh_*|zh-*|zh.*) ui_language=zh ;;
esac

print_message() {
    local english="$1" chinese="$2"
    shift 2
    if [[ "$ui_language" == zh ]]; then
        printf -- "$chinese" "$@"
    else
        printf -- "$english" "$@"
    fi
}

usage() {
    if [[ "$ui_language" == zh ]]; then
        cat <<'EOF'
用法：./install.sh <-i|--install|-r|--remove> [claude|codex|opencode|dsh|all ...] [--yes] [--global-instructions]

  -i, --install  安装
  -r, --remove   卸载

递归管理仓库内带有 SKILL.md 的目录，按相对父目录自动分类。
推荐布局：<类别>/<skill>/SKILL.md；根目录下的 skill 显示为 Uncategorized。
先选择 AI 工具，再逐个选择技能；命令行指定的工具默认勾选。
例如 -i codex 仍显示工具选择界面，并默认勾选 Codex。
--install 打开选择界面，默认勾选已安装的本仓库 skill。
按类别显示为树形列表，类别行可整组勾选或取消；[-] 表示部分选中。
按空格切换勾选，Enter 安装勾选项并移除取消勾选的本仓库链接。
按 q 或 Esc 取消，不应用当前选择。
--remove 仅列出本仓库已安装的链接，默认不勾选；只卸载勾选项。
使用 --yes 跳过两级选择；未指定工具时对全部工具执行批量安装或卸载。
选择界面包含全局指令文件选项，选中后以符号链接替换现有文件。
使用 --global-instructions 预选该选项；配合 --yes 可直接安装该链接。
安装时单独使用 --yes 不修改全局指令文件。取消勾选或卸载只移除本仓库链接。

示例：
  ./install.sh -i
  ./install.sh -i codex
  ./install.sh --install claude opencode
  ./install.sh --install all
  ./install.sh -i codex --yes
  ./install.sh -i codex --yes --global-instructions
  ./install.sh -r
  ./install.sh -r all --yes

默认安装目录：
  claude    ~/.claude/skills
  codex     ~/.codex/skills
  opencode  ~/.config/opencode/skills
  dsh       ~/.dsh/skills

全局指令文件（链接到本仓库 AGENTS.md）：
  claude    ~/.claude/CLAUDE.md
  codex     ~/.codex/AGENTS.md
  opencode  ~/.config/opencode/AGENTS.md
  dsh       ~/.dsh/AGENTS.md

环境变量：
  SKILLS_INSTALL_HOME  自定义默认安装路径所用的用户目录。
  CLAUDE_CONFIG_DIR    自定义 Claude 配置目录。
  CODEX_HOME          自定义 Codex 配置目录。
  XDG_CONFIG_HOME     自定义 OpenCode 所用的配置根目录。
  DSH_HOME            自定义 DSH 的配置目录。

语言按 LC_ALL、LC_MESSAGES、LANG 的优先级自动选择。
中文环境显示中文；其他环境或未设置语言时显示英文。

安装会覆盖同名文件、目录和符号链接。
卸载只移除指向本仓库的符号链接，包括源 skill 已删除后留下的失效链接。
EOF
    else
        cat <<'EOF'
Usage: ./install.sh <-i|--install|-r|--remove> [claude|codex|opencode|dsh|all ...] [--yes] [--global-instructions]

  -i, --install  Install
  -r, --remove   Uninstall

Recursively discover skill directories containing SKILL.md in this repository.
Group by relative parent directory: <category>/<skill>/SKILL.md.
Skills directly at the repository root appear under Uncategorized.
Choose AI tools first, then skills for each selected tool.
Named agents are preselected; -i codex still opens the tool checklist.
--install opens a checklist with this repository's installed skills selected.
Skills are grouped in a tree. Toggle a category to select or deselect all its
skills. [-] indicates a partially selected category.
Press Space to toggle a skill and Enter to install selected skills and remove
deselected repository links. Press q or Escape to cancel without applying.
--remove lists installed repository links, initially unchecked; only checked
links are removed. --yes skips both checklists and processes all skills for the
named tools, or all four tools when no agent is specified.
The checklist includes global instructions; selecting replaces the existing file
with a symlink. Use --global-instructions to preselect it, or combine with --yes
to install the link directly. On install, --yes alone leaves global instructions unchanged.
Deselecting or uninstalling removes only this repository's instruction links.

Examples:
  ./install.sh -i
  ./install.sh -i codex
  ./install.sh --install claude opencode
  ./install.sh --install all
  ./install.sh -i codex --yes
  ./install.sh -i codex --yes --global-instructions
  ./install.sh -r
  ./install.sh -r all --yes

Default destinations:
  claude    ~/.claude/skills
  codex     ~/.codex/skills
  opencode  ~/.config/opencode/skills
  dsh       ~/.dsh/skills

Global instructions (symlinks to this repository's AGENTS.md):
  claude    ~/.claude/CLAUDE.md
  codex     ~/.codex/AGENTS.md
  opencode  ~/.config/opencode/AGENTS.md
  dsh       ~/.dsh/AGENTS.md

Environment:
  SKILLS_INSTALL_HOME  Override the home directory for default destinations.
  CLAUDE_CONFIG_DIR    Override Claude's configuration directory.
  CODEX_HOME          Override Codex's configuration directory.
  XDG_CONFIG_HOME     Override the configuration root used by OpenCode.
  DSH_HOME            Override DSH's configuration directory.

Language follows LC_ALL, LC_MESSAGES, then LANG. Chinese locales use Chinese;
other or unset locales use English.

Install replaces existing files, directories, and symlinks with the same name.
Uninstall removes only symlinks pointing to this repository, including broken
links for skills that have been removed from the repository.
EOF
    fi
}

die() {
    print_message 'Error: ' '错误：' >&2
    print_message "$@" >&2
    printf '\n' >&2
    exit 1
}

skills_dir() {
    case "$1" in
        claude) printf '%s/skills\n' "${CLAUDE_CONFIG_DIR:-$install_home/.claude}" ;;
        codex) printf '%s/skills\n' "${CODEX_HOME:-$install_home/.codex}" ;;
        opencode) printf '%s/opencode/skills\n' "${XDG_CONFIG_HOME:-$install_home/.config}" ;;
        dsh) printf '%s/skills\n' "${DSH_HOME:-$install_home/.dsh}" ;;
    esac
}

instructions_file() {
    local config_dir
    config_dir="$(skills_dir "$1")"
    config_dir="${config_dir%/skills}"
    case "$1" in
        claude) printf '%s/CLAUDE.md\n' "$config_dir" ;;
        *) printf '%s/AGENTS.md\n' "$config_dir" ;;
    esac
}

is_instructions_link() {
    local destination="$1" source parent
    [[ -L "$destination" ]] || return 1
    source="$(readlink -- "$destination")"
    [[ "$source" == /* ]] || source="${destination%/*}/$source"
    parent="${source%/*}"
    if [[ -d "$parent" ]]; then
        source="$(cd -- "$parent" && pwd -P)/${source##*/}"
    fi
    [[ "$source" == "$repo_root/AGENTS.md" ]]
}

apply_instructions() {
    local agent="$1" destination="$2" selected="$3"
    if [[ "$selected" -eq 0 ]]; then
        if is_instructions_link "$destination"; then
            rm -- "$destination"
            print_message '[%s] Removed: %s\n' '[%s] 已移除：%s\n' "$agent" "$destination"
        fi
        return 0
    fi
    if is_instructions_link "$destination"; then
        print_message '[%s] Already linked: %s\n' '[%s] 已链接：%s\n' "$agent" "$destination"
        return 0
    fi
    [[ ! -d "$destination" || -L "$destination" ]] || die \
        'Refusing to replace an instructions directory: %s' '拒绝覆盖指令路径上的目录：%s' "$destination"
    [[ ! "$destination" -ef "$repo_root/AGENTS.md" ]] || die \
        'Refusing to replace the source instructions: %s' '拒绝覆盖源指令文件：%s' "$destination"
    mkdir -p -- "${destination%/*}"
    if [[ -e "$destination" || -L "$destination" ]]; then
        rm -- "$destination"
    fi
    ln -s -- "$repo_root/AGENTS.md" "$destination"
    print_message '[%s] Linked: %s -> %s\n' '[%s] 已创建链接：%s -> %s\n' "$agent" "$destination" "$repo_root/AGENTS.md"
}

repo_link_source() {
    local destination="$1"
    local source parent
    [[ -L "$destination" ]] || return 1
    source="$(readlink -- "$destination")"
    [[ "$source" == /* ]] || source="${destination%/*}/$source"
    parent="${source%/*}"
    if [[ -d "$parent" ]]; then
        source="$(cd -- "$parent" && pwd -P)/${source##*/}"
    fi
    # Retain ownership of broken links, including the old flat layout.
    [[ "$source" == "$repo_root/"* && "${source##*/}" == "${destination##*/}" ]] || return 1
    [[ "$source/" != */../* && "$source/" != */./* ]] || return 1
    printf '%s\n' "$source"
}

is_repo_link() {
    repo_link_source "$1" > /dev/null
}

is_source_directory() {
    [[ ! -L "$1" && "$1" -ef "$2" ]]
}

legacy_skill_name() {
    case "$1" in
        opencode-tools) printf '%s\n' check-opencode-usage ;;
        token-usage) printf '%s\n' token_usage ;;
        wechat-get-data) printf '%s\n' wechat_get_data ;;
    esac
}

remove_legacy_skill_link() {
    local agent="$1" target_dir="$2" name="$3" legacy destination
    legacy="$(legacy_skill_name "$name")"
    [[ -n "$legacy" ]] || return 0
    destination="$target_dir/$legacy"
    if is_repo_link "$destination"; then
        rm -- "$destination"
        print_message '[%s] Removed renamed skill: %s -> %s\n' '[%s] 已移除旧名称链接：%s -> %s\n' "$agent" "$legacy" "$name"
        removed=$((removed + 1))
    fi
}

discover_skills() {
    local directory="$1" source existing
    for source in "$directory"/*; do
        [[ -d "$source" && ! -L "$source" ]] || continue
        if [[ -f "$source/SKILL.md" ]]; then
            # Bash 3.2 treats an empty array as unset under set -u.
            for existing in ${skills[@]+"${skills[@]}"}; do
                [[ "${existing##*/}" != "${source##*/}" ]] || die \
                    'Duplicate skill name: %s and %s' 'skill 名称重复：%s 和 %s' "$existing" "$source"
            done
            skills+=("$source")
        else
            discover_skills "$source"
        fi
    done
}

collect_selection() {
    local target_dir="$1" instructions="$2"
    local source destination existing found legacy
    items=()
    selected=()
    statuses=()

    for source in ${skills[@]+"${skills[@]}"}; do
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
            legacy="$(legacy_skill_name "${source##*/}")"
            if [[ -n "$legacy" ]] && is_repo_link "$target_dir/$legacy"; then
                selected+=(1)
                statuses+=(installed)
            else
                selected+=(0)
                statuses+=(available)
            fi
        fi
    done

    # Include owned links whose source skill has been removed from the checkout.
    for destination in "$target_dir"/*; do
        source="$(repo_link_source "$destination")" || continue
        found=false
        for existing in ${skills[@]+"${skills[@]}"}; do
            if [[ "${existing##*/}" == "${destination##*/}" || "$(legacy_skill_name "${existing##*/}")" == "${destination##*/}" ]]; then
                found=true
                break
            fi
        done
        [[ "$found" == false ]] || continue
        items+=("$source")
        selected+=(1)
        statuses+=(stale)
    done

    items+=("$repo_root/AGENTS.md")
    if is_instructions_link "$instructions"; then
        selected+=(1)
        statuses+=(installed)
    else
        if [[ "$global_instructions" == true ]]; then selected+=(1); else selected+=(0); fi
        if [[ -e "$instructions" || -L "$instructions" ]]; then
            statuses+=(conflict)
        else
            statuses+=(available)
        fi
    fi
}

collect_removal_selection() {
    local target_dir="$1" instructions="$2" destination source
    items=()
    selected=()
    statuses=()
    for destination in "$target_dir"/*; do
        source="$(repo_link_source "$destination")" || continue
        items+=("$source")
        selected+=(0)
        statuses+=(installed)
    done
    if is_instructions_link "$instructions"; then
        items+=("$repo_root/AGENTS.md")
        selected+=(0)
        statuses+=(installed)
    fi
}

build_tree() {
    local category index last_child relative existing found
    local categories=()
    item_categories=()
    tree_items=()
    tree_categories=()
    tree_last_children=()

    for index in "${!items[@]}"; do
        relative="${items[index]#"$repo_root/"}"
        case "$relative" in
            AGENTS.md)
                item_categories[index]=''
                tree_items+=("$index")
                tree_categories+=('')
                tree_last_children+=(0)
                continue
                ;;
            */*) category="${relative%/*}" ;;
            *) category=Uncategorized ;;
        esac
        item_categories[index]="$category"
        found=false
        for existing in ${categories[@]+"${categories[@]}"}; do
            [[ "$existing" != "$category" ]] || found=true
        done
        [[ "$found" == true ]] || categories+=("$category")
    done

    for category in ${categories[@]+"${categories[@]}"}; do
        last_child=-1
        for index in "${!items[@]}"; do
            [[ ${item_categories[index]} == "$category" ]] || continue
            if [[ "$last_child" -eq -1 ]]; then
                tree_items+=(-1)
                tree_categories+=("$category")
                tree_last_children+=(0)
            fi
            tree_items+=("$index")
            tree_categories+=("$category")
            tree_last_children+=(0)
            last_child=$((${#tree_items[@]} - 1))
        done
        if [[ "$last_child" -ge 0 ]]; then
            tree_last_children[last_child]=1
        fi
    done
}

toggle_category() {
    local category="$1" index all_selected=1
    for index in "${!items[@]}"; do
        [[ ${item_categories[index]} == "$category" ]] || continue
        [[ ${selected[index]} -eq 1 ]] || all_selected=0
    done
    for index in "${!items[@]}"; do
        [[ ${item_categories[index]} == "$category" ]] || continue
        [[ ${statuses[index]} == source ]] && continue
        selected[index]=$((1 - all_selected))
    done
}

restore_terminal() {
    printf '\033[0m\033[?25h\033[?1049l'
}

choose_skills() {
    local agent="$1" target_dir="$2" stage="${3:-skills}"
    local cursor=0 start=0 end index item checked marker label key sequence name
    local category category_total category_checked child prefix
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
        [[ "$end" -le ${#tree_items[@]} ]] || end=${#tree_items[@]}
        checked=0
        for index in "${!items[@]}"; do
            checked=$((checked + selected[index]))
        done

        printf '\033[H\033[2J'
        if [[ "$stage" == tools ]]; then
            print_message 'AI tool selection\n\n' '选择 AI 工具\n\n'
        elif [[ "$action" == uninstall ]]; then
            print_message 'Skills to uninstall - %s\nDirectory: %s\n\n' '选择要卸载的 skill — %s\n目录：%s\n\n' "$agent" "$target_dir"
        else
            print_message 'Skill selection - %s\nDirectory: %s\n\n' 'Skill 选择 — %s\n目录：%s\n\n' "$agent" "$target_dir"
        fi
        print_message 'Up/Down or j/k: move | Space: toggle skill/category\n' '↑/↓ 或 j/k 移动 · 空格切换 skill/类别\n'
        print_message 'Enter: apply | a: all | n: none | q/Esc: cancel\n\n' 'Enter 应用 · a 全选 · n 全不选 · q/Esc 取消\n\n'
        print_message 'Selected %d/%d; rows %d-%d | [-] = partially selected\n' '已勾选 %d/%d，显示 %d-%d · [-] 表示部分选中\n' "$checked" "${#items[@]}" "$((start + 1))" "$end"

        for ((index = start; index < end; index++)); do
            [[ "$index" -ne "$cursor" ]] || printf '\033[7m'
            item="${tree_items[index]}"
            if [[ "$item" -eq -1 ]]; then
                category="${tree_categories[index]}"
                category_total=0
                category_checked=0
                for child in "${!items[@]}"; do
                    [[ ${item_categories[child]} == "$category" ]] || continue
                    category_total=$((category_total + 1))
                    category_checked=$((category_checked + selected[child]))
                done
                marker=' '
                if [[ "$category_checked" -eq "$category_total" ]]; then
                    marker=x
                elif [[ "$category_checked" -gt 0 ]]; then
                    marker=-
                fi
                printf ' [%s] %s (%d/%d)\033[0m\n' "$marker" "$category" "$category_checked" "$category_total"
                continue
            fi
            marker=' '
            [[ ${selected[item]} -eq 0 ]] || marker=x
            label=''
            if [[ "$stage" != tools ]]; then
                case "${statuses[item]}" in
                    installed) label="$(print_message 'Installed' '已安装')" ;;
                    available) label="$(print_message 'Not installed' '未安装')" ;;
                    conflict) label='' ;;
                    stale) label="$(print_message 'Installed; source skill removed' '已安装，源 skill 已删除')" ;;
                    source) label="$(print_message 'Source directory; cannot uninstall' '源目录，保留且不可卸载')" ;;
                esac
            fi
            prefix='├─'
            [[ ${tree_last_children[index]} -eq 0 ]] || prefix='└─'
            name="${items[item]##*/}"
            if [[ "${items[item]}" == "$repo_root/AGENTS.md" ]]; then
                if [[ "$action" == uninstall ]]; then
                    name="$(print_message 'AGENTS.md -> %s (remove link)' 'AGENTS.md -> %s（移除链接）' "$(instructions_file "$agent")")"
                else
                    name="$(print_message 'AGENTS.md -> %s (replaces file)' 'AGENTS.md -> %s（覆盖现有文件）' "$(instructions_file "$agent")")"
                fi
            fi
            [[ -z "$label" ]] || name+="  ($label)"
            if [[ "$stage" == tools || "${items[item]}" == "$repo_root/AGENTS.md" ]]; then
                printf ' [%s] %s\033[0m\n' "$marker" "$name"
            else
                printf '   %s [%s] %s\033[0m\n' "$prefix" "$marker" "$name"
            fi
        done
        if [[ "$stage" == tools ]]; then
            print_message '\nSelect at least one AI tool, then press Enter to choose its skills.\n' '\n至少勾选一个 AI 工具，按 Enter 进入技能选择。\n'
        elif [[ "$action" == uninstall ]]; then
            print_message '\nOnly checked repository links will be removed.\n' '\n仅卸载勾选的本仓库链接。\n'
        else
            print_message '\nSelected items will be linked; deselected repository links will be removed.\n' '\n勾选项会创建链接；取消勾选的本仓库链接会删除。\n'
        fi

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
            k) cursor=$(((cursor + ${#tree_items[@]} - 1) % ${#tree_items[@]})) ;;
            j) cursor=$(((cursor + 1) % ${#tree_items[@]})) ;;
            ' ')
                item="${tree_items[cursor]}"
                if [[ "$item" -eq -1 ]]; then
                    toggle_category "${tree_categories[cursor]}"
                elif [[ ${statuses[item]} != source ]]; then
                    selected[item]=$((1 - selected[item]))
                fi
                ;;
            a|n)
                for index in "${!items[@]}"; do
                    [[ ${statuses[index]} == source ]] && continue
                    if [[ "$key" == a ]]; then selected[index]=1; else selected[index]=0; fi
                done
                ;;
            ''|q)
                [[ "$stage" != tools || "$key" == q || "$checked" -gt 0 ]] || continue
                restore_terminal
                trap - EXIT INT TERM HUP
                [[ "$key" != q ]]
                return
                ;;
        esac
    done
}

choose_agents() {
    local index agent
    items=("$repo_root/claude" "$repo_root/codex" "$repo_root/opencode" "$repo_root/dsh")
    selected=(0 0 0 0)
    statuses=(available available available available)
    tree_items=(0 1 2 3)
    tree_categories=('' '' '' '')
    tree_last_children=(0 0 0 0)
    item_categories=('' '' '' '')
    for index in "${!items[@]}"; do
        for agent in ${agents[@]+"${agents[@]}"}; do
            [[ "${items[index]##*/}" != "$agent" ]] || selected[index]=1
        done
    done
    choose_skills '' '' tools || return 1
    agents=()
    for index in "${!items[@]}"; do
        [[ ${selected[index]} -eq 0 ]] || agents+=("${items[index]##*/}")
    done
}

case "${1:-}" in
    ''|-h|--help) usage; exit 0 ;;
    -i|--install) action=install; shift ;;
    -r|--remove) action=uninstall; shift ;;
    *) usage >&2; die 'Unknown action: %s' '未知操作：%s' "$1" ;;
esac

# Validate every agent before making any changes.
agents=()
non_interactive=false
global_instructions=false
for agent in "$@"; do
    case "$agent" in
        all) agents+=(claude codex opencode dsh) ;;
        claude|codex|opencode|dsh) agents+=("$agent") ;;
        -y|--yes) non_interactive=true ;;
        --global-instructions) global_instructions=true ;;
        -h|--help) usage; exit 0 ;;
        *) die 'Unknown agent: %s (supported: claude, codex, opencode, dsh, all)' '未知 agent：%s（支持 claude、codex、opencode、dsh、all）' "$agent" ;;
    esac
done
if [[ "$action" == uninstall && "$global_instructions" == true ]]; then
    die '--global-instructions requires --install; --remove already removes owned instruction links.' '--global-instructions 仅用于 --install；--remove 会自动移除本仓库的指令链接。'
fi
if [[ "$non_interactive" == true && ${#agents[@]} -eq 0 ]]; then
    agents=(claude codex opencode dsh)
fi
if [[ "$non_interactive" == false ]]; then
    [[ -t 0 && -t 1 ]] || die 'Interactive selection requires a terminal. Use --yes to skip both checklists.' '交互选择需要终端。使用 --yes 跳过工具和技能选择。'
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
install_home="${SKILLS_INSTALL_HOME:-${HOME:-}}"
[[ -n "$install_home" ]] || die 'HOME must be set' '必须设置 HOME'
shopt -s nullglob

if [[ "$non_interactive" == false ]] && ! choose_agents; then
    print_message 'Cancelled; no changes applied.\n' '已取消，未应用任何修改。\n'
    exit 0
fi

skills=()
if [[ "$action" == install ]]; then
    [[ -f "$repo_root/AGENTS.md" ]] || die 'Missing source: %s/AGENTS.md' '缺少源文件：%s/AGENTS.md' "$repo_root"
    discover_skills "$repo_root"
fi

for agent in "${agents[@]}"; do
    target_dir="$(skills_dir "$agent")"
    instructions="$(instructions_file "$agent")"
    if [[ -d "$target_dir" ]]; then
        target_dir="$(cd -- "$target_dir" && pwd -P)"
    fi
    count=0

    if [[ "$action" == install ]]; then
        collect_selection "$target_dir" "$instructions"
        [[ ${#items[@]} -gt 0 ]] || die 'No repository skills found to manage in %s or %s' '%s 或 %s 中没有可管理的本仓库 skill' "$repo_root" "$target_dir"
        if [[ "$non_interactive" == true ]]; then
            for index in "${!items[@]}"; do
                if [[ "${items[index]}" == "$repo_root/AGENTS.md" ]]; then
                    if [[ "$global_instructions" == true ]]; then selected[index]=1; else selected[index]=0; fi
                    continue
                fi
                selected[index]=1
            done
        else
            build_tree
            if ! choose_skills "$agent" "$target_dir"; then
                print_message '[%s] Cancelled; no changes applied to this agent.\n' '[%s] 已取消，未对当前 agent 应用任何修改。\n' "$agent"
                exit 0
            fi
        fi

        removed=0
        for index in "${!items[@]}"; do
            source="${items[index]}"
            if [[ "$source" == "$repo_root/AGENTS.md" ]]; then
                if [[ "$non_interactive" == false || "$global_instructions" == true ]]; then
                    apply_instructions "$agent" "$instructions" "${selected[index]}"
                fi
                continue
            fi
            name="${source##*/}"
            destination="$target_dir/$name"

            if [[ ${selected[index]} -eq 0 ]]; then
                if is_repo_link "$destination"; then
                    rm -- "$destination"
                    print_message '[%s] Removed: %s\n' '[%s] 已移除：%s\n' "$agent" "$destination"
                    removed=$((removed + 1))
                fi
                continue
            fi
            [[ -d "$source" && -f "$source/SKILL.md" ]] || continue

            # A checkout inside an agent's skills directory is already usable.
            if is_source_directory "$destination" "$source"; then
                print_message '[%s] Already present: %s\n' '[%s] 已存在：%s\n' "$agent" "$name"
                remove_legacy_skill_link "$agent" "$target_dir" "$name"
                continue
            fi
            if [[ -L "$destination" && "$destination" -ef "$source" ]]; then
                print_message '[%s] Already linked: %s\n' '[%s] 已链接：%s\n' "$agent" "$name"
                remove_legacy_skill_link "$agent" "$target_dir" "$name"
                continue
            fi
            case "$repo_root/" in
                "$destination/"*) die 'Refusing to replace the repository or its parent: %s' '拒绝覆盖本仓库或其上级目录：%s' "$destination" ;;
            esac

            mkdir -p -- "$target_dir"
            if [[ -e "$destination" || -L "$destination" ]]; then
                rm -rf -- "$destination"
            fi
            ln -s -- "$source" "$destination"
            print_message '[%s] Linked: %s -> %s\n' '[%s] 已创建链接：%s -> %s\n' "$agent" "$destination" "$source"
            count=$((count + 1))
            remove_legacy_skill_link "$agent" "$target_dir" "$name"
        done
        print_message '[%s] Installed %d skill(s), removed %d skill(s) in %s\n' '[%s] 已安装 %d 个 skill，移除 %d 个 skill，目录：%s\n' "$agent" "$count" "$removed" "$target_dir"
    else
        collect_removal_selection "$target_dir" "$instructions"
        if [[ ${#items[@]} -eq 0 ]]; then
            print_message '[%s] Nothing to uninstall: %s\n' '[%s] 没有可卸载的 skill：%s\n' "$agent" "$target_dir"
            continue
        fi
        if [[ "$non_interactive" == true ]]; then
            for index in "${!items[@]}"; do selected[index]=1; done
        else
            build_tree
            if ! choose_skills "$agent" "$target_dir"; then
                print_message '[%s] Cancelled; no changes applied to this agent.\n' '[%s] 已取消，未对当前 agent 应用任何修改。\n' "$agent"
                exit 0
            fi
        fi
        for index in "${!items[@]}"; do
            [[ ${selected[index]} -eq 1 ]] || continue
            source="${items[index]}"
            if [[ "$source" == "$repo_root/AGENTS.md" ]]; then
                apply_instructions "$agent" "$instructions" 0
                continue
            fi
            destination="$target_dir/${source##*/}"
            is_repo_link "$destination" || continue
            rm -- "$destination"
            print_message '[%s] Removed: %s\n' '[%s] 已移除：%s\n' "$agent" "$destination"
            count=$((count + 1))
        done
        print_message '[%s] Uninstalled %d skill(s) from %s\n' '[%s] 已卸载 %d 个 skill，目录：%s\n' "$agent" "$count" "$target_dir"
    fi
done

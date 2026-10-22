# SKILLS

用于编程、写作和日常任务的个人 skills。

[English](README.md) | 简体中文

## 使用

克隆并保留仓库目录，安装后的 skills 会链接到该目录。

```bash
git clone https://github.com/wty-yy/skills.git
cd skills
```

### Linux / macOS

需要 Bash 3.2+，兼容 macOS 自带的 Bash。

```bash
# 为 Codex 选择 skills
./install.sh -i codex

# 为全部 agent 安装所有 skills
./install.sh -i all --yes

# 安装全部 Codex skills，并以符号链接替换其全局指令文件
./install.sh -i codex --yes --global-instructions

# 卸载本仓库的链接
./install.sh -r all
```

使用 `-i` / `--install` 安装，`-r` / `--remove` 卸载。使用方向键移动，空格选择，Enter 应用，q 取消。

### Windows

需要 PowerShell 5.1+，以及支持目录联接的本地文件系统。全局指令文件的符号链接还需要开发者模式或管理员终端。在 CMD 或 PowerShell 中运行：

```powershell
# 为 Codex 选择 skills
.\install.cmd install codex

# 为全部 agent 安装所有 skills
.\install.cmd install all -Yes

# 安装全部 Codex skills，并以符号链接替换其全局指令文件
.\install.cmd install codex -Yes -GlobalInstructions

# 卸载本仓库的链接
.\install.cmd uninstall all
```

输入编号选择 skill 或类别，Enter 应用，q 取消。

### 选项

可选择 `claude`、`codex`、`opencode` 或 `all`。省略 agent 时，默认选择全部三个。

| Agent | 默认 skills 目录 | 全局指令文件 | 配置覆盖变量 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `~/.config/opencode/AGENTS.md` | `XDG_CONFIG_HOME` |

Windows 中的 `~` 表示 `%USERPROFILE%`。设置 `SKILLS_INSTALL_HOME` 可修改默认用户目录。

选择界面首项为独立的 **AGENTS.md** 选项，将 agent 的全局指令文件链接到本仓库的 [AGENTS.md](AGENTS.md)。文件包含 [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) 的四项英文原则：Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution。选中后直接替换现有文件，不备份；仓库更新通过链接生效。

使用 `--global-instructions`（PowerShell：`-GlobalInstructions`）预选该项，配合 `--yes` / `-Yes` 可跳过选择界面直接安装。单独使用 `--yes` / `-Yes` 不修改全局指令文件。已有的本仓库指令链接默认选中；取消选择或卸载会移除该链接，不恢复原文件。

安装会覆盖同名项。取消选择或卸载只移除本仓库的链接。更新时运行 `git pull`，新增或移动 skill 后重新运行安装器。

## Skills

类别采用 `<category>/<skill>/SKILL.md` 结构，安装器自动发现。

### Coding

- `code-simplifier`：保持行为不变，简化代码。
- `no-ai-slop`：润色写作，减少 AI 化表达。
- `python-docstring-standard`：规范 Python 文档字符串。
- `writing-a-project-proposal`：撰写中文项目申报材料。
- `wty-markdown-standards`：规范 Markdown 文档和更新日志。

### Tools

- `build-vps`：配置 VPS 访问、代理节点及 Clash Verge 订阅，支持流量用量和自动更新规则。
- `check-opencode-usage`：查询 OpenCode 用量和费用。
- `commandcode-tools`：查询 Command Code 用量并配置服务提供商。
- `get-wandb-data-from-chrome-cookie`：下载 W&B 运行数据。
- `wechat_get_data`：读取 Linux 本地微信记录并恢复表情。
- `youtube-download`：下载视频、音频和双语字幕。
- `yuketang-background`：管理雨课堂课程任务。

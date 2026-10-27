# SKILLS

用于编程、写作和日常任务的个人 skills。

[English](README.md) | 简体中文

## Skills

类别采用 `<category>/<skill>/SKILL.md` 结构，安装器自动发现。

### Coding

- [code-simplifier](Coding/code-simplifier/)：保持行为不变，简化代码。
- [no-ai-slop](Coding/no-ai-slop/)：润色写作，减少 AI 化表达。
- [python-docstring-standard](Coding/python-docstring-standard/)：规范 Python 文档字符串。
- [writing-a-project-proposal](Coding/writing-a-project-proposal/)：撰写中文项目申报材料。
- [wty-markdown-standards](Coding/wty-markdown-standards/)：规范 Markdown 文档和更新日志。

### Tools

- [build-vps](Tools/build-vps/)：配置 VPS 访问、代理节点及 Clash Verge 订阅，支持流量用量和自动更新规则。
- [cloud189-download](Tools/Downloader/cloud189-download/)：下载天翼云盘文件夹，支持断点续传和 MD5 校验。
- [data-collection](Tools/data-collection/)：部署为指定用户预留 GPU 显存的 Docker 服务。
- [get-wandb-data-from-chrome-cookie](Tools/Downloader/get-wandb-data-from-chrome-cookie/)：下载 W&B 运行数据。
- [wechat-get-data](Tools/Downloader/wechat-get-data/)：读取 Linux 本地微信记录并恢复表情。
- [youtube-download](Tools/Downloader/youtube-download/)：下载视频、音频和双语字幕。
- [yuketang-background](Tools/yuketang-background/)：管理雨课堂课程任务。

#### LLM

- [commandcode-tools](Tools/LLM/commandcode-tools/)：查询 Command Code 用量并配置服务提供商。
- [dsh-tools](Tools/LLM/dsh-tools/)：检查 DSH 依赖，为 Web 和 TUI 配置 API 接入。
- [opencode-tools](Tools/LLM/opencode-tools/)：查询 OpenCode 用量和费用。
- [token-usage](Tools/LLM/token-usage/)：部署和维护 Token 用量网页及采集器。

## 使用

克隆并保留仓库目录，安装后的 skills 会链接到该目录。

```bash
git clone https://github.com/wty-yy/skills.git
cd skills
```

### Linux / macOS

需要 Bash 3.2+，兼容 macOS 自带的 Bash。

```bash
# 先选择 AI 工具，再选择 skills
./install.sh -i

# 在工具选择界面默认勾选 Codex
./install.sh -i codex

# 为 DSH 选择 skills
./install.sh -i dsh

# 为全部 agent 安装所有 skills
./install.sh -i all --yes

# 安装全部 Codex skills，并以符号链接替换其全局指令文件
./install.sh -i codex --yes --global-instructions

# 选择要卸载的 AI 工具和 skills
./install.sh -r

# 跳过选择界面，卸载全部本仓库链接
./install.sh -r all --yes
```

使用 `-i` / `--install` 安装，`-r` / `--remove` 卸载。先勾选 AI 工具，再逐个选择对应的 skills。方向键移动，空格勾选，Enter 进入下一步或应用，q 取消。卸载界面只列出本仓库已安装的链接，默认不勾选，仅卸载勾选项。

### Windows

需要 PowerShell 5.1+，以及支持目录联接的本地文件系统。全局指令文件的符号链接还需要开发者模式或管理员终端。在 CMD 或 PowerShell 中运行：

```powershell
# 先选择 AI 工具，再选择 skills
.\install.cmd install

# 在工具选择界面默认勾选 Codex
.\install.cmd install codex

# 为全部 agent 安装所有 skills
.\install.cmd install all -Yes

# 安装全部 Codex skills，并以符号链接替换其全局指令文件
.\install.cmd install codex -Yes -GlobalInstructions

# 选择要卸载的 AI 工具和 skills
.\install.cmd uninstall
```

输入编号切换 AI 工具、skill 或类别的勾选状态，Enter 进入下一步或应用，q 取消。

### 选项

可选择 `claude`、`codex`、`opencode`、`dsh` 或 `all`。指定的工具会在第一级界面默认勾选。`--yes` / `-Yes` 跳过两级选择；未指定工具时选择全部四个。

| Agent | 默认 skills 目录 | 全局指令文件 | 配置覆盖变量 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `~/.config/opencode/AGENTS.md` | `XDG_CONFIG_HOME` |
| DSH | `~/.dsh/skills` | `~/.dsh/AGENTS.md` | `DSH_HOME` |

Windows 中的 `~` 表示 `%USERPROFILE%`。设置 `SKILLS_INSTALL_HOME` 可修改默认用户目录。

技能选择界面首项为独立的 **AGENTS.md** 选项，将 agent 的全局指令文件链接到本仓库的 [AGENTS.md](AGENTS.md)。文件包含 [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) 的四项英文原则：Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution。选中后直接替换现有文件，不备份；仓库更新通过链接生效。

使用 `--global-instructions`（PowerShell：`-GlobalInstructions`）预选该项，配合 `--yes` / `-Yes` 可跳过选择界面直接安装。安装时单独使用 `--yes` / `-Yes` 不修改全局指令文件。已有的本仓库指令链接默认选中；取消选择或卸载会移除该链接，不恢复原文件。

安装会覆盖同名项。取消选择或卸载只移除本仓库的链接。更新时运行 `git pull`，新增或移动 skill 后重新运行安装器。

安装 `opencode-tools`、`token-usage` 或 `wechat-get-data` 时，会清理本仓库对应的旧名称 `check-opencode-usage`、`token_usage` 或 `wechat_get_data` 链接。已有旧名称安装会默认勾选对应新名称；其他文件、目录和链接保持不变。

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

```bash
# 为 Codex 选择 skills
./install.sh install codex

# 为全部 agent 安装所有 skills
./install.sh install all --yes

# 卸载本仓库的链接
./install.sh uninstall all
```

使用方向键移动，空格选择，Enter 应用，q 取消。

### Windows

需要 PowerShell 5.1+，以及支持目录联接的本地文件系统。在 CMD 或 PowerShell 中运行：

```powershell
# 为 Codex 选择 skills
.\install.cmd install codex

# 为全部 agent 安装所有 skills
.\install.cmd install all -Yes

# 卸载本仓库的链接
.\install.cmd uninstall all
```

输入编号选择 skill 或类别，Enter 应用，q 取消。

### 选项

可选择 `claude`、`codex`、`opencode` 或 `all`。省略 agent 时，默认选择全部三个。

| Agent | 默认 skills 目录 | 配置覆盖变量 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/skills` | `CODEX_HOME` |
| OpenCode | `~/.config/opencode/skills` | `XDG_CONFIG_HOME` |

Windows 中的 `~` 表示 `%USERPROFILE%`。设置 `SKILLS_INSTALL_HOME` 可修改默认用户目录。

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

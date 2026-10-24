# 无界面客户端

## 安装

在实际使用 AI 工具的系统用户下安装。Node.js 至少 22.15.0，需要 npm 和 git；不要在 VPS 的 root 账号采集另一台电脑的数据。

先确定用户归属并询问设备展示名称，从管理员取得该用户的 `<user-id>-agent.env`，不要把整个 `users.json` 交给其他用户。Hub URL 和密钥复用已有服务端配置；新建 Hub 时另外询问 Hub/token 名称，不与设备名称混为一项。

```bash
SKILL=/path/to/token-usage
CLIENT="$HOME/token-monitor-agent"

python3 "$SKILL/scripts/manage.py" client \
  --root "$CLIENT" \
  --credentials /path/to/user-a-agent.env \
  --device unique-device-id --name "用户提供的设备名称" --install

cd "$CLIENT"
npm run preview
# 随后按下方「后台运行」启用自动上传与自启动
```

`preview` 不上传，`once` 上传一次，`start` 监视文件变化并持续上传。首次启动检查固定的 Tokscale 原生二进制并按需下载、校验；Hub 本身不需要这一步。

配置完成后默认继续安装并启用后台服务，不询问是否自动上传或上传频率。未指定频率时，已有安装保留 `.env` 中的设置，新安装使用上游默认 5 分钟周期并监听文件变化。用户指定频率时设置 `.env` 中的 `TOKEN_MONITOR_INTERVAL_MS`（毫秒）并重启服务；用户明确要求手动上传时才只使用 `npm run once`，不启用后台服务。

安装从官方 GitHub 提交解析 `token-monitor` 依赖，并固定其兼容的 Tokscale 基础版本。`--omit=dev` 不安装 Electron。生成的 `package-lock.json` 留在客户端目录，不放入 skill。

生成目录中的 `run.cjs` 从同目录 `.env` 加载配置，再运行官方采集器；无需手工导出密钥。默认开启历史与删除会话归档，关闭项目、会话标题和供应商额度采集。用户需要这些附加功能时再单独配置。

首次安装未指定名称时，脚本在交互终端询问；非交互运行缺少名称时会停止，由 agent 询问用户后以 `--name` 重试。名称保存在 `.env` 的 `TOKEN_MONITOR_DEVICE_NAME`，上传时作为 `displayName` 附加到原生协议。

重复运行生成脚本保留已有 `.env`，`--credentials` 与 `--device` 用于首次配置，`--name` 可更新展示名称。修改展示名称后重启采集服务即可，不修改设备 ID。切换账户、域名或设备 ID 前先停止采集器，按迁移说明处理。

## 后台运行

Linux 生成用户级 systemd 单元，使用生成时找到的 Node.js 绝对路径，不依赖交互式 shell 或 nvm 初始化。

```bash
mkdir -p ~/.config/systemd/user
install -m 644 "$CLIENT/token-usage-agent.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now token-usage-agent

systemctl --user status token-usage-agent --no-pager
journalctl --user -u token-usage-agent -n 50 --no-pager
systemctl --user stop token-usage-agent
systemctl --user start token-usage-agent
```

如果需要退出登录后继续运行，检查 `loginctl show-user "$USER" -p Linger`，按本次任务需要启用该用户的 linger。服务使用 `Restart=always`，因为官方 agent 在 SIGTERM/SIGHUP 后正常退出，`on-failure` 不会重新启动它。

macOS/Windows 使用相同 npm 客户端与 `.env`，持续运行交给 launchd 或 Task Scheduler；生成的 systemd 单元只用于 Linux。Node.js 路径变化后重新生成单元或调整 `ExecStart` 和 `PATH`。

安装完成前确认后台服务正在运行、已设置自启动，并通过成功上传日志及 Hub 中的设备记录验证；不要只给用户留下待执行命令。

## 从桌面客户端迁移

- 停止桌面客户端及其自动启动项，再启动 agent。不要同时运行两个采集器。
- 同一用户继续采集同一台设备时，复用原设备 ID，避免 Hub 把同一份历史作为另一台设备相加。
- 默认状态目录为 Linux `~/.config/Token Monitor/`、macOS `~/Library/Application Support/Token Monitor/`、Windows `%APPDATA%\Token Monitor\`，可用 `TOKEN_MONITOR_SHARED_DIR` 指定。保留已有状态与归档。
- 如果旧连接同步过会话标题，在旧 Hub、旧密钥、旧设备 ID 和旧状态目录仍可用时，执行一次 `--sync-session-titles=false` 的旧连接上传，确认清理后迁移。不要只删除本地状态。
- 改变设备 ID 后，确认旧采集器不会重新创建旧设备，再用对应用户的鉴权设备删除 API 清除旧快照。删除也会移除该设备的归档，不能把它当成普通隐藏开关。

## 检查与排查

成功日志形如 `posted <device-id>: today=... month=... allTime=...`。从公开统计确认正确用户下出现设备，历史与总量符合本地 preview。传输故障查看实际 agent 日志，不把仅健康检查成功当成上传成功。

| 现象 | 检查 |
| --- | --- |
| 401 | 对应用户的 Hub 密钥与 URL，不使用供应商 API key |
| 设备互相覆盖 | 同一用户下的设备 ID 必须唯一 |
| 总量翻倍 | 双采集器、WSL 重叠、复制日志或重复的账号级导出 |
| 缺少某工具 | 默认数据目录、当前系统用户、`TOKEN_MONITOR_CLIENTS` 与自定义扫描路径 |
| 缺少 `node:sqlite` | Node.js 版本或服务实际使用的可执行文件 |
| npm 安装包来源不符 | `package.json` 的依赖应为固定的官方 GitHub 提交，不是 registry 同名包 |
| 原生二进制版本不符 | 检查 `assets/versions.json`、生成包中的 overrides 和上游 vendor manifest |

停止后台服务后再执行写入状态的一次性采集或更新依赖，完成后恢复服务。保留 `.env`、状态与生成的 lockfile；不要卸载仍被其他工具使用的系统 Tokscale。

官方协议与平台细节：[headless agent](https://github.com/Javis603/token-monitor/blob/main/docs/headless-agent.md)、[配置](https://github.com/Javis603/token-monitor/blob/main/docs/configuration.md)。

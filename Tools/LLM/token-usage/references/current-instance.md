# 当前实例

以下为已有部署的定位信息。维护时先检查实际状态，不将这些值作为新部署的默认值。凭据与实时统计不存入 skill。

| 项目 | 位置或配置 |
| --- | --- |
| 公共网页 | `https://token.wty-yy.top` |
| SSH 别名 / 公网 IPv4 | `racknerd_184` / `198.44.54.184` |
| 服务端目录 | `/root/token_usage` |
| 服务端用户配置 | `/root/token_usage/config/users.json` |
| 用户接入文件 | `/root/token_usage/config/user-a-agent.env`、`user-b-agent.env` |
| 服务 / 备份定时器 | `token-usage.service` / `token-usage-backup.timer` |
| HTTPS / HTTP / loopback | `9443` / `80` / `17320` |
| Cloudflare 条件 | `(http.host eq "token.wty-yy.top" and ssl)` |
| Cloudflare Destination port | `9443` |
| 证书 / 续期 | `/root/token_usage/deploy/tls/` / `/root/.acme.sh` |
| 既有服务占用 | Xray `443`；x-ui `8443`、`2096`；订阅中转 `2053` |
| 本机工作目录 | `/home/yy/Documents/ai_search/token_usage` |
| 本机 agent 目录 | `/home/yy/Documents/ai_search/token_usage/agent` |
| 本机归属 / 设备 ID | `user-a` / `yy-x570-ud` |
| 本机设备展示名称 | `yy-X570-UD` |
| 本机 agent 配置 | 上述 agent 目录的 `.env`，权限 `600` |
| 本机用户服务 | `~/.config/systemd/user/token-usage-agent.service` |
| 本机 Node.js | `/home/yy/.nvm/versions/node/v22.22.2/bin/node` |
| 完整实例操作说明 | 本机及服务器的 `deploy/operations.md` |

两个 Hub/token 名称分别为 `yy`（`user-a`）和 `wt`（`user-b`）。本机已配置无界面 npm 客户端；不要再启动桌面客户端重复上传。实际密钥仅从实例配置读取，新增 Hub 时逐个询问名称。

```bash
# 服务器状态
ssh racknerd_184 'systemctl status token-usage --no-pager; systemctl list-timers token-usage-backup.timer --no-pager'

# 本机状态
systemctl --user status token-usage-agent --no-pager
journalctl --user -u token-usage-agent -n 30 --no-pager
```

这是部署定位参考，不是备份。恢复需要实例的 `backups/`、凭据和数据；不从 skill 创建新令牌替代工作中的旧令牌。

# 当前实例

以下为已有部署的定位信息。维护时先检查实际状态，不将这些值作为新部署的默认值。凭据与实时统计不存入 skill。

| 项目 | 位置或配置 |
| --- | --- |
| 公共网页 | `https://token.wty-yy.top` |
| SSH 别名 / 公网 IPv4 | `racknerd_188` / `192.255.132.188` |
| 服务端目录 | `/root/token_usage` |
| 服务端用户配置 | `/root/token_usage/config/users.json` |
| 用户接入文件 | `/root/token_usage/config/wty-agent.env`、`wt-agent.env`、`yjs-agent.env`、`zms-agent.env`、`xfy-agent.env` |
| 服务 / 备份定时器 | `token-usage.service` / `token-usage-backup.timer` |
| HTTPS / HTTP / loopback | `9443` / `80` / `17320` |
| Cloudflare 条件 | `(http.host eq "token.wty-yy.top" and ssl)` |
| Cloudflare Destination port | `9443` |
| Cloudflare Worker / 路由 | `token-usage` / `token.wty-yy.top/*`，失败时自动关闭 |
| Cloudflare KV / 绑定 | `token-usage-public` / `HUB_PUBLIC` |
| 公开快照推送 | `token-usage-cf-push.timer`，188 每 10 分钟运行 `deploy/cf-push.py` |
| 证书 / 续期 | `/root/token_usage/deploy/tls/` / `/root/.acme.sh` |
| 既有服务占用 | x-ui `443`、`2096`；Xray `8443`、`2053`、`2083` |
| 本机工作目录 | `/home/yy/Documents/ai_search/token_usage` |
| 本机 agent 目录 | `/home/yy/Documents/ai_search/token_usage/agent` |
| 本机归属 / 设备 ID | `wty` / `yy-x570-ud` |
| 本机设备展示名称 | `yy-X570-UD` |
| 本机 agent 配置 | 上述 agent 目录的 `.env`，权限 `600` |
| 本机用户服务 | `~/.config/systemd/user/token-usage-agent.service` |
| 本机 Node.js | `/home/yy/.nvm/versions/node/v22.22.2/bin/node` |
| 完整实例操作说明 | 本机及服务器的 `deploy/operations.md` |

当前五个 Hub/token 名称及用户 ID 均为 `wty`、`wt`、`yjs`、`zms`、`xfy`。前四位密钥于 2026-10-25 重新生成，`xfy` 于 2026-10-27 新增独立密钥。实际密钥仅从实例配置读取，新增 Hub 时逐个询问名称。本机、`ssh 4090`、`ssh 4090_133`、`ssh hongjun` 的现有采集器均归属 `wty`，设备 ID 和展示名称保留；均已设为每小时上传（`TOKEN_MONITOR_INTERVAL_MS=3600000`、`TOKEN_MONITOR_WATCH=0`）。不要再启动桌面客户端重复上传。

```bash
# 服务器状态
ssh racknerd_188 'systemctl status token-usage --no-pager; systemctl list-timers token-usage-backup.timer --no-pager'

# 本机状态
systemctl --user status token-usage-agent --no-pager
journalctl --user -u token-usage-agent -n 30 --no-pager
```

这是部署定位参考，不是备份。恢复需要实例的 `backups/`、凭据和数据；不从 skill 创建新令牌替代工作中的旧令牌。


2026-10-25 迁移：原 `racknerd_184` 因月流量超额暂停，其完整备份尚未取回。188 当前数据来自上述四台设备重新上传；其余用户和设备需更新新密钥后补传。已验证的 188 异地备份为本机工作目录 `backups/188-usage-20261025T114805Z.tar.gz`，包含四个用户配置、四台 wty 设备快照和完整当前历史 SQLite；该备份不是 184 的完整历史副本。

Hub 所有设备合计的上传请求体预算为 5 GB/天（Asia/Shanghai 零点换日），计数在 `history.sqlite/upload_usage`，重启保留，超额返回 429。2026-10-25 起网页资源、公开统计、上传流量面板和客户端 health 响应由 Cloudflare KV 提供；188 每 10 分钟主动推送，公开请求不回源，边缘缓存 60 秒并使用 ETag/304。推送失败保留旧快照；私有 API 及设备上传仍鉴权回源且不缓存。凭据只在本机及服务器实例的 `config/cloudflare.env`，不写入 skill。Worker 源码、推送脚本、回滚方式见实例 `deploy/operations.md`。这不限制 VPS 上其他服务的流量。

同账号的 `opencode-usage`、`commandcode-usage` 网站也每 10 分钟发布；源码位于本机相邻的 `opencode_usage/`、`commandcode_usage/`，操作说明见各目录 `AGENTS.md`。2026-10-25 已改为将 HTML 与元信息合并到一个 KV 键，每次发布只写一次；Worker 一次读取 HTML 与元信息，使用 60 秒实例内短缓存和 Last-Modified/304，保留原有访问保护。三个网站的常规定时 KV 写入合计约 432 次/天，不含部署、人工推送和重试。

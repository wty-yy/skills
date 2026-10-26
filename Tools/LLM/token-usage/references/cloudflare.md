# Cloudflare Worker 与公开快照

适用于网页访问不回源、源站主动推送的部署。源站保留原始数据、用户鉴权、设备上传和实时预算判断；Worker 只保存网页资源及固定公开接口，访问量不触发源站下载。

## 准备

先按服务端参考生成并启动 Hub。`manage.py server` 会准备：

| 文件 | 用途 |
| --- | --- |
| `deploy/cf-worker.mjs` | 根据 `--url` 写入目标主机名的 Worker |
| `deploy/cf-push.py` | 从 loopback 读取公开接口并写入 KV |
| `deploy/<service>-cf-push.service`、`.timer` | 使用生成目录与服务名称，每 10 分钟推送 |
| `tests/cf-worker.test.js`、`tests/cf-push.test.py` | 隔离验证路由、缓存、隐私和发布行为 |

推送端口取自 `config/deployment.json` 的 `port`，兼容旧配置时默认 `17320`。脚本只读取 `/api/public/stats`、`/api/public/uploads`、`/api/health` 和随附网页资源；不读取私有 Hub API、用户密钥或数据库。

## 配置与切换

1. 使用独立 KV 命名空间，避免覆盖其他网站；绑定到 Worker 的名称为 `HUB_PUBLIC`。复用已授权的 Cloudflare 凭据，配置文件不写入 skill。
2. 在生成目录的 `config/cloudflare.env` 保存 `CF_ACCOUNT_ID`、`CF_KV_NAMESPACE_ID`、`CF_API_TOKEN`，权限设为 `600`；API token 需要该账号的 KV 写入权限。
3. 将 `deploy/<service>-cf-push.service`、`.timer` 安装到 systemd，先手动启动推送服务，确认首次发布成功。首次发布包含网页资源，后续仅在资源内容变化时重新写入。
4. 部署生成的 `deploy/cf-worker.mjs`，保留 `HUB_PUBLIC` 绑定。先验证 Worker 已能提供页面和公开数据，再添加仅针对目标主机的 `<hostname>/*` **Route**，失败模式选择「失败时自动关闭」。保留当前代理 DNS 与源站端口规则；这里需要 Route 的同域回源行为，不用替换源站 DNS 的 Custom Domain。
5. 启用推送 timer，并确认自启动。网页修改后可手动启动一次推送；后端修改仍需重启源站 Hub。

默认服务名的操作示例：

```bash
install -m 644 "$ROOT/deploy/token-usage-cf-push.service" \
  "$ROOT/deploy/token-usage-cf-push.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl start token-usage-cf-push
systemctl enable --now token-usage-cf-push.timer
systemctl list-timers token-usage-cf-push.timer --no-pager
journalctl -u token-usage-cf-push -n 20 --no-pager
```

使用自定义 `--service` 时，相应替换单元名称。`manage.py` 只生成文件，不创建 CF 资源、保存 CF 凭据或启用系统服务。

## 缓存与验收

公开请求在 Worker 缓存未命中时只读 KV；KV 不可用返回 503，不回源。推送失败保留旧快照。边缘缓存 60 秒，忽略用户筛选及随机查询参数，JS/CSS 版本号单独缓存。源站每 10 分钟推送，网页每 10 分钟检查，另有 KV 传播及边缘缓存延迟。

`/api/health` 使用公开快照以兼容客户端探测；带鉴权的私有 API 及上传继续回源且 `no-store`，最终权限由源站验证；HTTP-01 证书验证仍回源。源站默认对所有设备合计实施 5 GB/天的上传请求体预算，按 Asia/Shanghai 零点换日，独立于网页所选的统计时区。页面上传流量是快照，不能用于判断实时剩余额度。

```bash
cd "$ROOT"
TZ=Asia/Shanghai node --test tests/*.test.js
python3 tests/cf-push.test.py
node deploy/verify.js
```

公网验证 `X-Hub-Source: cloudflare-kv`、重复访问的 `X-Hub-Cache: HIT`、`X-Hub-Published-At` 和条件请求 304；再确认一次真实设备上传及定时器自动推送。只读缓存功能测试不必停止真实 Hub。

公开快照每次合并为一个 KV 值，常规定时写入为 144 次/天，不含部署、资源变化、手动推送与重试。Cloudflare 请求和 KV 配额仍适用，且与账号内其他网站共享；缓存命中仍会执行当前 Worker。额度说明见 [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) 与 [KV pricing](https://developers.cloudflare.com/kv/platform/pricing/)。

需要恢复源站直接提供网页时，移除本次添加的主机专属 Worker Route，保留源站 DNS、端口规则和 Hub。正常运行不要改为失败时自动回源，否则超限后的访问会重新消耗 VPS 流量。

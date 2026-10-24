# 服务端部署与维护

## 组成

一个 Node.js 进程承载公开网页、按密钥分流的网关和每用户独立的 Token Monitor Hub。Hub 内部端口动态分配并只绑定 loopback。原始快照分别存入 `data/<user-id>.json`，长期每日、每月汇总存入 `data/history.sqlite`。

`assets/upstream.tar.xz` 包含固定提交的 Hub 依赖闭包、许可证和 `REVISION`，由生成脚本校验 SHA-256 后解包。服务端没有 npm 运行时依赖；客户端依赖另外安装。

## 生成目录

先检查目标目录、`ss -lntp`、现有反向代理和 Node.js。以下命令在目标 Linux 主机执行，`SKILL` 为已复制到该主机的 skill 路径。

```bash
SKILL=/path/to/token-usage
ROOT=/root/token_usage

python3 "$SKILL/scripts/manage.py" server \
  --root "$ROOT" --url https://usage.example.com \
  --user user-a=yy --user user-b=wt --tls-port 9443

# 安装固定版本的 Node.js；若已有运行环境，生成时使用 --node /absolute/path/to/node
python3 "$SKILL/scripts/manage.py" node --root "$ROOT"

cd "$ROOT"
TZ=Asia/Shanghai runtime/bin/node --test tests/*.test.js
```

每个新建 Hub/token 的名称先询问用户，再传入 `--user id=名称`；`yy`、`wt` 仅为当前实例已有名称。已有 ID 的密钥和名称保持不变，新 ID 创建独立数据区。首次创建时未传名称会在交互终端询问；非交互运行会停止并要求提供名称。重命名已有 Hub 直接编辑 `config/users.json` 的 `name` 后重启，不改 ID 或密钥。服务名称默认 `token-usage`，可用 `--service` 自定义。

`--port` 设置 loopback 网关端口，默认 `17320`；`--http-port` 默认 `80`；`--timezone` 默认 `Asia/Shanghai`。所有采集器采用相同日历时区；Hub 不重新划分设备上传的每日桶。

| 文件 | 用途 |
| --- | --- |
| `config/users.json` | 用户 ID、展示名称、随机密钥与设备别名；权限 `600` |
| `config/<user-id>-agent.env` | 对应用户的接入配置；权限 `600` |
| `config/deployment.json` | 公开地址和统计时区 |
| `src/`、`public/` | 可编辑后端与网页 |
| `vendor/token-monitor/` | 裁剪后的固定版本上游源码 |
| `data/` | 原始快照、SQLite 与 WAL |
| `data/device-names.json` | 客户端上传的设备展示名称，按用户和设备 ID 隔离 |
| `deploy/` | 单元文件、证书重载、验证和备份脚本 |
| `backups/` | 最近 30 份每日备份，包含用户密钥 |

服务端配置示例为 `{"users":[{"id":"alice","name":"Alice","token":"保留已有随机密钥","devices":{"laptop":"笔记本"}}]}`。不把该示例覆盖到已有配置；用户名称与设备别名可分别编辑。

## 域名与 HTTPS

直连部署把域名的 A 记录指向 VPS 公网 IPv4。使用 Cloudflare 代理且源站 HTTPS 不在 443 时，创建仅针对该主机的 Origin Rule：

```text
条件：(http.host eq "usage.example.com" and ssl)
Destination port：9443
```

`and ssl` 保证 HTTP-01 验证仍可回源 80。标准端口已空闲时可直接使用 443；已有反向代理或 Tunnel 时复用其路由，不再要求这条 Cloudflare 规则。代理或规则尚未接通不能算发布成功。

复用服务器已有的可信证书管理器。以下是已有 acme.sh 的 HTTP-01 配置；新主机先从官方来源安装并检查证书管理器。

```bash
mkdir -p "$ROOT/deploy/acme" "$ROOT/deploy/tls"

# 临时提供 HTTP-01 文件；在独立会话保持运行并记录进程，签发后只停止这个进程
python3 -m http.server 80 --bind 0.0.0.0 --directory "$ROOT/deploy/acme"
```

在另一会话签发并安装证书：

```bash
~/.acme.sh/acme.sh --issue -d usage.example.com \
  --webroot "$ROOT/deploy/acme" --server letsencrypt --keylength ec-256

~/.acme.sh/acme.sh --install-cert -d usage.example.com --ecc \
  --key-file "$ROOT/deploy/tls/key.pem" \
  --fullchain-file "$ROOT/deploy/tls/fullchain.pem" \
  --reloadcmd "$ROOT/deploy/reload-tls.sh"
```

启用续期调度并核对证书有效期。应用自己的 HTTP 监听随后接管 ACME 路径与 HTTPS 跳转。TLS 私钥不进入仓库或客户端配置。

## 启动与验证

以下按默认服务名执行；启动前证书必须就绪，临时 HTTP-01 进程已停止。

```bash
install -m 644 "$ROOT/deploy/token-usage.service" \
  "$ROOT/deploy/token-usage-backup.service" \
  "$ROOT/deploy/token-usage-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now token-usage.service token-usage-backup.timer

systemctl status token-usage --no-pager
systemctl reload token-usage
systemctl start token-usage-backup
systemctl list-timers token-usage-backup.timer
cd "$ROOT"
runtime/bin/node deploy/verify.js
```

使用已有 Node.js 时，测试和验证命令同样改用该可执行文件。服务器单元已写入生成时选择的 Node.js 路径。

`verify.js` 使用 Node fetch，通过配置的公网地址检查公开数据、每个用户的鉴权、非法上传与私有文件不可访问。它只做无效上传测试，不写入合成设备。Cloudflare 对 Python urllib 的拦截不等于 Node agent 不可用，使用真实客户端传输路径判断。

## 数据与接口

| 接口 | 行为 |
| --- | --- |
| `GET /api/public/stats` | 无需密钥，按白名单公开用量、工具、模型、设备别名与趋势 |
| `GET /api/health` | 无需密钥，兼容原生客户端的 Hub 版本探测 |
| `POST /api/ingest` | 用户密钥，更新该用户的一台设备快照 |
| `GET /api/stats`、`/api/devices`、`/api/history` | 用户密钥，仅返回该用户数据区 |
| 其他原生 Hub `/api/*` | 同一鉴权分流，包括同步设置、SSE、订阅与设备删除 |

密钥通过 `Authorization: Bearer ...` 或 `X-Token-Monitor-Secret` 传递，不放进 URL。用户密钥具有其数据区完整读写权限，不是只写令牌；两个人的密钥必须不同。

`POST /api/ingest` 可携带 `displayName`，服务端保留不超过 80 个字符的展示名称。改名不改变设备 ID；未携带该字段的后续上传保留已有名称。展示优先级为管理员 `devices` 别名、客户端名称、匿名设备编号。设备删除也清除对应名称。

网页参考 Tokscale 资料页，提供 Usage/Models、时间范围、2D/3D 贡献图、单日明细、曲线与 Token mix。历史中未提供的 Token 拆分标为未分类，不补造数值。Figtree 字体随附 OFL 许可证。

设备筛选默认全部设备，选择后汇总、历史图表和模型列表均限定到该设备；公开设备历史来自按用户和设备隔离的归档。分享链接保留筛选。趋势图 Token 坐标和提示默认用 K/M/B。页面默认选择近30天，趋势图默认显示每日用量。总览按用户绘制独立曲线，每条曲线的高度对应该用户用量，颜色在曲线、图例、悬浮提示和单日明细中保持一致，悬浮提示列出当天总量与各用户用量；单用户页面按模型展示。费用模式显示对应费用。总览单日明细在「工具与模型」上方列出各用户当天的 Token 用量。手机可点按趋势图查看该日期的提示及单日明细，抬手后提示保留，点按图表外部关闭；纵向滑动仍用于页面滚动。模型表默认按 Token 降序，点击表头切换字段与升降序。

中英文首次根据浏览器语言选择，手动语言和黑白主题选择保存在浏览器本地。单日明细和模型表显示缓存命中率，口径为缓存读取 Token ÷ 总输入 Token；总输入包含未缓存输入、缓存读取和缓存写入，不含输出。拆分不完整或总输入为零时显示「—」。

原生上传上限为 1 MiB。原生客户端会删减过大的明细，核心总量仍可上传。重复上传更新同一用户、设备的快照；SQLite 以用户、设备、日期作为主键更新历史，不按上传次数相加。原生每日历史有滚动窗口，额外归档保留已经接收的旧日期；无法恢复从未上传的记录。删除设备也会删除对应归档。

成本是模型价格估算，不是账单。无法定价的用量显示未定价标记。不同设备上传同一份日志或同一个账号级导出时可能重复计数。

## 备份、恢复与更新

备份脚本使用 SQLite backup API 复制数据库，再打包原始 JSON 和用户配置，保留最近 30 份。日程使用服务器时区。

恢复前停止服务，保留一份当前数据与配置副本。在空目录检查备份内容后恢复 `config/users.json` 与 `data/`，移走当前 SQLite 的旧 `-wal`、`-shm` 文件，再启动服务。恢复凭据后重新生成对应接入文件；不要另外生成新密钥。

网页只需更新 `public/`。后端源码更新后重启服务；证书变化只需重载。重跑生成脚本前备份定制源码；它保留用户配置与数据，但会重写应用和单元文件。

服务端在 HTML 的脚本和样式 URL 中加入内容摘要版本号。保留该机制，避免 CDN 或浏览器混用新版 HTML 和旧版资源。

升级上游时从干净官方 checkout 运行 `scripts/pack_upstream.py /path/to/checkout`。该脚本检查工作区、收集静态相对导入、保存许可证，更新压缩包和版本摘要；若出现非字面量导入则停止并检查，不继续猜测依赖。之后在隔离目录重新生成并执行功能测试，再更新真实实例。

---
name: token-usage
description: 部署和维护多用户、多设备的 AI Token 用量系统，包括 Token Monitor Hub、公开网页、历史存储、HTTPS 和 npm 无界面采集器。适用于复现整套部署、接入设备或排查上传与统计；不用于供应商账单查询。
---

# Token Usage

使用随附网页和服务端源码部署独立用户数据区，优先通过 npm 安装无界面客户端。运行依赖不存入 skill；Hub 的固定版本源码闭包已包含在压缩包中。

## 选择任务

- 新建或维护服务端：读 [references/server.md](references/server.md)。
- 安装或维护采集器：读 [references/client.md](references/client.md)。
- 维护当前已有部署：先读 [references/current-instance.md](references/current-instance.md)，再检查实际文件与服务状态。
- 只改网页：编辑部署目录的 `public/`，或在用户要求更新可复用模板时编辑 `assets/app/public/`。不为网页修改重建用户配置。

## 工作约定

1. 复用已确认的服务器、域名、用户归属与目录。为每个计划新建的 Hub/token 询问名称，以 `--user id=名称` 传入；用户已提供时直接复用，不默认使用「用户 A/B」。安装客户端时询问设备展示名称，以 `--name` 传入。缺少客户端归属时先确认对应用户，不默认把多个人的数据汇入第一个账户。
2. 在工作目录或服务器输出目录运行脚本，避免把凭据、数据库、日志、Node.js 或 `node_modules` 写回 skill。源码更新和实际部署分别处理。
3. `manage.py server` 生成应用、配置、systemd 单元和接入文件；保留已有密钥和数据，`--user` 中的新 ID 创建独立 Hub。它会覆盖应用源码，更新前备份本地定制。`client` 保留已有 `.env`，`--name` 可更新展示名称；换账户或设备 ID 时按客户端参考执行迁移。客户端配置完成后默认启用后台自动上传和自启动，不再询问是否开启；未指定频率时保留已有频率，新安装使用默认 5 分钟并监听文件变化。用户明确要求手动上传或指定频率时按其要求执行。
4. 安装前检查监听端口。已被其他服务占用的 443 不直接替换；使用独立 HTTPS 端口配合已有反向代理或 Cloudflare Origin Rule。不要改整个域名区域的 SSL 策略来解决单个站点问题。
5. 公共网页只读取 `/api/public/stats` 的字段白名单。完整 Hub API 继续按用户密钥鉴权；密钥、供应商账号、会话文本、项目路径和原始主机名不进入公开输出。
6. 同一用户的设备共享用户密钥，设备 ID 各自唯一。同一份日志只能由一个采集器负责；复制日志和账号级导出不会跨设备自动去重。Hub 密钥代表用户数据区，不自动识别切换过的供应商账号。
7. 固定版本见 `assets/versions.json`。npm 上同名的 `token-monitor` 不是 Javis603 项目；客户端使用官方 GitHub 依赖。升级时查看上游兼容性，再用 `scripts/pack_upstream.py` 从干净的官方 checkout 重建闭包。

## 脚本

```bash
# 先取得每个新 Hub/token 的名称；此处 yy/wt 是当前实例已有名称
python3 <skill>/scripts/manage.py server --root <output> --url https://<domain> --user user-a=yy --user user-b=wt

# 下载并校验 Linux Node.js；已有兼容运行环境时可通过 server --node 指定
python3 <skill>/scripts/manage.py node --root <output>

# 为对应用户生成采集器，并通过 npm 安装运行依赖
python3 <skill>/scripts/manage.py client --root <client-dir> --credentials <user-agent.env> --device <unique-id> --name "用户提供的设备名称" --install
```

Node.js 要求至少 22.15.0。生成脚本不启动系统服务、不配置 DNS、不签发证书，也不上传用量；这些步骤按对应参考在实际任务的授权范围内完成。

## 验收

- 在生成目录运行 `TZ=Asia/Shanghai node --test tests/*.test.js`，验证用户隔离、快照替换、公开字段、历史恢复、设备删除及上传限制。
- 验证公网 HTTPS、`deploy/verify.js`、服务自启、证书重载与一次实际备份。使用隔离目录做合成数据测试，不把测试记录混入真实用户。
- 客户端先 `npm run preview`，再按客户端参考启用后台服务；确认服务运行和自启动、对应用户设备出现、设备 ID 未重复、日志含成功上传记录。除用户明确要求外，不以仅生成配置、一次上传或前台运行作为安装完成。
- 页面变化检查桌面和手机布局、用户/周期筛选和空数据状态；趋势图同时检查桌面悬浮、手机点按定位、抬手保留提示与外部点按关闭。只部署新采集器时，接口结果和设备状态足以验证，无需重做网页。
- 网页保留浏览器语言自动选择、中英文按钮、黑白主题切换，以及单日/模型缓存命中率。命中率口径见服务端参考；缺少拆分时不猜测比例。

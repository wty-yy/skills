# 2026-11-09 独立 SSH 服务部署记录

2026-11-09，服务器 `amax`，Ubuntu 24.04，OpenSSH `9.6p1 Ubuntu-3ubuntu13.20`。

原始归档位于 `/data/user/wutianyang/Documents/ai_search/sshd_config`。以下记录本次实际操作；其他机器的安装使用 [通用流程](../readme.md)，不要沿用本次 IP、服务器地址和进程号。

## 部署结果

| 项目 | 配置 |
| --- | --- |
| 原服务 | `ssh.service`、`ssh.socket`，端口 `22` |
| 新服务 | `sshd-trusted.service`，已启动并设置开机启动 |
| 新监听地址 | `0.0.0.0:2222`，仅 IPv4 |
| 允许来源 | `115.154.236.42/32` |
| 允许账户 | `AllowUsers *@115.154.236.42`，允许该来源使用服务器上的正常账户认证登录 |
| 认证 | 保留密码、公钥及 PAM；账户仍需通过原有认证和账户检查 |
| root 登录 | 保留 `PermitRootLogin prohibit-password`，不开放 root 密码登录 |
| 防火墙 | 独立 nftables 表 `inet sshd_trusted`，仅处理 TCP `2222` |

白名单按服务器看到的来源 IP 判断。同一出口 IP 下的设备均可到达此端口，登录仍需有效的服务器账户凭据。原服务继续使用原配置，未重启。

## 文件

可复用模板与实际部署路径如下。SSH 和 nft 模板使用 IP、端口占位符，本次取值分别为 `115.154.236.42`、`2222`；服务单元与本次部署一致。

| 配套文件 | 实际部署路径 |
| --- | --- |
| [sshd_config_trusted.in](../assets/sshd_config_trusted.in) | `/etc/ssh/sshd_config_trusted` |
| [sshd-trusted.service](../assets/sshd-trusted.service) | `/etc/systemd/system/sshd-trusted.service` |
| [sshd-trusted.nft.in](../assets/sshd-trusted.nft.in) | `/etc/ssh/sshd-trusted.nft` |
| [verification-2026-11-09.txt](verification-2026-11-09.txt) | 本次检查结果 |

实际 SSH 配置权限为 `root:root 0600`，service 和 nft 文件权限为 `root:root 0644`。修改模板后，需要生成部署文件并重新安装到系统路径才会生效。

## 初始检查

1. 通过 `SSH_CONNECTION`、登录记录和活动 TCP 连接确认来源 IP 为 `115.154.236.42`，服务器本地地址为 `10.184.17.133`。
2. 检查 `sshd -T`、SSH 配置、PAM、封禁服务、nftables、IPv4/IPv6 iptables 及 legacy 规则，未发现按 IP 累计失败次数后临时封禁的配置。
3. UFW 未启用，原有 nftables 规则主要用于 Docker。端口 `2222` 空闲。
4. 原 SSH 主进程 PID 为 `4779`。部署前记录原配置校验值和防火墙结构，用于部署后比较。

```bash
# 查看原 SSH 服务和连接限制
sudo systemctl status ssh.service ssh.socket --no-pager
sudo /usr/sbin/sshd -T

# 查看防火墙及新端口占用
sudo ufw status verbose
sudo nft list ruleset
sudo ss -ltnp '( sport = :2222 )'
```

## 部署流程

1. 创建独立 SSH 配置，指定 `2222` 端口、独立 PID 文件和来源白名单，沿用原服务的认证及会话设置。
2. 创建专用 nftables 规则：允许 `115.154.236.42` 访问 TCP `2222`，丢弃其余 IPv4 和全部 IPv6 到该端口的流量。
3. 创建独立 systemd 服务，每次启动前检查 SSH 配置并加载防火墙；任一步失败时不启动新监听进程。
4. 执行配置检查、安装系统文件、加载服务并设置开机启动。

```bash
cd /data/user/wutianyang/Documents/ai_search/sshd_config

# 安装前检查配置；nft -c 仅检查，不应用规则
sudo /usr/sbin/sshd -t -f "$PWD/sshd_config_trusted"
sudo nft -c -f "$PWD/sshd-trusted.nft"
sudo systemd-analyze verify "$PWD/sshd-trusted.service"

# 安装独立配置、专用防火墙规则和服务单元
sudo install -o root -g root -m 0600 sshd_config_trusted /etc/ssh/sshd_config_trusted
sudo install -o root -g root -m 0644 sshd-trusted.nft /etc/ssh/sshd-trusted.nft
sudo install -o root -g root -m 0644 sshd-trusted.service /etc/systemd/system/sshd-trusted.service

# 启动新服务；不重启原 ssh.service 或 ssh.socket
sudo systemctl daemon-reload
sudo systemctl enable --now sshd-trusted.service
```

服务通过 `sshd -D -e -f /etc/ssh/sshd_config_trusted` 运行。它复用现有服务器主机密钥、用户账户和 PAM，不复制私钥或密码，不读取原服务的 `sshd_config.d` 配置片段。

新服务在启动前创建 OpenSSH 所需的 `/run/sshd` 目录，不在停止时删除该共享目录。新实例使用 `/run/sshd-trusted.pid`，与原实例 PID 文件分离。

防火墙文件只清空并重建自己的 `inet sshd_trusted` 表，使用 nft 批量原子加载。服务启动及重载时均先加载规则，失败时阻止后续步骤；重复加载不会叠加规则。停止服务后规则仍保留。开机启动时通过 `ExecStartPre` 恢复规则，不依赖启用 UFW 或全局 nftables 服务。

## 连接与管理

从来源 IP 为 `115.154.236.42` 的客户端连接；`10.184.17.133` 为服务器本地地址，也可换成原先可访问的服务器地址：

```bash
ssh -p 2222 wutianyang@10.184.17.133
```

更换用户名即可使用该来源 IP 下的其他正常服务器账户。

```bash
# 查看状态、监听地址、防火墙和日志
sudo systemctl status sshd-trusted.service --no-pager
sudo systemctl is-enabled sshd-trusted.service
sudo ss -ltnp '( sport = :22 or sport = :2222 )'
sudo nft list table inet sshd_trusted
sudo journalctl -u sshd-trusted.service -n 50 --no-pager

# 修改实际 SSH 配置或 nft 白名单后，检查并重载新服务
sudo /usr/sbin/sshd -t -f /etc/ssh/sshd_config_trusted
sudo nft -c -f /etc/ssh/sshd-trusted.nft
sudo systemctl reload sshd-trusted.service

# 仅在修改 systemd 单元文件后重新加载并重启新服务
sudo systemctl daemon-reload
sudo systemctl restart sshd-trusted.service
```

更换允许的来源 IP 时，同时修改 `/etc/ssh/sshd_config_trusted` 的 `AllowUsers` 和 `/etc/ssh/sshd-trusted.nft` 的允许规则，再检查并重载服务，同步部署档案。

## 验证结果

- SSH 配置、nftables 语法和 systemd 单元检查通过。
- 新服务 `active (running)`、`enabled`，主进程 PID 为 `1286388`，监听 `0.0.0.0:2222`。
- 重载后防火墙仍为两条规则，未重复添加。
- 在本机实际连接 `10.184.17.133:2222`，非白名单来源被丢弃；专用丢弃规则计数增加。
- 在临时隔离网络命名空间中使用实际安装的 SSH 配置和 nft 规则启动临时实例：模拟来源 `115.154.236.42` 收到 SSH banner，其他 IPv4 来源和 IPv6 来源均超时，允许与丢弃规则计数均增加；测试进程及临时 PID 文件已清理。
- 原 `ssh.service` 主进程仍为 PID `4779`，`ssh.socket` 正常；实际连接 `22` 端口仍收到 SSH banner。
- 原 SSH 配置校验值和原有防火墙结构均保持一致。
- 未重启服务器；已检查开机启动链接和启动前加载规则的配置。
- 2026-11-09 11:06，真实客户端已从 `115.154.236.42:36754` 连接 `10.184.17.133:2222`，以 `wutianyang` 登录到 `pts/7`。会话进程 `1348610` 的父进程为 `1348564`，后者由新服务主进程 `1286388` 创建，确认真实客户端通过独立服务登录成功。

## 原有限制说明

两个实例分别计算 `MaxStartups 10:30:100`：未认证连接少于 `10` 个时不触发该项限制，达到 `10` 个时以 `30%` 概率拒绝新连接，随连接数增加提高拒绝概率，达到 `100` 个时全部拒绝。完成认证或断开后释放名额。

`LoginGraceTime 120` 是单条连接的认证期限，`MaxAuthTries 6` 是单条连接的认证尝试上限，均不是按 IP 累计失败后临时封禁。独立实例隔离连接额度，两个实例仍共享服务器 CPU、内存和网络。

## 停用与移除

```bash
# 停用独立服务并取消开机启动，保留新端口的拦截规则
sudo systemctl disable --now sshd-trusted.service

# 完全移除时，确认 2222 已无监听，再删除本次新增的表和文件
sudo ss -ltnp '( sport = :2222 )'
sudo nft delete table inet sshd_trusted
sudo rm /etc/systemd/system/sshd-trusted.service /etc/ssh/sshd_config_trusted /etc/ssh/sshd-trusted.nft
sudo systemctl daemon-reload
```

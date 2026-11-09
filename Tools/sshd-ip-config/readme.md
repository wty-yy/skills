# SSH 来源 IP 白名单

为 Linux 服务器新增独立的 `sshd-trusted.service`，通过单独端口和来源 IPv4 白名单提供 SSH 入口。原 SSH 服务保持运行，两个实例分别计算 `MaxStartups` 额度。

## 使用

- [SKILL.md](SKILL.md)：部署、维护与验证规范
- [assets/](assets/)：SSH 配置、防火墙规则和 systemd 服务模板
- [本次安装记录](references/deployment-2026-11-09.md)：2026-11-09 的实际安装流程和真实客户端登录结果
- [原始验证结果](references/verification-2026-11-09.txt)：配置检查、进程及防火墙验证

需要已有 OpenSSH Server、systemd、nftables、Python 3.9+，以及 sudo 权限。模板以 Ubuntu 24.04 / OpenSSH 9.6 的现有部署为基础；认证、PAM、SFTP 和转发设置应先与目标机核对。

### 1. 检查目标机器

```bash
# 核对现有服务、有效配置、端口和防火墙
sudo systemctl status ssh.service ssh.socket --no-pager
sudo /usr/sbin/sshd -T
sudo ss -ltnp
sudo nft list ruleset
sudo ufw status verbose

# 查询当前连接；tmux 或常驻工具中的 SSH 环境变量可能保留旧值
ss -tn state established '( sport = :22 or sport = :2222 )'
who -u
```

确认新端口空闲，记录原配置、服务主进程和防火墙结构。目标机已使用 UFW、firewalld 或其他管理器时，先核对其生效链和优先级，避免直接套用本例规则。

### 2. 生成部署文件

在本 skill 目录执行，替换 `<CLIENT_IPV4>` 为服务器实际看到的客户端出口 IPv4。本例新端口为 `2222`：

```bash
TRUSTED_IPV4='<CLIENT_IPV4>'
TRUSTED_PORT=2222
sshd_stage=$(mktemp -d)

TRUSTED_IPV4="$TRUSTED_IPV4" TRUSTED_PORT="$TRUSTED_PORT" SSHD_STAGE="$sshd_stage" python3 - <<'PY'
import ipaddress
import os
from pathlib import Path
import shutil

client = str(ipaddress.IPv4Address(os.environ['TRUSTED_IPV4']))
port = int(os.environ['TRUSTED_PORT'])
if not 1 <= port <= 65535:
    raise ValueError('Invalid SSH port')
stage = Path(os.environ['SSHD_STAGE'])
for name in ['sshd_config_trusted', 'sshd-trusted.nft']:
    text = (Path('assets') / (name + '.in')).read_text()
    text = text.replace('__TRUSTED_IPV4__', client).replace('__TRUSTED_PORT__', str(port))
    (stage / name).write_text(text)
shutil.copyfile('assets/sshd-trusted.service', stage / 'sshd-trusted.service')
print(stage)
PY
```

生成后的关键配置为 `Port 2222` 和 `AllowUsers *@<CLIENT_IPV4>`。该通配符允许来源 IP 使用所有正常服务器账户，仍需通过原有账户认证；root 保留禁止密码登录的策略。

先检查生成文件中的认证和会话选项，与原服务的有效配置比较。模板不读取原服务的配置片段，后续认证策略需分别维护。

### 3. 检查并安装

先确认以下三个系统文件尚不存在。已有同名部署时，比较并备份现有文件后按维护流程更新，不直接覆盖。

```bash
# 创建 OpenSSH 需要的运行目录；不在新服务停止时删除
sudo install -d -o root -g root -m 0755 /run/sshd

# 仅检查配置，不应用防火墙
sudo /usr/sbin/sshd -t -f "$sshd_stage/sshd_config_trusted"
sudo nft -c -f "$sshd_stage/sshd-trusted.nft"
sudo systemd-analyze verify "$sshd_stage/sshd-trusted.service"

# 检查通过后安装；不要修改原 sshd_config 或重启原 SSH 服务
sudo install -o root -g root -m 0600 "$sshd_stage/sshd_config_trusted" /etc/ssh/sshd_config_trusted
sudo install -o root -g root -m 0644 "$sshd_stage/sshd-trusted.nft" /etc/ssh/sshd-trusted.nft
sudo install -o root -g root -m 0644 "$sshd_stage/sshd-trusted.service" /etc/systemd/system/sshd-trusted.service
sudo systemctl daemon-reload
sudo systemctl enable --now sshd-trusted.service
```

### 4. 验证连接

```bash
sudo systemctl status sshd-trusted.service --no-pager
sudo systemctl is-enabled sshd-trusted.service
sudo ss -ltnp '( sport = :22 or sport = :2222 )'
sudo nft list table inet sshd_trusted
sudo journalctl -u sshd-trusted.service -n 50 --no-pager
```

从白名单客户端执行，替换服务器地址和账户名：

```bash
ssh -p 2222 '<USER>@<SERVER_ADDRESS>'
```

验证真实认证成功，并从其他来源测试访问被阻止。服务器上的 `127.0.0.1` 和本机地址也不在该白名单内，本机直接测试新端口预期被丢弃。

通过活动连接的目标端口、登录用户及会话进程的父子关系确认使用新服务；不要仅查看旧 shell 中的 `SSH_CONNECTION`。复查原服务、原配置及其他防火墙结构。开机启用检查与实际重启测试分别记录。

## 实现与维护

独立服务以 root 运行 `sshd -D -e -f /etc/ssh/sshd_config_trusted`，使用 `/run/sshd-trusted.pid`。无需新增 `.socket` 单元。`ListenAddress` 指定服务器监听地址，不是来源白名单。

`AllowUsers` 在认证阶段限制登录；nftables 在连接进入 SSH 前限制来源，避免其他 IP 占用新实例的未认证连接额度。专用 `inet sshd_trusted` 表允许指定 IPv4 到新端口，丢弃其余 IPv4 和全部 IPv6 到该端口的流量，其他流量继续通过原有规则处理。

服务在启动前检查 SSH 配置并加载专用规则，任一步失败时不会启动新监听。重载时检查配置、原子替换专用规则，再向新主进程发送 HUP。停止服务后规则仍保留；开机启动时重新加载。不依赖启用 UFW 或全局 nftables 服务。

更换来源 IP 时，同时修改实际 SSH 配置中的 `AllowUsers` 和 nft 文件的允许规则，再检查和重载：

```bash
sudo /usr/sbin/sshd -t -f /etc/ssh/sshd_config_trusted
sudo nft -c -f /etc/ssh/sshd-trusted.nft
sudo systemctl reload sshd-trusted.service
sudo nft list table inet sshd_trusted
```

仅修改 systemd 单元文件时，执行 `sudo systemctl daemon-reload` 后重启 `sshd-trusted.service`。更换端口还需同步修改 SSH 配置、防火墙匹配及客户端连接命令。

`MaxStartups 10:30:100` 根据当前未认证连接数决定是否拒绝新连接；`LoginGraceTime 120` 和 `MaxAuthTries 6` 分别是单条连接的认证期限和尝试上限。这些参数没有按 IP 累计失败后封禁固定时间的含义。独立进程隔离额度，仍共享服务器资源。

### 停用与移除

```bash
# 停止新服务并取消开机启动，保留端口拦截规则
sudo systemctl disable --now sshd-trusted.service

# 确认新端口已无监听后，完全移除本次新增内容
sudo ss -ltnp '( sport = :2222 )'
sudo nft delete table inet sshd_trusted
sudo rm /etc/systemd/system/sshd-trusted.service /etc/ssh/sshd_config_trusted /etc/ssh/sshd-trusted.nft
sudo systemctl daemon-reload
```

## 参考

- [OpenSSH sshd 手册](https://man.openbsd.org/sshd.8)
- [OpenSSH 9.6 配置实现](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/servconf.c)
- [nftables 原子规则替换](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement)

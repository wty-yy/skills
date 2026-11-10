[English](README.md) | 简体中文

## 介绍

该脚本为 Debian/Ubuntu 配置 SSH、TigerVNC 和 noVNC，可选安装 ZeroTier 并加入指定网络。TigerVNC 的 `x0vncserver` 共享当前 X11 桌面，根据 `xrandr` 检测结果为每个屏幕创建独立端口。

默认构建 TigerVNC `1.16.2`，应用随仓库提供的输入补丁，并设置 `KeyEventDelay=20`，支持 AVNC 手机键盘连续输入中文。

键码恢复补丁默认启用 `RecoverKeyMappings`：在 X11 中记录临时映射及所属实例；槽位不足时，仅回收实例已退出、映射内容未变且未按下的键码。分配与回收通过 X server grab 串行化，避免多个屏幕同时抢占槽位。旧版未登记的映射不会自动清理。

## 使用

```bash
# 安装 Python；其他依赖由脚本安装
sudo apt update
sudo apt install -y python3

# 配置远程桌面；在当前 X11 会话登录后运行
sudo python3 auto_remote_config.py --vnc_password '<your_password>'

# 可选：加入 ZeroTier 并为源码下载设置代理
sudo python3 auto_remote_config.py \
    --vnc_password '<your_password>' \
    --zt_network_id '<your_network_id>' \
    --proxy 7890
```

`--zt_network_id` 留空时跳过 ZeroTier。`--proxy` 支持端口号、`host:port` 或完整代理 URL；APT 安装使用不含代理变量的环境。

安装过程会生成并重启 `multivnc.service`。首次源码编译需要联网；只有版本匹配且同时具备 `KeyEventDelay`、`RecoverKeyMappings` 的程序才会复用，旧补丁版本会重新编译。

### 连接

- AVNC：第一个屏幕连接 `<your_ip>:5900`，后续屏幕依次使用 `5901`、`5902` 等。
- noVNC：第一个屏幕访问 `http://<your_ip>:6080/vnc.html`，后续屏幕依次使用 `6081`、`6082` 等。
- 屏幕顺序与检测结果一致，使用命令行设置的 VNC 密码。

```bash
# 查看服务状态
sudo systemctl status multivnc.service

# 重启服务，无需重启电脑
sudo systemctl restart multivnc.service

# 停止服务
sudo systemctl stop multivnc.service

# 查看服务日志
sudo journalctl -u multivnc.service -f
```

## 实现

- `auto_remote_config.py`：安装依赖、校验源码 SHA-256、构建 TigerVNC、检测屏幕并生成系统服务。
- `tigervnc-key-event-delay.patch`：增加可配置的按键释放延时。
- `tigervnc-keymap-recovery.patch`：记录临时映射归属，在实例异常退出后按需回收。
- `start_multivnc.sh.in`：生成各屏幕的启动脚本，自动重试退出的 TigerVNC 和 noVNC 进程。

安装位置：

- TigerVNC：`~/.local/bin/x0vncserver-avnc`
- 启动脚本：`~/.local/bin/start_multivnc.sh`
- 系统服务：`/etc/systemd/system/multivnc.service`
- noVNC：`/opt/noVNC`
- 构建缓存：`/var/cache/auto_remote_config/tigervnc-1.16.2`
- 密码文件：`/etc/x11vnc.pass`，保留原文件名以兼容现有配置，权限为 `0640`，服务用户所属组可读取

默认 X11 显示为 `:1`。启动脚本优先使用 `XAUTHORITY`，否则检查 `/run/user/<uid>/gdm/Xauthority` 和 `~/.Xauthority`；登录前等待认证文件就绪。

### 验证键码恢复

安装测试依赖 `xvfb`、`python3-xlib`，使用已编译的新二进制运行：

```bash
/usr/bin/python3 tests/test_keymap_recovery.py --server ~/.local/bin/x0vncserver-avnc -v
```

测试自行创建隔离的 Xvfb 桌面和仅监听本机的测试端口，验证崩溃恢复、超过 19 个不同汉字、存活实例保护、未登记或已修改的映射、按键未释放及正常退出清理，不连接当前桌面。支持 `--xvfb /path/to/Xvfb`。测试不代表已修复触发进程崩溃的 Xlib/XCB 问题。

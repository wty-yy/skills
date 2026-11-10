---
name: linux-vnc-remote-control
description: 在 Debian/Ubuntu 上安装、配置或排查共享当前 X11 桌面的 TigerVNC、noVNC 和 SSH，支持多屏独立端口、AVNC 中文输入及可选 ZeroTier 组网。用于 Linux 远程桌面部署和维护，不适用于 Wayland 原生桌面或独立虚拟桌面。
---

# Linux VNC Remote Control

使用随附脚本部署共享当前桌面的远程访问服务。仅在用户要求部署或维护的目标机器上执行安装。

## 随附文件

- [scripts/auto_remote_config.py](scripts/auto_remote_config.py)：安装依赖、校验并编译 TigerVNC、检测屏幕、生成 systemd 服务。
- [scripts/tigervnc-key-event-delay.patch](scripts/tigervnc-key-event-delay.patch)：TigerVNC 键盘事件延时补丁。
- [scripts/tigervnc-keymap-recovery.patch](scripts/tigervnc-keymap-recovery.patch)：临时键码归属登记与异常退出恢复补丁。
- [scripts/start_multivnc.sh.in](scripts/start_multivnc.sh.in)：按屏幕启动并自动重试 TigerVNC 和 noVNC 的模板。
- [scripts/tests/test_keymap_recovery.py](scripts/tests/test_keymap_recovery.py)：在隔离 Xvfb 中验证崩溃恢复和多实例映射保护；依赖 `xvfb`、`python3-xlib`。
- 使用和安装位置详见 [中文说明](references/README.zh-CN.md) 或 [English guide](references/README.md)。其中安装命令从本 skill 的 `scripts/` 目录执行。

以上文件复制自 `dotfiles/scripts/auto_remote_config/`。部署时使用 skill 内的副本，不依赖原仓库路径。Python 安装脚本通过自身路径查找补丁和模板，因此安装脚本、两个补丁和启动模板必须放在同一目录；远程部署时一并传输。

## 部署前

- 确定目标机器、已登录图形桌面的普通用户和连接方式，复用会话中已有的信息。
- 检查目标为 Debian/Ubuntu、使用 systemd，并有活动的 X11 桌面。此脚本共享实际屏幕，不创建虚拟桌面。
- 脚本的屏幕检测和服务配置固定使用 `DISPLAY=:1`。先在目标用户的图形会话检查 `echo "$XDG_SESSION_TYPE"`、`echo "$DISPLAY"` 和 `xrandr --listmonitors`；通过 SSH 检查时需使用对应会话的 DISPLAY 和 XAUTHORITY，不能只看 SSH 环境变量。若实际显示不同，先定位脚本中的 `:1` 并在部署副本中一致调整，不要假设支持 `--display` 参数。
- 安装必须从目标普通用户通过 `sudo python3 ...` 执行；脚本依靠 `SUDO_USER` 确定主目录和服务用户，直接以 root 登录运行不符合其要求。
- 安装前先询问用户是否使用 ZeroTier，按下节引导完成选择和准备；已有明确选择时不重复询问。尚未答复时先做只读检查，等待选择后再执行安装，不能将未提供网络 ID 视为选择跳过。
- 获取必填的 VNC 密码，下载代理按需提供。ZeroTier 首次安装会先调用 `curl`，启用该选项前确保目标已有 `curl`。
- 若已有部署，先检查 `multivnc.service`、启动脚本及端口占用；需要覆盖时备份现有配置。重新运行会重写密码、启动脚本和服务并重启服务。

### ZeroTier 选择与引导

首次询问可使用：“是否需要通过 ZeroTier 从外网连接这台电脑？可以选择使用已有网络、创建新网络，或不使用 ZeroTier。”

- 不使用：省略 `--zt_network_id`，按用户选定的网络方式连接。
- 使用已有网络：获取用户指定的 Network ID，确认用于连接的客户端也会加入该网络。
- 创建新网络：引导用户登录 ZeroTier Central，按 [官方入门指南](https://docs.zerotier.com/quickstart/) 创建或选择网络，复制 Network ID；收到 ID 后再执行带 `--zt_network_id` 的安装命令。

安装后继续引导，不以脚本输出成功作为组网完成：

1. 用 `sudo zerotier-cli info` 获取服务器 Node ID，引导用户在 Central 对应网络中核对该设备并授权；客户端也需要加入同一网络并按需授权。
2. 用 `sudo zerotier-cli listnetworks` 检查目标网络状态和分配的地址。若为 `ACCESS_DENIED`，先完成授权再复查；尚未授权时明确标记待完成。
3. 获取服务器实际分配的 ZeroTier IP，指导用户从客户端测试 VNC 或 noVNC，并在最终连接信息中列出该地址。不要仅依赖安装脚本筛选出的物理网卡 IP。

## 安装

在目标机器切换到包含这三个运行文件的目录，再执行：

```bash
sudo apt update
sudo apt install -y python3
sudo python3 auto_remote_config.py --vnc_password '<VNC_PASSWORD>'
```

需要 ZeroTier 或源码下载代理时，按需追加参数：

```bash
sudo python3 auto_remote_config.py \
    --vnc_password '<VNC_PASSWORD>' \
    --zt_network_id '<ZEROTIER_NETWORK_ID>' \
    --proxy 7890
```

替换占位符后执行；不使用的可选参数直接省略。代理接受端口、`host:port` 或完整 URL，仅用于下载等网络请求，APT 环境会移除代理变量。

脚本会启用 SSH；默认构建 TigerVNC `1.16.2`，验证源码 SHA-256 并应用两个补丁；安装 noVNC；按 `xrandr` 检测结果创建各屏幕端点，启用并重启 `multivnc.service`。只有相同版本且同时具备 `KeyEventDelay`、`RecoverKeyMappings` 的二进制才会复用。启动模板设置 `KeyEventDelay=20`，用于 AVNC 手机键盘连续输入中文；键码恢复默认开启。

脚本末尾会打印 VNC 密码，分享日志或汇报结果时隐去密码。ZeroTier 加网请求后，如网络要求授权，还需在对应管理端批准；加网请求成功不等于已连通。

## 验证与连接

```bash
sudo systemctl is-enabled multivnc.service
sudo systemctl status multivnc.service --no-pager
sudo journalctl -u multivnc.service -n 80 --no-pager
sudo ss -ltnp
```

确认服务启用、无持续重试错误，每个屏幕对应的端口实际监听。启动器会重试失败的组件，仅有 systemd 显示 active 不能证明桌面共享正常。

- AVNC 或其他 VNC 客户端：首屏 `<IP>:5900`，后续依次 `5901`、`5902`。
- noVNC：首屏 `http://<IP>:6080/vnc.html`，后续依次 `6081`、`6082`。
- 屏幕顺序取自安装时检测结果，使用提供的 VNC 密码。连接 IP 按实际可达的局域网或 ZeroTier 地址选择；脚本汇总的地址只筛选物理/无线网卡，不保证列出 ZeroTier 地址。

有客户端测试条件时验证画面、鼠标、键盘和各屏幕映射；使用 AVNC 时检查连续中文输入。汇报实际验证范围、连接地址和服务状态，未做客户端连接时明确说明。

## 维护与排查

```bash
sudo systemctl restart multivnc.service
sudo systemctl stop multivnc.service
sudo journalctl -u multivnc.service -f
```

- 检测不到屏幕：检查登录状态、X11 显示号、XAUTHORITY 和目标用户执行 `xrandr` 的结果，不反复运行完整安装。
- 启动器等待认证文件：它优先使用 `XAUTHORITY`，然后检查 `/run/user/<uid>/gdm/Xauthority` 和 `~/.Xauthority`；先确认图形用户已登录且文件可读。
- 端口未监听或连接失败：结合组件日志、端口占用、目标 IP 和现有网络规则定位，不仅依靠服务状态判断。
- 屏幕布局改变：启动脚本保存的是安装时的几何参数，不会实时重新检测；按新检测结果更新启动脚本，或在备份并确认参数后重新运行安装。
- 编译或下载失败：查看具体失败命令、代理和 SHA-256 校验结果；不要跳过源码校验。
- 中文输入出现 `Failure adding new keysym`：检查键码是否耗尽、进程是否异常退出以及是否运行恢复补丁。补丁只回收已登记、所属实例已退出、内容未变且未按下的映射；旧版残留没有归属记录，需要备份后单独判断，不能在各屏幕重启时批量清空 Unicode 映射。Xlib/XCB 崩溃本身需另行排查。

安装位置和完整依赖以随附脚本及参考说明为准。修复时只调整与当前问题有关的配置。

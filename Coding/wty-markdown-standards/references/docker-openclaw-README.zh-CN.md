# OpenClaw Docker 使用说明

[English Version](./docker-openclaw-README.md)

这个目录包含 OpenClaw 开发环境的 Docker 镜像和启动脚本。几个文件功能如下：

- `Dockerfile`：基于 `ubuntu:24.04` 构建镜像，创建与宿主机同 UID/GID 的普通用户，按 `nvm` 方式安装 Node.js 24，并安装 `openclaw` 和 `pm2`
- `run.sh`：辅助脚本，支持 build / up / shell / stop / rm / rmi / logs，自动挂载容器home目录到`./openclaw-data`下

额外功能：
- 修复`openclaw`中无法链接代理问题
- Dockerfile安装支持自动代理识别，如果宿主机设置了`HTTP_PROXY`/`HTTPS_PROXY`环境变量，build中会自动找到宿主机的代理设置并配置到镜像里
- 地区时间`TZ`识别

脚本：
- 支持直接将`codex`, `gemini`的`oauth.json`转为openclaw的凭证更新到`auth-profiles.json`内（见[自动配置凭证](#自动配置凭证)）

当前脚本构建结果默认使用：

- 镜像名：`wtyyy/openclaw:latest`
- 容器名：`openclaw`
- 容器内用户名：默认固定为 `user`
- 容器内 UID/GID：默认取宿主机当前 `id -u` / `id -g`

目录如下：
- [构建/启动容器](#构建启动容器)
- [管理openclaw](#管理openclaw)
- [自动配置凭证](#自动配置凭证)
- [其他细节](#其他细节)

## 构建/启动容器

```bash
cd slay-the-spire2-ai
# 创建并启动容器
./docker-openclaw/run.sh
# 仅构建镜像
./docker-openclaw/run.sh build
# 进入正在运行的容器
./docker-openclaw/run.sh shell
# 停止容器
./docker-openclaw/run.sh stop
# 删除容器
./docker-openclaw/run.sh rm
# 删除镜像
./docker-openclaw/run.sh rmi
# 查看日志
./docker-openclaw/run.sh logs
```

使用完成后，删除容器数据也会保存在本地，因为容器内的 `/home/${HOST_USER}` 是挂载的 `${PROJECT_DIR}/openclaw-data`，你可以在宿主机这个目录里看到数据。

## 管理openclaw

openclaw依赖后端启动的`openclaw-gateway`，我们用pm2来管理这个进程，确保它在容器里一直运行，并且如果崩溃了能自动重启。

这里给出一些openclaw常用命令，可以直接使用
```bash
openclaw configure  # 配置通讯，Model, Gateway Port等
openclaw tui        # 启动TUI界面，可以在里面查看连接的客户端，日志等
openclaw dashboard  # 启动Dashboard界面
```

pm2管理openclaw-gateway这个进程，一些常用命令如下：

```bash
# 查看日志，连接信息和错误都会输出在日志里
pm2 logs openclaw-gateway
# 查看状态
pm2 status
# 重启
pm2 restart openclaw-gateway
# 停止
pm2 stop openclaw-gateway
```

## 自动配置凭证
如果宿主机安装过`codex, gemini`，并已登陆，执行
```bash
cd slay-the-spire2-ai
# codex凭证安装到容器
node docker-openclaw/tools/import-codex-auth.js ~/.codex/auth.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
# gemini凭证安装到容器
node docker-openclaw/tools/import-gemini-auth.js ~/.gemini/oauth_creds.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
```
安装完成后需执行`pm2 restart openclaw-gateway`重启网关让它加载新的凭证。

## 其他细节
### 容器运行参数

脚本默认会带上这些运行参数

- `--gpus all`
- `--privileged`
- `DISPLAY`
- `/tmp/.X11-unix:/tmp/.X11-unix`
- `/usr/share/vulkan/icd.d/nvidia_icd.json:/usr/share/vulkan/icd.d/nvidia_icd.json:ro`
- `--net=host`
- `--ipc=host`
- 项目目录挂载：`${PROJECT_DIR}:/workspace`
- Home 挂载：`${PROJECT_DIR}/openclaw-data:/home/${HOST_USER}`

### 镜像里安装了什么

镜像会安装：

- 通过 `nvm` 安装的 Node.js 24
- npm
- `openclaw`
- `pm2`
- 构建阶段执行过的 `openclaw setup`
- 自动启动的 `openclaw-gateway`
- 与宿主机同 UID/GID 的普通用户
- 可直接使用的免密码 `sudo`
- 启动时自动补齐到挂载 home 的默认模板：`nvm`、`zsh/p10k`、`vim`、OpenClaw 相关文件
- 常用工具：`curl`、`git`、`sudo`、`vim`、`zsh`、`powerlevel10k`、`zsh-autosuggestions`、`zsh-syntax-highlighting`、`gruvbox`

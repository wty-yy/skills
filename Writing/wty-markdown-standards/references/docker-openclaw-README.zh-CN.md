# OpenClaw Docker 使用说明

[English Version](./docker-openclaw-README.md)

该目录包含 OpenClaw 开发环境的 Docker 镜像与启动脚本。主要文件：

- `Dockerfile`：基于 `ubuntu:24.04` 构建镜像，创建与宿主机同 UID/GID 的普通用户，通过 `nvm` 安装 Node.js 24，并安装 `openclaw` 和 `pm2`
- `run.sh`：辅助脚本，支持 `build` / `up` / `shell` / `stop` / `rm` / `rmi` / `logs`，并将容器 home 目录挂载至 `./openclaw-data`

额外特性：

- 修复 `openclaw` 代理连接问题
- 构建镜像时自动检测宿主机 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量并写入镜像代理配置
- 自动检测宿主机 `TZ` 时区设置

脚本：

- 支持将 `codex`、`gemini` 凭证导入 OpenClaw 的 `auth-profiles.json`（见[自动配置凭证](#自动配置凭证)）

默认构建结果：

- 镜像名：`wtyyy/openclaw:latest`
- 容器名：`openclaw`
- 容器内用户名：固定为 `user`
- 容器内 UID/GID：当前宿主机 `id -u` / `id -g`

目录：

- [构建/启动容器](#构建启动容器)
- [管理 OpenClaw](#管理-openclaw)
- [自动配置凭证](#自动配置凭证)
- [其他细节](#其他细节)

## 构建/启动容器

```bash
cd slay-the-spire2-ai
# 创建并启动容器
./docker-openclaw/run.sh
# 仅构建镜像
./docker-openclaw/run.sh build
# 进入运行中的容器
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

容器内 `/home/${HOST_USER}` 挂载到 `${PROJECT_DIR}/openclaw-data`，删除容器后数据仍保留在宿主机该目录中。

## 管理 OpenClaw

OpenClaw 依赖后台进程 `openclaw-gateway`，由 `pm2` 托管并在异常退出时自动重启。

常用 OpenClaw 命令：

```bash
openclaw configure  # 配置通讯、模型、网关端口等
openclaw tui        # 启动 TUI 界面，查看客户端、日志与连接状态
openclaw dashboard  # 启动 Dashboard 界面
```

常用 `pm2` 管理命令：

```bash
# 查看日志（包含连接详情与报错）
pm2 logs openclaw-gateway
# 查看状态
pm2 status
# 重启网关
pm2 restart openclaw-gateway
# 停止网关
pm2 stop openclaw-gateway
```

## 自动配置凭证

若宿主机已安装并登录 `codex` 或 `gemini`，执行：

```bash
cd slay-the-spire2-ai
# 导入 Codex 凭证到容器
node docker-openclaw/tools/import-codex-auth.js ~/.codex/auth.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
# 导入 Gemini 凭证到容器
node docker-openclaw/tools/import-gemini-auth.js ~/.gemini/oauth_creds.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
```

导入完成后执行 `pm2 restart openclaw-gateway` 使网关重新加载凭证。

## 其他细节

### 容器运行参数

该脚本默认附带以下运行参数：

- `--gpus all`
- `--privileged`
- `DISPLAY`
- `/tmp/.X11-unix:/tmp/.X11-unix`
- `/usr/share/vulkan/icd.d/nvidia_icd.json:/usr/share/vulkan/icd.d/nvidia_icd.json:ro`
- `--net=host`
- `--ipc=host`
- 项目目录挂载：`${PROJECT_DIR}:/workspace`
- Home 目录挂载：`${PROJECT_DIR}/openclaw-data:/home/${HOST_USER}`

### 镜像内容

镜像默认安装与配置：

- 通过 `nvm` 安装的 Node.js 24
- `npm`
- `openclaw`
- `pm2`
- 构建阶段执行的 `openclaw setup`
- 自动启动的 `openclaw-gateway`
- 与宿主机同 UID/GID 的普通用户
- 免密码 `sudo`
- 启动时同步挂载 home 模板：`nvm`、`zsh/p10k`、`vim` 及 OpenClaw 相关文件
- 常用工具：`curl`、`git`、`sudo`、`vim`、`zsh`、`powerlevel10k`、`zsh-autosuggestions`、`zsh-syntax-highlighting`、`gruvbox`

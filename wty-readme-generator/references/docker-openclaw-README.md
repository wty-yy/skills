# OpenClaw Docker Guide

[中文版](./docker-openclaw-README.zh-CN.md)

This directory contains the Docker image and helper scripts for the OpenClaw development environment. Main files:

- `Dockerfile`: builds from `ubuntu:24.04`, creates a regular user with the host UID/GID, installs Node.js 24 through `nvm`, and installs `openclaw` and `pm2`
- `run.sh`: helper script for `build` / `up` / `shell` / `stop` / `rm` / `rmi` / `logs`, and mounts the container home directory under `./openclaw-data`

Extra behavior:

- Fixes the proxy connection issue in `openclaw`
- Detects host `HTTP_PROXY` / `HTTPS_PROXY` during image build and applies the proxy settings inside the image
- Detects the host `TZ` setting

Scripts:

- Supports importing `codex` and `gemini` credentials into `auth-profiles.json` for OpenClaw (see [Import credentials](#import-credentials))

Default build output:

- Image: `wtyyy/openclaw:latest`
- Container: `openclaw`
- Container user: fixed as `user`
- Container UID/GID: current host `id -u` / `id -g`

Contents:

- [Build or start the container](#build-or-start-the-container)
- [Manage OpenClaw](#manage-openclaw)
- [Import credentials](#import-credentials)
- [Other details](#other-details)

## Build or start the container

```bash
cd slay-the-spire2-ai
# Create and start the container
./docker-openclaw/run.sh
# Build the image only
./docker-openclaw/run.sh build
# Enter the running container
./docker-openclaw/run.sh shell
# Stop the container
./docker-openclaw/run.sh stop
# Remove the container
./docker-openclaw/run.sh rm
# Remove the image
./docker-openclaw/run.sh rmi
# Show logs
./docker-openclaw/run.sh logs
```

Container data remains on the host after use because `/home/${HOST_USER}` inside the container is mounted to `${PROJECT_DIR}/openclaw-data`, so files stay visible on the host.

## Manage OpenClaw

OpenClaw depends on the backend process `openclaw-gateway`. `pm2` keeps that process running inside the container and restarts it if it crashes.

Common OpenClaw commands:

```bash
openclaw configure  # Configure communication, model, gateway port, and related settings
openclaw tui        # Launch the TUI for clients, logs, and connection status
openclaw dashboard  # Launch the dashboard UI
```

Common `pm2` commands for `openclaw-gateway`:

```bash
# Show logs, including connection details and errors
pm2 logs openclaw-gateway
# Show process status
pm2 status
# Restart the gateway
pm2 restart openclaw-gateway
# Stop the gateway
pm2 stop openclaw-gateway
```

## Import credentials

If `codex` or `gemini` is installed on the host and already logged in, run:

```bash
cd slay-the-spire2-ai
# Import Codex credentials into the container
node docker-openclaw/tools/import-codex-auth.js ~/.codex/auth.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
# Import Gemini credentials into the container
node docker-openclaw/tools/import-gemini-auth.js ~/.gemini/oauth_creds.json ./openclaw-data/.openclaw/agents/main/agent/auth-profiles.json
```

After importing credentials, run `pm2 restart openclaw-gateway` so the gateway reloads them.

## Other details

### Container runtime arguments

The script uses these runtime options by default:

- `--gpus all`
- `--privileged`
- `DISPLAY`
- `/tmp/.X11-unix:/tmp/.X11-unix`
- `/usr/share/vulkan/icd.d/nvidia_icd.json:/usr/share/vulkan/icd.d/nvidia_icd.json:ro`
- `--net=host`
- `--ipc=host`
- Project mount: `${PROJECT_DIR}:/workspace`
- Home mount: `${PROJECT_DIR}/openclaw-data:/home/${HOST_USER}`

### What the image installs

The image installs:

- Node.js 24 through `nvm`
- `npm`
- `openclaw`
- `pm2`
- `openclaw setup` during build
- auto-started `openclaw-gateway`
- a regular user with the host UID/GID
- passwordless `sudo`
- startup sync for the mounted home template: `nvm`, `zsh/p10k`, `vim`, and OpenClaw-related files
- common tools: `curl`, `git`, `sudo`, `vim`, `zsh`, `powerlevel10k`, `zsh-autosuggestions`, `zsh-syntax-highlighting`, `gruvbox`

English | [简体中文](README.zh-CN.md)

## Introduction

This script configures SSH, TigerVNC, and noVNC on Debian/Ubuntu, with optional ZeroTier installation and network joining. TigerVNC's `x0vncserver` shares the current X11 desktop and creates one endpoint per monitor detected by `xrandr`.

The default builds TigerVNC `1.16.2`, applies the bundled input patch, and sets `KeyEventDelay=20` for continuous Chinese input through AVNC's phone keyboard.

The keymap recovery patch enables `RecoverKeyMappings` by default. It records temporary mappings and their owning instances in X11. When slots run out, it only recovers mappings whose owner has exited, whose contents are unchanged, and whose key is released. An X server grab serializes allocation and recovery across screen servers. Unregistered mappings left by older builds are not automatically cleared.

## Usage

```bash
# Install Python; the script installs the remaining dependencies
sudo apt update
sudo apt install -y python3

# Configure remote access after logging into the current X11 session
sudo python3 auto_remote_config.py --vnc_password '<your_password>'

# Optional: join ZeroTier and use a proxy for source downloads
sudo python3 auto_remote_config.py \
    --vnc_password '<your_password>' \
    --zt_network_id '<your_network_id>' \
    --proxy 7890
```

An empty `--zt_network_id` skips ZeroTier. `--proxy` accepts a port, `host:port`, or a complete proxy URL; APT uses an environment without proxy variables.

Setup generates and restarts `multivnc.service`. The first source build requires network access. A binary is reused only when its version matches and it supports both `KeyEventDelay` and `RecoverKeyMappings`; older patched builds are rebuilt.

### Connections

- AVNC: connect to `<your_ip>:5900` for the first monitor, then `5901`, `5902`, and so on.
- noVNC: open `http://<your_ip>:6080/vnc.html` for the first monitor, then `6081`, `6082`, and so on.
- Monitor order follows detection order. Use the VNC password supplied on the command line.

```bash
# Inspect the service
sudo systemctl status multivnc.service

# Restart the service without rebooting
sudo systemctl restart multivnc.service

# Stop the service
sudo systemctl stop multivnc.service

# Follow service logs
sudo journalctl -u multivnc.service -f
```

## Implementation

- `auto_remote_config.py`: install dependencies, verify the source SHA-256, build TigerVNC, detect monitors, and generate the system service.
- `tigervnc-key-event-delay.patch`: add a configurable delay after key releases.
- `tigervnc-keymap-recovery.patch`: record temporary mapping ownership and recover slots after an instance exits unexpectedly.
- `start_multivnc.sh.in`: generate the per-monitor launcher and retry exited TigerVNC and noVNC processes.

Installed paths:

- TigerVNC: `~/.local/bin/x0vncserver-avnc`
- Launcher: `~/.local/bin/start_multivnc.sh`
- System service: `/etc/systemd/system/multivnc.service`
- noVNC: `/opt/noVNC`
- Build cache: `/var/cache/auto_remote_config/tigervnc-1.16.2`
- Password file: `/etc/x11vnc.pass`, retaining the existing filename for compatibility, with mode `0640` and read access for the service user's group

The default X11 display is `:1`. The launcher prefers `XAUTHORITY`, then checks `/run/user/<uid>/gdm/Xauthority` and `~/.Xauthority`; before login, it waits for an authority file to become available.

### Verify keymap recovery

Install the test dependencies `xvfb` and `python3-xlib`, then run against the newly built binary:

```bash
/usr/bin/python3 tests/test_keymap_recovery.py --server ~/.local/bin/x0vncserver-avnc -v
```

Tests create a private Xvfb desktop and loopback-only test ports. They cover crash recovery, more than 19 distinct Chinese characters, live-owner protection, unregistered or modified mappings, held keys, and normal shutdown cleanup without connecting to the current desktop. Use `--xvfb /path/to/Xvfb` for a custom Xvfb path. These tests do not establish a fix for the underlying Xlib/XCB crashes.

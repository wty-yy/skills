#!/usr/bin/env python3
"""Configure SSH, TigerVNC desktop sharing, noVNC, and optional ZeroTier.

Overview:
    Build TigerVNC with the bundled input-pacing patch and create one shared
    X11 screen endpoint per monitor, managed by multivnc.service.

Quick Start:
    sudo python3 auto_remote_config.py --vnc_password <your_password>

Full Command:
    sudo python3 auto_remote_config.py --vnc_password <your_password> \
        --zt_network_id <your_id> --proxy 127.0.0.1:7890

Options:
    --vnc_password: Password for VNC and noVNC access.
    --zt_network_id: Optional ZeroTier network to join.
    --proxy: Optional HTTP/HTTPS proxy for source downloads.

Notes:
    Run through sudo on Debian/Ubuntu with an active X11 desktop at :1.
    Setup installs dependencies and restarts multivnc.service.
"""
import os
import sys
import argparse
import subprocess
import re
import pwd
import time
import hashlib
from pathlib import Path
import shlex
import shutil
import tempfile

# Define ANSI color codes for terminal output
class Colors:
    CMD = '\033[96m'      # Cyan for commands
    OUT = '\033[90m'      # Dark Gray for real-time output
    ERR = '\033[91m'      # Red for errors
    INFO = '\033[93m'     # Yellow for step information
    SUCCESS = '\033[92m'  # Green for success messages
    RESET = '\033[0m'     # Reset to default terminal color

def run_cmd(cmd, env=None, check=True):
    """Run an argument list or shell command and stream its output in color."""
    command_text = cmd if isinstance(cmd, str) else shlex.join(cmd)
    print(f"{Colors.CMD}>>> Executing: {command_text}{Colors.RESET}")
    
    try:
        process = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1 
        )
        
        output_lines = []
        for line in process.stdout:
            stripped_line = line.rstrip()
            output_lines.append(stripped_line)
            print(f"{Colors.OUT}    | {stripped_line}{Colors.RESET}")
            
        process.wait()
        
        if check and process.returncode != 0:
            print(f"{Colors.ERR}[ERROR] Command failed with exit code {process.returncode}{Colors.RESET}")
            sys.exit(1)
            
        return "\n".join(output_lines)
        
    except Exception as e:
        print(f"{Colors.ERR}[ERROR] Execution exception: {e}{Colors.RESET}")
        if check:
            sys.exit(1)
        return None

def build_env_without_proxy(base_env=None):
    """Return an environment copy with proxy variables removed."""
    env = (base_env or os.environ).copy()
    for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
        env.pop(key, None)
    return env

def check_root():
    """Ensure the script is run with root privileges."""
    if os.geteuid() != 0:
        print(f"{Colors.ERR}[ERROR] This script must be run as root. Please use sudo.{Colors.RESET}")
        sys.exit(1)

def get_real_user():
    """Get the real user who invoked sudo to place files in their home directory."""
    sudo_user = os.environ.get('SUDO_USER')
    if not sudo_user:
        print(f"{Colors.ERR}[ERROR] Could not determine the original user. Please run via 'sudo python3 ...'{Colors.RESET}")
        sys.exit(1)
    
    user_info = pwd.getpwnam(sudo_user)
    return sudo_user, user_info.pw_dir

def get_ipv4_addresses():
    """Collect global IPv4 addresses for physical or Wi-Fi interfaces only."""
    ip_out = run_cmd("ip -o -4 addr show up scope global", check=False)
    if not ip_out:
        return []

    addresses = []
    seen = set()
    pattern = re.compile(r"^\d+:\s+([^ ]+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/")
    for line in ip_out.split('\n'):
        match = pattern.search(line)
        if not match:
            continue
        iface = match.group(1)
        ipv4 = match.group(2)
        if not os.path.exists(f"/sys/class/net/{iface}/device"):
            continue
        key = (iface, ipv4)
        if key in seen:
            continue
        seen.add(key)
        addresses.append({"interface": iface, "ip": ipv4})
    return addresses

def is_package_installed(package_name):
    """Check whether a Debian package is already installed."""
    result = subprocess.run(
        ["dpkg", "-s", package_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0

def install_missing_packages(packages, apt_env):
    """Install only packages that are not already installed."""
    missing_packages = [package for package in packages if not is_package_installed(package)]
    if not missing_packages:
        print(f"{Colors.OUT}[*] Packages already installed: {' '.join(packages)}{Colors.RESET}")
        return
    run_cmd(f"apt-get install -y {' '.join(missing_packages)}", env=apt_env)

class TigerVNCInstaller:
    """Install the pinned TigerVNC server with the bundled key-event delay option."""

    VERSION = "1.16.2"
    SOURCE_SHA256 = "b107c0c8b8a962594281690366c24186e95c2ea4a169acbc0076aa62ed01f467"
    CACHE_ROOT = Path("/var/cache/auto_remote_config")
    BUILD_PACKAGES = [
        "build-essential", "cmake", "pkg-config", "gettext", "patch", "curl",
        "libx11-dev", "libxtst-dev", "libxdamage-dev", "libxfixes-dev",
        "libxrandr-dev", "libxext-dev", "libjpeg-dev", "zlib1g-dev",
        "libpixman-1-dev", "libpam0g-dev", "libgnutls28-dev", "nettle-dev",
    ]

    def __init__(self, user_info, apt_env):
        """Record the target account and package-installation environment."""
        self.user_info = user_info
        self.apt_env = apt_env
        self.binary = Path(user_info.pw_dir) / ".local/bin/x0vncserver-avnc"

    def is_ready(self):
        """Check whether the installed server has the pinned version and pacing patch."""
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            return False
        version = subprocess.run([str(self.binary), "-version"], capture_output=True, text=True)
        help_output = subprocess.run([str(self.binary), "-help"], capture_output=True, text=True)
        return (version.returncode == 0
                and f"version {self.VERSION}," in version.stdout + version.stderr
                and "KeyEventDelay" in help_output.stdout + help_output.stderr)

    def install(self):
        """Build and install the patched server unless a matching binary already exists."""
        if self.is_ready():
            print(f"{Colors.OUT}[*] Patched TigerVNC {self.VERSION} already installed.{Colors.RESET}")
            return str(self.binary)

        install_missing_packages(self.BUILD_PACKAGES, self.apt_env)
        cache = self.CACHE_ROOT / f"tigervnc-{self.VERSION}"
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / "source.tar.gz"
        source = cache / f"tigervnc-{self.VERSION}"
        build = cache / "build"
        url = f"https://github.com/TigerVNC/tigervnc/archive/refs/tags/v{self.VERSION}.tar.gz"
        run_cmd(["curl", "--fail", "--location", "--retry", "3", url, "--output", str(archive)])
        with archive.open("rb") as source_file:
            digest = hashlib.sha256(source_file.read()).hexdigest()
        if digest != self.SOURCE_SHA256:
            raise RuntimeError("TigerVNC source checksum mismatch")
        if source.exists():
            shutil.rmtree(source)
        if build.exists():
            shutil.rmtree(build)
        run_cmd(["tar", "-xzf", str(archive), "-C", str(cache)])
        patch = Path(__file__).resolve().with_name("tigervnc-key-event-delay.patch")
        run_cmd(["patch", "--directory", str(source), "-p1", "--input", str(patch)])
        run_cmd([
            "cmake", "-S", str(source), "-B", str(build),
            "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_VIEWER=OFF",
            "-DENABLE_H264=OFF", "-DENABLE_WAYLAND=OFF", "-DENABLE_GNUTLS=ON",
        ])
        run_cmd(["cmake", "--build", str(build), "--target", "x0vncserver",
                 "--parallel", str(min(os.cpu_count() or 1, 4))])
        self.binary.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.binary.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            shutil.copyfile(build / "unix/x0vncserver/x0vncserver", temporary_path)
            temporary_path.chmod(0o755)
            os.chown(temporary_path, self.user_info.pw_uid, self.user_info.pw_gid)
            os.replace(temporary_path, self.binary)
        finally:
            temporary_path.unlink(missing_ok=True)
        if not self.is_ready():
            raise RuntimeError("Built TigerVNC server failed its version/capability check")
        return str(self.binary)


def write_vnc_password(password, user_info):
    """Write a TigerVNC password file readable by the service account."""
    result = subprocess.run(["tigervncpasswd", "-f"], input=password.encode("utf-8") + b"\n",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    password_file = Path("/etc/x11vnc.pass")
    password_file.write_bytes(result.stdout)
    os.chown(password_file, 0, user_info.pw_gid)
    password_file.chmod(0o640)


def render_launcher(monitors, vnc_binary, novnc_dir):
    """Render supervised TigerVNC and noVNC commands for the detected monitors."""
    template = Path(__file__).resolve().with_name("start_multivnc.sh.in").read_text()
    commands = [
        f"start_screen {index + 1} {5900 + index} {6080 + index} {shlex.quote(monitor['geometry'])}"
        for index, monitor in enumerate(monitors)
    ]
    return (template.replace("@VNC_SERVER@", shlex.quote(vnc_binary))
            .replace("@NOVNC_PROXY@", shlex.quote(f"{novnc_dir}/utils/novnc_proxy"))
            .replace("@SCREEN_COMMANDS@", "\n".join(commands)))


def main():
    """Install remote-access components and configure the per-screen system service."""
    parser = argparse.ArgumentParser(description="Automate ZeroTier, SSH, TigerVNC, and noVNC setup.")
    # Made zt_network_id optional
    parser.add_argument("--zt_network_id", required=False, default="", help="Your ZeroTier Network ID (Leave empty to skip ZeroTier)")
    parser.add_argument("--vnc_password", required=True, help="Password for VNC access")
    # Added proxy argument
    parser.add_argument("--proxy", required=False, default="", help="Optional HTTP/HTTPS proxy (e.g., 127.0.0.1:7890) for git and curl")
    args = parser.parse_args()
    check_root()

    real_user, user_home = get_real_user()
    user_info = pwd.getpwnam(real_user)
    print(f"{Colors.INFO}[*] Detected target user: {real_user} (Home: {user_home}){Colors.RESET}")

    # Set up global proxy environment variables if provided
    if args.proxy:
        proxy_value = args.proxy.strip()
        if proxy_value.isdigit():
            proxy_value = f"127.0.0.1:{proxy_value}"
        proxy_url = proxy_value if "://" in proxy_value else f"http://{proxy_value}"
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        print(f"{Colors.INFO}[*] Proxy configured for network requests: {proxy_url}{Colors.RESET}")

    # Step 1: Install ZeroTier and join network (Conditional)
    if args.zt_network_id:
        print(f"\n{Colors.INFO}[Step 1] Installing ZeroTier and joining network...{Colors.RESET}")
        if not os.path.exists("/usr/sbin/zerotier-cli"):
            run_cmd("curl -s https://install.zerotier.com | bash")
        else:
            print(f"{Colors.OUT}[*] ZeroTier is already installed.{Colors.RESET}")
        
        run_cmd(f"zerotier-cli join {args.zt_network_id}")
        print(f"{Colors.SUCCESS}[+] Successfully requested to join ZeroTier network: {args.zt_network_id}{Colors.RESET}")
    else:
        print(f"\n{Colors.INFO}[Step 1] Skipping ZeroTier setup (No Network ID provided).{Colors.RESET}")

    apt_env = build_env_without_proxy()

    # Step 2: Enable sshd service
    print(f"\n{Colors.INFO}[Step 2] Installing and enabling SSH service...{Colors.RESET}")
    if is_package_installed("openssh-server"):
        print(f"{Colors.OUT}[*] Package already installed: openssh-server{Colors.RESET}")
    else:
        run_cmd("apt-get update", env=apt_env)
        install_missing_packages(["openssh-server"], apt_env)
    run_cmd("systemctl enable --now ssh")
    print(f"{Colors.SUCCESS}[+] SSH service enabled and started.{Colors.RESET}")

    # Step 3: Install the patched TigerVNC server and compatible password utility.
    print(f"\n{Colors.INFO}[Step 3] Installing TigerVNC and setting up password...{Colors.RESET}")
    install_missing_packages(["tigervnc-tools"], apt_env)
    vnc_binary = TigerVNCInstaller(user_info, apt_env).install()
    write_vnc_password(args.vnc_password, user_info)
    print(f"{Colors.SUCCESS}[+] TigerVNC installed and password saved to /etc/x11vnc.pass.{Colors.RESET}")

    # Step 4: Install noVNC
    print(f"\n{Colors.INFO}[Step 4] Installing noVNC...{Colors.RESET}")
    novnc_dir = "/opt/noVNC"
    if not os.path.exists(novnc_dir):
        install_missing_packages(["git", "websockify"], apt_env)
        run_cmd(f"git clone https://github.com/novnc/noVNC.git {novnc_dir}")
    else:
        print(f"{Colors.OUT}[*] noVNC already cloned in /opt/noVNC.{Colors.RESET}")
    print(f"{Colors.SUCCESS}[+] noVNC ready.{Colors.RESET}")

    # Step 5: Detect monitors using xrandr
    print(f"\n{Colors.INFO}[Step 5] Detecting connected monitors...{Colors.RESET}")
    env = os.environ.copy()
    env["DISPLAY"] = ":1"

    xrandr_out = run_cmd(
        f"sudo -u {real_user} DISPLAY=:1 xrandr | grep -w connected",
        env=env,
        check=False,
    )
    if not xrandr_out:
        print(f"{Colors.INFO}[*] xrandr via {real_user} failed, trying to grant root X access...{Colors.RESET}")
        run_cmd(
            f"sudo -u {real_user} DISPLAY=:1 xhost +local:root",
            env=env,
            check=False,
        )
        xrandr_out = run_cmd("xrandr | grep -w connected", env=env, check=False)

    if not xrandr_out:
        print(f"{Colors.ERR}[ERROR] Failed to detect monitors. Is the GUI running and user logged in?{Colors.RESET}")
        sys.exit(1)

    monitors = []
    pattern = re.compile(r"^([a-zA-Z0-9\-]+)\s+connected.*?\b(\d+x\d+\+\d+\+\d+)\b")
    for line in xrandr_out.split('\n'):
        match = pattern.search(line)
        if match:
            monitors.append({
                "name": match.group(1),
                "geometry": match.group(2)
            })

    if not monitors:
        print(f"{Colors.ERR}[ERROR] No monitors with valid geometries found.{Colors.RESET}")
        sys.exit(1)
        
    print(f"{Colors.SUCCESS}[+] Found {len(monitors)} monitor(s):{Colors.RESET}")
    for i, m in enumerate(monitors):
        print(f"{Colors.SUCCESS}    - Screen {i+1}: {m['name']} ({m['geometry']}){Colors.RESET}")

    # Step 6: Generate the launcher script
    print(f"\n{Colors.INFO}[Step 6] Generating TigerVNC + noVNC wrapper script...{Colors.RESET}")
    local_bin_dir = f"{user_home}/.local/bin"
    os.makedirs(local_bin_dir, exist_ok=True)
    run_cmd(f"chown -R {real_user}:{real_user} {user_home}/.local")

    script_path = f"{local_bin_dir}/start_multivnc.sh"
    
    base_vnc_port = 5900
    base_novnc_port = 6080
    script_content = render_launcher(monitors, vnc_binary, novnc_dir)

    with open(script_path, "w") as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    run_cmd(f"chown {real_user}:{real_user} {script_path}")
    print(f"{Colors.SUCCESS}[+] Script generated at {script_path}{Colors.RESET}")

    # Step 7: Create the systemd service for the current X11 display.
    print(f"\n{Colors.INFO}[Step 7] Configuring systemd service for auto-start...{Colors.RESET}")
    service_path = "/etc/systemd/system/multivnc.service"
    service_content = f"""[Unit]
Description=Multi-Screen TigerVNC and noVNC Service
After=network.target graphical.target

[Service]
Type=simple
User={real_user}
Environment=DISPLAY=:1
ExecStart={script_path}
Restart=always
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=graphical.target
"""
    with open(service_path, "w") as f:
        f.write(service_content)

    run_cmd("systemctl daemon-reload")
    run_cmd("systemctl enable multivnc.service")
    run_cmd("systemctl restart multivnc.service")
    print(f"{Colors.SUCCESS}[+] systemd service 'multivnc.service' enabled and started.{Colors.RESET}")

    # Step 8: Get Connection IP
    print(f"\n{Colors.INFO}[Step 8] Gathering connection info...{Colors.RESET}")
    
    if args.zt_network_id:
        time.sleep(2)

    access_addresses = get_ipv4_addresses()
    primary_ip = access_addresses[0]["ip"] if access_addresses else "YOUR_SERVER_IP"

    print(f"\n{Colors.SUCCESS}" + "="*65)
    print("                 SETUP COMPLETED SUCCESSFULLY!                ")
    print("="*65)
    if access_addresses:
        print("Available IPv4 Addresses:")
        for entry in access_addresses:
            print(f"  - {entry['interface']:<12} {entry['ip']}")
    else:
        print(f"Server IP Address   : {primary_ip}")
    if args.zt_network_id:
        print("                      (Approve in ZeroTier Admin Panel if needed)")
    print(f"VNC Access Password : {args.vnc_password}")
    print("-" * 65)
    
    for i, m in enumerate(monitors):
        novnc_port = base_novnc_port + i
        if access_addresses:
            for entry in access_addresses:
                print(f"Screen {i+1} ({m['name']}) URL [{entry['interface']}] : http://{entry['ip']}:{novnc_port}/vnc.html")
        else:
            print(f"Screen {i+1} ({m['name']}) URL : http://{primary_ip}:{novnc_port}/vnc.html")
        
    print("-" * 65)
    print(f"{Colors.INFO}File Locations:{Colors.SUCCESS}")
    print(f"  - noVNC Directory  : /opt/noVNC")
    print(f"  - Wrapper Script   : {script_path}")
    print(f"\n{Colors.INFO}Service Management:{Colors.SUCCESS}")
    print(f"  - Check Status     : sudo systemctl status multivnc.service")
    print(f"  - Restart Service  : sudo systemctl restart multivnc.service")
    print("="*65 + f"{Colors.RESET}")

if __name__ == "__main__":
    main()

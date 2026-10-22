#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / 'assets'
VERSIONS = json.loads((ASSETS / 'versions.json').read_text())


def write(file, content, mode=0o644):
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + '.' + secrets.token_hex(4) + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    os.replace(temp, file)


def quoted(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def unit_section(name, settings):
    return '[' + name + ']\n' + '\n'.join(f'{key}={value}' for key, value in settings) + '\n\n'


def service_name(value):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', value):
        raise ValueError('Service name must contain letters, numbers, hyphens or underscores')
    return value


def base_url(value):
    url = urlsplit(value)
    if any(character.isspace() for character in value) or url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
        raise ValueError('Use an HTTP(S) origin without a path or credentials')
    url.port
    return value.rstrip('/')


def display_name(value, prompt):
    if not value:
        if not sys.stdin.isatty():
            raise ValueError(prompt + '；请先询问用户，再通过参数传入名称')
        value = input(prompt + '：')
    value = value.strip()
    if not 1 <= len(value) <= 80 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError('名称需为 1–80 个字符，不能包含换行或控制字符')
    return value


def unpack(root):
    bundle = ASSETS / 'upstream.tar.xz'
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != VERSIONS['upstream']['bundle_sha256']:
        raise ValueError('Upstream bundle checksum mismatch')
    with tarfile.open(bundle) as archive:
        for member in archive.getmembers():
            destination = (root / member.name).resolve()
            destination.relative_to(root.resolve())
            if not member.isfile():
                raise ValueError('The upstream bundle must contain only ordinary files')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
            destination.chmod(0o644)


def server(args):
    root = args.root.resolve()
    public_url = base_url(args.url)
    node = (args.node or root / 'runtime/bin/node').resolve()
    name = service_name(args.service)
    root.mkdir(parents=True, exist_ok=True)
    for directory in ['config', 'data', 'logs', 'backups', 'deploy/tls', 'deploy/acme']:
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory).chmod(0o700)
    for file in (ASSETS / 'app').rglob('*'):
        if file.is_file():
            relative = file.relative_to(ASSETS / 'app')
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, destination)
    unpack(root)
    users_file = root / 'config/users.json'
    users = json.loads(users_file.read_text())['users'] if users_file.exists() else []
    entries = args.user or []
    if not users and not entries:
        entries = [identifier + '=' + display_name('', f'请输入 {identifier} 的 Hub/token 名称') for identifier in ['user-a', 'user-b']]
    changed = not users_file.exists()
    for entry in entries:
        identifier, separator, label = entry.partition('=')
        if not separator or not re.fullmatch(r'[a-z0-9-]{1,40}', identifier):
            raise ValueError('Use --user id=DisplayName with a lowercase ID')
        if any(user['id'] == identifier for user in users):
            continue
        users.append({'id': identifier, 'name': display_name(label, f'请输入 {identifier} 的 Hub/token 名称'), 'token': 'th_' + secrets.token_urlsafe(32), 'devices': {}})
        changed = True
    if changed:
        write(users_file, json.dumps({'users': users}, ensure_ascii=False, indent=2) + '\n', 0o600)
    users_file.chmod(0o600)
    users = json.loads(users_file.read_text())['users']
    for user in users:
        identifier = user['id']
        if not re.fullmatch(r'[a-z0-9-]{1,40}', identifier):
            raise ValueError('Invalid existing user ID')
        env = f'TOKEN_MONITOR_HUB_URL={public_url}\nTOKEN_MONITOR_SECRET={user["token"]}\nTOKEN_MONITOR_PROJECTS_ENABLED=0\nTOKEN_MONITOR_SYNC_SESSION_TITLES=0\n'
        write(root / f'config/{identifier}-agent.env', env, 0o600)
    deployment = {'publicUrl': public_url, 'timeZone': args.timezone}
    write(root / 'config/deployment.json', json.dumps(deployment, indent=2) + '\n')
    settings = [
        ('Type', 'simple'), ('WorkingDirectory', str(root).replace('%', '%%')),
        ('Environment', quoted('TZ=' + args.timezone)), ('Environment', 'NODE_ENV=production'),
        ('Environment', f'PORT={args.port}'), ('Environment', f'TLS_PORT={args.tls_port}'),
        ('Environment', f'HTTP_PORT={args.http_port}'),
        ('Environment', quoted(f'TLS_CERT={root}/deploy/tls/fullchain.pem')),
        ('Environment', quoted(f'TLS_KEY={root}/deploy/tls/key.pem')),
        ('ExecStart', f'{quoted(node)} --max-old-space-size=96 {quoted(root / "src/server.js")}'),
        ('ExecReload', '/bin/kill -HUP $MAINPID'), ('Restart', 'always'), ('RestartSec', '5'),
        ('TimeoutStopSec', '15'), ('UMask', '0077'), ('NoNewPrivileges', 'true'),
        ('PrivateTmp', 'true'), ('ProtectSystem', 'strict'), ('ProtectHome', 'read-only'),
        ('ReadWritePaths', f'{quoted(root / "data")} {quoted(root / "logs")}'),
        ('MemoryMax', '180M'), ('TasksMax', '64')
    ]
    unit = unit_section('Unit', [('Description', 'Token Usage dashboard and isolated hubs'), ('After', 'network-online.target'), ('Wants', 'network-online.target')])
    unit += unit_section('Service', settings) + unit_section('Install', [('WantedBy', 'multi-user.target')])
    write(root / f'deploy/{name}.service', unit)
    backup = unit_section('Unit', [('Description', 'Token Usage daily backup'), ('After', f'{name}.service')])
    backup += unit_section('Service', [('Type', 'oneshot'), ('UMask', '0077'), ('ExecStart', f'/usr/bin/python3 {quoted(root / "deploy/backup.py")}')])
    write(root / f'deploy/{name}-backup.service', backup)
    timer = unit_section('Unit', [('Description', 'Token Usage daily backup')])
    timer += unit_section('Timer', [('OnCalendar', '*-*-* 04:20:00'), ('Persistent', 'true'), ('RandomizedDelaySec', '300')])
    timer += unit_section('Install', [('WantedBy', 'timers.target')])
    write(root / f'deploy/{name}-backup.timer', timer)
    service = shlex.quote(name + '.service')
    write(root / 'deploy/reload-tls.sh', f'#!/bin/sh\nset -eu\nif systemctl is-active --quiet {service}; then\n  systemctl reload {service}\nfi\n', 0o700)
    print(f'Prepared server: {root}; {len(users)} users; public URL {public_url}')
    print('Existing credentials and usage data preserved; system services were not changed.')


def read_env(file):
    values = {}
    for line in file.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if separator:
                value = value.strip()
                values[key.strip()] = json.loads(value) if value.startswith('"') else value.strip("'")
    return values


def client(args):
    root = args.root.resolve()
    node = (args.node or Path(shutil.which('node') or '/usr/bin/node')).resolve()
    name = service_name(args.service)
    root.mkdir(parents=True, exist_ok=True)
    env_file = root / '.env'
    existing = read_env(env_file) if env_file.exists() else {}
    device_name = display_name(args.name or existing.get('TOKEN_MONITOR_DEVICE_NAME'), '请输入客户端设备展示名称（--name）')
    if not env_file.exists():
        if not args.credentials:
            raise ValueError('First setup requires --credentials /path/to/user-agent.env')
        env = read_env(args.credentials)
        base_url(env.get('TOKEN_MONITOR_HUB_URL', ''))
        if len(env.get('TOKEN_MONITOR_SECRET', '')) < 24:
            raise ValueError('The credentials file must contain the user token')
        device = args.device or re.sub(r'[^a-z0-9_-]+', '-', platform.node().lower()).strip('-')
        if not device or '\n' in device or '\r' in device:
            raise ValueError('Use a nonblank device ID without newlines')
        env.update(TOKEN_MONITOR_DEVICE_ID=device, TOKEN_MONITOR_PROJECTS_ENABLED='0',
                   TOKEN_MONITOR_SYNC_SESSION_TITLES='0', TOKEN_MONITOR_LIMITS_ENABLED='0',
                   TOKEN_MONITOR_HISTORY_ENABLED='1', TOKEN_MONITOR_SESSION_USAGE_ARCHIVE_ENABLED='1')
        write(env_file, ''.join(f'{key}={value}\n' for key, value in env.items()), 0o600)
    lines = [line for line in env_file.read_text().splitlines() if not line.startswith('TOKEN_MONITOR_DEVICE_NAME=')]
    write(env_file, '\n'.join(lines) + '\nTOKEN_MONITOR_DEVICE_NAME=' + json.dumps(device_name, ensure_ascii=False) + '\n', 0o600)
    env_file.chmod(0o600)
    pin = VERSIONS['upstream']
    package = {
        'name': 'token-usage-agent', 'version': '1.0.0', 'private': True,
        'scripts': {'start': 'node run.cjs', 'once': 'node run.cjs --once', 'preview': 'node run.cjs --once --dry-run', 'test': 'node --test name.test.cjs'},
        'dependencies': {'token-monitor': f'git+https://github.com/{pin["repository"]}.git#{pin["commit"]}'},
        'overrides': {'tokscale': pin['binary_base']}
    }
    write(root / 'package.json', json.dumps(package, indent=2) + '\n')
    for file in (ASSETS / 'client').glob('*.cjs'):
        shutil.copyfile(file, root / file.name)
    write(root / '.gitignore', '.env\nnode_modules/\nlogs/\n')
    environment_path = str(node.parent) + ':/usr/local/bin:/usr/bin:/bin'
    unit = unit_section('Unit', [('Description', 'Headless Token Usage collector'), ('After', 'network-online.target')])
    unit += unit_section('Service', [
        ('Type', 'simple'), ('WorkingDirectory', str(root).replace('%', '%%')),
        ('Environment', quoted('PATH=' + environment_path)), ('Environment', quoted('TZ=' + args.timezone)),
        ('ExecStart', f'{quoted(node)} {quoted(root / "run.cjs")}'), ('Restart', 'always'),
        ('RestartSec', '15'), ('TimeoutStopSec', '15'), ('UMask', '0077'), ('NoNewPrivileges', 'true')
    ])
    unit += unit_section('Install', [('WantedBy', 'default.target')])
    write(root / f'{name}.service', unit)
    if args.install:
        env = {**os.environ, 'PATH': environment_path}
        subprocess.run(['npm', 'install', '--omit=dev', '--no-audit', '--no-fund'], cwd=root, env=env, check=True)
    print(f'Prepared client: {root}; credentials preserved at .env; GUI is not installed.')
    print('No data uploaded. Use npm run preview, npm run once or npm start in this directory.')


def download(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def install_node(args):
    if platform.system() != 'Linux':
        raise ValueError('This runtime installer targets Linux servers; use an existing Node.js on other systems')
    arch = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
    if arch is None:
        raise ValueError('Use a supported Linux Node.js installation for this architecture')
    version = VERSIONS['node']
    name = f'node-v{version}-linux-{arch}'
    origin = f'https://nodejs.org/dist/v{version}/'
    sums = download(origin + 'SHASUMS256.txt').decode()
    expected = next(line.split()[0] for line in sums.splitlines() if line.endswith(' ' + name + '.tar.xz'))
    data = download(origin + name + '.tar.xz')
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Node.js archive checksum mismatch')
    destination = args.root.resolve() / 'runtime/bin/node'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        member = archive.getmember(name + '/bin/node')
        if not member.isfile():
            raise ValueError('Expected an ordinary Node.js executable')
        temp = destination.with_name('node.download')
        temp.write_bytes(archive.extractfile(member).read())
        temp.chmod(0o755)
        os.replace(temp, destination)
    subprocess.run([str(destination), '--version'], check=True)
    print(f'Installed verified runtime: {destination}')


def main():
    parser = argparse.ArgumentParser(description='Prepare Token Usage server and headless client files')
    commands = parser.add_subparsers(dest='command', required=True)
    node = commands.add_parser('node', help='Download and verify the pinned Linux Node.js runtime')
    node.add_argument('--root', type=Path, required=True)
    node.set_defaults(run=install_node)
    for command, callback in [('server', server), ('client', client)]:
        child = commands.add_parser(command)
        child.add_argument('--root', type=Path, required=True)
        child.add_argument('--node', type=Path)
        child.add_argument('--timezone', default='Asia/Shanghai')
        child.add_argument('--service', default='token-usage' if command == 'server' else 'token-usage-agent')
        child.set_defaults(run=callback)
        if command == 'server':
            child.add_argument('--url', required=True)
            child.add_argument('--port', type=int, default=17320)
            child.add_argument('--tls-port', type=int, default=9443)
            child.add_argument('--http-port', type=int, default=80)
            child.add_argument('--user', action='append', help='Repeat id=HubTokenName; new IDs add hubs without replacing existing users')
        else:
            child.add_argument('--credentials', type=Path)
            child.add_argument('--device')
            child.add_argument('--name', help='Device display name; required on first setup without an interactive terminal')
            child.add_argument('--install', action='store_true')
    args = parser.parse_args()
    try:
        if hasattr(args, 'timezone'):
            ZoneInfo(args.timezone)
        for key in ['port', 'tls_port', 'http_port']:
            if hasattr(args, key) and not 1 <= getattr(args, key) <= 65535:
                raise ValueError('Ports must be between 1 and 65535')
        args.run(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()

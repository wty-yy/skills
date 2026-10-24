#!/usr/bin/env python3
"""Install a checksum-verified, pinned cloud189 CLI inside a task workspace."""
import argparse
import hashlib
import io
from pathlib import Path
import platform
import tarfile
import zipfile
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    systems = {'Linux': 'linux', 'Darwin': 'darwin', 'Windows': 'windows'}
    machines = {'x86_64': 'amd64', 'AMD64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    system, machine = systems.get(platform.system()), machines.get(platform.machine())
    if not system or not machine:
        parser.error('Supported platforms: Linux/macOS/Windows, amd64 or arm64')
    version = '0.7.0'
    suffix = 'zip' if system == 'windows' else 'tar.gz'
    archive = f'cloud189_{version}_{system}_{machine}.{suffix}'
    base = f'https://github.com/gowsp/cloud189/releases/download/v{version}/'
    checksums = requests.get(base + 'checksums.txt', timeout=60)
    checksums.raise_for_status()
    expected = next(line.split()[0] for line in checksums.text.splitlines() if line.split()[-1] == archive)
    response = requests.get(base + archive, timeout=120)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != expected:
        raise RuntimeError('Release SHA-256 mismatch')
    name = 'cloud189.exe' if system == 'windows' else 'cloud189'
    if suffix == 'zip':
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            member = next(x for x in package.namelist() if Path(x).name == name)
            binary = package.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as package:
            member = next(x for x in package.getmembers() if x.isfile() and Path(x.name).name == name)
            binary = package.extractfile(member).read()
    path = args.workdir.resolve() / 'bin' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise FileExistsError('Refusing symlink executable destination')
    if path.exists() and path.read_bytes() != binary:
        raise FileExistsError('Refusing to replace a different existing CLI')
    path.write_bytes(binary)
    path.chmod(0o755)
    print(f'CLI v{version}: {path}; release SHA-256 verified')


if __name__ == '__main__':
    main()

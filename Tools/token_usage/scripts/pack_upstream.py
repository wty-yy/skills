#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


def pack(source, assets):
    source = source.resolve()
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    tracked = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if tracked:
        raise ValueError('Use an unmodified upstream checkout')
    pending = [source / 'src/hub/server.js']
    files = set()
    while pending:
        file = pending.pop().resolve()
        if file in files:
            continue
        file.relative_to(source)
        files.add(file)
        if file.suffix != '.js':
            continue
        code = file.read_text(encoding='utf-8-sig')
        if re.search(r'''require\(\s*[^\s'"]''', code):
            raise ValueError(f'Inspect nonliteral imports before bundling: {file}')
        for name in re.findall(r'''require\(\s*['"](\.[^'"]+)['"]\s*\)''', code):
            base = file.parent / name
            candidates = [base, Path(str(base) + '.js'), Path(str(base) + '.json'), base / 'index.js']
            match = next((item for item in candidates if item.is_file()), None)
            if match is None:
                raise ValueError(f'Unresolved import {name} in {file}')
            pending.append(match)
    files.add(source / 'LICENSE')
    bundle = assets / 'upstream.tar.xz'
    with tarfile.open(bundle, 'w:xz', preset=9) as archive:
        entries = [(str(file.relative_to(source)), file.read_bytes()) for file in sorted(files)]
        for name, data in entries + [('REVISION', (revision + '\n').encode())]:
            member = tarfile.TarInfo('vendor/token-monitor/' + name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    manifest_file = assets / 'versions.json'
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {'node': '22.22.2'}
    pin = json.loads((source / 'scripts/vendor/tokscale.json').read_text())
    manifest['upstream'] = {
        'repository': 'Javis603/token-monitor', 'commit': revision,
        'binary_base': pin['baseVersion'],
        'bundle_sha256': hashlib.sha256(bundle.read_bytes()).hexdigest()
    }
    manifest_file.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{len(files)} source files + revision; bundle {bundle.stat().st_size:,} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pack the Node Hub import closure from a clean official checkout')
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    pack(args.source, Path(__file__).resolve().parents[1] / 'assets')

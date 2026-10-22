#!/usr/bin/env python3
import datetime
import pathlib
import sqlite3
import tarfile
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
backups = root / 'backups'
backups.mkdir(exist_ok=True, mode=0o700)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
with tempfile.TemporaryDirectory() as tmp:
    copy = pathlib.Path(tmp) / 'history.sqlite'
    with sqlite3.connect(root / 'data/history.sqlite') as source, sqlite3.connect(copy) as target:
        source.backup(target)
    with tarfile.open(backups / f'usage-{stamp}.tar.gz', 'w:gz') as archive:
        archive.add(copy, arcname='data/history.sqlite')
        for file in (root / 'data').glob('*.json'):
            archive.add(file, arcname=f'data/{file.name}')
        archive.add(root / 'config/users.json', arcname='config/users.json')
for file in sorted(backups.glob('usage-*.tar.gz'))[:-30]:
    file.unlink()

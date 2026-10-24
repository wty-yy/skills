#!/usr/bin/env python3
"""Plan, download, and verify personal cloud189 folders using a local QR session."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import email.utils
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

import requests


API_LOCK = threading.Lock()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def md5(path):
    digest = hashlib.md5()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest().upper()


def safe_relative(value):
    parts = value.split('/')
    if not value or any(p in ('', '.', '..') for p in parts) or '\\' in value or '\x00' in value or ':' in value:
        raise ValueError('Unsafe relative path in manifest')
    return PurePosixPath(value).as_posix()


def local_name(value, literal=False):
    return value if literal else re.sub(r"\\+(?=['\"])", '', value)


def load_entries(manifest):
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('entries'), list):
        raise ValueError('Unsupported manifest schema')
    seen = set()
    for entry in data['entries']:
        entry['relative_path'] = safe_relative(entry['relative_path'])
        key = os.path.normcase(entry['relative_path'])
        if key in seen:
            raise ValueError('Duplicate destination in manifest')
        seen.add(key)
        if not str(entry['file_id']).isdigit() or not isinstance(entry['size'], int) or entry['size'] < 0:
            raise ValueError('Invalid file identity or size')
        if not re.fullmatch(r'[0-9a-fA-F]{1,32}', entry['checksum']):
            raise ValueError('Missing or invalid cloud MD5; full verification is unavailable')
        entry['checksum'] = entry['checksum'].upper().zfill(32)
    return data['entries']


def destination(root, relative):
    root = root.resolve()
    result = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Refusing symlink destination')
    if not result.resolve().is_relative_to(root):
        raise ValueError('Destination escapes output directory')
    return result


def valid(path, entry):
    return path.is_file() and path.stat().st_size == entry['size'] and md5(path) == entry['checksum']


def plan(args):
    entries = []
    for folder in args.folder:
        if not folder.startswith('/') or '..' in PurePosixPath(folder).parts or folder == '/':
            raise ValueError('Choose an explicit absolute personal-cloud folder below /')
        result = subprocess.run([str(args.cli.resolve()), '--config', str(args.config.resolve()), '-j', 'ls', '-R', folder], capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError('Cloud listing failed; check QR login with the CLI')
        rows = json.loads(result.stdout)
        if not isinstance(rows, list):
            raise RuntimeError('Unexpected CLI listing response')
        for row in rows:
            if row['is_dir']:
                continue
            relative = str(PurePosixPath(folder).name) + '/' + row['relative_path']
            entries.append({'file_id': str(row['file_id']), 'size': row['size'], 'checksum': row['checksum'], 'relative_path': safe_relative(local_name(relative, args.literal_names)), 'cloud_path': row['path']})
    candidate = args.manifest.with_suffix('.candidate.json')
    save_json(candidate, {'version': 1, 'folders': args.folder, 'entries': entries})
    load_entries(candidate)
    candidate.replace(args.manifest)
    print(json.dumps({'files': len(entries), 'bytes': sum(e['size'] for e in entries)}, ensure_ascii=False))


def download_url(entry, config):
    with API_LOCK:
        session = json.loads(config.read_text(encoding='utf-8'))['session']
        date = email.utils.formatdate(usegmt=True)
        path = '/getFileDownloadUrl.action'
        message = f"SessionKey={session['sessionKey']}&Operate=GET&RequestURI={path}&Date={date}"
        headers = {'Date': date, 'SessionKey': session['sessionKey'], 'Signature': hmac.new(session['sessionSecret'].encode(), message.encode(), hashlib.sha1).hexdigest(), 'User-Agent': 'desktop', 'Accept': 'application/json;charset=UTF-8'}
        params = {'fileId': entry['file_id'], 'rand': str(int(time.time()*1000)), 'clientType': 'TELEPC', 'version': '7.1.8.0', 'channelId': 'web_cloud.189.cn'}
        response = requests.get('https://api.cloud.189.cn' + path, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        if 'json' in response.headers.get('Content-Type', ''):
            data = response.json()
        else:
            data = {item.tag: item.text for item in ET.fromstring(response.content)}
        url = data.get('fileDownloadUrl')
        if not url or not url.startswith(('https://', 'http://')):
            raise RuntimeError('Download URL unavailable; refresh login with CLI')
        return url


def fetch_chunk(url, start, end, total, target, attempts):
    length = end - start + 1
    if target.is_file() and target.stat().st_size == length:
        return
    temporary = target.with_suffix('.tmp')
    for attempt in range(attempts):
        try:
            with requests.get(url, headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'}, stream=True, timeout=(20, 60)) as response:
                ranged = response.status_code == 206 and response.headers.get('Content-Range') == f'bytes {start}-{end}/{total}'
                whole = response.status_code == 200 and start == 0 and end == total - 1
                if not (ranged or whole):
                    raise RuntimeError('Invalid range response')
                count = 0
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(256 * 1024):
                        count += len(chunk)
                        if count > length:
                            raise RuntimeError('Range exceeds expected length')
                        stream.write(chunk)
                if count != length:
                    raise RuntimeError('Incomplete range')
                temporary.replace(target)
                return
        except (requests.RequestException, RuntimeError, OSError):
            if attempt + 1 == attempts:
                raise RuntimeError('Range failed after bounded retries') from None
            time.sleep(attempt + 1)


def download_one(entry, args):
    result = {'relative_path': entry['relative_path'], 'size': entry['size'], 'checksum': entry['checksum']}
    try:
        dest = destination(args.output, entry['relative_path'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if valid(dest, entry):
            return dict(result, status='verified', skipped=True)
        if dest.exists():
            raise FileExistsError('Existing destination has different content')
        identity = json.dumps([entry['file_id'], entry['size'], entry['checksum'], entry['relative_path'], args.chunk_mib], ensure_ascii=False).encode()
        cache_key = hashlib.sha256(identity).hexdigest()
        parts = args.work / 'parts' / cache_key
        parts.mkdir(parents=True, exist_ok=True)
        partial = dest.parent / ('.cloud189-' + cache_key + '.part')
        if partial.is_symlink():
            raise ValueError('Refusing symlink staging file')
        chunk_size = args.chunk_mib * 1024 * 1024
        ranges = [(s, min(s + chunk_size, entry['size']) - 1) for s in range(0, entry['size'], chunk_size)]
        for attempt in range(args.attempts):
            try:
                if ranges:
                    url = download_url(entry, args.config)
                    with ThreadPoolExecutor(max_workers=args.chunks) as pool:
                        futures = [pool.submit(fetch_chunk, url, s, e, entry['size'], parts / str(s), args.attempts) for s, e in ranges]
                        for future in as_completed(futures):
                            future.result()
                with partial.open('wb') as output:
                    for start, end in ranges:
                        output.write((parts / str(start)).read_bytes())
                if not valid(partial, entry):
                    for start, end in ranges:
                        (parts / str(start)).unlink(missing_ok=True)
                    raise RuntimeError('MD5 mismatch')
                if dest.exists():
                    raise FileExistsError('Destination appeared during download')
                partial.replace(dest)
                for part in parts.iterdir():
                    part.unlink()
                parts.rmdir()
                return dict(result, status='verified', skipped=False)
            except FileExistsError:
                raise
            except (requests.RequestException, RuntimeError, OSError, ValueError, KeyError):
                if attempt + 1 == args.attempts:
                    raise RuntimeError('Download or checksum failed after bounded retries') from None
                time.sleep(2 * (attempt + 1))
    except Exception as error:
        # Exception text can contain signed URLs, so report only a safe error class.
        return dict(result, status='failed', error=type(error).__name__)


def run_download(args):
    entries = load_entries(args.manifest)
    args.work.mkdir(parents=True, exist_ok=True)
    lock = args.work / 'download.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    results = []
    try:
        save_json(args.work / 'download_report.json', results)
        with ThreadPoolExecutor(max_workers=args.files) as pool:
            futures = [pool.submit(download_one, entry, args) for entry in entries]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                save_json(args.work / 'download_report.json', results)
                print(f"[{len(results)}/{len(entries)}] {result['status']}: {result['relative_path']}", flush=True)
    finally:
        lock.unlink(missing_ok=True)
    return int(any(r['status'] != 'verified' for r in results))


def verify(args):
    entries = load_entries(args.manifest)
    failures, missing_tracks = [], []
    for entry in entries:
        path = destination(args.output, entry['relative_path'])
        if not valid(path, entry):
            failures.append(entry['relative_path'])
        if path.is_file() and path.suffix.lower() == '.m3u8':
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if not line or line.startswith('#') or re.match(r'^[A-Za-z][\w+.-]*://', line):
                    continue
                track = path.parent / line
                if not track.resolve().is_relative_to(args.output.resolve()) or not track.is_file():
                    missing_tracks.append({'playlist': entry['relative_path'], 'track': line})
    report = {'ok': not failures and not missing_tracks, 'expected_files': len(entries), 'verified_files': len(entries)-len(failures), 'bytes': sum(e['size'] for e in entries), 'failed_files': failures, 'playlist_missing_tracks': missing_tracks}
    save_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(not report['ok'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan', help='Refresh a recursive cloud manifest')
    p.add_argument('--cli', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--folder', action='append', required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--literal-names', action='store_true')
    p.set_defaults(run=plan)
    p = commands.add_parser('download', help='Download missing files and verify MD5')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--files', type=int, default=4)
    p.add_argument('--chunks', type=int, default=4)
    p.add_argument('--chunk-mib', type=int, default=4)
    p.add_argument('--attempts', type=int, default=3)
    p.set_defaults(run=run_download)
    p = commands.add_parser('verify', help='Check every file and local M3U8 reference')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.set_defaults(run=verify)
    args = parser.parse_args()
    if args.command == 'download' and not (1 <= args.files <= 8 and 1 <= args.chunks <= 8 and args.files*args.chunks <= 32 and 1 <= args.chunk_mib <= 64 and 1 <= args.attempts <= 5):
        parser.error('Use 1–8 workers, at most 32 connections, 1–64 MiB chunks, and 1–5 attempts')
    try:
        return args.run(args) or 0
    except Exception as error:
        print(f'Failed: {type(error).__name__}. Check manifest, session, paths, or active/stale download.lock; no credentials are printed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

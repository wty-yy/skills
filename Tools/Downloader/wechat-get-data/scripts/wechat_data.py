"""Read scoped Linux WeChat messages and recover verified original emoji files.

Overview:
Scan authorized process memory for database keys, query decrypted SQLite copies
in memory, or recover one original image by its message MD5 and length.

Quick Start:
    python wechat_data.py --help

Full Command:
    python wechat_data.py scan-keys --pid PID --account ACCOUNT --output KEYS
    python wechat_data.py query --account ACCOUNT --keys KEYS --chat filehelper
    python wechat_data.py extract --pid PID --md5 MD5 --length BYTES --output FILE

Options:
    scan-keys --database: Restrict scanning to selected relative database paths.
    query --type/--since/--until/--contains/--limit: Restrict returned messages.
    extract --width/--height: Filter GIF candidates by known dimensions.

Notes:
    Requires pycryptodome; compressed message content also requires zstandard.
    Process memory access may require authorized sudo. No password argument is
    accepted. Key files and exports are private and never overwrite files.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import struct
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from Crypto.Cipher import AES

PAGE_SIZE = 4096
RESERVE = 80
KEY_PATTERN = re.compile(rb"x'([0-9a-fA-F]{64})([0-9a-fA-F]{32})'")
IMAGE_PATTERN = re.compile(rb'GIF8[79]a|\x89PNG\r\n\x1a\n|\xff\xd8\xff|RIFF|wxgf')
EMOJI_FIELDS = ('md5', 'len', 'width', 'height', 'type', 'productid', 'externmd5')


def write_private(path, data):
    """Create a private output file owned by the invoking sudo user.

    Existing files and symlinks are refused rather than overwritten.
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        if os.geteuid() == 0 and 'SUDO_UID' in os.environ:
            os.fchown(stream.fileno(), int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))


def hmac_key(raw_key, salt):
    """Derive the SQLCipher page authentication key from a raw database key."""
    return hashlib.pbkdf2_hmac('sha512', raw_key, bytes(x ^ 0x3a for x in salt), 2, 32)


def authenticate(page, number, key):
    """Verify an encrypted page's HMAC before its content is used."""
    skip = 16 if number == 1 else 0
    if len(page) != PAGE_SIZE or number < 1:
        raise ValueError('Invalid encrypted page length or number')
    expected = hmac.new(key, page[skip:-64] + struct.pack('<I', number), hashlib.sha512).digest()
    if not hmac.compare_digest(expected, page[-64:]):
        raise ValueError(f'Page HMAC mismatch at page {number}')


class ProcessMemory:
    """Read authorized writable process mappings without changing process state."""

    def __init__(self, pid):
        """Select the live process whose memory will be inspected."""
        self.pid = pid

    def blocks(self):
        """Yield overlapped memory blocks, their addresses, and mapping ends.

        Short overlap preserves image signatures and keys across block boundaries.
        Unmapped regions encountered during a live scan are skipped.
        """
        maps = Path(f'/proc/{self.pid}/maps').read_text()
        with open(f'/proc/{self.pid}/mem', 'rb', buffering=0) as memory:
            for line in maps.splitlines():
                fields = line.split()
                if not fields[1].startswith('rw'):
                    continue
                start, end = (int(value, 16) for value in fields[0].split('-'))
                cursor, carry = start, b''
                while cursor < end:
                    size = min(8 * 1024**2, end - cursor)
                    try:
                        block = os.pread(memory.fileno(), size, cursor)
                    except OSError:
                        break
                    if not block:
                        break
                    yield carry + block, cursor - len(carry), end, memory.fileno()
                    carry = block[-128:]
                    cursor += len(block)


class EncryptedDatabase:
    """Authenticate and query a temporary in-memory SQLCipher database copy."""

    def __init__(self, path, entry):
        """Configure a database with its matched raw key and salt."""
        self.path = path
        self.key = bytes.fromhex(entry['key'])
        self.salt = bytes.fromhex(entry['salt'])
        self.authentication_key = hmac_key(self.key, self.salt)

    def decrypt_page(self, page, number):
        """Authenticate and reconstruct one SQLite page without writing it."""
        authenticate(page, number, self.authentication_key)
        skip = 16 if number == 1 else 0
        iv = page[-RESERVE:-64]
        prefix = b'SQLite format 3\0' if number == 1 else b''
        return prefix + AES.new(self.key, AES.MODE_CBC, iv).decrypt(page[skip:-RESERVE]) + bytes(RESERVE)

    @staticmethod
    def checksum(data, state=(0, 0), endian='<'):
        """Compute SQLite's chained WAL checksum over paired 32-bit words."""
        a, b = state
        words = struct.unpack(endian + str(len(data) // 4) + 'I', data)
        for index in range(0, len(words), 2):
            a = (a + words[index] + b) & 0xffffffff
            b = (b + words[index + 1] + a) & 0xffffffff
        return a, b

    def committed_frames(self, wal):
        """Return authenticated WAL frames through the last complete commit.

        A truncated or stale-salt tail is ignored. A complete current-generation
        frame with a bad checksum is an error, not a reason to return stale data.
        """
        if not wal:
            return [], None
        if len(wal) < 32:
            raise ValueError('Incomplete WAL header; retry the snapshot')
        magic, _, page_size = struct.unpack('>III', wal[:12])
        if magic not in (0x377f0682, 0x377f0683) or page_size != PAGE_SIZE:
            raise ValueError('Unsupported WAL format')
        endian = '<' if magic == 0x377f0682 else '>'
        state = self.checksum(wal[:24], endian=endian)
        if state != struct.unpack('>II', wal[24:32]):
            raise ValueError('WAL header checksum mismatch')
        frames, committed_count, final_size = [], 0, None
        for offset in range(32, len(wal) - PAGE_SIZE - 24 + 1, PAGE_SIZE + 24):
            header = wal[offset:offset + 24]
            if header[8:16] != wal[16:24]:
                break
            page = wal[offset + 24:offset + 24 + PAGE_SIZE]
            state = self.checksum(header[:8] + page, state, endian)
            if state != struct.unpack('>II', header[16:24]):
                raise ValueError('WAL frame checksum mismatch; retry or verify this WeChat version')
            number, size = struct.unpack('>II', header[:8])
            frames.append((number, page))
            if size:
                committed_count, final_size = len(frames), size
        return frames[:committed_count], final_size

    def snapshot(self):
        """Copy a database and its WAL only when neither changes during reading."""
        wal_path = Path(str(self.path) + '-wal')
        for _ in range(3):
            paths = [self.path] + ([wal_path] if wal_path.exists() else [])
            before = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
            source = self.path.read_bytes()
            wal = wal_path.read_bytes() if wal_path in paths else b''
            after = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
            if before == after and (wal_path in paths) == wal_path.exists():
                return source, wal
            time.sleep(0.1)
        raise ValueError('Database changed during three snapshot attempts')

    def connect(self):
        """Build a query-only in-memory SQLite connection including committed WAL."""
        source, wal = self.snapshot()
        if source[:16] != self.salt or len(source) % PAGE_SIZE:
            raise ValueError('Database salt or page size changed')
        plain = bytearray(len(source))
        for offset in range(0, len(source), PAGE_SIZE):
            number = offset // PAGE_SIZE + 1
            plain[offset:offset + PAGE_SIZE] = self.decrypt_page(source[offset:offset + PAGE_SIZE], number)
        frames, final_size = self.committed_frames(wal)
        for number, page in frames:
            if final_size is not None and number > final_size:
                continue
            offset = (number - 1) * PAGE_SIZE
            if offset + PAGE_SIZE > len(plain):
                plain.extend(bytes(offset + PAGE_SIZE - len(plain)))
            plain[offset:offset + PAGE_SIZE] = self.decrypt_page(page, number)
        if final_size is not None:
            del plain[final_size * PAGE_SIZE:]
        plain[18:20] = b'\x01\x01'
        connection = sqlite3.connect(':memory:')
        connection.deserialize(plain)
        connection.execute('PRAGMA query_only=ON')
        return connection


def resolve_database(account, relative):
    """Resolve a relative database path within the selected account directory."""
    path = (account / relative).resolve()
    path.relative_to(account.resolve())
    return path


def scan_keys(args):
    """Save only memory keys that match and authenticate selected databases."""
    relatives = args.database
    if not relatives:
        relatives = ['db_storage/emoticon/emoticon.db']
        relatives += [str(p.relative_to(args.account)) for p in sorted((args.account / 'db_storage/message').glob('message_*.db')) if re.fullmatch(r'message_\d+\.db', p.name)]
    targets = {}
    for relative in relatives:
        with resolve_database(args.account, relative).open('rb') as stream:
            page = stream.read(PAGE_SIZE)
        targets.setdefault(page[:16].hex(), []).append((relative, page))
    found = {}
    for block, _, _, _ in ProcessMemory(args.pid).blocks():
        for match in KEY_PATTERN.finditer(block):
            salt = match.group(2).decode().lower()
            for relative, page in targets.get(salt, []):
                if relative in found:
                    continue
                raw = bytes.fromhex(match.group(1).decode())
                try:
                    authenticate(page, 1, hmac_key(raw, bytes.fromhex(salt)))
                except ValueError:
                    continue
                found[relative] = {'key': raw.hex(), 'salt': salt}
        if len(found) == len(relatives):
            break
    if not found:
        raise ValueError('No authenticated database keys found')
    write_private(args.output, json.dumps(found).encode())
    print(json.dumps({'matched_databases': list(found), 'missing_databases': [r for r in relatives if r not in found], 'output': str(args.output)}))


def decode_content(value):
    """Decode ordinary UTF-8 or a Zstandard-compressed message BLOB."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if value.startswith(b'\x28\xb5\x2f\xfd'):
        import zstandard
        value = zstandard.ZstdDecompressor().decompress(value)
    return value.decode('utf-8')


def timestamp(value):
    """Parse Unix seconds or an ISO date into a query timestamp."""
    try:
        return int(value)
    except ValueError:
        return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())


def query_messages(args):
    """Query one conversation across supplied message shards and limit output."""
    if args.keys.stat().st_mode & 0o077:
        raise ValueError('Key file must have mode 0600 or stricter')
    keys = json.loads(args.keys.read_text())
    table = 'Msg_' + hashlib.md5(args.chat.encode()).hexdigest()
    clauses, parameters = [], []
    for column, operator, value in [('local_type', '=', args.type), ('create_time', '>=', args.since), ('create_time', '<=', args.until)]:
        if value is not None:
            clauses.append(f'{column} {operator} ?')
            parameters.append(value)
    if args.contains is not None:
        clauses.append('local_type = 1')
    condition = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    results, matched_tables = [], 0
    for relative, entry in keys.items():
        if not re.fullmatch(r'db_storage/message/message_\d+\.db', relative):
            continue
        connection = EncryptedDatabase(resolve_database(args.account, relative), entry).connect()
        try:
            if not connection.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
                continue
            matched_tables += 1
            sql = f'SELECT local_id,server_id,local_type,create_time,message_content FROM "{table}"{condition} ORDER BY create_time DESC,local_id DESC'
            query_parameters = list(parameters)
            if args.contains is None:
                sql += ' LIMIT ?'
                query_parameters.append(args.limit)
            shard_count = 0
            for local_id, server_id, kind, created, content in connection.execute(sql, query_parameters):
                text = decode_content(content)
                if args.contains is not None and args.contains not in text:
                    continue
                record = {'database': relative, 'local_id': local_id, 'server_id': server_id, 'type': kind, 'timestamp': created, 'time': datetime.fromtimestamp(created).astimezone().isoformat()}
                if kind == 47:
                    element = ET.fromstring(text).find('.//emoji')
                    record['emoji'] = {key: element.attrib[key] for key in EMOJI_FIELDS if element is not None and key in element.attrib}
                else:
                    record['content'] = text
                results.append(record)
                shard_count += 1
                if shard_count >= args.limit:
                    break
        finally:
            connection.close()
    if not matched_tables:
        raise ValueError('Conversation table not found in supplied message shards')
    results.sort(key=lambda record: (record['timestamp'], record['local_id']), reverse=True)
    output = json.dumps(results[:args.limit], ensure_ascii=False, indent=2)
    if args.output:
        write_private(args.output, output.encode())
        print(json.dumps({'messages': len(results[:args.limit]), 'output': str(args.output)}))
    else:
        print(output)


def extract_image(args):
    """Recover one original image only when its full message MD5 matches."""
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError('Export destination already exists')
    for block, address, end, descriptor in ProcessMemory(args.pid).blocks():
        for match in IMAGE_PATTERN.finditer(block):
            start = address + match.start()
            if start + args.length > end:
                continue
            try:
                header = os.pread(descriptor, 32, start)
                if header.startswith(b'GIF8'):
                    width, height = struct.unpack('<HH', header[6:10])
                    if (args.width and width != args.width) or (args.height and height != args.height):
                        continue
                data = os.pread(descriptor, args.length, start)
            except OSError:
                continue
            if len(data) == args.length and hashlib.md5(data).hexdigest() == args.md5:
                write_private(args.output, data)
                print(json.dumps({'md5_verified': True, 'md5': args.md5, 'bytes': len(data), 'output': str(args.output)}))
                return
    raise ValueError('Original image not found in current memory; reopen the target emoji in WeChat and retry')


def positive_integer(value):
    """Reject nonpositive process IDs, sizes, and query limits."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('Value must be positive')
    return parsed


def main():
    """Parse the scoped operation and report failures without exposing secrets."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('scan-keys', help='Scan and authenticate keys; may require sudo')
    scan.add_argument('--pid', type=positive_integer, required=True)
    scan.add_argument('--account', type=Path, required=True)
    scan.add_argument('--database', action='append')
    scan.add_argument('--output', type=Path, required=True)
    scan.set_defaults(operation=scan_keys)
    query = commands.add_parser('query', help='Read one conversation in memory')
    query.add_argument('--account', type=Path, required=True)
    query.add_argument('--keys', type=Path, required=True)
    query.add_argument('--chat', required=True)
    query.add_argument('--type', type=int)
    query.add_argument('--since', type=timestamp)
    query.add_argument('--until', type=timestamp)
    query.add_argument('--contains')
    query.add_argument('--limit', type=positive_integer, default=10)
    query.add_argument('--output', type=Path)
    query.set_defaults(operation=query_messages)
    extract = commands.add_parser('extract', help='Recover a single original image from process memory')
    extract.add_argument('--pid', type=positive_integer, required=True)
    extract.add_argument('--md5', required=True)
    extract.add_argument('--length', type=positive_integer, required=True)
    extract.add_argument('--width', type=positive_integer)
    extract.add_argument('--height', type=positive_integer)
    extract.add_argument('--output', type=Path, required=True)
    extract.set_defaults(operation=extract_image)
    args = parser.parse_args()
    if args.command == 'extract':
        args.md5 = args.md5.lower()
        if not re.fullmatch('[0-9a-f]{32}', args.md5):
            parser.error('--md5 must contain exactly 32 hexadecimal characters')
    try:
        args.operation(args)
    except (OSError, ValueError, sqlite3.Error, ET.ParseError, ImportError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

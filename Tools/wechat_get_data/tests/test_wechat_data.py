"""Verify authenticated WeChat reads and exact image recovery with synthetic data.

Overview:
Use generated encrypted pages and an owned child process instead of real keys,
chat records, or user images. No sudo is needed.

Quick Start:
    python -m unittest discover -s wechat_get_data/tests -v

Notes:
    Tests require Linux /proc access, pycryptodome, and zstandard.
"""

import argparse
import base64
import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from Crypto.Cipher import AES
import zstandard

SCRIPT = Path(__file__).parents[1] / 'scripts/wechat_data.py'
SPEC = importlib.util.spec_from_file_location('wechat_data', SCRIPT)
wechat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wechat)


class DatabaseFixture(unittest.TestCase):
    """Provide synthetic encrypted pages and WALs for independent test cases."""

    def setUp(self):
        """Create fixed synthetic secrets and a private workspace."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.db'
        self.key = bytes(range(32))
        self.salt = bytes(range(16))
        self.entry = {'key': self.key.hex(), 'salt': self.salt.hex()}
        self.db = wechat.EncryptedDatabase(self.path, self.entry)

    def encrypted_page(self, number, marker):
        """Construct an independently authenticated SQLCipher test page."""
        skip = 16 if number == 1 else 0
        body = marker + bytes(4096 - 80 - skip - len(marker))
        iv = bytes([number]) * 16
        encrypted = AES.new(self.key, AES.MODE_CBC, iv).encrypt(body)
        authentication_key = hashlib.pbkdf2_hmac('sha512', self.key, bytes(x ^ 0x3a for x in self.salt), 2, 32)
        tag = hmac.new(authentication_key, encrypted + iv + struct.pack('<I', number), hashlib.sha512).digest()
        return (self.salt if skip else b'') + encrypted + iv + tag

    def wal(self, entries):
        """Build valid WAL framing around generated encrypted page fixtures."""
        salt = bytes.fromhex('1020304050607080')
        header = struct.pack('>IIII', 0x377f0682, 3007000, 4096, 0) + salt
        state = self.db.checksum(header)
        result = header + struct.pack('>II', *state)
        for number, committed_size, page in entries:
            prefix = struct.pack('>II', number, committed_size)
            state = self.db.checksum(prefix + page, state)
            result += prefix + salt + struct.pack('>II', *state) + page
        return result


class DatabaseTests(DatabaseFixture):
    """Check page authentication and committed WAL application boundaries."""

    def test_page_authentication_and_plaintext(self):
        """Reject tampered data and restore the authenticated first-page prefix."""
        page = self.encrypted_page(1, b'fixture-body')
        restored = self.db.decrypt_page(page, 1)
        self.assertEqual(restored[:28], b'SQLite format 3\0fixture-body')
        altered = bytearray(page)
        altered[100] ^= 1
        with self.assertRaisesRegex(ValueError, 'HMAC'):
            self.db.decrypt_page(altered, 1)
        with self.assertRaisesRegex(ValueError, 'HMAC'):
            self.db.decrypt_page(page, 2)

    def test_last_commit_excludes_uncommitted_tail(self):
        """Return the last commit while excluding a later valid uncommitted frame."""
        first = self.encrypted_page(1, b'first')
        newer = self.encrypted_page(2, b'committed')
        uncommitted = self.encrypted_page(2, b'uncommitted')
        wal = self.wal([(1, 0, first), (2, 2, newer), (2, 0, uncommitted)])
        frames, size = self.db.committed_frames(wal)
        self.assertEqual(size, 2)
        self.assertEqual(len(frames), 2)
        self.assertTrue(self.db.decrypt_page(frames[-1][1], 2).startswith(b'committed'))

    def test_corrupt_wal_is_not_silently_skipped(self):
        """Reject current-generation corruption instead of returning an old commit."""
        wal = bytearray(self.wal([(1, 1, self.encrypted_page(1, b'valid'))]))
        wal[-100] ^= 1
        with self.assertRaisesRegex(ValueError, 'frame checksum'):
            self.db.committed_frames(wal)

    def test_message_decompression(self):
        """Recover compressed UTF-8 text without corrupting ordinary strings."""
        text = '文件传输助手测试消息'
        self.assertEqual(wechat.decode_content(zstandard.ZstdCompressor().compress(text.encode())), text)
        self.assertEqual(wechat.decode_content(text), text)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux process memory')
class MemoryTests(DatabaseFixture):
    """Check scoped scans against a synthetic process owned by this test."""

    def setUp(self):
        """Start a child holding a synthetic key and a valid one-pixel GIF."""
        super().setUp()
        self.image = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==')
        token = "x'" + self.key.hex() + self.salt.hex() + "'"
        code = "import sys,json,base64,ctypes; d=json.loads(sys.stdin.readline()); buffers=[ctypes.create_string_buffer(d['key'].encode()),ctypes.create_string_buffer(base64.b64decode(d['image']))]; print('ready',flush=True); sys.stdin.readline()"
        self.child = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.close_child)
        self.child.stdin.write(json.dumps({'key': token, 'image': base64.b64encode(self.image).decode()}) + '\n')
        self.child.stdin.flush()
        self.assertEqual(self.child.stdout.readline().strip(), 'ready')

    def close_child(self):
        """Release the synthetic child process and its pipes after each test."""
        self.child.stdin.close()
        self.child.wait(timeout=5)
        self.child.stdout.close()

    def test_scoped_keys_and_private_output(self):
        """Export only the key authenticating the selected fixture database."""
        account = Path(self.temp.name)
        relative = 'db_storage/message/message_1.db'
        path = account / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(self.encrypted_page(1, b'fixture'))
        output = account / 'keys.json'
        args = argparse.Namespace(pid=self.child.pid, account=account, database=[relative], output=output)
        with contextlib.redirect_stdout(io.StringIO()) as log:
            wechat.scan_keys(args)
        self.assertEqual(json.loads(output.read_text()), {relative: self.entry})
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(self.key.hex(), log.getvalue())
        self.assertNotIn(self.salt.hex(), log.getvalue())

    def test_exact_image_hash_and_no_overwrite(self):
        """Recover verified original bytes and refuse overwriting an export."""
        output = Path(self.temp.name) / 'image.gif'
        args = argparse.Namespace(pid=self.child.pid, md5=hashlib.md5(self.image).hexdigest(), length=len(self.image), width=1, height=1, output=output)
        with contextlib.redirect_stdout(io.StringIO()):
            wechat.extract_image(args)
        self.assertEqual(output.read_bytes(), self.image)
        with self.assertRaises(FileExistsError):
            wechat.extract_image(args)
        output.unlink()
        args.md5 = '0' * 32
        with self.assertRaisesRegex(ValueError, 'not found'):
            wechat.extract_image(args)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()

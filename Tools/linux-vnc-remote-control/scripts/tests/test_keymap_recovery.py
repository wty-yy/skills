#!/usr/bin/env python3
"""Exercise patched TigerVNC keyboard recovery on a private Xvfb display.

Quick Start:
    python3 test_keymap_recovery.py --server /path/to/x0vncserver

Full Command:
    python3 test_keymap_recovery.py --server /path/to/x0vncserver --xvfb /path/to/Xvfb

Notes:
    Requires python-xlib and Xvfb. Uses loopback VNC without authentication
    only on an isolated test display; never connects to the user's desktop.
"""

import argparse
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import tempfile
import time
import unittest

from Xlib import X, Xatom, display
from Xlib.ext import xtest


class KeymapRecoveryTest(unittest.TestCase):
    """Verify recovery and ownership using actual RFB key events."""

    def setUp(self):
        """Start a private X server and a window that receives test keystrokes."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        read_fd, write_fd = os.pipe()
        self.xvfb = subprocess.Popen(
            [OPTIONS.xvfb, '-displayfd', str(write_fd), '-screen', '0', '640x480x24',
             '-nolisten', 'tcp', '-ac', '-r'], pass_fds=(write_fd,),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop_process, self.xvfb)
        os.close(write_fd)
        with os.fdopen(read_fd) as reader:
            self.assertTrue(select.select([reader], [], [], 10)[0], 'Xvfb startup timeout')
            number = reader.readline().strip()
        self.assertTrue(number, 'Xvfb failed to start')
        self.display_name = ':' + number
        self.env = dict(os.environ, DISPLAY=self.display_name)
        self.x = display.Display(self.display_name)
        self.addCleanup(self.x.close)
        self.root = self.x.screen().root
        self.window = self.root.create_window(
            0, 0, 200, 100, 0, self.x.screen().root_depth,
            event_mask=X.KeyPressMask | X.KeyReleaseMask)
        self.window.map()
        self.window.set_input_focus(X.RevertToParent, X.CurrentTime)
        self.x.sync()
        self.empty = [key for key, syms in self.mapping().items() if not any(syms)]
        self.assertGreater(len(self.empty), 0)

    @staticmethod
    def stop_process(process):
        """Reap a test process, falling back to a kill if shutdown stalls."""
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def mapping(self):
        """Read current keysyms directly from the isolated X server."""
        first = self.x.display.info.min_keycode
        last = self.x.display.info.max_keycode
        return dict(enumerate(self.x.get_keyboard_mapping(first, last - first + 1), first))

    @staticmethod
    def receive(connection, size):
        """Read one fixed-size field from the RFB stream."""
        result = b''
        while len(result) < size:
            chunk = connection.recv(size - len(result))
            if not chunk:
                raise EOFError('RFB connection closed')
            result += chunk
        return result

    def start_server(self):
        """Connect to a fresh patched server using the RFB 3.8 handshake."""
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        log_path = Path(self.temp.name) / f'{port}.log'
        log = log_path.open('wb')
        self.addCleanup(log.close)
        process = subprocess.Popen(
            [OPTIONS.server, '-display', self.display_name, '-rfbport', str(port),
             '-localhost', '-SecurityTypes', 'None', '-AlwaysShared',
             '-KeyEventDelay', '20', '-Log', '*:stderr:30'],
            stdout=log, stderr=log, env=self.env)
        self.addCleanup(self.stop_process, process)
        deadline = time.monotonic() + 10
        while True:
            try:
                connection = socket.create_connection(('127.0.0.1', port), timeout=2)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    self.fail(log_path.read_text())
                time.sleep(0.05)
        self.addCleanup(connection.close)
        self.assertEqual(self.receive(connection, 12), b'RFB 003.008\n')
        connection.sendall(b'RFB 003.008\n')
        count = self.receive(connection, 1)[0]
        self.assertIn(1, self.receive(connection, count))
        connection.sendall(b'\x01')
        self.assertEqual(self.receive(connection, 4), b'\0' * 4)
        connection.sendall(b'\x01')
        header = self.receive(connection, 24)
        self.receive(connection, struct.unpack('!I', header[20:24])[0])
        return process, connection, log_path

    def type_symbol(self, connection, symbol, expect=True):
        """Check the symbol delivered to the window, then release the key."""
        self.x.sync()
        while self.x.pending_events():
            self.x.next_event()
        connection.sendall(struct.pack('!BBHI', 4, 1, 0, symbol))
        received = None
        deadline = time.monotonic() + (2 if expect else 0.25)
        try:
            while time.monotonic() < deadline:
                if self.x.pending_events():
                    event = self.x.next_event()
                    if event.type == X.KeyPress:
                        received = self.x.get_keyboard_mapping(event.detail, 1)[0][0]
                        break
                else:
                    select.select([self.x.fileno()], [], [], 0.01)
            self.assertEqual(received, symbol if expect else None)
        finally:
            connection.sendall(struct.pack('!BBHI', 4, 0, 0, symbol))
            time.sleep(0.03)

    def fill_slots(self, connection):
        """Allocate every initially unused keycode through the VNC protocol."""
        for i in range(len(self.empty)):
            self.type_symbol(connection, 0x1004e00 + i)
        self.assertFalse(any(not any(syms) for syms in self.mapping().values()))

    def test_crash_recovery_and_live_owner(self):
        """Preserve a live peer, then recover its mappings after SIGKILL."""
        first, client, _ = self.start_server()
        self.fill_slots(client)
        _, second_client, log = self.start_server()
        before = self.mapping()
        self.type_symbol(second_client, 0x1006000, expect=False)
        self.assertEqual(self.mapping(), before)
        self.type_symbol(client, 0x1004e00)
        first.kill()
        first.wait(timeout=5)
        for i in range(60):
            self.type_symbol(second_client, 0x1006000 + i)
        self.assertIn('Recovering orphaned keycode', log.read_text())

    def test_unregistered_mapping_is_not_recovered(self):
        """Do not treat arbitrary Unicode mappings as abandoned VNC slots."""
        for key in self.empty:
            self.x.change_keyboard_mapping(key, [(0x1007000 + key,)])
        self.x.sync()
        before = self.mapping()
        _, client, _ = self.start_server()
        self.type_symbol(client, 0x1006500, expect=False)
        self.assertEqual(self.mapping(), before)

    def test_interrupted_mapping_update(self):
        """Recover when the journal was written but the new mapping was not."""
        owner, client, _ = self.start_server()
        self.fill_slots(client)
        for key in self.empty:
            atom = self.x.intern_atom(f'_TIGERVNC_KEYCODE_V1_{key}')
            saved = list(self.root.get_full_property(atom, Xatom.CARDINAL).value)
            pending = [saved[0], 0x1007000 + key, 0, *saved[:3]]
            self.root.change_property(atom, Xatom.CARDINAL, 32, pending)
        self.x.sync()
        owner.kill()
        owner.wait(timeout=5)
        _, client, _ = self.start_server()
        self.type_symbol(client, 0x1006500)

    def test_changed_mapping_is_not_recovered(self):
        """Leave externally modified mappings intact after their owner dies."""
        owner, client, _ = self.start_server()
        self.fill_slots(client)
        owner.kill()
        owner.wait(timeout=5)
        for key in self.empty:
            self.x.change_keyboard_mapping(key, [(0x1007000 + key,)])
        self.x.sync()
        before = self.mapping()
        _, client, _ = self.start_server()
        self.type_symbol(client, 0x1006500, expect=False)
        self.assertEqual(self.mapping(), before)

    def test_pressed_orphan_is_not_recovered(self):
        """Wait for held orphaned keys to be released before recovering them."""
        owner, client, _ = self.start_server()
        self.fill_slots(client)
        owner.kill()
        owner.wait(timeout=5)
        for key in self.empty:
            xtest.fake_input(self.x, X.KeyPress, key)
        self.x.sync()
        _, client, _ = self.start_server()
        self.type_symbol(client, 0x1006500, expect=False)
        for key in self.empty:
            xtest.fake_input(self.x, X.KeyRelease, key)
        self.x.sync()
        self.type_symbol(client, 0x1006500)

    def test_normal_shutdown_cleans_mapping(self):
        """Check that normal termination still releases temporary mappings."""
        owner, client, _ = self.start_server()
        before = self.mapping()
        self.fill_slots(client)
        self.stop_process(owner)
        self.x.sync()
        after = self.mapping()
        for key in self.empty:
            self.assertFalse(any(after[key]))
        for key in before.keys() - set(self.empty):
            self.assertEqual(before[key], after[key])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--xvfb', default='Xvfb')
    OPTIONS, remaining = parser.parse_known_args()
    unittest.main(argv=[__file__, *remaining])

#!/usr/bin/env python3
import argparse
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import unittest


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skills-interactive-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repository with spaces'
        self.repo.mkdir()
        source = Path(__file__).resolve().parents[1]
        for name in ['install.sh', 'install.ps1', 'AGENTS.md']:
            shutil.copy(source / name, self.repo / name)
        for category, name in [('LLM', 'opencode-tools'), ('LLM', 'token-usage'),
                               ('Downloader', 'wechat-get-data')]:
            folder = self.repo / 'Tools' / category / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('fixture\n')
        self.profile = self.root / 'profile with spaces'
        self.env = dict(os.environ, SKILLS_INSTALL_HOME=str(self.profile), LC_ALL='C')
        for name in ['CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'XDG_CONFIG_HOME', 'DSH_HOME', 'AGY_CONFIG_DIR']:
            self.env.pop(name, None)
        self.links = self.profile / '.codex/skills'

    def command(self, action, *args):
        if options.powershell:
            return [options.powershell, '-NoLogo', '-NoProfile', '-File',
                    str(self.repo / 'install.ps1'), action, *args]
        flag = '-i' if action == 'install' else '-r'
        return [options.bash, str(self.repo / 'install.sh'), flag, *args]

    def batch(self, action, *args):
        yes = '-Yes' if options.powershell else '--yes'
        subprocess.run(self.command(action, *args, yes), env=self.env,
                       check=True, capture_output=True, text=True)

    def interactive(self, action, args, steps):
        if options.powershell:
            steps = [(marker, keys + b'\n' if keys in (b'a\n', b'n\n') else keys)
                     for marker, keys in steps]
            steps = [(marker, line + b'\r') for marker, keys in steps
                     for line in keys.split(b'\n')[:-1]]
        master, slave = pty.openpty()
        process = subprocess.Popen(self.command(action, *args), env=self.env,
                                   stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        output = b''
        pending = b''
        next_step = 0
        deadline = time.monotonic() + 20
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    output += chunk
                    pending += chunk
                    # Console.ReadLine queries the cursor position on a real terminal.
                    for _ in range(chunk.count(b'\x1b[6n')):
                        os.write(master, b'\x1b[1;1R')
                if next_step < len(steps):
                    marker, keys = steps[next_step]
                    if marker.encode() in pending:
                        os.write(master, keys)
                        pending = b''
                        next_step += 1
            if process.poll() is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.fail(output.decode(errors='replace'))
            self.assertEqual(process.wait(), 0, output.decode(errors='replace'))
            self.assertEqual(next_step, len(steps), output.decode(errors='replace'))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        return output.decode(errors='replace')

    def tool_step(self, keys=b'\n'):
        marker = 'Number: toggle' if options.powershell else 'Select at least one AI tool'
        return marker, keys

    def skill_step(self, keys=b'a\n'):
        marker = 'Number: toggle' if options.powershell else 'Selected items will be linked'
        return marker, keys

    def removal_step(self, keys=b'\n'):
        marker = 'Number: toggle' if options.powershell else 'Only checked repository links'
        return marker, keys

    def test_no_argument_tool_selection(self):
        keys = b'2\n\n' if options.powershell else b'j \n'
        self.interactive('install', [], [self.tool_step(keys), self.skill_step()])
        self.assertTrue((self.links / 'token-usage').is_symlink())
        self.assertFalse((self.profile / '.claude').exists())
        self.assertFalse((self.profile / '.dsh').exists())
        self.assertFalse((self.profile / '.gemini').exists())

    def test_explicit_tool_is_preselected_and_can_add_dsh(self):
        keys = b'4\n\n' if options.powershell else b'jjj \n'
        output = self.interactive('install', ['codex'], [
            self.tool_step(keys), self.skill_step(), self.skill_step()])
        self.assertIn('[x] codex', output)
        self.assertTrue((self.links / 'token-usage').is_symlink())
        self.assertTrue((self.profile / '.dsh/skills/token-usage').is_symlink())

    def test_explicit_tool_can_add_agy(self):
        keys = b'5\n\n' if options.powershell else b'jjjj \n'
        output = self.interactive('install', ['codex'], [
            self.tool_step(keys), self.skill_step(), self.skill_step()])
        self.assertIn('[x] codex', output)
        self.assertTrue((self.links / 'token-usage').is_symlink())
        self.assertTrue((self.profile / '.gemini/config/skills/token-usage').is_symlink())

    def test_cancel_tool_selection_changes_nothing(self):
        self.interactive('install', ['codex'], [self.tool_step(b'q\n')])
        self.assertFalse(self.profile.exists())

    def test_legacy_names_are_preselected_and_migrated(self):
        self.links.mkdir(parents=True)
        for old in ['check-opencode-usage', 'token_usage', 'wechat_get_data']:
            (self.links / old).symlink_to(self.repo / 'Tools' / old)
        self.interactive('install', ['codex'], [self.tool_step(), self.skill_step(b'\n')])
        for old in ['check-opencode-usage', 'token_usage', 'wechat_get_data']:
            self.assertFalse((self.links / old).is_symlink())
        for new in ['opencode-tools', 'token-usage', 'wechat-get-data']:
            self.assertTrue((self.links / new).is_symlink())

    def test_deselect_replacements_keeps_legacy_links(self):
        self.links.mkdir(parents=True)
        (self.links / 'token_usage').symlink_to(self.repo / 'Tools/token_usage')
        self.interactive('install', ['codex'], [self.tool_step(), self.skill_step(b'n\n')])
        self.assertTrue((self.links / 'token_usage').is_symlink())
        self.assertFalse((self.links / 'token-usage').exists())

    def test_selective_uninstall_keeps_other_links_and_instructions(self):
        flag = '-GlobalInstructions' if options.powershell else '--global-instructions'
        self.batch('install', 'codex', flag)
        keys = b'6\n\n' if options.powershell else b'jjj \n'
        self.interactive('uninstall', ['codex'], [self.tool_step(), self.removal_step(keys)])
        self.assertFalse((self.links / 'token-usage').is_symlink())
        self.assertTrue((self.links / 'opencode-tools').is_symlink())
        self.assertTrue((self.profile / '.codex/AGENTS.md').is_symlink())
        self.assertTrue((self.repo / 'Tools/LLM/token-usage/SKILL.md').is_file())

    def test_cancel_uninstall_keeps_instructions(self):
        flag = '-GlobalInstructions' if options.powershell else '--global-instructions'
        self.batch('install', 'codex', flag)
        self.interactive('uninstall', ['codex'], [self.tool_step(), self.removal_step(b'q\n')])
        self.assertTrue((self.links / 'token-usage').is_symlink())
        self.assertTrue((self.profile / '.codex/AGENTS.md').is_symlink())

    def test_uninstall_defaults_to_no_skills_selected(self):
        self.batch('install', 'codex')
        self.interactive('uninstall', ['codex'], [self.tool_step(), self.removal_step()])
        self.assertTrue((self.links / 'opencode-tools').is_symlink())
        self.assertTrue((self.links / 'token-usage').is_symlink())

    def test_batch_dsh_home_and_legacy_cleanup(self):
        self.env['DSH_HOME'] = str(self.root / 'custom dsh home')
        self.env['AGY_CONFIG_DIR'] = str(self.root / 'custom agy config')
        self.batch('install', 'all')
        for relative in ['.claude', '.codex', '.config/opencode']:
            self.assertTrue((self.profile / relative / 'skills/token-usage').is_symlink())
        agy_links = Path(self.env['AGY_CONFIG_DIR']) / 'skills'
        self.assertTrue((agy_links / 'token-usage').is_symlink())
        links = Path(self.env['DSH_HOME']) / 'skills'
        self.assertTrue((links / 'token-usage').is_symlink())
        (links / 'token_usage').symlink_to(self.repo / 'Tools/token_usage')
        self.batch('install', 'dsh')
        self.assertFalse((links / 'token_usage').is_symlink())
        foreign = self.root / 'foreign/check-opencode-usage'
        foreign.mkdir(parents=True)
        (links / 'check-opencode-usage').symlink_to(foreign)
        (links / 'token_usage').mkdir()
        (links / 'token_usage/keep.txt').write_text('keep\n')
        self.batch('install', 'dsh')
        self.assertEqual((links / 'check-opencode-usage').resolve(), foreign)
        self.assertTrue((links / 'token_usage/keep.txt').is_file())
        self.batch('uninstall', 'dsh')
        self.assertFalse((links / 'token-usage').is_symlink())
        self.assertTrue((links / 'token_usage/keep.txt').is_file())
        self.assertTrue((self.links / 'token-usage').is_symlink())

    def test_legacy_link_retained_without_replacement_source(self):
        self.links.mkdir(parents=True)
        (self.links / 'check-opencode-usage').symlink_to(self.repo / 'Tools/check-opencode-usage')
        shutil.rmtree(self.repo / 'Tools/LLM/opencode-tools')
        self.batch('install', 'codex')
        self.assertTrue((self.links / 'check-opencode-usage').is_symlink())

    def spawn_pty_with_ctty(self, action, args, env, rows=None, cols=None):
        master, slave = pty.openpty()
        if rows is not None and cols is not None:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            self.command(action, *args), env=env,
            stdin=slave, stdout=slave, stderr=slave, preexec_fn=preexec)
        os.close(slave)
        return master, process

    def read_pty_until(self, master, marker, timeout=5.0):
        buf = b''
        deadline = time.monotonic() + timeout
        encoded = marker.encode('utf-8')
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                if encoded in buf:
                    # Drain any trailing bytes of the same frame.
                    while select.select([master], [], [], 0.03)[0]:
                        try:
                            more = os.read(master, 65536)
                        except OSError:
                            break
                        if not more:
                            break
                        buf += more
                    break
        return buf

    @staticmethod
    def strip_ansi(text):
        return re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', text)

    def add_extra_skills(self, count=10):
        for index in range(count):
            folder = self.repo / 'Coding' / f'extra-skill-{index:02d}'
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('fixture\n')

    def test_terminal_resize_expands_and_shrinks_content(self):
        if options.powershell:
            self.skipTest('Bash TUI resize behavior only')
        self.add_extra_skills(10)
        # 1 AGENTS.md + 3 categories (Coding, Tools/Downloader, Tools/LLM) + 13 skills = 17 rows
        master, process = self.spawn_pty_with_ctty('install', ['codex'], self.env, rows=16, cols=55)
        try:
            self.read_pty_until(master, 'Select at least one AI tool')
            os.write(master, b'\n')
            initial_raw = self.read_pty_until(master, 'Selected items will be linked')
            initial = self.strip_ansi(initial_raw.decode('utf-8'))
            match = re.search(r'rows (\d+)-(\d+)', initial)
            self.assertIsNotNone(match, initial)
            self.assertEqual(int(match.group(1)), 1)
            self.assertLess(int(match.group(2)), 17)
            self.assertIn('AGENTS.md -> ', initial)
            self.assertIn('...', initial)

            # Scroll down so viewport start > 0.
            os.write(master, b'j' * 10)
            scrolled_raw = self.read_pty_until(master, 'extra-skill-08')
            scrolled_frame = self.strip_ansi(scrolled_raw.decode('utf-8').rsplit('\x1b[H', 1)[-1])
            match = re.search(r'rows (\d+)-(\d+)', scrolled_frame)
            self.assertIsNotNone(match, scrolled_frame)
            self.assertGreater(int(match.group(1)), 1)

            # Expand terminal without pressing any key: viewport pulls start back to 1
            # and expands both vertically (all 17 rows) and horizontally (full AGENTS.md line).
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 140, 0, 0))
            expanded_raw = self.read_pty_until(master, 'rows 1-17')
            expanded = self.strip_ansi(expanded_raw.decode('utf-8'))
            self.assertIn('rows 1-17', expanded)
            self.assertIn('(replaces file)  (Not installed)', expanded)
            self.assertIn('token-usage', expanded)

            # Shrink terminal without pressing any key: viewport shrinks and keeps cursor visible.
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 14, 48, 0, 0))
            shrunk_raw = self.read_pty_until(master, 'Selected items will be linked')
            shrunk = self.strip_ansi(shrunk_raw.decode('utf-8'))
            match = re.search(r'rows (\d+)-(\d+)', shrunk)
            self.assertIsNotNone(match, shrunk)
            visible_rows = int(match.group(2)) - int(match.group(1)) + 1
            self.assertLess(visible_rows, 17)
            self.assertIn('extra-skill-08', shrunk)

            # Keys (including arrow keys) continue working after resizes.
            os.write(master, b'\x1b[B \n')
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        self.assertTrue((self.links / 'extra-skill-09').is_symlink())

    def test_zero_pty_size_falls_back_to_default_viewport(self):
        if options.powershell:
            self.skipTest('Bash TUI resize behavior only')
        self.add_extra_skills(10)
        master, process = self.spawn_pty_with_ctty('install', ['codex'], self.env)
        try:
            self.read_pty_until(master, 'Select at least one AI tool')
            os.write(master, b'\n')
            raw = self.read_pty_until(master, 'Selected items will be linked')
            screen = self.strip_ansi(raw.decode('utf-8'))
            match = re.search(r'rows (\d+)-(\d+)', screen)
            self.assertIsNotNone(match, screen)
            self.assertEqual(int(match.group(1)), 1)
            self.assertGreater(int(match.group(2)), 10)
            os.write(master, b'q')
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_chinese_utf8_narrow_and_wide_resize(self):
        if options.powershell:
            self.skipTest('Bash TUI resize behavior only')
        self.add_extra_skills(10)
        zh_env = dict(self.env)
        zh_env.pop('LC_ALL', None)
        zh_env['LC_CTYPE'] = 'C.UTF-8'
        zh_env['LC_MESSAGES'] = 'zh_CN.UTF-8'
        master, process = self.spawn_pty_with_ctty('install', ['codex'], zh_env, rows=16, cols=52)
        try:
            self.read_pty_until(master, '至少勾选一个 AI 工具')
            os.write(master, b'\n')
            narrow_raw = self.read_pty_until(master, '勾选项会创建链接')
            narrow = self.strip_ansi(narrow_raw.decode('utf-8', errors='strict'))
            self.assertIn('AGENTS.md -> ', narrow)
            self.assertIn('...', narrow)

            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 140, 0, 0))
            wide_raw = self.read_pty_until(master, '显示 1-17')
            wide = self.strip_ansi(wide_raw.decode('utf-8', errors='strict'))
            self.assertIn('显示 1-17', wide)
            self.assertIn('（覆盖现有文件）  (未安装)', wide)

            os.write(master, b'q')
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--powershell', help='Run the same cases against install.ps1 using this pwsh executable')
    parser.add_argument('--bash', default='bash')
    options, remaining = parser.parse_known_args()
    unittest.main(argv=[__file__, *remaining])

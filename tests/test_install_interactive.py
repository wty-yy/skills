#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
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
        for name in ['CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'XDG_CONFIG_HOME', 'DSH_HOME']:
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

    def test_explicit_tool_is_preselected_and_can_add_dsh(self):
        keys = b'4\n\n' if options.powershell else b'jjj \n'
        output = self.interactive('install', ['codex'], [
            self.tool_step(keys), self.skill_step(), self.skill_step()])
        self.assertIn('[x] codex', output)
        self.assertTrue((self.links / 'token-usage').is_symlink())
        self.assertTrue((self.profile / '.dsh/skills/token-usage').is_symlink())

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
        self.batch('install', 'all')
        for relative in ['.claude', '.codex', '.config/opencode']:
            self.assertTrue((self.profile / relative / 'skills/token-usage').is_symlink())
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--powershell', help='Run the same cases against install.ps1 using this pwsh executable')
    parser.add_argument('--bash', default='bash')
    options, remaining = parser.parse_known_args()
    unittest.main(argv=[__file__, *remaining])

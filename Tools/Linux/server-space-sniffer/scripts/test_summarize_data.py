"""Verify directory scan records and hard-link accounting with isolated files.

Quick Start:
    python3 -m unittest -v test_summarize_data
"""

import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from summarize_data import parse_dust, parse_usage

DUST_PATH = str(Path("~/.local/bin/dust").expanduser())


class DataUsageTests(unittest.TestCase):
    """Check byte parsing and the single-traversal allocation convention."""

    def test_dust_byte_tree_preserves_parent_totals(self):
        """Read parent and child allocations without adding children twice."""
        tree = {"name": "/scan", "size": "12288B", "children": [
            {"name": "/scan/docker", "size": "8192B", "children": []},
            {"name": "/scan/user/a b", "size": "4096B", "children": []},
        ]}
        usage = parse_dust(tree)
        self.assertEqual(usage["/data"], 12288)
        self.assertEqual(usage["/data/docker"], 8192)
        self.assertEqual(usage["/data/user/a b"], 4096)

    def test_paths_with_whitespace_are_preserved(self):
        """Preserve spaces, tabs, and newlines in NUL-delimited file names."""
        raw = b"4096\t/scan/user/a b\tc\nd\0" + b"8192\t/scan/docker\0"
        usage = parse_usage(raw)
        self.assertEqual(usage["/data/user/a b\tc\nd"], 4096)
        self.assertEqual(usage["/data/docker"], 8192)

    def test_single_scan_counts_shared_hardlink_once(self):
        """Measure a shared inode once across two user directories."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            first.mkdir()
            second.mkdir()
            original = first / "large"
            original.write_bytes(b"x" * 1024 * 1024)
            os.link(original, second / "shared")
            output = subprocess.check_output([
                "du", "-a", "-x", "-B1", "--max-depth=2", "--null", str(root),
            ])
            usage = parse_usage(output)
            directories = sum(path.stat().st_blocks * 512 for path in (root, first, second))
            self.assertEqual(usage[str(root)], original.stat().st_blocks * 512 + directories)
            self.assertEqual(usage[str(first)] + usage[str(second)] + root.stat().st_blocks * 512, usage[str(root)])

    @unittest.skipUnless(os.access(DUST_PATH, os.X_OK), "Specified Dust is not executable")
    def test_dust_matches_du_for_sparse_files_links_and_hidden_files(self):
        """Check real Dust allocation against du on an isolated fixture."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / ".hidden").write_bytes(b"x" * 8192)
            os.link(fixture / ".hidden", fixture / "hardlink")
            with (fixture / "sparse").open("wb") as stream:
                stream.truncate(1024**3)
            external = root / "external"
            external.write_bytes(b"x" * 16384)
            (fixture / "outside").symlink_to(external)
            config = root / "config.toml"
            config.write_text("limit-filesystem = true\n")
            output = subprocess.check_output([
                DUST_PATH, "--config", str(config), "-T", "2", "-x", "-j", "-o", "b", "-P", str(fixture),
            ])
            measured = int(json.loads(output)["size"].removesuffix("B"))
            expected = int(subprocess.check_output(["du", "-s", "-B1", str(fixture)]).split(b"\t", 1)[0])
            self.assertEqual(measured, expected)


if __name__ == "__main__":
    unittest.main()

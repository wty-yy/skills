"""Verify storage accounting and failure behavior without scanning production data.

Quick Start:
    python3 -m unittest -v
"""

import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from storage_monitor import StorageMonitor, collect_target


class StorageMonitorTests(unittest.TestCase):
    """Exercise duplicate mounts, container exclusions, and incomplete results."""

    def test_deduplicates_bind_mounts_and_excludes_container_views(self):
        """Count one backing filesystem despite aliases and overlay mount views."""
        mounts = [
            {"source": "/dev/sda1", "target": "/data", "fstype": "ext4", "maj:min": "8:1", "uuid": "disk"},
            {"source": "/dev/sda1[/dir]", "target": "/alias/data", "fstype": "ext4", "maj:min": "8:1", "uuid": "disk"},
            {"source": "overlay", "target": "/data/docker/merged", "fstype": "overlay", "maj:min": "0:50"},
            {"source": "/dev/loop0", "target": "/snap/app", "fstype": "squashfs", "maj:min": "7:0"},
            {"source": "nas:/share", "target": "/share", "fstype": "nfs4", "maj:min": "0:51"},
        ]
        stats = SimpleNamespace(f_blocks=100, f_bfree=40, f_bavail=30, f_frsize=1024)
        monitor = StorageMonitor()
        with patch.object(monitor, "run", return_value=json.dumps({"filesystems": mounts})), patch("storage_monitor.os.statvfs", return_value=stats) as stat:
            rows, warnings = monitor.filesystems()
        self.assertEqual(len(rows), 1)
        self.assertEqual(stat.call_count, 1)
        self.assertEqual(rows[0]["total_bytes"], 102400)
        self.assertEqual(rows[0]["used_bytes"], 61440)
        self.assertEqual(rows[0]["available_bytes"], 30720)
        self.assertEqual(rows[0]["reserved_bytes"], 10240)
        self.assertEqual(rows[0]["used_percent"], 67)
        self.assertEqual(warnings, [])

    def test_btrfs_subvolumes_use_filesystem_uuid(self):
        """Avoid counting Btrfs subvolume capacities twice across device numbers."""
        mounts = [
            {"source": "/dev/sda1[/@]", "target": "/", "fstype": "btrfs", "maj:min": "0:20", "uuid": "pool"},
            {"source": "/dev/sda1[/@home]", "target": "/home", "fstype": "btrfs", "maj:min": "0:21", "uuid": "pool"},
        ]
        stats = SimpleNamespace(f_blocks=10, f_bfree=5, f_bavail=5, f_frsize=4096)
        monitor = StorageMonitor()
        with patch.object(monitor, "run", return_value=json.dumps({"filesystems": mounts})), patch("storage_monitor.os.statvfs", return_value=stats):
            rows, warnings = monitor.filesystems()
        self.assertEqual(len(rows), 1)
        self.assertTrue(warnings)

    def test_unreadable_mount_is_reported(self):
        """Expose inaccessible disks instead of silently reporting a complete total."""
        mounts = [{"source": "/dev/sda1", "target": "/data", "fstype": "ext4", "maj:min": "8:1"}]
        monitor = StorageMonitor()
        with patch.object(monitor, "run", return_value=json.dumps({"filesystems": mounts})), patch("storage_monitor.os.statvfs", side_effect=PermissionError("denied")):
            rows, warnings = monitor.filesystems()
        self.assertEqual(rows, [])
        self.assertIn("denied", warnings[0])

    def test_docker_failure_preserves_disk_report(self):
        """Keep disk counters available when Docker permissions are absent."""
        monitor = StorageMonitor()
        row = dict(total_bytes=100, used_bytes=60, available_bytes=30, reserved_bytes=10)
        with patch.object(monitor, "filesystems", return_value=([row], [])), patch.object(monitor, "run", side_effect=RuntimeError("denied")):
            report = monitor.collect()
        self.assertEqual(report["totals"]["used_bytes"], 60)
        self.assertEqual(report["docker"]["status"], "unavailable")

    def test_default_does_not_scan_docker_usage(self):
        """Fetch only daemon metadata unless expensive details are requested."""
        monitor = StorageMonitor()
        with patch.object(monitor, "run", return_value='{"name":"test"}') as run:
            monitor.docker(False)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][1], "info")

    def test_docker_details_timeout_is_visible(self):
        """Preserve metadata and mark details incomplete after a timeout."""
        monitor = StorageMonitor()
        with patch.object(monitor, "run", side_effect=['{"name":"test"}', RuntimeError("timed out")]):
            result = monitor.docker(True)
        self.assertEqual(result["status"], "ok")
        self.assertIn("timed out", result["details_error"])

    def test_command_timeout_becomes_target_error(self):
        """Return a failed host result when a required command exceeds its deadline."""
        with patch("storage_monitor.subprocess.run", side_effect=subprocess.TimeoutExpired("findmnt", 1)):
            result = collect_target("local", False, 1, "")
        self.assertIn("exceeded", result["error"])


if __name__ == "__main__":
    unittest.main()

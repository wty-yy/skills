"""Collect mounted local disk capacity, including space occupied by containers.

Overview:
    Read filesystem counters without walking file trees; optionally collect over SSH.

Quick Start:
    python3 storage_monitor.py

Full Command:
    python3 storage_monitor.py --host local --host user@server --docker-details --json

Options:
    --host: Repeat for Linux SSH targets; default is the local machine.
    --docker-details: Run the more expensive Docker disk usage query on demand.
    --json: Emit byte counts as JSON instead of a readable table.
    --timeout: Limit each external command in seconds, default 15.

Notes:
    Requires Python 3.9+ and Linux findmnt. Run on the host, outside containers.
    Docker figures are diagnostic details, never added to filesystem usage.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


class StorageMonitor:
    """Collect filesystem counters and optional Docker diagnostics on one host."""

    def __init__(self, timeout=15):
        """Set the collector's external command timeout."""
        self.timeout = timeout

    def run(self, command, **kwargs):
        """Run a read-only command with a bounded wait and readable errors."""
        try:
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=self.timeout, **kwargs,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{command[0]} exceeded {self.timeout}s") from error
        except OSError as error:
            raise RuntimeError(str(error)) from error
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"exit {result.returncode}")
        return result.stdout

    def filesystems(self):
        """Read local disk counters and deduplicate filesystem mounts.

        Returns:
            Filesystem rows and warnings for inaccessible mount points.
        """
        data = json.loads(self.run([
            "findmnt", "--json", "--list", "--real", "--output",
            "SOURCE,TARGET,FSTYPE,MAJ:MIN,UUID",
        ]))
        rows, warnings, seen = [], [], set()
        mounts = sorted(data.get("filesystems", []), key=lambda row: len(row["target"]))
        for mount in mounts:
            source, kind = mount["source"], mount["fstype"]
            if kind in {"squashfs", "iso9660", "overlay", "aufs"}:
                continue
            if not source.startswith("/dev/") and kind not in {"zfs", "btrfs"}:
                continue
            # Btrfs subvolumes can have different device numbers but one capacity.
            key = mount.get("uuid") if kind == "btrfs" else mount["maj:min"]
            key = key or mount["maj:min"]
            if key in seen:
                continue
            try:
                stats = os.statvfs(mount["target"])
            except OSError as error:
                warnings.append(f"{mount['target']}: {error}")
                continue
            seen.add(key)
            total = stats.f_blocks * stats.f_frsize
            used = (stats.f_blocks - stats.f_bfree) * stats.f_frsize
            available = max(0, stats.f_bavail * stats.f_frsize)
            denominator = used + available
            rows.append({
                "source": source, "mount": mount["target"], "fstype": kind,
                "total_bytes": total, "used_bytes": used,
                "available_bytes": available,
                "reserved_bytes": max(0, total - used - available),
                "used_percent": math.ceil(100 * used / denominator) if denominator else 0,
            })
        if not rows:
            warnings.append("No supported mounted local disk filesystems found.")
        if any(row["fstype"] in {"zfs", "btrfs"} for row in rows):
            warnings.append("ZFS/Btrfs shared pools and quotas require pool-specific accounting; totals may overlap.")
        return rows, warnings

    def docker(self, details):
        """Read daemon metadata and optionally query Docker's disk usage categories."""
        template = (
            '{"name":{{json .Name}},"root":{{json .DockerRootDir}},'
            '"driver":{{json .Driver}},"containers":{{.Containers}},'
            '"running":{{.ContainersRunning}}}'
        )
        try:
            result = json.loads(self.run(["docker", "info", "--format", template]))
        except (RuntimeError, ValueError) as error:
            return {"status": "unavailable", "error": str(error)}
        result["status"] = "ok"
        result["scope"] = "Current Docker CLI context; may refer to another machine."
        if details:
            try:
                output = self.run(["docker", "system", "df", "--format", "{{json .}}"])
                result["usage_categories"] = [json.loads(line) for line in output.splitlines() if line.strip()]
            except (RuntimeError, ValueError) as error:
                result["details_error"] = str(error)
        return result

    def collect(self, details=False):
        """Build one timestamped host snapshot without scanning directory trees."""
        start = time.monotonic()
        rows, warnings = self.filesystems()
        if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
            warnings.append("Running inside a container: this snapshot is not a complete host inventory.")
        totals = {
            key: sum(row[key] for row in rows)
            for key in ("total_bytes", "used_bytes", "available_bytes", "reserved_bytes")
        }
        return {
            "host": socket.gethostname(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "filesystems": rows, "totals": totals,
            "docker": self.docker(details), "warnings": warnings,
            "elapsed_seconds": round(time.monotonic() - start, 4),
        }


def collect_target(target, details, timeout, source):
    """Collect locally or stream the same collector over an existing SSH connection."""
    monitor = StorageMonitor(timeout)
    try:
        if target == "local":
            result = monitor.collect(details)
        else:
            if target.startswith("-") or any(char.isspace() for char in target):
                raise RuntimeError("Use an SSH alias or user@hostname without spaces.")
            command = [
                "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                target, "python3", "-", "--json", "--timeout", str(timeout),
            ]
            if details:
                command.append("--docker-details")
            # Account for connection setup, findmnt, Docker metadata, and optional df.
            monitor.timeout = timeout * (3 if details else 2) + 10
            result = json.loads(monitor.run(command, input=source))
        result["target"] = target
        return result
    except (RuntimeError, ValueError) as error:
        return {"target": target, "error": str(error)}


def human_size(value):
    """Format a byte count using binary units."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(value) < 1024 or unit == "PiB":
            return f"{value:.2f} {unit}"
        value /= 1024


def print_report(reports):
    """Print each machine's capacity and Docker diagnostics without combining hosts."""
    for report in reports:
        if "error" in report:
            print(f"[{report['target']}] ERROR: {report['error']}")
            continue
        print(f"[{report['host']}] {report['collected_at']} ({report['elapsed_seconds']}s)")
        print(f"{'Mount':<24} {'Total':>13} {'Used':>13} {'Available':>13} {'Use%':>6}")
        for row in report["filesystems"]:
            sizes = [human_size(row[key]) for key in ("total_bytes", "used_bytes", "available_bytes")]
            print(f"{row['mount']:<24} {sizes[0]:>13} {sizes[1]:>13} {sizes[2]:>13} {row['used_percent']:>5}%")
        totals = report["totals"]
        print(f"TOTAL: {human_size(totals['total_bytes'])}; used: {human_size(totals['used_bytes'])}; available: {human_size(totals['available_bytes'])}")
        docker = report["docker"]
        if docker["status"] == "ok":
            print(f"Docker ({docker['name']}): {docker['containers']} containers, {docker['running']} running; root: {docker['root']}")
            print(docker["scope"])
            for row in docker.get("usage_categories", []):
                print(f"  {row['Type']}: {row['Size']} ({row['TotalCount']} items)")
            if "details_error" in docker:
                print(f"WARNING: Docker details: {docker['details_error']}")
        else:
            print(f"Docker metadata unavailable: {docker['error']}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        print("Local container disk usage is already included in filesystem usage.\n")


def main():
    """Parse targets and output one snapshot per requested Linux host."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", action="append", help="local, SSH alias, or user@hostname; repeat for multiple hosts")
    parser.add_argument("--docker-details", action="store_true", help="query Docker disk categories; may scan many files")
    parser.add_argument("--json", action="store_true", help="emit JSON with byte counts")
    parser.add_argument("--timeout", type=int, default=15, help="external command timeout in seconds")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    targets = list(dict.fromkeys(args.host or ["local"]))
    source = Path(__file__).read_text() if any(target != "local" for target in targets) else ""
    with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        futures = [pool.submit(collect_target, target, args.docker_details, args.timeout, source) for target in targets]
        reports = [future.result() for future in futures]
    # A remote invocation produces a single object for the parent collector.
    output = reports[0] if len(reports) == 1 else reports
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_report(reports)
    return int(any(
        "error" in report or not report.get("filesystems") or report.get("warnings")
        or (args.docker_details and (
            report["docker"]["status"] != "ok" or "details_error" in report["docker"]
        ))
        for report in reports
    ))


if __name__ == "__main__":
    sys.exit(main())

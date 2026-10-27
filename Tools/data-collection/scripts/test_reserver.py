"""Test reservation decisions, allocation races, and launcher authentication.

Quick Start:
    python3 scripts/test_reserver.py

Notes:
    Uses simulated GPU memory; no driver initialization or real allocations.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from gpu_backend import Cuda, DriverError, GIB, MIB, Process
import yaml

from data_collection import Policy, Service, arguments, load_config


class ConfigTests(unittest.TestCase):
    """Verify YAML settings reach the service and invalid input fails before CUDA init."""

    def setUp(self):
        """Use the shipped configuration as the baseline for isolated file tests."""
        self.settings = load_config(Path(__file__).resolve().parents[1] / "assets" / "config.yaml")

    def write_config(self, directory, settings):
        """Serialize a configuration into a temporary test file."""
        path = Path(directory) / "config.yaml"
        path.write_text(yaml.safe_dump(settings), encoding="utf-8")
        return path

    def test_custom_settings_reach_service_options(self):
        """Read tuning values exclusively from the supplied YAML file."""
        self.settings.update(reserve_mib=2048, startup_seconds=45,
                             stable_seconds=12, idle_duty=0.42, shared_duty=0.01)
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, self.settings)
            options = arguments(["--config", str(path)])
        for name, value in self.settings.items():
            self.assertEqual(getattr(options, name), value)

    def test_invalid_values_are_rejected(self):
        """Reject invalid types, nonfinite values, and settings outside valid ranges."""
        invalid = [("reserve_mib", True), ("reserve_mib", 63), ("reserve_mib", 1024.5),
                   ("startup_seconds", 0), ("stable_seconds", -1),
                   ("idle_duty", "0.42"), ("idle_duty", float("nan")),
                   ("idle_duty", 0.9), ("shared_duty", float("inf")), ("shared_duty", 0.1),
                   ("uid", -1), ("uid", "1000"), ("uid", True), ("gpu_uuid", "0"),
                   ("gpu_uuid", 0), ("gpu_uuid", "MIG-abc")]
        with tempfile.TemporaryDirectory() as directory:
            for name, value in invalid:
                with self.subTest(name=name, value=value):
                    path = self.write_config(directory, dict(self.settings, **{name: value}))
                    with self.assertRaises(ValueError):
                        load_config(path)

    def test_unknown_and_missing_fields_are_rejected(self):
        """Catch misspelled settings instead of silently ignoring them."""
        missing = dict(self.settings)
        missing.pop("idle_duty")
        with tempfile.TemporaryDirectory() as directory:
            for settings in (missing, dict(self.settings, extra=1), [], None):
                with self.subTest(settings=settings):
                    path = self.write_config(directory, settings)
                    with self.assertRaises(ValueError):
                        load_config(path)

    def test_settings_flags_are_rejected(self):
        """Keep identity and tuning out of the command line; only the YAML file supplies them."""
        for flag in ("--uid", "--gpu-uuid", "--idle-duty", "--shared-duty", "--reserve-mib",
                     "--startup-seconds", "--stable-seconds"):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    arguments([flag, "0"])
                self.assertEqual(error.exception.code, 2)


class SimulatedCuda(Cuda):
    """Exercise real reconciliation against an in-memory allocation boundary."""

    def __init__(self, free):
        """Avoid native library loading and install a simulated allocator."""
        self.external_free = free
        self.chunks = []
        self.next_pointer = 1
        self.alloc = self.allocate_native
        self.free = self.free_native
        self.fail = False

    def available(self):
        """Report free memory after service and external allocations."""
        return self.external_free - self.held

    def allocate_native(self, pointer, size):
        """Simulate a CUDA out-of-memory race or return a new pointer."""
        if self.fail or size > self.available():
            raise DriverError("cuMemAlloc_v2: error 2")
        pointer._obj.value = self.next_pointer
        self.next_pointer += 1

    def free_native(self, pointer):
        """Verify that the service only frees its own live pointers."""
        assert pointer in {item[0] for item in self.chunks}


class ReservationTests(unittest.TestCase):
    """Verify observable reservation behavior under competing workloads."""

    def test_other_user_exit_is_reclaimed(self):
        """Reclaim memory released by an external process without touching its allocations."""
        cuda = SimulatedCuda(3 * GIB)
        for _ in range(3):
            cuda.reconcile(GIB)
        self.assertEqual(cuda.available(), GIB)
        self.assertEqual(cuda.held, 2 * GIB)
        cuda.external_free += GIB
        cuda.reconcile(GIB)
        self.assertEqual(cuda.held, 3 * GIB)
        self.assertEqual(cuda.available(), GIB)

    def test_external_growth_does_not_release_reservations(self):
        """Prevent foreign processes from progressively consuming the reservation."""
        cuda = SimulatedCuda(2 * GIB)
        cuda.reconcile(GIB)
        cuda.external_free -= 256 * MIB
        cuda.reconcile(GIB)
        self.assertEqual(cuda.available(), 768 * MIB)
        self.assertEqual(cuda.held, GIB)

    def test_allocation_race_is_nonfatal(self):
        """Keep the service alive when a competing allocation wins a race."""
        cuda = SimulatedCuda(2 * GIB)
        cuda.fail = True
        cuda.reconcile(GIB)
        self.assertEqual(cuda.held, 0)

    def test_reserve_rounding_and_release(self):
        """Keep at most one allocation chunk above the floor and release all on demand."""
        cuda = SimulatedCuda(2 * GIB + 13 * MIB)
        cuda.reconcile(GIB)
        self.assertGreaterEqual(cuda.available(), GIB)
        self.assertLess(cuda.available(), GIB + 64 * MIB)
        cuda.release()
        self.assertEqual(cuda.held, 0)


class PolicyTests(unittest.TestCase):
    """Verify UID filtering and the time-dependent startup lifecycle."""

    def setUp(self):
        """Use short deterministic windows and a designated UID."""
        self.policy = Policy(1000, startup=3, stable=2)

    def update(self, processes, now, free=GIB):
        """Evaluate policy with a one-GiB free-memory floor."""
        return self.policy.update(processes, now, free, GIB)

    def test_other_uid_and_graphics_do_not_trigger_yield(self):
        """Ignore a foreign CUDA job and the target user's desktop graphics context."""
        processes = [Process(1, 1001, "a", GIB, True),
                     Process(2, 1000, "b", GIB, False)]
        self.assertFalse(self.update(processes, 0))

    def test_target_start_growth_stability_and_late_growth(self):
        """Yield on growth, resume after stability, and reopen on later growth."""
        job = Process(1, 1000, "a", 32 * MIB, True)
        self.assertTrue(self.update([job], 0))
        self.assertTrue(self.update([job], 2))
        self.assertFalse(self.update([job], 3))
        grown = Process(1, 1000, "a", GIB, True)
        self.assertTrue(self.update([grown], 4))
        self.assertTrue(self.update([grown], 5))
        self.assertFalse(self.update([grown], 6))
        self.assertFalse(self.update([], 7))

    def test_launcher_yields_before_cuda_context_exists(self):
        """Honor a prelaunch request and reclaim after an unused window expires."""
        self.policy.prepare(0)
        self.assertTrue(self.update([], 0))
        self.assertTrue(self.update([], 2))
        self.assertFalse(self.update([], 3))

    def test_pid_reuse_is_a_new_launch(self):
        """Treat a reused PID with a different start time as a new job."""
        self.update([Process(1, 1000, "a", GIB, True)], 0)
        self.assertFalse(self.update([Process(1, 1000, "a", GIB, True)], 5))
        self.assertTrue(self.update([Process(1, 1000, "b", GIB, True)], 6))

    def test_memory_pressure_reopens_window(self):
        """Release reservations when small target growth consumes its headroom."""
        job = Process(1, 1000, "a", GIB, True)
        self.update([job], 0)
        self.assertFalse(self.update([job], 4, free=128 * MIB))
        grown = Process(1, 1000, "a", GIB + MIB, True)
        self.assertTrue(self.update([grown], 5, free=128 * MIB))

    def test_early_exit_reclaims_immediately(self):
        """Cancel an observed job's startup window as soon as it exits."""
        self.assertTrue(self.update([Process(1, 1000, "a", GIB, True)], 0))
        self.assertFalse(self.update([], 1))

    def test_prelaunch_is_preserved_when_old_job_exits(self):
        """Retain a pending launch request if an earlier job exits concurrently."""
        self.update([Process(1, 1000, "a", GIB, True)], 0)
        self.policy.prepare(1)
        self.assertTrue(self.update([], 2))

    def test_old_small_growth_does_not_yield_to_later_foreign_pressure(self):
        """Do not treat an earlier small target allocation as continuing growth."""
        job = Process(1, 1000, "a", 32 * MIB, True)
        self.update([job], 0)
        self.assertFalse(self.update([job], 3))
        grown = Process(1, 1000, "a", 33 * MIB, True)
        self.assertFalse(self.update([grown], 4))
        self.assertFalse(self.update([grown], 5, free=256 * MIB))


class SocketTests(unittest.TestCase):
    """Check actual kernel peer credentials and release-before-ack ordering."""

    def request(self, uid):
        """Connect to a real Unix socket using the test process's credentials."""
        cuda = SimulatedCuda(2 * GIB)
        cuda.reconcile(GIB)
        service = Service(SimpleNamespace(uid=uid, startup_seconds=3,
                          stable_seconds=2, gpu_uuid="GPU-test"), None, cuda)
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:
                path = str(Path(directory) / "control.sock")
                server.bind(path)
                server.listen(1)
                client.connect(path)
                service.accept(server)
                reply = json.loads(client.recv(4096))
        return cuda, reply

    def test_allowed_uid_has_memory_released_before_reply(self):
        """Allow the configured UID and return the selected GPU UUID."""
        cuda, reply = self.request(os.getuid())
        self.assertEqual(reply, {"gpu_uuid": "GPU-test"})
        self.assertEqual(cuda.held, 0)

    def test_different_uid_cannot_release_memory(self):
        """Reject a different peer UID without changing reservations."""
        cuda, reply = self.request(os.getuid() + 1)
        self.assertIn("error", reply)
        self.assertEqual(cuda.held, GIB)


if __name__ == "__main__":
    unittest.main(verbosity=2)

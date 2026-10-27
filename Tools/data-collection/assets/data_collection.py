"""Reserve one GPU's memory for host UIDs and yield during workload startup.

Quick Start:
    python3 data_collection.py --config /path/to/config.yaml

Options:
    --config: YAML file holding the GPU identity, memory, timing, and duty settings.
    --socket: Host-shared control socket used by gpu_run.py.
    --inspect: Report GPU processes without creating a CUDA context.
    --smoke-test: Allocate just 16 MiB and execute one short kernel, then exit.

Notes:
    The service takes no identity or tuning arguments; it reads them from the
    config file so process listings never show deployment parameters.
    Soft reservation only. Use host PID namespace for UID attribution.
    Only the configured target UIDs lower the duty cycle; other users' jobs and
    desktop infrastructure (root Xorg, gdm) leave the device in occupancy mode.
    Graphics workloads count towards shared mode but do not trigger UID yielding.
    The process exits after restart_seconds so the container rebuilds its context.
"""

import argparse
import ctypes
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import signal
import socket
import struct
import time

import yaml

from gpu_backend import Cuda, MIB, Monitor

LOG = logging.getLogger("data-collection")
PR_SET_NAME = 15
# A target allocation change no larger than this counts as stable.
STABLE_DELTA = 1024 * MIB


def own_processes(processes, target_uids):
    """Keep only the configured users' processes for the duty decision.

    Desktop infrastructure and other users' jobs leave the card in occupancy
    mode; only the target UIDs lower the duty cycle.
    """
    return [p for p in processes if p.uid in target_uids]


def set_process_name(name):
    """Replace the kernel process name so top shows the service, not python3."""
    ctypes.CDLL(None).prctl(PR_SET_NAME, ctypes.c_char_p(name.encode("ascii")), 0, 0, 0)


class Policy:
    """Track startup windows and stable memory use for the designated UIDs."""

    def __init__(self, uids, startup, stable):
        """Configure the minimum startup and memory stabilization windows."""
        self.uids, self.startup, self.stable = set(uids), startup, stable
        self.until = 0
        self.launch_until = 0
        self.last_change = float("-inf")
        self.identities = set()
        self.memory = 0
        self.observed_memory = 0

    def prepare(self, now):
        """Open a startup window before acknowledging an authorized launcher."""
        self.until = max(self.until, now + self.startup)
        self.launch_until = self.until
        self.last_change = now

    def update(self, processes, now, free, reserve):
        """Yield for new target processes, growth, or pressure until usage stabilizes."""
        target = [p for p in processes if p.compute and p.uid in self.uids]
        identities = {(p.pid, p.started) for p in target}
        memory = sum(p.memory for p in target)
        grew = memory > self.observed_memory
        self.observed_memory = memory
        if identities - self.identities:
            self.until = max(self.until, now + self.startup)
            self.launch_until = 0
        if self.identities and not identities:
            self.until = self.launch_until
        if identities != self.identities or abs(memory - self.memory) > STABLE_DELTA:
            self.last_change = now
            self.memory = memory
        if target and grew and free < reserve // 2:
            self.last_change = now
        self.identities = identities
        return now < self.until or (bool(target) and now - self.last_change < self.stable)


class Service:
    """Coordinate reservation, authenticated launch requests, and duty-cycled load."""

    def __init__(self, options, monitor, cuda):
        """Keep all GPU operations on the CUDA context's owning thread."""
        self.options, self.monitor, self.cuda = options, monitor, cuda
        self.uids = frozenset(options.uids)
        self.policy = Policy(self.uids, options.startup_seconds, options.stable_seconds)
        self.started = time.monotonic()
        self.running = True

    def stop(self, signum, frame):
        """Finish the current short pulse before cleaning up on termination."""
        self.running = False

    def accept(self, server):
        """Authenticate the socket peer using its kernel-reported host UID."""
        try:
            connection, _ = server.accept()
        except BlockingIOError:
            return
        with connection:
            connection.settimeout(0.2)
            _, uid, _ = struct.unpack("3i", connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            try:
                if uid not in self.uids:
                    connection.sendall(b'{"error":"UID is not authorized"}\n')
                    return
                self.cuda.release()
                self.policy.prepare(time.monotonic())
                connection.sendall(json.dumps({"gpu_uuid": self.options.gpu_uuid}).encode() + b"\n")
                LOG.info("authorized launch: released reservations for UID %s", uid)
            except (BrokenPipeError, TimeoutError):
                LOG.warning("launcher disconnected before acknowledgment")

    def run(self):
        """Reconcile memory every 100 ms and stop extra load during target warmup."""
        path = Path(self.options.socket)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with open(str(path) + ".lock", "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path.unlink(missing_ok=True)
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(path))
                path.chmod(0o666)
                server.listen(16)
                server.setblocking(False)
                signal.signal(signal.SIGTERM, self.stop)
                signal.signal(signal.SIGINT, self.stop)
                try:
                    self.loop(server)
                finally:
                    path.unlink(missing_ok=True)

    def loop(self, server):
        """Choose warmup, shared, or solo behavior from fresh process observations."""
        last_log, previous = 0, None
        reserve = self.options.reserve_mib * MIB
        while self.running:
            start = time.monotonic()
            self.accept(server)
            processes = self.monitor.processes()
            workload = own_processes(processes, self.uids)
            warmup = self.policy.update(processes, start, self.cuda.available(), reserve)
            if warmup:
                self.cuda.release()
                duty, state = 0, "warmup"
            else:
                self.cuda.reconcile(reserve)
                duty = self.options.shared_duty if workload else self.options.idle_duty
                state = "shared" if workload else "solo"
            if state != previous or start - last_log >= 10:
                LOG.info("state=%s held_mib=%d free_mib=%d extra_duty=%.0f%% pids=%s others=%d",
                         state, self.cuda.held // MIB, self.cuda.available() // MIB,
                         duty * 100, [p.pid for p in workload], len(processes) - len(workload))
                previous, last_log = state, start
            busy = 0
            # Account for actual kernel time, not time spent allocating memory.
            while self.running and busy < duty * 0.1 and time.monotonic() - start < 0.1:
                busy += self.cuda.pulse()
            if self.running and time.monotonic() - self.started >= self.options.restart_seconds:
                LOG.info("scheduled restart after %.0f seconds of uptime",
                         time.monotonic() - self.started)
                self.running = False
            time.sleep(max(0, 0.1 - (time.monotonic() - start)))


def load_config(path):
    """Read and validate the deployment identity and every tuning value."""
    with open(path, encoding="utf-8") as stream:
        settings = yaml.safe_load(stream)
    fields = {"gpu_uuid", "reserve_mib", "startup_seconds", "stable_seconds",
              "restart_seconds", "idle_duty", "shared_duty"}
    identities = {"uid", "uids"}
    if not isinstance(settings, dict) or set(settings) - identities != fields:
        raise ValueError("config must contain exactly: "
                         + ", ".join(sorted(fields | {"uid"})) + " (uid or uids)")
    if len(set(settings) & identities) != 1:
        raise ValueError("config must hold either uid or uids")
    uids = settings["uids"] if "uids" in settings else [settings["uid"]]
    if not isinstance(uids, list) or not uids or any(type(item) is not int or item < 0
                                                    for item in uids):
        raise ValueError("uids must be a nonempty list of nonnegative integers")
    if not isinstance(settings["gpu_uuid"], str) or not settings["gpu_uuid"].startswith("GPU-"):
        raise ValueError("gpu_uuid must be a full physical GPU UUID (GPU-...)")
    for name in ("reserve_mib", "startup_seconds", "stable_seconds", "restart_seconds",
                 "idle_duty", "shared_duty"):
        value = settings[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    if type(settings["reserve_mib"]) is not int or settings["reserve_mib"] < 64:
        raise ValueError("reserve_mib must be an integer of at least 64 MiB")
    if settings["startup_seconds"] <= 0 or settings["stable_seconds"] <= 0:
        raise ValueError("startup_seconds and stable_seconds must be positive")
    if settings["restart_seconds"] <= 0:
        raise ValueError("restart_seconds must be positive")
    if not (0 <= settings["idle_duty"] <= 0.8 and 0 <= settings["shared_duty"] <= 0.8):
        raise ValueError("idle_duty and shared_duty must be 0..0.8")
    settings["uids"] = sorted(uids)
    settings.pop("uid", None)
    return settings


def arguments(argv=None):
    """Load the config before any CUDA context exists; accept no identity flags."""
    parser = argparse.ArgumentParser(prog="data-collection", description=__doc__, allow_abbrev=False,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--socket", default="/run/data-collection/control.sock")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--smoke-test", action="store_true")
    options = parser.parse_args(argv)
    try:
        settings = load_config(options.config)
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.error(f"invalid config: {error}")
    for name, value in settings.items():
        setattr(options, name, value)
    return options


def main():
    """Inspect, smoke-test, or serve the configured physical GPU."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    set_process_name("data-collection")
    options = arguments()
    monitor = Monitor(options.gpu_uuid)
    try:
        if options.inspect:
            from dataclasses import asdict
            print(json.dumps({"free_mib": monitor.memory().free // MIB,
                              "processes": [asdict(p) for p in monitor.processes()]}, indent=2))
            return
        if options.reserve_mib * MIB >= monitor.memory().total:
            raise ValueError("reserve must be smaller than total GPU memory")
        cuda = Cuda(options.gpu_uuid)
        try:
            if options.smoke_test:
                cuda.allocate(16 * MIB)
                elapsed = cuda.pulse()
                cuda.release()
                LOG.info("smoke passed: allocated/freed 16 MiB, pulse %.2f ms", elapsed * 1000)
            else:
                Service(options, monitor, cuda).run()
        finally:
            cuda.close()
    finally:
        monitor.close()


if __name__ == "__main__":
    main()

"""Test a short Docker reservation lifecycle while keeping most GPU memory free.

Quick Start:
    python3 scripts/test_container.py --user yy --gpu 0

Notes:
    Requires a prebuilt data-collection:24.04 image and Docker GPU access.
    Tests run without background kernels and remove their own container on exit.
"""

import argparse
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from gpu_backend import MIB, Monitor


def docker(*args, check=True):
    """Run a bounded Docker command and return its text output."""
    return subprocess.run(["docker", *args], check=check, capture_output=True,
                          text=True, timeout=20)


def wait_for(predicate, seconds=10):
    """Wait briefly for an observable container state, failing on timeout."""
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError("container state timed out")


def main():
    """Check root execution, peer UID authentication, target launch, and reclamation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--gpu", required=True)
    options = parser.parse_args()
    uid = pwd.getpwnam(options.user).pw_uid
    if uid != os.getuid() or uid == 0:
        parser.error("run this local integration test as the nonroot target user")
    uuid = subprocess.check_output(["nvidia-smi", "-i", options.gpu, "--query-gpu=uuid",
                                    "--format=csv,noheader"], text=True).strip()
    monitor = Monitor(uuid)
    name = f"data-collection-test-{os.getpid()}"
    launcher = Path(__file__).resolve().parents[1] / "assets" / "gpu_run.py"
    workdir = "/opt/dataset-platform/data-collection/data/7e2fa4b1"

    def logs():
        """Read both output streams from the test service."""
        output = docker("logs", name)
        return output.stdout + output.stderr

    try:
        if any(p.compute and p.uid == uid for p in monitor.processes()):
            raise RuntimeError("target UID already has a CUDA job; postpone the integration test")
        reserve = monitor.memory().free // MIB - 768
        if reserve < 4096:
            raise RuntimeError("need at least 5 GiB free for this conservative integration test")
        with tempfile.TemporaryDirectory(prefix="data-collection-test-") as directory:
            os.chmod(directory, 0o777)  # Allow cap-dropped container root to create its test socket.
            config = Path(directory) / "config.yaml"
            config.write_text(f"uid: {uid}\ngpu_uuid: {uuid}\nreserve_mib: {reserve}\n"
                              "startup_seconds: 1\nstable_seconds: 1\n"
                              "idle_duty: 0\nshared_duty: 0\n", encoding="utf-8")
            docker("run", "--detach", "--name", name, "--user", "0", "--gpus",
                   f"device={uuid}", "--pid=host", "--network=none", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--read-only", "--volume",
                   f"{directory}:/run/data-collection", "--mount",
                   f"type=bind,src={config},dst={workdir}/config.yaml,readonly",
                   "data-collection:24.04")
            wait_for(lambda: "state=" in logs())
            assert docker("exec", name, "id", "-u").stdout.strip() == "0"
            wait_for(lambda: re.search(r"held_mib=[1-9]\d*", logs()))
            service_pid = int(docker("inspect", "--format", "{{.State.Pid}}", name).stdout)
            initial_memory = next(p.memory for p in monitor.processes() if p.pid == service_pid)
            rejected = docker("exec", "--user", "0", name, "python3", "gpu_run.py",
                              "--", "true", check=False)
            assert rejected.returncode != 0 and "UID is not authorized" in rejected.stderr
            # The actual host UID requests release before an exec'd CUDA workload starts.
            code = ("import sys,time; sys.path.insert(0," + repr(workdir) + "); "
                    "from gpu_backend import Cuda,MIB; c=Cuda(" + repr(uuid) + "); "
                    "c.allocate(128*MIB); print('target-ready',flush=True); time.sleep(4); c.close()")
            command = [sys.executable, str(launcher), "--socket", f"{directory}/control.sock",
                       "--", "docker", "exec", "--user", str(uid), name, "python3", "-c", code]
            job = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                wait_for(lambda: "authorized launch" in logs() and "state=warmup held_mib=0" in logs())
                wait_for(lambda: any(p.compute and p.uid == uid for p in monitor.processes()))
                wait_for(lambda: logs().rfind("state=shared") > logs().rfind("state=warmup"))
                output, errors = job.communicate(timeout=10)
                assert job.returncode == 0, errors
                assert "target-ready" in output
            finally:
                if job.poll() is None:
                    job.terminate()
                    job.wait(timeout=5)
            wait_for(lambda: not any(p.compute and p.uid == uid for p in monitor.processes()))
            wait_for(lambda: any(p.pid == service_pid and p.memory >= initial_memory - 64 * MIB
                                 for p in monitor.processes()))
            docker("stop", "--time", "10", name)
            wait_for(lambda: not any(p.pid == service_pid for p in monitor.processes()))
            output = logs()
            assert "Traceback" not in output
            print(output, end="")
            print(json.dumps({"test": "passed", "target_user": options.user, "uid": uid,
                              "reserve_mib": reserve, "background_duty": 0,
                              "root_peer": "rejected", "target_lifecycle": "passed"}))
    finally:
        docker("rm", "--force", name, check=False)
        monitor.close()


if __name__ == "__main__":
    main()

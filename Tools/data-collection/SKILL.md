---
name: data-collection
description: Build, deploy, and troubleshoot a Docker-based soft GPU memory reservation service for a named host user and NVIDIA GPU. It keeps about 1 GiB of VRAM free, yields that memory when the user's program starts, and adjusts background load between exclusive and shared states. Use for GPU occupancy and dynamic VRAM reclamation; it does not provide strict per-user access control.
---

# Data Collection

Soft GPU memory reservation, deployed as a Docker service.

Deploy the service from the host username and GPU ID the user provides. The operator has Docker privileges; the target user may be someone else. Resolve the username to a host UID and the GPU index to the full physical GPU UUID. When the user gives no GPU, use the only card if there is one and ask which card to use when several exist. Never hard-code `yy` as a default user.

## Behavior

- Built on `ubuntu:24.04` with Python 3 and PyYAML, calling the host CUDA Driver API and NVML directly; no PyTorch or CUDA Toolkit is required.
- Reserves 1024 MiB of free memory by default in 64 MiB chunks, settling at roughly 1024-1088 MiB free. When other users consume that headroom the service does not release reservations to top it up, so free memory may fall below 1 GiB.
- With no other GPU processes present, the extra kernel duty cycle is 65%; with any compute or graphics process present it drops to about 3%. While the target user is inside a startup or memory-growth window, the extra load is 0.
- GPU utilization means kernel activity time, so no single `nvidia-smi` sample is guaranteed. In shared mode 3% is this service's own extra activity target; whole-device utilization still includes other programs.
- On a new CUDA process for the target UID, a clear memory change, or memory pressure that coincides with memory growth from that UID, the service releases every reservation it holds. The startup window is at least 30 seconds by default, reservations resume 10 seconds after memory stops changing, and they are reclaimed immediately once all observed target processes exit.
- After another user's process exits, the service keeps occupying the memory that was freed. It releases only its own allocations and never stops, pauses, or modifies other users' processes.
- The target user's graphics processes count toward shared mode but never trigger a yield, so a desktop session cannot leave the service in a released state for long.

## Deployment

Check `id USER`, `nvidia-smi -L`, and `docker info` first. Requirements: Linux, rootful Docker, NVIDIA Container Toolkit, host PID visibility, and an independent physical GPU. MIG, CUDA MPS, rootless Docker, and UID-remapping environments are unsupported; do not adapt by disabling host isolation. If a service already exists for the same GPU, inspect its configuration first; do not delete or overwrite it automatically.

Paths below are relative to this skill directory. Run these after the user authorizes deployment:

```bash
# user yy, host GPU index 0
bash scripts/deploy.sh yy 0

# custom config file; the script still fixes the user, GPU, and socket path
bash scripts/deploy.sh yy 0 /absolute/path/to/config.yaml
```

Reservation size, load ratios, timings, the target UID, and the GPU UUID all live in [assets/config.yaml](assets/config.yaml). The service accepts no identity or tuning arguments, so nothing about the deployment appears in process listings. The config must contain every field below, with ratios as 0-1 decimals:

```yaml
uid: 1000
gpu_uuid: GPU-...
reserve_mib: 1024
startup_seconds: 30
stable_seconds: 10
idle_duty: 0.65
shared_duty: 0.03
```

The deploy script resolves the username and GPU, writes `uid` and `gpu_uuid` into a generated copy at `./.state/<hash>/config.yaml`, validates it, then mounts that file read-only at `/opt/dataset-platform/data-collection/data/7e2fa4b1/config.yaml`, where the service looks for its default config. Tune a running deployment by editing that generated copy and restarting the container; there is no runtime hot reload. Administrators with the relevant Docker privileges can still read the config file and the logs.

The script builds `data-collection:24.04` and names the container `data-collection-<first 12 hex digits of the SHA-256 of the GPU UUID>`, with the host socket directory at `/run/data-collection-<same hash>/`. The module lives at `/opt/dataset-platform/data-collection/data/7e2fa4b1/data_collection.py` and runs as container root. The entrypoint is `python3 -c "import data_collection; data_collection.main()"` and takes no arguments, so process listings show only that snippet, never the script path, the UID, or the GPU UUID. The comm name is also set to `data-collection`, so the default `top` COMMAND column shows `data-collection` instead of `python3`. It uses `--pid=host` to attribute host UIDs, exposes only the chosen GPU, disables container networking, and drops Linux capabilities. After a clean start it sets the `unless-stopped` restart policy; a failed first start stops the container and reports the logs rather than retrying indefinitely. See [assets/Dockerfile](assets/Dockerfile).

Container root, renaming, and unusual paths do not stop users with Docker privileges from inspecting or entering the container. `docker exec` runs commands directly and bypasses `ENTRYPOINT` or a shell password script; do not present such scripts as access control. If the user asks for enforced password checks, explain that this needs host policy for the Docker socket, the `docker` group, and sudo; never change host groups or sudoers during an ordinary deployment. References: [Docker exec](https://docs.docker.com/reference/cli/docker/container/exec/), [Docker group privileges](https://docs.docker.com/engine/install/linux-postinstall/).

## Launching user programs

Prefer launching through [assets/gpu_run.py](assets/gpu_run.py). The deploy script prints the actual socket path and the full launch command. Run it as the target user:

```bash
python3 assets/gpu_run.py \
  --socket /run/data-collection-<hash>/control.sock \
  -- python3 train.py
```

The service verifies the caller's UID through `SO_PEERCRED` on the Unix socket. It returns confirmation only after releasing the reserved memory, then the launcher `exec`s the user command with `CUDA_VISIBLE_DEVICES` set to the target UUID. Inside the user's program the chosen card is therefore `cuda:0` even when its host index differs. Increase `startup_seconds` in the config for longer model loading.

Running a user program directly is still detected automatically, but the first large allocation may fail with OOM. The monitor cannot intercept or retry another process's `cudaMalloc`, so a sudden large allocation after memory has stabilized carries the same race. Use the launcher with a sufficiently long startup window when the start must succeed.

Jobs inside containers need access to the host socket, the same host UID, and the chosen GPU. Use the in-container path `/run/data-collection/control.sock` only when connecting to the socket with `docker exec --user <target UID>` in the management container. Standalone job containers need the host socket directory and the launcher mounted separately; do not impersonate the target user with container root.

Soft reservation cannot stop other users from taking the reserved 1 GiB or the yield window, and it cannot guarantee that the first CUDA context initialization succeeds. Do not claim strict device access control or zero-impact sharing.

The neutral naming changes only what `top` and `ps` show at a glance; it is neither concealment nor access control. `docker inspect`, image layers, cgroup paths, host `/proc/<pid>/`, and the `nvidia-smi` process list still reveal that this is a resident service and what it does. Never describe it as invisible.

## Verification and troubleshooting

```bash
# pure simulation tests, no real GPU allocation
# PyYAML is required on the host for the Python tests and the read-only inspection
python3 scripts/test_reserver.py

# read-only inspection; point --config at a copy holding the real uid and gpu_uuid
python3 assets/data_collection.py --config .state/<hash>/config.yaml --inspect

# build plus a small in-container test: allocate only 16 MiB, run one short kernel, exit
# identity still comes from the config file, not from arguments
docker build -t data-collection:24.04 assets
docker run --rm --gpus device=GPU-... --pid=host --network=none \
  --mount "type=bind,src=$PWD/.state/<hash>/config.yaml,dst=/opt/dataset-platform/data-collection/data/7e2fa4b1/config.yaml,readonly" \
  data-collection:24.04 --smoke-test

# container integration test: keep most memory free and disable the extra kernel load
python3 scripts/test_container.py --user yy --gpu 0

# inspect and stop; use the container name printed by the deployment
docker logs --tail 50 CONTAINER
docker stop --time 10 CONTAINER
```

Run the simulation tests and the small allocation test first. For an automated integration test on a shared desktop card, use a separate test config that keeps most memory free with `idle_duty: 0` and `shared_duty: 0`, run it briefly, then stop the test container. Run the full 1 GiB reservation mode only when the user asks to enable the service. Delivering this skill does not imply keeping a background container or installing into the global skills directory.

Stopping the container destroys its CUDA context and returns all reserved memory; it does not destroy other processes' contexts. If a PID is unreadable, an NVML query fails, or a CUDA operation returns a non-OOM error, the service exits and the driver reclaims its allocations; check the logs and the host configuration before deciding to restart.

Technical references: [NVIDIA container GPU selection](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html), [NVML device and process queries](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html), [CUDA memory allocation and free](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html).

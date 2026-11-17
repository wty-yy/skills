#!/usr/bin/env bash
# Scan allocated blocks with Dust across /data, including Docker, without following links.
# Usage: bash scan_data.sh
# Requires the specified Dust path, local rootful Docker access, and ubuntu:24.04.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p results
endpoint="${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}"
if [[ "$endpoint" != unix://* ]]; then
    echo 'A local Unix-socket Docker daemon is required.' >&2
    exit 1
fi
docker image inspect ubuntu:24.04 >/dev/null
scanner="$HOME/.local/bin/dust"
if [[ ! -x "$scanner" ]]; then
    echo "Dust is not executable: $scanner" >&2
    exit 1
fi
python3 - <<'PY'
import json
import os
from pathlib import Path
import time

def counters():
    """Read aggregate host CPU time counters."""
    return list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))

before = counters()
time.sleep(2)
after = counters()
delta = [b - a for a, b in zip(before, after)]
# Treat iowait as occupied, so outstanding disk work does not inflate the budget.
idle_fraction = delta[3] / sum(delta)
cpus = len(os.sched_getaffinity(0))
threads = max(1, int(cpus * idle_fraction * 0.5))
Path('results/cpu_budget.json').write_text(json.dumps({
    'available_cpus': cpus, 'idle_fraction': round(idle_fraction, 4),
    'free_cpu_equivalents': round(cpus * idle_fraction, 2),
    'threads': threads, 'docker_cpu_limit': threads, 'sample_seconds': 2,
    'memory_limit_gib': 64,
}, indent=2) + '\n')
PY
threads="$(python3 -c 'import json; print(json.load(open("results/cpu_budget.json"))["threads"])')"
date -Iseconds > results/data_scan_started.txt
# Disable recursive bind mounts to exclude running containers' overlay views.
# Keep inode-level hard-link deduplication across the entire /data traversal.
docker run --rm --pull never --network none --read-only \
    --cap-drop ALL --cap-add DAC_READ_SEARCH \
    --security-opt no-new-privileges --pids-limit 512 --memory 64g --memory-swap 64g --cpus "$threads" \
    --mount type=bind,source=/data,target=/scan,readonly,bind-recursive=disabled \
    --mount "type=bind,source=$scanner,target=/usr/local/bin/dust,readonly" \
    --mount "type=bind,source=$script_dir/dust_config.toml,target=/dust_config.toml,readonly" \
    --entrypoint /usr/local/bin/dust ubuntu:24.04 \
    --config /dust_config.toml --threads "$threads" --limit-filesystem \
    --depth 2 --number-of-lines 100000 --full-paths --output-format b \
    --no-progress --print-errors --output-json /scan \
    > results/data_dust.json 2> results/data_dust_errors.txt
date -Iseconds > results/data_scan_finished.txt
python3 "$script_dir/summarize_data.py"

#!/usr/bin/env bash
# Build and start soft GPU reservations for named host users and one physical GPU.
# Usage: bash deploy.sh USER[,USER...] GPU_ID [CONFIG_YAML]
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
    echo "Usage: bash $0 USER[,USER...] GPU_ID [CONFIG_YAML]" >&2
    exit 2
fi
target_users="$1"
gpu_id="$2"
if [[ ! "$gpu_id" =~ ^[0-9]+$ && ! "$gpu_id" =~ ^GPU-[[:xdigit:]-]+$ ]]; then
    echo 'GPU_ID must be a physical GPU index or full GPU UUID' >&2
    exit 2
fi
IFS=',' read -r -a user_list <<< "$target_users"
uids=()
for user in "${user_list[@]}"; do
    uids+=("$(id -u -- "$user")")
done
gpu_uuid="$(nvidia-smi -i "$gpu_id" --query-gpu=uuid --format=csv,noheader)"
if [[ ! "$gpu_uuid" =~ ^GPU-[[:xdigit:]-]+$ ]]; then
    echo 'Expected exactly one physical GPU UUID' >&2
    exit 2
fi
skill_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
config_file="$(realpath -- "${3:-$skill_dir/assets/config.yaml}")"
if [[ ! -f "$config_file" || ! -r "$config_file" ]]; then
    echo "Config must be a readable YAML file: $config_file" >&2
    exit 2
fi
container="data-collection-$(printf %s "$gpu_uuid" | sha256sum | cut -c1-12)"
image='data-collection:24.04'
socket_dir="/run/$container"
state_dir="$skill_dir/.state/${container#data-collection-}"
runtime_config="$state_dir/config.yaml"
config_path='/opt/dataset-platform/data-collection/data/7e2fa4b1/config.yaml'
if docker container inspect "$container" >/dev/null 2>&1; then
    echo "Container already exists: $container. Inspect or stop/remove it explicitly." >&2
    exit 1
fi
docker info >/dev/null
# Resolve users and GPU into the config so the service needs no arguments at all.
mkdir -p "$state_dir"
{ grep -vE '^[[:space:]]*(uid|uids|gpu_uuid)[[:space:]]*:' "$config_file" || true; } > "$runtime_config"
printf 'uids: [%s]\ngpu_uuid: %s\n' "$(IFS=,; echo "${uids[*]}")" "$gpu_uuid" >> "$runtime_config"
docker build --tag "$image" "$skill_dir/assets"
# Validate before starting the GPU service; this command never initializes CUDA.
docker run --rm --network=none --read-only \
    --mount "type=bind,src=$runtime_config,dst=$config_path,readonly" \
    --entrypoint python3 "$image" -c \
    "from data_collection import load_config; load_config('$config_path')"
# Docker creates the host directory as root; the service creates a world-connectable
# socket inside it and verifies the connecting UID with SO_PEERCRED.
docker run --detach --name "$container" --restart=no \
    --user 0 --gpus "device=$gpu_uuid" --pid=host --network=none \
    --cap-drop=ALL --security-opt=no-new-privileges --read-only \
    --volume "$socket_dir:/run/data-collection" \
    --mount "type=bind,src=$runtime_config,dst=$config_path,readonly" \
    "$image"
ready=false
for ((attempt = 0; attempt < 30; attempt++)); do
    if [[ "$(docker inspect --format '{{.State.Status}}' "$container")" != running ]]; then
        break
    fi
    logs="$(docker logs "$container" 2>&1)"
    if [[ "$logs" =~ state=(solo|shared|warmup) ]]; then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != true ]]; then
    docker logs --tail 40 "$container" >&2
    docker stop --time 10 "$container" >/dev/null
    echo "Service did not start cleanly: $container" >&2
    exit 1
fi
docker update --restart unless-stopped "$container" >/dev/null
printf 'Container: %s\nUsers: %s (UIDs %s)\nGPU: %s\nSocket: %s/control.sock\n' \
    "$container" "$target_users" "${uids[*]}" "$gpu_uuid" "$socket_dir"
printf 'Config: %s (generated from %s)\n' "$runtime_config" "$config_file"
printf 'Launch as %s: python3 %q --socket %q -- COMMAND\n' \
    "$target_users" "$skill_dir/assets/gpu_run.py" "$socket_dir/control.sock"
docker logs --tail 5 "$container"

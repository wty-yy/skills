"""Collect Docker allocation by container, shared image layer, and local volume.

Overview:
    Read minimal Docker metadata, then scan only Docker's data directory once.
    Write DOCKER_USAGE.md and results/docker_usage.json in the working directory.

Quick Start:
    python3 /path/to/server-space-sniffer/scripts/docker_usage.py

Full Command:
    python3 /path/to/server-space-sniffer/scripts/docker_usage.py --report-only

Options:
    --report-only: Regenerate the report from the saved metadata and scan.

Notes:
    Requires Linux, local rootful Docker with overlay2, Dust, and ubuntu:24.04.
    Use half the initially idle CPU as thread count and CPU quota, with 64 GiB RAM.
    Bind-mounted user data is listed but not counted again under Docker.
"""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
import shlex
from pathlib import Path
import subprocess
import time

from summarize_data import human


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path.cwd()
RESULTS = ROOT / "results"
DUST_PATH = Path("~/.local/bin/dust").expanduser()


def command(args, **kwargs):
    """Run a bounded metadata command and return stdout without exposing secrets."""
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=60, **kwargs).stdout


def inspect_rows(kind, ids, template):
    """Inspect only the explicitly requested fields for a set of Docker objects."""
    if not ids:
        return []
    output = command(["docker", kind, "inspect", "--format", template, *ids])
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def chain_ids(diff_ids):
    """Compute Docker overlay2 image chain digests from ordered filesystem diffs."""
    chains, previous = [], ""
    for diff in diff_ids:
        previous = diff if not previous else "sha256:" + hashlib.sha256(f"{previous} {diff}".encode()).hexdigest()
        chains.append(previous.removeprefix("sha256:"))
    return chains


def collect_metadata():
    """Read object identities, mounts, and layer paths without querying disk sizes."""
    endpoint = os.environ.get("DOCKER_HOST") or command(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"]).strip()
    if not endpoint.startswith("unix://"):
        raise RuntimeError("A local Unix-socket Docker daemon is required.")
    info = json.loads(command(["docker", "info", "--format", '{"root":{{json .DockerRootDir}},"driver":{{json .Driver}},"name":{{json .Name}}}']))
    if info["driver"] != "overlay2":
        raise RuntimeError("This collector currently supports overlay2 only.")
    ids = command(["docker", "ps", "-aq", "--no-trunc", "--size=false"]).split()
    containers = inspect_rows("container", ids, '{"id":{{json .Id}},"name":{{json .Name}},"image_id":{{json .Image}},"image":{{json .Config.Image}},"state":{{json .State.Status}},"upper_dir":{{json .GraphDriver.Data.UpperDir}},"log_path":{{json .LogPath}},"log_driver":{{json .HostConfig.LogConfig.Type}},"mounts":{{json .Mounts}},"owner_label":{{json (index .Config.Labels "owner")}}}')
    ids = list(dict.fromkeys(command(["docker", "image", "ls", "-aq", "--no-trunc"]).split()))
    images = inspect_rows("image", ids, '{"id":{{json .Id}},"tags":{{json .RepoTags}},"virtual_bytes":{{.Size}},"layers":{{json .RootFS.Layers}}}')
    for image in images:
        image["chain_ids"] = chain_ids(image["layers"] or [])
    ids = command(["docker", "volume", "ls", "-q"]).split()
    volumes = inspect_rows("volume", ids, '{"name":{{json .Name}},"driver":{{json .Driver}},"mountpoint":{{json .Mountpoint}},"scope":{{json .Scope}},"type":{{json (index .Options "type")}}}')
    return {"daemon": info, "containers": containers, "images": images, "volumes": volumes}


def container_command(data_root):
    """Build a restricted temporary container with a nonrecursive read-only bind."""
    return [
        "docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--cap-add", "DAC_READ_SEARCH", "--security-opt", "no-new-privileges",
        "--mount", f"type=bind,source={data_root},target=/scan,readonly,bind-recursive=disabled",
    ]


def collect_layer_map(metadata):
    """Read Docker's image chain-to-layer mapping using only small metadata files."""
    chains = sorted({chain for image in metadata["images"] for chain in image["chain_ids"]})
    script = 'while IFS= read -r id; do p="/scan/image/overlay2/layerdb/sha256/$id/cache-id"; if [ -f "$p" ]; then printf "%s\\t%s\\n" "$id" "$(cat "$p")"; fi; done'
    args = container_command(metadata["daemon"]["root"]) + ["-i", "--entrypoint", "/bin/sh", "ubuntu:24.04", "-c", script]
    output = command(args, input="\n".join(chains) + "\n")
    return dict(line.split("\t", 1) for line in output.splitlines())


def cpu_budget():
    """Sample idle host CPU and assign half of the initially idle capacity."""
    before = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
    time.sleep(2)
    after = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
    delta = [b - a for a, b in zip(before, after)]
    idle = delta[3] / sum(delta)
    cpus = len(os.sched_getaffinity(0))
    return {"cpus": cpus, "idle_fraction": round(idle, 4), "threads": max(1, int(cpus * idle * 0.5)), "memory_limit_gib": 64}


def scan(metadata, layer_map):
    """Scan Docker once with a bounded CPU budget and save the raw byte tree."""
    scanner = str(DUST_PATH)
    if not DUST_PATH.is_file() or not os.access(DUST_PATH, os.X_OK):
        raise RuntimeError(f"Dust is not executable: {DUST_PATH}")
    budget = cpu_budget()
    metadata.update({"cpu_budget": budget, "layer_map": layer_map, "started_at": datetime.now().astimezone().isoformat()})
    (RESULTS / "docker_inventory.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(f"Scanning Docker only: {budget['threads']} threads, {budget['threads']} CPU quota, 64 GiB memory", flush=True)
    args = container_command(metadata["daemon"]["root"]) + [
        "--cpus", str(budget["threads"]), "--memory", "64g", "--memory-swap", "64g", "--pids-limit", "512",
        "--mount", f"type=bind,source={scanner},target=/usr/local/bin/dust,readonly",
        "--mount", f"type=bind,source={SCRIPT_DIR / 'dust_config.toml'},target=/dust_config.toml,readonly",
        "--entrypoint", "/usr/local/bin/dust", "ubuntu:24.04",
        "--config", "/dust_config.toml", "--threads", str(budget["threads"]), "--limit-filesystem",
        "--depth", "3", "--number-of-lines", "100000", "--full-paths", "--output-format", "b",
        "--no-progress", "--print-errors", "--output-json", "/scan",
    ]
    start = time.monotonic()
    with (RESULTS / "docker_dust.json").open("w") as output, (RESULTS / "docker_dust_errors.txt").open("w") as errors:
        subprocess.run(args, stdout=output, stderr=errors, check=True)
    metadata["finished_at"] = datetime.now().astimezone().isoformat()
    metadata["elapsed_seconds"] = round(time.monotonic() - start, 2)
    (RESULTS / "docker_inventory.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")


def flatten(node, data_root):
    """Map the scanned /scan tree back to Docker's real root directory."""
    usage = {data_root + node["name"].removeprefix("/scan"): int(node["size"].removesuffix("B"))}
    for child in node.get("children", []):
        usage.update(flatten(child, data_root))
    return usage


def attribute(metadata, usage):
    """Attribute allocated blocks without adding shared layers or bind data twice."""
    data_root = metadata["daemon"]["root"]
    containers = []
    for item in metadata["containers"]:
        row = dict(item)
        directory = f"{data_root}/containers/{row['id']}"
        row["writable_bytes"] = usage.get(row["upper_dir"])
        row["container_directory_bytes"] = usage.get(directory)
        log = row["log_path"]
        if log and str(Path(log).parent) == directory:
            row["log_bytes"] = sum(size for path, size in usage.items() if str(Path(path).parent) == directory and (path == log or path.startswith(log + ".")))
        elif log and str(Path(log).parent) in usage:
            row["log_bytes"] = usage[str(Path(log).parent)]
        else:
            row["log_bytes"] = None
        row["allocated_bytes"] = None if row["writable_bytes"] is None or row["container_directory_bytes"] is None else row["writable_bytes"] + row["container_directory_bytes"]
        row["name"] = row["name"].removeprefix("/")
        containers.append(row)
    containers.sort(key=lambda row: row["allocated_bytes"] if row["allocated_bytes"] is not None else -1, reverse=True)
    chain_map = metadata["layer_map"]
    refs = Counter(chain for image in metadata["images"] for chain in image["chain_ids"])
    image_usage = []
    for image in metadata["images"]:
        paths = [f"{data_root}/overlay2/{chain_map[chain]}/diff" for chain in image["chain_ids"] if chain in chain_map]
        complete = len(paths) == len(image["chain_ids"]) and all(path in usage for path in paths)
        image_usage.append({**image, "layer_bytes": sum(usage[path] for path in paths) if complete else None,
            "unique_layer_bytes": sum(usage[f"{data_root}/overlay2/{chain_map[chain]}/diff"] for chain in image["chain_ids"] if refs[chain] == 1) if complete else None,
            "containers": sum(row["image_id"] == image["id"] for row in containers)})
    readonly_paths = {f"{data_root}/overlay2/{cache}/diff" for cache in chain_map.values()}
    volumes = [{**volume, "bytes": usage.get(volume["mountpoint"]), "containers": [row["name"] for row in containers if any(mount.get("Name") == volume["name"] for mount in row["mounts"])]} for volume in metadata["volumes"]]
    result = {"started_at": metadata["started_at"], "finished_at": metadata["finished_at"], "elapsed_seconds": metadata["elapsed_seconds"], "cpu_budget": metadata["cpu_budget"], "root": data_root,
        "total_bytes": usage[data_root], "container_allocated_bytes": sum(row["allocated_bytes"] or 0 for row in containers),
        "image_layer_union_bytes": sum(usage.get(path, 0) for path in readonly_paths), "containers": containers, "images": image_usage, "volumes": volumes}
    result["volume_data_bytes"] = sum(row["bytes"] or 0 for row in volumes)
    result["other_bytes"] = result["total_bytes"] - result["container_allocated_bytes"] - result["image_layer_union_bytes"] - result["volume_data_bytes"]
    result["missing_container_measurements"] = [row["name"] for row in containers if row["allocated_bytes"] is None]
    writable_paths = {row["upper_dir"] for row in containers}
    extra = [{"path": path, "bytes": value} for path, value in usage.items()
        if path.endswith("/diff") and str(Path(path).parent.parent) == data_root + "/overlay2"
        and path not in writable_paths and path not in readonly_paths]
    result["init_layer_bytes"] = sum(row["bytes"] for row in extra if Path(row["path"]).parent.name.endswith("-init"))
    result["unmapped_layers"] = sorted([row for row in extra if not Path(row["path"]).parent.name.endswith("-init")], key=lambda row: row["bytes"], reverse=True)
    return result


def size(value):
    """Display missing measurements distinctly from zero allocation."""
    return human(value) if value is not None else "未测得"


def write_report(report):
    """Write all containers, images, volumes, and mount relationships for review."""
    rows = report["containers"]
    lines = ["# Docker 存储使用信息", "", f"扫描时间：{report['started_at']} 至 {report['finished_at']}；{report['cpu_budget']['threads']} 线程，耗时 {report['elapsed_seconds']:.0f} 秒。", "",
        f"Docker 根目录 `{report['root']}` 实际分配 **{size(report['total_bytes'])}**。已测得容器可写层及容器目录合计 **{size(report['container_allocated_bytes'])}**；镜像只读层去重后已测得 **{size(report['image_layer_union_bytes'])}**；本地卷数据 **{size(report['volume_data_bytes'])}**；其余目录、init 层及元数据等 **{size(report['other_bytes'])}**。", "",
        f"共 {len(rows)} 个容器，运行中 {sum(row['state'] == 'running' for row in rows)} 个。按容器名称展示；明确的 owner 标签保留在 JSON，不根据容器内 UID 推断创建者。", "", "## 容器占用排名", "",
        "占用合计 = 可写层 + 容器目录；日志已包含在容器目录中。共享镜像层、卷、bind mount 不计入该合计。", "",
        "| 容器 | 状态 | 可写层 | 日志 | 合计 | 镜像 |", "| --- | --- | ---: | ---: | ---: | --- |"]
    for row in rows:
        lines.append(f"| `{row['name']}` | {row['state']} | {size(row['writable_bytes'])} | {size(row['log_bytes'])} | {size(row['allocated_bytes'])} | `{row['image']}` |")
    lines.extend(["", "## 镜像占用", "", "只读层数值按扫描分配块计算；多个镜像可能引用相同层，各行总量不能相加。独有层仅指未被其他镜像引用，不代表可立即回收。", "", "| 镜像 | 只读层总量 | 独有层 | 引用容器数 |", "| --- | ---: | ---: | ---: |"])
    for image in sorted(report["images"], key=lambda row: row["layer_bytes"] or 0, reverse=True):
        name = ", ".join(image["tags"] or []) or image["id"][:19]
        lines.append(f"| `{name}` | {size(image['layer_bytes'])} | {size(image['unique_layer_bytes'])} | {image['containers']} |")
    lines.extend(["", "## 本地卷", "", "| 卷 | 占用 | 引用容器 |", "| --- | ---: | --- |"])
    for volume in report["volumes"]:
        lines.append(f"| `{volume['name']}` | {size(volume['bytes'])} | {', '.join(volume['containers']) or '无'} |")
    lines.extend(["", "## 未映射 overlay 层", "", f"另有 init 层 {size(report['init_layer_bytes'])}。下列层未对应到本次采集的容器可写层或现有镜像层，属于其余占用；不能仅据此认定可安全删除。", "", "| 层目录 | 占用 |", "| --- | ---: |"])
    for layer in report["unmapped_layers"]:
        lines.append(f"| `{layer['path']}` | {size(layer['bytes'])} |")
    lines.extend(["", "## 挂载关系", "", "bind mount 数据属于宿主机对应目录，已在用户目录统计中覆盖；此处只列映射，不重复扫描或累加。", "", "| 容器 | 类型 | 宿主机路径 | 容器路径 |", "| --- | --- | --- | --- |"])
    for row in rows:
        for mount in row["mounts"]:
            lines.append(f"| `{row['name']}` | {mount['Type']} | `{mount['Source']}` | `{mount['Destination']}` |")
    lines.extend(["", "## 复现与口径", "", "```bash", "# 刷新 Docker 元数据并只扫描 Docker 根目录", f"python3 {shlex.quote(str(SCRIPT_DIR / 'docker_usage.py'))}", "", "# 从保存的扫描结果重新生成报告", f"python3 {shlex.quote(str(SCRIPT_DIR / 'docker_usage.py'))} --report-only", "```", "", "通过 Dust 只读扫描 overlay2 底层目录，禁用递归挂载、不跟随符号链接、按 inode 全局去重。镜像层通过 Docker chain ID 与 cache ID 对应；可写层通过容器 inspect 的 UpperDir 对应。元数据采集与扫描存在时间差，运行中写入会带来快照误差。", "", "日志仅统计 Docker 根目录内的 json-file 日志及其轮转文件，或 local 日志目录；外部日志驱动的空间不在此处计量。空缺显示为未测得，不视为零。镜像、容器、卷以外的 init 层、缓存及元数据仍属于根目录总量。", "", "可写层、共享镜像、日志和卷的口径参见 [Docker 存储说明](https://docs.docker.com/engine/storage/drivers/)。本报告不执行清理。", ""])
    (ROOT / "DOCKER_USAGE.md").write_text("\n".join(lines))
    (RESULTS / "docker_usage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Docker: {size(report['total_bytes'])}; {len(rows)} containers; report: DOCKER_USAGE.md", flush=True)
    for row in rows[:12]:
        print(row["name"], row["state"], size(row["allocated_bytes"]), flush=True)


def main():
    """Refresh Docker allocation or regenerate the report from saved scan data."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    if not args.report_only:
        metadata = collect_metadata()
        mapping = collect_layer_map(metadata)
        scan(metadata, mapping)
    metadata = json.loads((RESULTS / "docker_inventory.json").read_text())
    errors = (RESULTS / "docker_dust_errors.txt").read_text()
    if errors:
        raise RuntimeError(f"Review results/docker_dust_errors.txt before using this scan: {errors[:1000]}")
    usage = flatten(json.loads((RESULTS / "docker_dust.json").read_text()), metadata["daemon"]["root"])
    write_report(attribute(metadata, usage))


if __name__ == "__main__":
    main()

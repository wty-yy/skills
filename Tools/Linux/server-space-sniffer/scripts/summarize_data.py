"""Summarize one read-only /data scan by user directory and Docker allocation.

Overview:
    Read scan_data.sh output and write a sorted Markdown and JSON report.

Quick Start:
    bash /path/to/server-space-sniffer/scripts/scan_data.sh

Notes:
    Directory names define attribution; file UID does not determine ownership.
    Symlinks to other disks are excluded. Shared hard links are counted once.
"""

from datetime import datetime
import json
import os
import shlex
from pathlib import Path


def parse_usage(raw):
    """Parse GNU du's NUL-terminated byte counts without splitting path names."""
    result = {}
    for entry in raw.split(b"\0"):
        if entry:
            size, path = entry.split(b"\t", 1)
            result[path.decode(errors="surrogateescape").replace("/scan", "/data", 1)] = int(size)
    return result


def parse_dust(node):
    """Flatten Dust's depth-limited JSON tree while preserving exact byte counts."""
    path = node["name"].replace("/scan", "/data", 1)
    usage = {path: int(node["size"].removesuffix("B"))}
    for child in node.get("children", []):
        usage.update(parse_dust(child))
    return usage


def human(value):
    """Display allocated bytes using binary units."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024


def summarize(usage):
    """Separate named user directories, Docker, other allocations, and links."""
    users, others, links = [], [], []
    for path in sorted(Path("/data").iterdir()):
        if path.is_symlink():
            links.append({"path": str(path), "target": str(path.resolve()), "bytes_on_data": usage.get(str(path), 0)})
        elif path.name == "user":
            for child in sorted(path.iterdir()):
                if child.is_symlink():
                    links.append({"path": str(child), "target": str(child.resolve()), "bytes_on_data": usage.get(str(child), 0)})
                elif child.is_dir():
                    users.append({"user": child.name, "path": str(child), "bytes": usage[str(child)]})
            child_total = sum(size for name, size in usage.items() if str(Path(name).parent) == "/data/user")
            others.append({"path": "/data/user (directory overhead)", "bytes": usage[str(path)] - child_total})
        elif path.name != "docker":
            row = {"path": str(path), "bytes": usage[str(path)]}
            if path.is_dir() and path.name not in {"home_bak", "www", "lost+found"}:
                users.append({"user": path.name, **row})
            else:
                others.append(row)
    users.sort(key=lambda row: row["bytes"], reverse=True)
    others.sort(key=lambda row: row["bytes"], reverse=True)
    docker_dirs = [
        {"path": path, "bytes": size}
        for path, size in usage.items() if str(Path(path).parent) == "/data/docker"
    ]
    docker_dirs.sort(key=lambda row: row["bytes"], reverse=True)
    return {"users": users, "docker_bytes": usage["/data/docker"], "docker_directories": docker_dirs, "others": others, "links": links, "total_bytes": usage["/data"]}


def main():
    """Save the scan's directory accounting and render a concise result table."""
    root = Path.cwd()
    script_dir = Path(__file__).resolve().parent
    results = root / "results"
    errors = (results / "data_dust_errors.txt").read_text()
    if errors:
        raise RuntimeError(f"Scan has warnings; review results/data_dust_errors.txt: {errors[:1000]}")
    report = summarize(parse_dust(json.loads((results / "data_dust.json").read_text())))
    report["cpu_budget"] = json.loads((results / "cpu_budget.json").read_text())
    report["started_at"] = (results / "data_scan_started.txt").read_text().strip()
    report["finished_at"] = (results / "data_scan_finished.txt").read_text().strip()
    report["elapsed_seconds"] = (datetime.fromisoformat(report["finished_at"]) - datetime.fromisoformat(report["started_at"])).total_seconds()
    stats = os.statvfs("/data")
    report["filesystem_used_bytes"] = (stats.f_blocks - stats.f_bfree) * stats.f_frsize
    report["filesystem_available_bytes"] = stats.f_bavail * stats.f_frsize
    (results / "data_usage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# data 下用户目录与 Docker 占用", "",
        f"扫描时间：{report['started_at']} 至 {report['finished_at']}，耗时 {report['elapsed_seconds']:.0f} 秒。", "",
        f"使用当前用户的 `~/.local/bin/dust`，{report['cpu_budget']['threads']} 个线程；启动时取空闲 CPU 的约 50%，并设置同等 CPU 配额上限。", "",
        "按目录归属统计实际分配块，包含隐藏文件。Docker 独立列出，不分摊给用户。", "",
        "| 用户目录 | 路径 | 占用 |", "| --- | --- | ---: |",
    ]
    for row in report["users"]:
        lines.append(f"| {row['user']} | `{row['path']}` | {human(row['bytes'])} |")
    lines.extend(["", f"**Docker `/data/docker`：{human(report['docker_bytes'])}**。包含镜像、容器可写层、Docker 本地卷、该目录下的日志和元数据。", "", "## Docker 目录明细", "", "| 路径 | 占用 |", "| --- | ---: |"])
    for row in report["docker_directories"]:
        lines.append(f"| `{row['path']}` | {human(row['bytes'])} |")
    lines.extend(["", "容器、镜像和卷的内部使用信息见 [DOCKER_USAGE.md](DOCKER_USAGE.md)。通过指定脚本刷新。"])
    lines.extend(["", "## 其他占用", "", "| 路径 | 占用 |", "| --- | ---: |"])
    for row in report["others"]:
        lines.append(f"| `{row['path']}` | {human(row['bytes'])} |")
    lines.extend(["", f"**扫描总计：{human(report['total_bytes'])}**。报告生成时文件系统已用 {human(report['filesystem_used_bytes'])}，可用 {human(report['filesystem_available_bytes'])}。", "", "## 外部链接", "", "以下目标不在 `/data`，不计入上述用户占用：", ""])
    for row in report["links"]:
        lines.append(f"- `{row['path']}` → `{row['target']}`")
    lines.extend(["", "## 复现", "", "```bash", "# 使用指定路径的 Dust 与已有 ubuntu:24.04 镜像；自动采样空闲 CPU 并取约一半", f"bash {shlex.quote(str(script_dir / 'scan_data.sh'))}", "", "# 仅重新生成报告，不重新扫描", f"python3 {shlex.quote(str(script_dir / 'summarize_data.py'))}", "```", "", "## 口径", "", "Dust 使用 `--threads N --limit-filesystem --depth 2 --number-of-lines 100000 --output-format b --output-json` 单次遍历 `/data`，统计实际分配块，包含隐藏文件；输出深度不会减少扫描深度。不跟随符号链接，不读取普通文件内容。无现成配额计数时，目录计量需要遍历元数据，耗时随文件数量增长。线程数取启动时两秒采样的空闲 CPU 约 50%，不随之后的负载动态调整；CPU 配额是上限，不保证实际用满。", "", "Docker bind mount 到用户目录的数据计入对应目录，不重复计入 Docker 根目录。容器 overlay 挂载视图排除；共享硬链接全局只计一次，归属由去重顺序决定。目录归属不等于文件 UID 归属，例如 `/data/guohanwei` 按目录名称归属。", "", "Dust 使用并行遍历并去重 inode；JSON 输出设为字节，保留精确数值。[Dust 扫描源码](https://github.com/bootandy/dust/blob/master/src/dir_walker.rs)", "", "扫描通过 Docker 只读挂载执行，并禁用子挂载，避免容器 overlay 重复统计。[Docker 挂载说明](https://docs.docker.com/engine/storage/bind-mounts/#recursive-mounts)", "", "这是运行中系统的扫描快照；扫描期间的写入和已删除但仍打开的文件等因素，会使目录合计与 `df` 的已用空间不同。`/data/user` 和 `/data` 自身目录块、链接文件等少量开销不分摊给用户。", ""])
    output = "\n".join(lines)
    (root / "DATA_USAGE.md").write_text(output)
    print(output)


if __name__ == "__main__":
    main()

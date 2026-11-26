---
name: server-space-sniffer
description: "统计 Linux 服务器磁盘容量、/data 下各用户目录和 Docker 内部存储占用，生成容器、共享镜像、日志、卷和挂载明细。适用于空间排查与占用排名，不用于自动清理磁盘或容器。"
---

# Server Space Sniffer

## 环境与输出

使用当前用户的 `~/.local/bin/dust`，运行时展开用户主目录，不限制版本，不通过 PATH 选择其他 dust，也不自行下载安装或升级。

依赖 Linux、Python 3.9+、`findmnt`；完整目录扫描另需本机 rootful Docker 权限及已有 `ubuntu:24.04` 镜像。Docker 内部明细目前支持 `overlay2`。临时扫描容器只读挂载数据目录、禁用子挂载，完成后自动删除。

在用户指定的统计工作目录执行脚本；未指定时使用当前项目目录。结果写入该工作目录的 `space_sniffer_results/`、`DATA_USAGE.md`、`DOCKER_USAGE.md`，不要在 Skill 目录中生成主机快照。命令中的 `SKILL_DIR` 指本文件所在目录，使用其实际绝对路径。

## 按需求运行

只查整盘容量与可用空间时，读取文件系统计数即可：

```bash
python3 "$SKILL_DIR/scripts/storage_monitor.py"
# 多机使用已有 SSH 别名，按需重复 --host
python3 "$SKILL_DIR/scripts/storage_monitor.py" --host local --host user@server --json
```

查 `/data` 下每个用户目录占用时，执行一次完整目录扫描：

```bash
bash "$SKILL_DIR/scripts/scan_data.sh"
# 仅重新生成已保存扫描的报告
python3 "$SKILL_DIR/scripts/summarize_data.py"
```

用户目录覆盖 `/data/<用户名>` 和 `/data/user/<用户名>`；Docker、备份、公共目录和 swapfile 分开列出。统计按目录名称归属，不等同于文件 UID 或容器创建者归属。

查 Docker 内部明细时，只扫描 Docker 根目录：

```bash
python3 "$SKILL_DIR/scripts/docker_usage.py"
# 仅解读或重新生成已有明细，无需重扫
python3 "$SKILL_DIR/scripts/docker_usage.py" --report-only
```

该报告覆盖运行中及已停止容器的可写层、日志、配置，现有镜像层去重、本地卷、挂载关系及未映射 overlay 层。请求完整用户与 Docker 信息时，先后运行用户目录扫描和 Docker 明细扫描，避免两次扫描同时竞争磁盘。

## 采集与解释

- 扫描启动时采样两秒 CPU 空闲量，取约 50% 作为线程数和 CPU 配额；之后不动态调整。内存上限 64 GiB，禁用扫描容器 swap。不要将线程数或旧机器的耗时直接当作新扫描的完成时间。
- Dust 读取目录和文件元数据，仍需遍历；输出深度不限制扫描深度。只有整盘计数查询能避免遍历。现成配额计数可支持频繁的按用户查询，但本 Skill 不修改配额或挂载配置。
- 不跟随符号链接；指向 `/hard_data` 的用户目录仅列出目标，不计入 `/data`。硬链接全局只计一次，容器 overlay 运行视图排除。
- 容器占用合计为可写层加容器目录，日志已包含其中；共享镜像、卷和 bind mount 分开列出。镜像各行可能引用相同层，不能直接累加。详细口径见 [references/accounting.md](references/accounting.md)。
- 查询容器列表时显式使用 `--size=false` 和选定字段；`docker ps --format '{{json .}}'` 可能隐式触发大小计算。脚本只采集选定 inspect 字段，不采集环境变量或启动命令。
- 用户要求当前用量时刷新；仅解读已有结果时直接读取快照并注明时间。扫描失败或出现错误时检查 `space_sniffer_results/*errors.txt`，未测得的项目不能当成零，也不要把历史报告当成该次成功结果。

报告先给磁盘占用、用户排名或最大容器，再链接完整明细。说明数据时间、未计入的外部目录和未测得项目；不依据“已停止”或“未映射”判断可安全删除。

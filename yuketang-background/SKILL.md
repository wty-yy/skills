---
name: yuketang-background
description: 使用 Chrome 登录状态管理雨课堂后台视频任务，排查进度与视频时长问题，并按用户明确范围处理图文、学习讨论、章节测试和考试流程。
---

# 雨课堂后台视频任务

本 skill 自包含于当前目录。脚本面向 Linux 桌面 Chrome，运行入口为 `scripts/ykt.sh`，目录内另有 `./ykt.sh` 快捷入口。执行前切换到本 SKILL.md 所在目录，以下相对路径均以该目录为基准。

## 使用

首次缺少环境时执行 `bash scripts/setup.sh`；依赖安装到本目录的 `.venv`。目录内也可使用 `./ykt.sh` 快捷入口。随后按用户意图执行：

```bash
bash scripts/ykt.sh scan                         # 只读扫描全部课程的视频状态
bash scripts/ykt.sh start                        # 后台处理 config.json 中的范围
bash scripts/ykt.sh start --classroom-id 32132220 # 单课程后台处理
bash scripts/ykt.sh status                       # 进程、计数、当前视频及最后状态
bash scripts/ykt.sh logs                         # 最近 40 行日志
bash scripts/ykt.sh stop                         # 优雅停止
```

`run` 为前台执行；`scan` 也接受 `--classroom-id`。启动前先查看 `status`；已运行时不要重复创建任务。若用户已明确要求后台刷课，可直接执行扫描、启动与状态核验，无须另行确认相同范围。

## 按任务读取

- 视频缺失时长、学校上下文、接口报错或后台失败：读 [references/troubleshooting.md](references/troubleshooting.md)。
- 未完成数量不符、图文、讨论、章节测试或考试：读 [references/course-tasks.md](references/course-tasks.md)。
- API 来源与视频实现：读 [references/implementation.md](references/implementation.md)。

## 范围与状态判断

- `config.json` 的 `classroom_ids: []` 表示账号课程列表中的全部课程；可填写班级 ID 列表。显式 `--classroom-id` 优先。默认跳过已结束、未开放、锁定、隐藏或超过截止时间的节点。
- 仅处理 `leaf_type=0` 的视频，包括拓展视频；非视频节点计入跳过统计。作业、考试、讨论发言和图文不由该后台命令执行，按 course-tasks.md 中的流程分别处理。
- 这是批量视频心跳上报，不是实际播放。用服务器 `completed` 字段判断完成，不能把请求成功或后台 PID 存在描述为全部刷完。
- 进程自动处理一轮后退出，不安装开机服务，不定时扫描新课程。再次启动会查询服务器并跳过已完成视频。
- `.runtime/state.json` 含每个课程和视频的状态；`.runtime/task.log` 为日志。`finished` 仅表示本轮可处理视频均被确认；检查 `videos_skipped` 和 `non_video_skipped` 后再描述范围。`finished_with_pending` 表示存在未确认的视频或无法访问的课程。`courses_unavailable` 记录课程接口返回 400001、但主账号登录复查仍有效的课程；这类课程跳过后继续扫描，其余鉴权错误仍停止任务。
- `failed`、限流、会话失效或数据格式变化时，先读日志排查，不无限重启。进程不在但状态仍为 running/scanning 时属于意外中断，不能报成功。
- `stop` 在当前网络请求结束后退出；下次启动从服务器进度恢复，而不是依赖本地完成记录。

## 登录与配置

`chrome_profile: "auto"` 自动选择含目标站点 Cookie 的唯一配置。多个配置已登录时需指定 `Default`、`Profile 1` 等目录名。读取 Chrome Cookie 和系统密钥环需要用户的桌面登录会话；在 Chrome 重新登录后再启动即可刷新凭据。

只在内存中保存 `sessionid` 与 `csrftoken`，仅发送至配置允许的雨课堂域名，不打印 Cookie、完整请求头或账号数据，不要求把 Cookie 粘贴进对话。不要将 `.runtime` 或 `.venv` 提交到版本库。

默认学校为 `2938`、平台为 `3`、域名为 `www.yuketang.cn`；课程自身的学校信息优先。心跳间隔、请求间隔、重试上限在 config.json 中设置。学校 ID 为 0 是合法值，不替换成默认值。详情和进度均缺失时长时，可按 troubleshooting.md 使用带来源的本地播放器核对记录。单视频超出 `max_video_seconds` 时保留为未完成，不截短时长后报成功。

接口出处、实现验证记录见 [references/implementation.md](references/implementation.md)。维护后运行：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile scripts/yuketang.py
```

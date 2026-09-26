# 实现依据

参考项目：[COCOSTEAM/yuketang](https://github.com/COCOSTEAM/yuketang)，调研版本 `168f3177d8aaa587b84342a58b18f759af01c0b6`。本地实现独立编写，没有安装或执行该仓库代码。API 与事件字段参考其 `api.py`、`client/base.py`、`client/video.py`，并通过本账号实际响应核对。未在该版本的文件树发现 LICENSE，因此未将其代码直接作为依赖或复制进项目。

核对接口：

| 用途 | 路径 |
| --- | --- |
| 登录校验 | `/api/v3/user/basic-info` |
| 课程列表 | `/v2/api/web/courses/list?identity=2` |
| 班级信息 | `/v2/api/web/classrooms/{id}?role=5` |
| 章节 | `/mooc-api/v1/lms/learn/course/chapter` |
| 视频详情 | `/mooc-api/v1/lms/learn/leaf_info/{classroom_id}/{leaf_id}/` |
| 视频进度 | `/video-log/get_video_watch_progress/` |
| 心跳上报 | `/video-log/heartbeat/` |

请求不跟随重定向，网络或鉴权失败立即停止。心跳提交最多两轮，每轮最多三次延迟复查。视频事件按顺序分批，每批最多 200 条。结束时间不超过当前时间，进度不超过视频长度；服务器仍可能拒绝或不计入，必须依赖复查结果。

2026-09-26 实测：心跳接口的成功响应为 HTTP 200 与空对象 `{}`，仅对此接口接受空确认。首个 861 秒视频随后由进度接口返回 `completed: 1`、`rate: 1.0`，验证上报有效。空确认本身不作为完成依据。

后台运行依赖当前机器持续开机和网络可用；终端关闭不影响独立进程，系统关机或休眠会中断。下次启动重新核对服务器状态。私有运行目录权限为 0700，状态文件权限为 0600。

本地测试覆盖锁定及时间过滤、心跳序号与边界、HTTP 重定向/鉴权/限流失败、服务器未确认时不报完成，以及 PID 复用防护。

"""在 Linux 后台处理雨课堂视频任务并保存服务器确认的进度。

Overview:
    从本地 Chrome 读取本站 Cookie，扫描课程，发送视频心跳并复查结果。
Quick Start:
    ./ykt.sh scan
Full Command:
    ./ykt.sh start --classroom-id 32132220
Options:
    command: scan/run/start/status/stop/logs。
    --classroom-id: 限定班级；省略时使用配置中的范围。
Notes:
    仅支持视频；心跳上报不等于实际播放视频。Cookie 不写入文件或日志。
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

import browser_cookie3
import requests

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
STOP = threading.Event()
LOG = logging.getLogger('yuketang')


class TaskError(Exception):
    """可安全输出、不包含请求凭据的运行错误。"""


class Stopped(TaskError):
    """用户请求停止任务。"""


class ApiError(TaskError):
    """保留业务错误码，供调用方区分课程访问失败。"""

    def __init__(self, key, code, path):
        """记录不包含凭据的 API 错误。"""
        self.code = code
        super().__init__(f'API 拒绝请求：{key}={code!r}，路径 {path}')


def pause(seconds):
    """等待指定时间，并及时响应停止信号。"""
    if STOP.wait(seconds):
        raise Stopped('用户已停止任务')


def save_json(path, data):
    """原子写入仅当前用户可读的状态文件。"""
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as file:
        os.chmod(tmp, 0o600)
        json.dump(data, file, ensure_ascii=False, indent=2)
    tmp.replace(path)


def read_config():
    """加载配置并限制凭据发送目标与运行参数。"""
    config = json.loads((ROOT / 'config.json').read_text())
    if config['host'] not in {'www.yuketang.cn', 'pro.yuketang.cn', 'changjiang.yuketang.cn'}:
        raise TaskError('host 必须是支持的雨课堂官方域名')
    for key, low, high in [('request_interval', .2, 60), ('heartbeat_interval', 1, 30),
                           ('max_rounds', 1, 3), ('max_video_seconds', 1, 28800)]:
        value = config[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise TaskError(f'配置项 {key} 超出允许范围')
    if not isinstance(config['max_rounds'], int):
        raise TaskError('max_rounds 必须是整数')
    return config


def chrome_auth(config):
    """仅提取目标雨课堂域名的两项登录 Cookie。"""
    root = Path.home() / '.config/google-chrome'
    profile = config.get('chrome_profile', 'auto')
    candidates = sorted(root.glob('*/Cookies')) + sorted(root.glob('*/Network/Cookies'))
    if profile != 'auto':
        candidates = [p for p in candidates if p.parent.name == profile or
                      (p.parent.name == 'Network' and p.parent.parent.name == profile)]
    domains = (config['host'], '.yuketang.cn', 'yuketang.cn')
    found = []
    for path in candidates:
        try:
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
                names = {row[0] for row in db.execute(
                    'SELECT name FROM cookies WHERE host_key IN (?,?,?) AND name IN (?,?)',
                    (*domains, 'sessionid', 'csrftoken'))}
            if names == {'sessionid', 'csrftoken'}:
                found.append(path)
        except sqlite3.Error:
            continue
    if len(found) != 1:
        raise TaskError('未找到唯一的已登录 Chrome 配置；请登录雨课堂，或在 config.json 指定 chrome_profile')
    try:
        jar = browser_cookie3.chrome(cookie_file=str(found[0]), domain_name='yuketang.cn')
        auth = {}
        # 精确域名优先于父域 Cookie，避免跨子站复用会话。
        for domain in reversed(domains):
            for cookie in jar:
                if cookie.domain == domain and cookie.name in {'sessionid', 'csrftoken'} and not cookie.is_expired():
                    auth[cookie.name] = cookie.value
        if not all(auth.get(name) for name in ('sessionid', 'csrftoken')):
            raise TaskError('Cookie 缺失或已过期，请在 Chrome 重新登录')
        return auth
    except TaskError:
        raise
    except Exception as exc:
        raise TaskError(f'Chrome Cookie 解密失败（{type(exc).__name__}），请在桌面登录会话中运行') from None


def timestamp(value):
    """将 API 的秒或毫秒时间戳统一为秒。"""
    value = float(value or 0)
    return value / 1000 if value > 100_000_000_000 else value


def closed_reason(node, now=None):
    """判断课程或节点是否尚未开放、已结束或被锁定。"""
    now = time.time() if now is None else now
    if node.get('is_locked') or node.get('is_deleted') or node.get('is_show') is False or node.get('has_classend'):
        return '锁定、隐藏或已结束'
    for key in ('class_start', 'class_start_time', 'start_time', 'publish_time'):
        if timestamp(node.get(key)) > now:
            return '未开放'
    for key in ('class_end', 'class_end_time', 'end_time', 'score_deadline'):
        deadline = timestamp(node.get(key))
        if deadline and deadline < now:
            return '已结束或超过截止时间'
    return ''


def collect_leaves(nodes, inherited=''):
    """递归收集叶子节点，并保留父节点的访问限制。"""
    for node in nodes:
        reason = inherited or closed_reason(node)
        if 'leaf_type' in node and 'id' in node:
            yield node, reason
        for key in ('section_leaf_list', 'leaf_list'):
            yield from collect_leaves(node.get(key, []), reason)


def completed(progress):
    """只接受服务器明确返回的视频完成标记。"""
    return isinstance(progress, dict) and (progress.get('completed') is True or
                                          type(progress.get('completed')) is int and progress['completed'] == 1)


def video_duration(progress, media, classroom_id, leaf_id):
    """优先读取服务器时长，缺失时使用带来源的本地播放器核对记录。"""
    for value in (progress.get('video_length'), media.get('duration')):
        try:
            seconds = float(value or 0)
        except (TypeError, ValueError):
            continue
        if math.isfinite(seconds) and seconds > 0:
            return seconds
    path = RUNTIME / 'video-durations.json'
    if not path.exists():
        return 0
    try:
        entries = json.loads(path.read_text())
        entry = entries.get(f'{classroom_id}:{leaf_id}')
        if entry is None:
            return 0
        source = entry.get('source')
        if not isinstance(source, str) or not source.strip():
            raise ValueError('missing source')
        seconds = float(entry['seconds'])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('invalid duration')
        return seconds
    except (ValueError, TypeError, KeyError, AttributeError):
        raise TaskError('video-durations.json 格式无效；需要 seconds 和非空 source') from None


class Client:
    """维护单账号的雨课堂 API 会话。"""

    def __init__(self, config, auth):
        """创建固定目标域名的 HTTP 会话。"""
        self.config = config
        self.base = 'https://' + config['host']
        self.session = requests.Session()
        self.session.cookies.update(auth)
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 Chrome/134.0.0.0',
                                     'X-Csrftoken': auth['csrftoken'], 'xtbz': config['xtbz'],
                                     'Referer': self.base + '/', 'Origin': self.base})
        self.cid = 0
        self.last_request = 0
        self.context(0, config['university_id'])

    def context(self, classroom_id, university_id):
        """切换课程所属学校与班级上下文。"""
        self.cid = int(classroom_id)
        self.session.headers.update({'University-Id': str(university_id), 'Classroom-Id': str(self.cid)})
        self.session.cookies.update({'university_id': str(university_id), 'uv_id': str(university_id),
                                     'classroom_id': str(self.cid), 'classroomId': str(self.cid),
                                     'platform_id': str(self.config['platform_id'])})

    def request(self, method, path, **kwargs):
        """请求 API；拒绝重定向，遇到鉴权、限流或网络错误即停止。"""
        pause(max(0, self.last_request + self.config['request_interval'] - time.monotonic()))
        try:
            response = self.session.request(method, self.base + path, timeout=(10, 30),
                                            allow_redirects=False, **kwargs)
            self.last_request = time.monotonic()
            if response.status_code in (401, 403):
                raise TaskError('登录失效或访问被拒绝，请在 Chrome 中确认登录状态')
            if response.status_code == 429:
                raise TaskError('平台限流，任务停止；稍后重新启动')
            if response.status_code == 400:
                try:
                    failure = response.json()
                except ValueError:
                    failure = None
                if isinstance(failure, dict) and failure.get('error_code') == 80019 and failure.get('success') is False:
                    raise ApiError('error_code', 80019, path)
            if not 200 <= response.status_code < 300:
                raise TaskError(f'API 请求失败：HTTP {response.status_code}，路径 {path}')
            data = response.json()
        except requests.RequestException as exc:
            raise TaskError(f'网络请求失败（{type(exc).__name__}），任务停止') from None
        except ValueError:
            raise TaskError('API 返回非 JSON 内容，可能需要重新登录') from None
        if not isinstance(data, dict):
            raise TaskError('API 返回格式已变化')
        for key in ('code', 'errcode', 'error_code'):
            if key in data and data[key] != 0:
                raise ApiError(key, data[key], path)
        if data.get('success') is False:
            raise TaskError(f'API 返回失败，路径 {path}')
        empty_heartbeat_ack = path == '/video-log/heartbeat/' and method == 'POST' and data == {}
        if not empty_heartbeat_ack and not any(key in data for key in ('code', 'errcode', 'success')):
            raise TaskError(f'API 缺少成功标记，路径 {path}')
        return data.get('data', {})

    def progress(self, user_id, course_id, leaf_id):
        """读取一个视频的服务器学习进度。"""
        data = self.request('GET', '/video-log/get_video_watch_progress/', params={
            'user_id': user_id, 'cid': course_id, 'classroom_id': self.cid,
            'video_id': leaf_id, 'video_type': 'video', 'vtype': 'rate', 'snapshot': 1})
        return data.get(str(leaf_id)) or {}

    def heartbeat(self, events):
        """向固定雨课堂域名提交视频事件。"""
        self.request('POST', '/video-log/heartbeat/', json={'heart_data': events})


def video_events(user_id, course_id, classroom_id, leaf_id, info, duration, interval=5):
    """按视频时长生成有序心跳，时间戳不超过当前时间。"""
    if not math.isfinite(duration) or duration <= 0:
        raise TaskError('视频时长无效')
    media = info['content_info']['media']
    base = {'i': 5, 'p': 'web', 'n': 'ali-cdn.xuetangx.com', 'lob': 'ykt',
            'u': user_id, 'uip': '', 'c': course_id, 'v': leaf_id,
            'skuid': info['sku_id'], 'classroomid': classroom_id, 'cc': media['ccid'],
            'd': duration, 'pg': f'{leaf_id}_{uuid.uuid4().hex[:8]}', 't': 'video',
            'cards_id': 0, 'slide': 0, 'v_url': '', 'fp': 0, 'tp': 0, 'sp': 1}
    start = int(time.time() * 1000) - math.ceil(duration * 1000) - 3000
    events = []
    sequence = [('loadstart', 0, 0), ('loadeddata', 0, 500), ('play', 0, 1000), ('playing', 0, 1100)]
    position = min(interval, duration)
    while True:
        sequence.append(('heartbeat', position, 1100 + round(position * 1000)))
        if position >= duration:
            break
        position = min(duration, position + interval)
    sequence.extend([('pause', duration, 1200 + round(duration * 1000)),
                     ('videoend', duration, 1300 + round(duration * 1000))])
    for number, (event, position, offset) in enumerate(sequence, 1):
        events.append({**base, 'et': event, 'cp': position, 'ts': start + offset, 'sq': number,
                       'd': 0 if event == 'loadstart' else duration})
    return events


class Runner:
    """扫描视频并记录可复查的后台运行状态。"""

    def __init__(self, config, classroom_id=None):
        """初始化范围、统计和状态文件。"""
        self.config = config
        self.targets = [classroom_id] if classroom_id else config['classroom_ids']
        self.state = {'status': 'initializing', 'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                      'counts': {}, 'courses': [], 'videos': []}
        self.counts = Counter()

    def update(self, **values):
        """保存运行状态，供 status 命令查询。"""
        self.state.update(values)
        self.state['counts'] = dict(self.counts)
        self.state['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_json(RUNTIME / 'state.json', self.state)

    def execute(self, write=False):
        """依次处理课程，完整记录跳过项与未确认的完成状态。"""
        self.update(status='running' if write else 'scanning', mode='run' if write else 'scan')
        client = Client(self.config, chrome_auth(self.config))
        try:
            user_id = client.request('GET', '/api/v3/user/basic-info')['id']
            courses = client.request('GET', '/v2/api/web/courses/list', params={'identity': 2})['list']
            if self.targets:
                courses = [c for c in courses if c['classroom_id'] in self.targets]
                if {c['classroom_id'] for c in courses} != set(self.targets):
                    raise TaskError('指定班级不在当前账号课程列表中')
            self.counts['courses_total'] = len(courses)
            for course in courses:
                cid = course['classroom_id']
                name = course.get('course', {}).get('name', str(cid))
                uv = course.get('course', {}).get('university_id')
                if uv is None:
                    uv = self.config['university_id']
                client.context(cid, uv)
                self.update(current_course=f'{name} ({cid})', current_video=None)
                record = {'id': cid, 'name': name}
                self.state['courses'].append(record)
                try:
                    classroom = client.request('GET', f'/v2/api/web/classrooms/{cid}', params={'role': 5})
                except ApiError as exc:
                    if exc.code != 400001:
                        raise
                    # 旧学校课程可能无账号关联；先确认主账号会话仍然有效。
                    client.context(0, self.config['university_id'])
                    current_user = client.request('GET', '/api/v3/user/basic-info')
                    if current_user.get('id') != user_id:
                        raise TaskError('账号登录状态发生变化，任务停止') from None
                    record.update(status='unavailable', reason='课程所属学校没有用户信息（400001）')
                    self.counts['courses_unavailable'] += 1
                    self.update()
                    LOG.warning('跳过无法访问的课程 %s (%s)：400001，主账号登录有效', name, cid)
                    continue
                reason = closed_reason(classroom)
                if reason:
                    record['skipped'] = reason
                    self.counts['courses_skipped'] += 1
                    LOG.info('跳过课程 %s (%s)：%s', name, cid, reason)
                    continue
                if not classroom.get('course_sign'):
                    record['skipped'] = '无线上课程目录'
                    self.counts['courses_skipped'] += 1
                    LOG.info('跳过课程 %s (%s)：无线上课程目录', name, cid)
                    continue
                try:
                    tree = client.request('GET', '/mooc-api/v1/lms/learn/course/chapter', params={
                        'cid': cid, 'classroom_id': cid, 'sign': classroom['course_sign'], 'uv_id': uv})['course_chapter']
                except ApiError as exc:
                    if exc.code != 80019:
                        raise
                    record.update(status='unavailable', reason='没有该课程的学习权限（80019）')
                    self.counts['courses_unavailable'] += 1
                    self.update()
                    LOG.warning('跳过无法访问的课程 %s (%s)：没有该课程的学习权限（80019）', name, cid)
                    continue
                leaves = list(collect_leaves(tree))
                self.counts['non_video_skipped'] += sum(leaf.get('leaf_type') != 0 for leaf, _ in leaves)
                LOG.info('扫描课程 %s (%s)：%d 个节点', name, cid, len(leaves))
                for leaf, reason in leaves:
                    if leaf.get('leaf_type') != 0:
                        continue
                    self.process_video(client, user_id, classroom['course_id'], leaf, reason, write)
                record['scanned'] = True
            incomplete = bool(self.counts['pending'] or self.counts['courses_unavailable'])
            status = 'scan_complete' if not write else ('finished_with_pending' if incomplete else 'finished')
            self.update(status=status, current_video=None)
            LOG.info('本轮结束：%s', json.dumps(dict(self.counts), ensure_ascii=False))
            return 2 if write and incomplete else 0
        finally:
            client.session.close()

    def process_video(self, client, user_id, course_id, leaf, reason, write):
        """检查单个视频，仅在服务器确认后记录完成。"""
        leaf_id = leaf['id']
        title = leaf.get('name') or leaf.get('title') or str(leaf_id)
        row = {'classroom_id': client.cid, 'id': leaf_id, 'name': title, 'status': 'pending'}
        self.state['videos'].append(row)
        self.counts['videos_total'] += 1
        self.update(current_video=title)
        if reason:
            row.update(status='skipped', reason=reason)
            self.counts['videos_skipped'] += 1
            return
        progress = client.progress(user_id, course_id, leaf_id)
        if completed(progress):
            row['status'] = 'already_complete'
            self.counts['already_complete'] += 1
            return
        if not write:
            self.counts['pending'] += 1
            return
        info = client.request('GET', f'/mooc-api/v1/lms/learn/leaf_info/{client.cid}/{leaf_id}/')
        reason = closed_reason(info)
        if reason:
            row.update(status='skipped', reason=reason)
            self.counts['videos_skipped'] += 1
            return
        media = info.get('content_info', {}).get('media') or {}
        duration = video_duration(progress, media, client.cid, leaf_id)
        if not math.isfinite(duration) or not 0 < duration <= self.config['max_video_seconds'] or not media.get('ccid') or not info.get('sku_id'):
            row.update(reason='时长或媒体信息无效，未发送心跳')
            self.counts['pending'] += 1
            LOG.warning('未处理 %s：媒体信息无效', title)
            return
        for attempt in range(1, self.config['max_rounds'] + 1):
            LOG.info('视频 %s (%s)，时长 %.1fs，第 %d 轮', title, leaf_id, duration, attempt)
            events = video_events(user_id, course_id, client.cid, leaf_id, info, duration,
                                  self.config['heartbeat_interval'])
            # 限制请求大小；同一视频保留事件顺序。
            for offset in range(0, len(events), 200):
                client.heartbeat(events[offset:offset + 200])
            for delay in (3, 7, 15):
                pause(delay)
                progress = client.progress(user_id, course_id, leaf_id)
                if completed(progress):
                    row.update(status='completed', verified_at=time.strftime('%Y-%m-%d %H:%M:%S'))
                    self.counts['completed'] += 1
                    self.update()
                    LOG.info('服务器确认完成：%s', title)
                    return
        row['reason'] = '达到重试上限，服务器未确认完成'
        self.counts['pending'] += 1
        self.update()
        LOG.warning('未确认完成：%s', title)


def process_identity(pid):
    """读取 Linux 进程启动标识，避免向复用 PID 的进程发送信号。"""
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return fields[19]
    except (OSError, IndexError):
        return None


def active_pid():
    """返回经启动时间与命令行共同确认的任务 PID。"""
    try:
        record = json.loads((RUNTIME / 'pid.json').read_text())
        pid = int(record['pid'])
        command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        if pid > 1 and process_identity(pid) == record['identity'] and os.fsencode(__file__) in command:
            return pid
    except (OSError, ValueError, KeyError):
        pass
    return None


def run_worker(args):
    """获得独占锁后执行任务，保证失败与停止状态可见。"""
    with (RUNTIME / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise TaskError('已有扫描或后台任务在运行') from None
        save_json(RUNTIME / 'pid.json', {'pid': os.getpid(), 'identity': process_identity(os.getpid())})
        signal.signal(signal.SIGTERM, lambda *_: STOP.set())
        signal.signal(signal.SIGINT, lambda *_: STOP.set())
        runner = None
        try:
            runner = Runner(read_config(), args.classroom_id)
            return runner.execute(write=args.command == 'run')
        except Stopped:
            if runner:
                runner.update(status='stopped')
            LOG.info('任务已停止')
            return 130
        except Exception as exc:
            message = str(exc) if isinstance(exc, TaskError) else f'数据格式或运行异常：{type(exc).__name__}'
            if runner:
                runner.update(status='failed', error=message)
            LOG.error('%s', message)
            return 1
        finally:
            (RUNTIME / 'pid.json').unlink(missing_ok=True)


def control(args):
    """管理后台任务的启动、查询和停止。"""
    if args.command == 'logs':
        path = RUNTIME / 'task.log'
        if path.exists():
            with path.open() as file:
                print(''.join(deque(file, maxlen=40)), end='')
        else:
            print('暂无日志')
        return 0
    # 串行化 start/stop，防止启动握手期间产生多个进程。
    with (RUNTIME / 'control.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        pid = active_pid()
        if args.command == 'status':
            print(f'后台进程：{pid}' if pid else '后台进程：未运行')
            path = RUNTIME / 'state.json'
            if path.exists():
                data = json.loads(path.read_text())
                if data.get('status') == 'failed':
                    print('上次任务执行失败（不是 status 命令报错）：')
                print(json.dumps({k: v for k, v in data.items() if k not in ('courses', 'videos')}, ensure_ascii=False, indent=2))
                if not pid and data.get('status') in ('initializing', 'running', 'scanning'):
                    print('注意：进程已退出，以上为中断前状态；重新启动会复查服务器进度。')
            return 0
        if args.command == 'stop':
            if not pid:
                print('没有正在运行的任务')
                return 0
            os.kill(pid, signal.SIGTERM)
            for _ in range(90):
                if active_pid() != pid:
                    print('任务已停止')
                    return 0
                time.sleep(.5)
            raise TaskError('停止请求已发送，但进程尚未退出；请检查 status')
        if pid:
            print(f'已有任务在运行，PID={pid}')
            return 0
        command = [sys.executable, str(Path(__file__).resolve()), 'run']
        if args.classroom_id:
            command += ['--classroom-id', str(args.classroom_id)]
        with (RUNTIME / 'task.log').open('a') as log:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     start_new_session=True, close_fds=True, cwd=ROOT)
        for _ in range(50):
            if child.poll() is not None:
                raise TaskError('后台任务提前退出，请运行 ./ykt.sh logs 查看原因')
            if active_pid() == child.pid:
                print(f'后台任务已启动，PID={child.pid}；日志：{RUNTIME / "task.log"}')
                return 0
            time.sleep(.1)
        raise TaskError('启动握手超时，请检查 status 和 logs')


def main():
    """解析命令行并运行任务或进程管理操作。"""
    os.umask(0o077)
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['scan', 'run', 'start', 'status', 'stop', 'logs'])
    parser.add_argument('--classroom-id', type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        return run_worker(args) if args.command in ('scan', 'run') else control(args)
    except (TaskError, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, TaskError) else f'本地运行错误：{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

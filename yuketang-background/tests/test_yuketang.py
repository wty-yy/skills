"""测试后台脚本的边界行为，不访问真实账号。

Quick Start:
    .venv/bin/python -m unittest discover -s tests -v
"""

import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('ykt', Path(__file__).resolve().parents[1] / 'scripts/yuketang.py')
ykt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ykt)


class TaskTests(unittest.TestCase):
    """验证进度、请求与进程管理的不变量。"""

    def setUp(self):
        """为每个测试隔离状态目录。"""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = patch.object(ykt, 'RUNTIME', Path(self.temp.name))
        self.runtime.start()
        self.addCleanup(self.runtime.stop)
        self.config = ykt.read_config()

    def test_access_windows_and_parent_lock(self):
        """锁定父章节与过期节点不能被当作可处理视频。"""
        self.assertTrue(ykt.closed_reason({'start_time': 200_000_000_000}, now=100))
        self.assertTrue(ykt.closed_reason({'class_end': 10}, now=100))
        self.assertFalse(ykt.closed_reason({'start_time': 10, 'end_time': 0}, now=100))
        tree = [{'is_locked': True, 'section_leaf_list': [{'leaf_list': [{'leaf_type': 0, 'id': 1}]}]}]
        self.assertTrue(list(ykt.collect_leaves(tree))[0][1])

    def test_events_cover_fractional_duration_without_future_time(self):
        """事件序号连续，末尾进度精确，时间戳不超出当前时刻。"""
        now = time.time()
        info = {'sku_id': 3, 'content_info': {'media': {'ccid': 'test'}}}
        for duration in (.2, 5, 12.5, 14400):
            events = ykt.video_events(1, 2, 3, 4, info, duration)
            self.assertEqual(events[-1]['cp'], duration)
            self.assertEqual([e['sq'] for e in events], list(range(1, len(events) + 1)))
            self.assertTrue(all(0 <= e['cp'] <= duration for e in events))
            self.assertLessEqual(events[-1]['ts'], int(now * 1000) + 100)
            self.assertEqual(sorted(e['ts'] for e in events), [e['ts'] for e in events])

    def test_completed_is_explicit(self):
        """字符串 false、空进度和请求成功不能代表完成。"""
        for value in ({}, None, {'completed': 'false'}, {'completed': False}, {'completed': '1'}):
            self.assertFalse(ykt.completed(value))
        self.assertTrue(ykt.completed({'completed': True}))
        self.assertTrue(ykt.completed({'completed': 1}))

    def test_duration_fallback_is_scoped_and_server_preferred(self):
        """核对记录只作用于指定班级视频，服务器有效时长优先。"""
        ykt.save_json(ykt.RUNTIME / 'video-durations.json', {'1:2': {'seconds': 491, 'source': '播放器 00:08:11'}})
        self.assertEqual(ykt.video_duration({}, {'duration': 0}, 1, 2), 491)
        self.assertEqual(ykt.video_duration({}, {'duration': 0}, 9, 2), 0)
        self.assertEqual(ykt.video_duration({'video_length': 100}, {}, 1, 2), 100)
        self.assertEqual(ykt.video_duration({'video_length': 'bad'}, {'duration': 30}, 1, 2), 30)

    def test_duration_fallback_requires_valid_evidence(self):
        """无来源、无效时长或错误结构不能用于上报。"""
        for entry in ({'seconds': 491}, {'seconds': -1, 'source': 'player'},
                      {'seconds': 'NaN', 'source': 'player'}, []):
            ykt.save_json(ykt.RUNTIME / 'video-durations.json', {'1:2': entry})
            with self.assertRaises(ykt.TaskError):
                ykt.video_duration({}, {}, 1, 2)

    def test_http_fails_closed(self):
        """重定向、限流和失败响应不触发重试或凭据转发。"""
        client = ykt.Client(self.config, {'sessionid': 'dummy', 'csrftoken': 'dummy'})
        self.addCleanup(client.session.close)
        with patch.object(ykt, 'pause'):
            for status, body in [(302, {}), (400, {}), (400, {'error_code': 999}), (401, {}), (429, {}), (200, {'code': 1}),
                                 (200, {'success': False}), (200, {})]:
                response = Mock(status_code=status)
                response.json.return_value = body
                with patch.object(client.session, 'request', return_value=response) as request:
                    with self.assertRaises(ykt.TaskError):
                        client.request('GET', '/test')
                    self.assertFalse(request.call_args.kwargs['allow_redirects'])
                    self.assertEqual(request.call_count, 1)

    def test_unconfirmed_video_remains_pending(self):
        """心跳成功但服务器未确认时，不记作完成。"""
        runner = ykt.Runner(self.config)
        client = Mock(cid=1)
        client.progress.return_value = {}
        client.request.return_value = {'sku_id': 3, 'content_info': {'media': {'duration': 5, 'ccid': 'test'}}}
        with patch.object(ykt, 'pause'):
            runner.process_video(client, 1, 2, {'id': 4, 'name': 'test'}, '', True)
        self.assertEqual(runner.counts['completed'], 0)
        self.assertEqual(runner.counts['pending'], 1)
        self.assertEqual(client.heartbeat.call_count, self.config['max_rounds'])

    def test_empty_heartbeat_ack_is_not_completion(self):
        """仅心跳接口接受空确认，完成判断仍依赖进度接口。"""
        client = ykt.Client(self.config, {'sessionid': 'dummy', 'csrftoken': 'dummy'})
        self.addCleanup(client.session.close)
        response = Mock(status_code=200)
        response.json.return_value = {}
        with patch.object(ykt, 'pause'), patch.object(client.session, 'request', return_value=response):
            ack = client.request('POST', '/video-log/heartbeat/', json={'heart_data': []})
            self.assertFalse(ykt.completed(ack))
            with self.assertRaises(ykt.TaskError):
                client.request('GET', '/video-log/get_video_watch_progress/')

    def test_existing_completed_video_does_not_submit(self):
        """已经完成的视频不会重复提交。"""
        runner = ykt.Runner(self.config)
        client = Mock(cid=1)
        client.progress.return_value = {'completed': True}
        runner.process_video(client, 1, 2, {'id': 4}, '', True)
        client.heartbeat.assert_not_called()
        self.assertEqual(runner.counts['already_complete'], 1)

    def test_reused_pid_is_not_active(self):
        """启动时间不符时不将 PID 视作本任务。"""
        pid = ykt.os.getpid()
        ykt.save_json(ykt.RUNTIME / 'pid.json', {'pid': pid, 'identity': 'wrong'})
        self.assertIsNone(ykt.active_pid())

    def test_unavailable_course_does_not_abort_other_courses(self):
        """主账号有效时跳过无用户信息的课程，并继续处理后续课程。"""
        client = Mock()
        courses = [{'classroom_id': 1}, {'classroom_id': 2}]
        client.request.side_effect = [
            {'id': 9}, {'list': courses}, ykt.ApiError('errcode', 400001, '/classroom'),
            {'id': 9}, {'course_sign': ''},
        ]
        runner = ykt.Runner(self.config)
        with patch.object(ykt, 'Client', return_value=client), patch.object(ykt, 'chrome_auth', return_value={}):
            result = runner.execute(write=True)
        self.assertEqual(result, 2)
        self.assertEqual(runner.state['status'], 'finished_with_pending')
        self.assertEqual(runner.counts['courses_unavailable'], 1)
        self.assertEqual(runner.counts['courses_skipped'], 1)
        self.assertEqual(client.request.call_count, 5)

    def test_invalid_session_still_stops_on_course_error(self):
        """课程错误后的登录复查失败时立即停止，不吞掉鉴权失败。"""
        for validation in (ykt.TaskError('登录失效'), {'id': 99}):
            with self.subTest(validation=type(validation).__name__):
                client = Mock()
                client.request.side_effect = [
                    {'id': 9}, {'list': [{'classroom_id': 1}]},
                    ykt.ApiError('errcode', 400001, '/classroom'), validation,
                ]
                runner = ykt.Runner(self.config)
                with patch.object(ykt, 'Client', return_value=client), patch.object(ykt, 'chrome_auth', return_value={}):
                    with self.assertRaises(ykt.TaskError):
                        runner.execute(write=True)
                self.assertEqual(runner.counts['courses_unavailable'], 0)

    def test_http_400_purchase_error_preserves_business_code(self):
        """保留明确的无学习权限错误码，不将其当作通用 HTTP 故障。"""
        client = ykt.Client(self.config, {'sessionid': 'dummy', 'csrftoken': 'dummy'})
        self.addCleanup(client.session.close)
        response = Mock(status_code=400)
        response.json.return_value = {'success': False, 'error_code': 80019}
        with patch.object(ykt, 'pause'), patch.object(client.session, 'request', return_value=response):
            with self.assertRaises(ykt.ApiError) as caught:
                client.request('GET', '/mooc-api/v1/lms/learn/course/chapter')
        self.assertEqual(caught.exception.code, 80019)

    def test_unentitled_course_continues_and_preserves_zero_university(self):
        """无学习权限的章节不阻断后续课程，学校 ID 为零时不替换。"""
        client = Mock()
        courses = [{'classroom_id': 1, 'course': {'university_id': 0}}, {'classroom_id': 2}]
        client.request.side_effect = [
            {'id': 9}, {'list': courses}, {'course_sign': 'sign'},
            ykt.ApiError('error_code', 80019, '/chapter'), {'course_sign': ''},
        ]
        runner = ykt.Runner(self.config)
        with patch.object(ykt, 'Client', return_value=client), patch.object(ykt, 'chrome_auth', return_value={}):
            self.assertEqual(runner.execute(write=True), 2)
        self.assertEqual(runner.state['status'], 'finished_with_pending')
        self.assertEqual(runner.counts['courses_unavailable'], 1)
        self.assertEqual(runner.counts['courses_skipped'], 1)
        client.context.assert_any_call(1, 0)
        self.assertEqual(client.request.call_args_list[3].kwargs['params']['uv_id'], 0)


if __name__ == '__main__':
    unittest.main()

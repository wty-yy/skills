import contextlib
import datetime as dt
import importlib.util
import io
import ipaddress
import socket
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.server_ip = socket.gethostbyname('localhost')
        (self.root / 'settings.json').write_text(json.dumps({
            'token': 'test-token', 'server_ip': self.server_ip,
            'api_credentials': str(self.root / 'api.json')}))
        (self.root / 'api.json').write_text(json.dumps({'key': 'SECRET_KEY', 'hash': 'SECRET_HASH'}))
        (self.root / 'clash.yaml').write_text('proxies: []\n')
        self.environment = patch.dict(os.environ, {
            'RACKNERD_SUB_CONFIG': str(self.root), 'RACKNERD_SUB_DATA': str(self.root)})
        self.environment.start()
        spec = importlib.util.spec_from_file_location('subscription_under_test',
                                                     Path(__file__).with_name('subscription_server.py'))
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    @contextlib.contextmanager
    def http_server(self):
        server = ThreadingHTTPServer(('localhost', 0), self.module.SubscriptionHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f'http://localhost:{server.server_port}'
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def api_result(self, **updates):
        value = {'status': 'success', 'ipaddress': self.server_ip, 'bw': '10000,1200,8800,12'}
        value.update(updates)
        return io.BytesIO(json.dumps(value).encode())

    def test_download_headers_and_no_api_credentials(self):
        with patch.object(self.module, 'urlopen', return_value=self.api_result()) as provider:
            with self.http_server() as base:
                with urlopen(base + '/sub/test-token/clash.yaml', timeout=3) as response:
                    content = response.read()
                    self.assertEqual(response.headers['Subscription-Userinfo'],
                                     'upload=0; download=1200; total=10000')
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.assertEqual(content, b'proxies: []\n')
                    self.assertNotIn(b'SECRET', content)
            request = provider.call_args.args[0]
            self.assertNotIn('SECRET', request.full_url)
            self.assertIn(b'action=info', request.data)

    def test_unknown_token_does_not_query_provider(self):
        with patch.object(self.module, 'urlopen') as provider, self.http_server() as base:
            with self.assertRaises(HTTPError) as raised:
                urlopen(base + '/sub/wrong-token/clash.yaml', timeout=3)
            self.assertEqual(raised.exception.code, 404)
            provider.assert_not_called()

    def test_expiry_in_get_and_head(self):
        expiry = int(dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc).timestamp())
        self.module.expires_at = expiry
        with patch.object(self.module, 'urlopen', return_value=self.api_result()):
            with self.http_server() as base:
                for method in ['GET', 'HEAD']:
                    with self.subTest(method=method):
                        request = Request(base + '/sub/test-token/clash.yaml', method=method)
                        with urlopen(request, timeout=3) as response:
                            self.assertEqual(response.headers['Subscription-Userinfo'],
                                             f'upload=0; download=1200; total=10000; expire={expiry}')
                            expected = b'' if method == 'HEAD' else b'proxies: []\n'
                            self.assertEqual(response.read(), expected)

    def test_expiry_settings_validation(self):
        path = self.root / 'settings.json'
        settings = json.loads(path.read_text())
        for value in [None, 1893456000, 0, -1, True, 1.5, '1893456000']:
            with self.subTest(expires_at=value):
                settings['expires_at'] = value
                path.write_text(json.dumps(settings))
                spec = importlib.util.spec_from_file_location(
                    'subscription_expiry_test', Path(__file__).with_name('subscription_server.py'))
                module = importlib.util.module_from_spec(spec)
                if value is None or (type(value) is int and value > 0):
                    spec.loader.exec_module(module)
                    self.assertEqual(module.expires_at, value)
                else:
                    with self.assertRaisesRegex(ValueError, 'expires_at'):
                        spec.loader.exec_module(module)

    def test_provider_error_with_http_200_is_not_zero_usage(self):
        with patch.object(self.module, 'urlopen', return_value=self.api_result(status='error')):
            with self.assertRaises(RuntimeError):
                self.module.current_usage()
            self.assertFalse((self.root / 'usage.json').exists())

    def test_recent_stale_cache_and_month_boundary(self):
        self.module.last_usage = {'total': 10000, 'used': 1200, 'remaining': 8800,
                                  'checked_at': time.time() - 60,
                                  'month': self.module.month_key()}
        with patch.object(self.module, 'urlopen', side_effect=TimeoutError):
            usage, state = self.module.current_usage()
            self.assertEqual(state, 'stale')
            self.assertEqual(usage['used'], 1200)
            self.module.last_usage['month'] = '2000-01'
            with self.assertRaises(RuntimeError):
                self.module.current_usage()

    def test_wrong_vps_is_rejected(self):
        with patch.object(self.module, 'urlopen', return_value=self.api_result(ipaddress=str(ipaddress.IPv4Address(int(ipaddress.IPv4Address(self.server_ip)) ^ 1)))):
            with self.assertRaises(RuntimeError):
                self.module.current_usage()


if __name__ == '__main__':
    unittest.main()

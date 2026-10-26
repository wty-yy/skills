import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('cf_push', Path(__file__).resolve().parents[1] / 'deploy/cf-push.py')
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)


class PublishTests(unittest.TestCase):
    def test_origin_uses_generated_loopback_port(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/deployment.json').write_text(json.dumps({'port': 18420}))
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'public snapshot'
            response.__enter__.return_value.headers = {'content-type': 'application/json'}
            with patch.object(push, 'ROOT', root), patch.object(push, 'urlopen', return_value=response) as request:
                body, headers = push.read_origin('/api/public/stats')
            request.assert_called_once_with('http://127.0.0.1:18420/api/public/stats', timeout=25)
            self.assertEqual(body, b'public snapshot')
            self.assertEqual(headers['content-type'], 'application/json')

    def test_repeated_push_updates_only_snapshot_and_keeps_failed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin = lambda route: (b'{"users":[]}' if route in push.PUBLIC_APIS else b'public website', {'content-type': 'text/plain'})
            with patch.object(push, 'ROOT', root), patch.object(push, 'read_origin', origin), patch.dict(push.os.environ, {'CF_KV_NAMESPACE_ID': 'isolated-namespace'}), patch.object(push, 'put') as put:
                push.main()
                self.assertEqual(put.call_count, 9)
                first_state = (root / 'data/cf-push-state.json').read_bytes()
                put.reset_mock()
                push.main()
                self.assertEqual([call.args[0] for call in put.call_args_list], ['snapshot'])
                snapshot = json.loads(put.call_args.args[1])
                self.assertEqual(set(snapshot['responses']), set(push.PUBLIC_APIS))
                saved = (root / 'data/cf-push-state.json').read_bytes()
                put.side_effect = RuntimeError('network failure')
                with self.assertRaises(RuntimeError):
                    push.main()
                self.assertEqual((root / 'data/cf-push-state.json').read_bytes(), saved)
                self.assertIn(b'isolated-namespace', first_state)

    def test_private_fields_abort_before_any_cloudflare_write(self):
        with patch.object(push, 'read_origin', return_value=(b'{"users":[{"token":"private"}]}', {})), patch.object(push, 'put') as put:
            with self.assertRaisesRegex(ValueError, 'Private field'):
                push.main()
            put.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'credential'):
            push.assert_public({'name': 'th_' + 'x' * 43})


if __name__ == '__main__':
    unittest.main()

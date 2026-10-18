import argparse
import datetime as dt
import hmac
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import ssl
import threading
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


CONFIG_DIR = Path(os.environ.get('RACKNERD_SUB_CONFIG', '/etc/racknerd-subscription'))
DATA_DIR = Path(os.environ.get('RACKNERD_SUB_DATA', '/var/lib/racknerd-subscription'))
API_URL = 'https://ctrl.racknerd.com/api/client/command.php'
settings = json.loads((CONFIG_DIR / 'settings.json').read_text())
settings['server_ip'] = str(ipaddress.IPv4Address(settings['server_ip']))
expires_at = settings.get('expires_at')
if expires_at is not None and (type(expires_at) is not int or expires_at <= 0):
    raise ValueError('expires_at must be a positive Unix timestamp in seconds')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
usage_lock = threading.Lock()
last_usage = None


def month_key():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')


def save_usage(usage):
    temporary = DATA_DIR / 'usage.tmp'
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(usage, handle)
    os.replace(temporary, DATA_DIR / 'usage.json')


def current_usage():
    global last_usage
    with usage_lock:
        now = time.time()
        if last_usage is None:
            try:
                last_usage = json.loads((DATA_DIR / 'usage.json').read_text())
            except (OSError, ValueError):
                pass
        same_month = last_usage and last_usage.get('month') == month_key()
        if same_month and now - last_usage['checked_at'] < 15:
            return last_usage, 'recent'
        try:
            credentials = json.loads(Path(settings['api_credentials']).read_text())
            payload = urlencode({**credentials, 'action': 'info', 'bw': '1',
                                 'rdtype': 'json'}).encode()
            request = Request(API_URL, data=payload, method='POST', headers={
                'User-Agent': 'curl/8.5.0', 'Accept': 'application/json'})
            with urlopen(request, timeout=15) as response:
                result = json.load(response)
            if result.get('status') != 'success':
                raise ValueError('RackNerd API rejected the usage request')
            if result.get('ipaddress') != settings['server_ip']:
                raise ValueError('RackNerd API returned a different VPS')
            total, used, remaining, _ = result['bw'].split(',')
            total, used, remaining = int(total), int(used), int(remaining)
            if min(total, used, remaining) < 0 or total <= 0:
                raise ValueError('Invalid bandwidth counters')
            usage = {'total': total, 'used': used, 'remaining': remaining,
                     'checked_at': int(now), 'month': month_key()}
            save_usage(usage)
            last_usage = usage
            return usage, 'live'
        except Exception as error:
            logging.warning('Usage refresh failed: %s', type(error).__name__)
            if same_month and now - last_usage['checked_at'] <= 3600:
                return last_usage, 'stale'
            raise RuntimeError('Provider usage temporarily unavailable') from None


class SubscriptionHandler(BaseHTTPRequestHandler):
    server_version = 'Subscription'
    sys_version = ''

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.serve_subscription(False)

    def do_HEAD(self):
        self.serve_subscription(True)

    def serve_subscription(self, head_only):
        expected = '/sub/' + settings['token'] + '/clash.yaml'
        if not hmac.compare_digest(urlsplit(self.path).path.encode(), expected.encode()):
            self.send_error(404)
            return
        try:
            usage, source = current_usage()
            content = (CONFIG_DIR / 'clash.yaml').read_bytes()
        except (RuntimeError, OSError):
            self.send_error(503, 'Subscription data temporarily unavailable')
            return
        # RackNerd exposes combined billable traffic, not separate RX/TX.
        # Store that total under download so clients sum upload+download correctly.
        self.send_response(200)
        self.send_header('Content-Type', 'application/yaml; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        profile_name = f'racknerd_{settings["server_ip"]}'
        self.send_header('Content-Disposition', f'attachment; filename={profile_name}.yaml')
        userinfo = f'upload=0; download={usage["used"]}; total={usage["total"]}'
        if expires_at is not None:
            userinfo += f'; expire={expires_at}'
        self.send_header('Subscription-Userinfo', userinfo)
        self.send_header('Profile-Title', profile_name)
        self.send_header('Profile-Update-Interval', '1')
        self.send_header('Cache-Control', 'private, no-store, no-cache, max-age=0')
        self.send_header('CDN-Cache-Control', 'no-store')
        self.send_header('Cloudflare-CDN-Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-RackNerd-Usage-Source', source)
        self.send_header('X-RackNerd-Usage-Checked-At', str(usage['checked_at']))
        self.send_header('X-RackNerd-Traffic-Reset', 'monthly-1st-00:00-UTC')
        if source == 'stale':
            self.send_header('Warning', '110 - "Provider usage is temporarily stale"')
        self.end_headers()
        if not head_only:
            self.wfile.write(content)


class SubscriptionServer(ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(20)
        try:
            return self.tls_context.wrap_socket(connection, server_side=True), address
        except Exception:
            connection.close()
            raise


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--usage', action='store_true', help='Query official bandwidth usage and exit')
    arguments = parser.parse_args()
    if arguments.usage:
        usage, source = current_usage()
        print(json.dumps({**usage, 'source': source}, indent=2))
        raise SystemExit(0)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(settings['certificate'], settings['private_key'])
    server = SubscriptionServer((settings.get('listen_host', ''), settings['port']), SubscriptionHandler)
    server.tls_context = context
    current_usage()
    logging.info('Subscription service ready on port %s', settings['port'])
    server.serve_forever()

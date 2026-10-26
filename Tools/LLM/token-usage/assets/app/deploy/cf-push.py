#!/usr/bin/env python3
"""Publish only the Hub's public responses and website assets to Cloudflare KV."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ['/', '/app.js', '/style.css', '/favicon.svg', '/figtree.woff2', '/figtree-OFL.txt']
PUBLIC_APIS = ['/api/public/stats', '/api/public/uploads', '/api/health']
HEADER_NAMES = ['content-type', 'content-security-policy', 'referrer-policy']


def digest(body):
    return hashlib.sha256(body).hexdigest()


def assert_public(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {'token', 'secret', 'authorization', 'apikey', 'sessiontext', 'projectpath', 'hostname', 'email'}:
                raise ValueError('Private field in public snapshot: ' + key)
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)
    elif isinstance(value, str) and re.search(r'\bth_[A-Za-z0-9_-]{35,}', value):
        raise ValueError('Hub credential in public snapshot')


def read_origin(route):
    # Fixed loopback source: neither public visitors nor a domain redirect trigger pulls.
    deployment = json.loads((ROOT / 'config/deployment.json').read_text())
    origin = f"http://127.0.0.1:{deployment.get('port', 17320)}"
    with urlopen(origin + route, timeout=25) as response:
        return response.read(), {key: response.headers[key] for key in HEADER_NAMES if response.headers.get(key)}


def put(key, body, metadata=None):
    account = os.environ['CF_ACCOUNT_ID']
    namespace = os.environ['CF_KV_NAMESPACE_ID']
    endpoint = f'https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{namespace}/values/{quote(key, safe="")}'
    headers = {'Authorization': 'Bearer ' + os.environ['CF_API_TOKEN']}
    if metadata is None:
        headers['Content-Type'] = 'application/json'
    else:
        boundary = 'hub-public-' + digest(body)[:24]
        metadata_bytes = json.dumps(metadata).encode()
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
                + metadata_bytes
                + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="value"; filename="asset"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + body + f'\r\n--{boundary}--\r\n'.encode())
        headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
    with urlopen(Request(endpoint, data=body, headers=headers, method='PUT'), timeout=45) as response:
        result = json.load(response)
    if not result.get('success'):
        raise RuntimeError('Cloudflare KV write failed: ' + json.dumps(result.get('errors')))


def main():
    published_at = datetime.now(timezone.utc).isoformat()
    responses = {}
    for route in PUBLIC_APIS:
        body, _ = read_origin(route)
        assert_public(json.loads(body))
        responses[route] = {'body': body.decode(), 'etag': '"' + digest(body)[:32] + '"'}
    snapshot = json.dumps({'publishedAt': published_at, 'responses': responses}, separators=(',', ':')).encode()
    if len(snapshot) > 24 * 1024 * 1024:
        raise ValueError('Public snapshot exceeds safe KV size')

    state_path = ROOT / 'data/cf-push-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    # A different namespace must receive a complete first publication.
    target = os.environ['CF_KV_NAMESPACE_ID']
    previous = state.get('assets', {}) if state.get('namespace') == target else {}
    assets = {}
    pending = []
    for route in ASSETS:
        body, headers = read_origin(route)
        fingerprint = digest(body)
        headers['etag'] = '"' + fingerprint[:32] + '"'
        headers['cache-control'] = 'public, max-age=60' if route == '/' else 'public, max-age=3600'
        keys = [route]
        if route in ['/app.js', '/style.css']:
            keys.insert(0, route + '?v=' + fingerprint[:12])
        for key in keys:
            assets[key] = fingerprint
            if previous.get(key) != fingerprint:
                pending.append((key, body, headers))
    # Versioned dependencies first, then HTML. Older immutable keys remain usable.
    pending.sort(key=lambda item: item[0] == '/')
    for key, body, headers in pending:
        put('asset:' + key, body, headers)
    put('snapshot', snapshot)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'namespace': target, 'assets': assets, 'publishedAt': published_at, 'snapshotBytes': len(snapshot)}))
    temporary.replace(state_path)
    print(f'Published public snapshot: {len(snapshot)} bytes, {len(pending)} changed assets, {published_at}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Public snapshot push failed: ' + str(error), file=sys.stderr)
        sys.exit(1)

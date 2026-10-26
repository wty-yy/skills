const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const deploymentFile = path.join(__dirname, '../config/deployment.json');
const deployment = fs.existsSync(deploymentFile) ? JSON.parse(fs.readFileSync(deploymentFile, 'utf8')) : {};
const publicUrl = new URL(deployment.publicUrl || 'https://usage.example.com');
publicUrl.protocol = 'https:';
const TEST_ORIGIN = publicUrl.origin;

async function setup(t) {
  const worker = (await import('../deploy/cf-worker.mjs')).default;
  const requests = [], reads = [], cache = new Map(), pending = [];
  const originalFetch = global.fetch, originalCaches = global.caches;
  global.fetch = async request => {
    requests.push(request);
    return new Response('origin', { headers: { 'cache-control': 'public, max-age=9999' } });
  };
  global.caches = { default: {
    async match(key) { return cache.get(key.url)?.clone(); },
    async put(key, response) { cache.set(key.url, response.clone()); }
  } };
  t.after(() => { global.fetch = originalFetch; global.caches = originalCaches; });
  const snapshot = { publishedAt: '2026-10-25T12:00:00Z', responses: Object.fromEntries(
    ['/api/public/stats', '/api/public/uploads', '/api/health'].map(route => [route, { body: JSON.stringify({ route }), etag: '"published"' }])
  ) };
  const env = { HUB_PUBLIC: {
    async get(key) { reads.push(key); return snapshot; },
    async getWithMetadata(key) {
      reads.push(key);
      return { value: new TextEncoder().encode('website'), metadata: { 'content-type': 'text/html', etag: '"asset"' } };
    }
  } };
  const run = async (route, options) => {
    const response = await worker.fetch(new Request(TEST_ORIGIN + route, options), env, { waitUntil(value) { pending.push(value); } });
    await Promise.all(pending);
    return response;
  };
  return { run, env, reads, requests, cache };
}

test('public page and both APIs stay at Cloudflare despite cache-busting requests', async t => {
  const { run, requests, reads } = await setup(t);
  for (const route of ['/', '/api/public/stats', '/api/public/uploads', '/api/health']) {
    assert.equal((await run(route + '?random=1')).status, 200);
    const response = await run(route + '?random=2', { headers: { 'cache-control': 'no-cache', authorization: 'Bearer ignored' } });
    assert.equal(response.headers.get('x-hub-cache'), 'HIT');
    assert.equal(response.headers.get('x-hub-source'), 'cloudflare-kv');
  }
  assert.equal(reads.length, 4);
  assert.equal(requests.length, 0);
});

test('snapshot errors, missing assets and unknown paths never fall back to VPS', async t => {
  const { run, env, requests } = await setup(t);
  env.HUB_PUBLIC.get = async () => { throw new Error('KV unavailable'); };
  env.HUB_PUBLIC.getWithMetadata = async () => ({ value: null });
  assert.equal((await run('/api/public/stats')).status, 503);
  assert.equal((await run('/app.js?v=not-published')).status, 503);
  assert.equal((await run('/config/users.json')).status, 404);
  assert.equal((await run('/api/public/uploads', { method: 'POST' })).status, 405);
  assert.equal(requests.length, 0);
});

test('old origin cache entries are replaced with the published KV assets', async t => {
  const { run, cache, reads, requests } = await setup(t);
  cache.set(TEST_ORIGIN + '/app.js?v=old', new Response('old origin file'));
  const response = await run('/app.js?v=old');
  assert.equal(await response.text(), 'website');
  assert.equal(response.headers.get('x-hub-source'), 'cloudflare-kv');
  assert.ok(reads.includes('asset:/app.js?v=old'));
  assert.equal(requests.length, 0);
});

test('private uploads retain method, body and credentials, with no caching', async t => {
  const { run, requests, reads } = await setup(t);
  const response = await run('/api/ingest', { method: 'POST', headers: { authorization: 'Bearer example' }, body: 'payload' });
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(await response.text(), 'origin');
  assert.equal(requests[0].method, 'POST');
  assert.equal(requests[0].headers.get('authorization'), 'Bearer example');
  assert.equal(await requests[0].text(), 'payload');
  assert.equal((await run('/api/stats')).status, 401);
  assert.equal(requests.length, 1);
  assert.equal(reads.length, 0);
});

test('conditional requests and HEAD have no body, asset versions have distinct cache keys', async t => {
  const { run, reads } = await setup(t);
  const first = await run('/api/public/stats');
  assert.equal((await run('/api/public/stats', { headers: { 'if-none-match': 'W/' + first.headers.get('etag') } })).status, 304);
  assert.equal(await (await run('/', { method: 'HEAD' })).text(), '');
  assert.match((await run('/app.js?v=aaaa')).headers.get('cache-control'), /immutable/);
  await run('/app.js?v=bbbb');
  assert.ok(reads.includes('asset:/app.js?v=aaaa'));
  assert.ok(reads.includes('asset:/app.js?v=bbbb'));
});

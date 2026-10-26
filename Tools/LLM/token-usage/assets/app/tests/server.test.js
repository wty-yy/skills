'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createApp } = require('../src/server');

const users = [
  { id: 'user-a', name: '用户 A', token: 'test-a-01234567890123456789012345' },
  { id: 'user-b', name: '用户 B', token: 'test-b-01234567890123456789012345' }
];

function payload(deviceId, count, historyTokens = count) {
  const date = new Date().toISOString().slice(0, 10);
  const period = { totalTokens: count, costUsd: count / 1000000, clients: { codex: count }, models: { 'test-model': count },
    sessions: { 'private-session': { client: 'codex', sessionId: 'private-session', totalTokens: count, projectLabel: 'private-project', projectId: '/private/folder' } } };
  return { deviceId, hostname: 'private-hostname', platform: 'linux-x64', updatedAt: new Date().toISOString(),
    today: period, month: period, allTime: period, historyAvailable: true,
    limits: { providers: [{ provider: 'codex', accountEmail: 'private@example.com', accountKey: 'private-account-key' }] },
    history: { daily: [{ date, tokens: historyTokens, cost: 0, perClient: { codex: { tokens: historyTokens, cost: 0 } }, perModel: {} }],
      monthly: [{ month: date.slice(0, 7), tokens: historyTokens, cost: 0, perClient: {}, perModel: {} }] } };
}

async function fixture(t, options = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'token-usage-test-'));
  const app = await createApp({ ...options, users, dataDir: dir });
  await app.start(0);
  const url = `http://127.0.0.1:${app.server.address().port}`;
  t.after(() => app.stop());
  const request = (route, user, body, method = body ? 'POST' : 'GET') => fetch(url + route, {
    method, headers: { ...(user ? { Authorization: `Bearer ${user.token}` } : {}), 'content-type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
  return { app, request, dir };
}

test('daily upload budget is shared by every user and rejects before ingesting', async (t) => {
  const record = payload('laptop', 100);
  const bytes = Buffer.byteLength(JSON.stringify(record));
  const { request, app } = await fixture(t, { dailyUploadLimitBytes: bytes * 2 - 1 });
  assert.equal((await request('/api/ingest', users[0], record)).status, 200);
  const blocked = await request('/api/ingest', users[1], record);
  assert.equal(blocked.status, 429);
  assert.equal((await blocked.json()).error, 'daily_upload_limit');
  assert.ok(Number(blocked.headers.get('retry-after')) > 0);
  assert.equal(app.hubs.get('user-b').getDevices().length, 0);
  assert.equal((await request('/api/ingest', users[0], record)).status, 429);
  const traffic = await (await request('/api/public/uploads')).json();
  assert.equal(traffic.todayBytes, bytes);
  assert.equal(traffic.users[0].totalBytes, bytes);
  assert.equal(traffic.users[1].totalBytes, 0);
  assert.equal((await request('/api/health')).status, 200);
  assert.equal((await request('/api/public/stats')).status, 200);
});

test('upload budget survives restart and resets at Shanghai midnight', async (t) => {
  const record = payload('laptop', 100);
  const bytes = Buffer.byteLength(JSON.stringify(record));
  let now = Date.parse('2026-10-25T15:59:59Z');
  const options = { dailyUploadLimitBytes: bytes, now: () => now };
  const { request, app, dir } = await fixture(t, options);
  assert.equal((await request('/api/ingest', users[0], record)).status, 200);
  const copy = fs.mkdtempSync(path.join(os.tmpdir(), 'token-budget-restore-'));
  app.archive.db.prepare('VACUUM INTO ?').run(path.join(copy, 'history.sqlite'));
  const restored = await createApp({ ...options, users, dataDir: copy });
  await restored.start(0);
  t.after(() => restored.stop());
  const base = `http://127.0.0.1:${restored.server.address().port}`;
  const upload = () => fetch(base + '/api/ingest', { method: 'POST', headers: { Authorization: `Bearer ${users[0].token}`, 'content-type': 'application/json' }, body: JSON.stringify(record) });
  assert.equal((await upload()).status, 429);
  now += 1000;
  assert.equal((await upload()).status, 200);
  assert.equal((await upload()).status, 429);
});

test('chunked uploads charge actual bytes and invalid uploads consume the budget', async (t) => {
  const http = require('node:http');
  const { app } = await fixture(t, { dailyUploadLimitBytes: 2 * 1024 * 1024 });
  const body = '{invalid json}';
  const send = () => new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: app.server.address().port, path: '/api/ingest', method: 'POST', headers: { Authorization: `Bearer ${users[0].token}`, 'content-type': 'application/json', 'transfer-encoding': 'chunked' } }, (res) => { res.resume(); res.on('end', () => resolve(res.statusCode)); });
    req.on('error', reject); req.write(body); req.end();
  });
  assert.equal(await send(), 400);
  const usage = app.archive.db.prepare('SELECT sum(bytes) AS bytes FROM upload_usage').get();
  assert.equal(usage.bytes, Buffer.byteLength(body));
  assert.equal(await send(), 400);
  assert.equal(app.archive.db.prepare('SELECT sum(bytes) AS bytes FROM upload_usage').get().bytes, Buffer.byteLength(body) * 2);
});

test('same device IDs are isolated by user; repeated snapshots update without summing', async (t) => {
  const { request } = await fixture(t);
  for (const [user, id, tokens] of [[users[0], 'laptop', 100], [users[0], 'desktop', 200], [users[1], 'laptop', 900], [users[0], 'laptop', 150], [users[0], 'laptop', 150]]) {
    assert.equal((await request('/api/ingest', user, payload(id, tokens))).status, 200);
  }
  const a = await (await request('/api/stats', users[0])).json();
  const b = await (await request('/api/stats', users[1])).json();
  assert.equal(a.periods.allTime.totalTokens, 350);
  assert.equal(b.periods.allTime.totalTokens, 900);
  const shared = await (await request('/api/public/stats')).json();
  assert.equal(shared.periods.allTime.totalTokens, 1250);
  assert.equal(shared.history['user-a'].daily[0].tokens, 350);
});

test('public stats revalidate unchanged data while private APIs remain uncached', async (t) => {
  const { request } = await fixture(t);
  await request('/api/ingest', users[0], payload('cache-test', 100));
  const first = await request('/api/public/stats');
  const etag = first.headers.get('etag');
  assert.ok(etag);
  assert.match(first.headers.get('cache-control'), /public.*max-age=60/);
  await first.arrayBuffer();
  const cached = await fetch(first.url, { headers: { 'if-none-match': etag } });
  assert.equal(cached.status, 304);
  assert.equal((await cached.text()).length, 0);
  await request('/api/ingest', users[0], payload('cache-test', 200));
  const changed = await fetch(first.url, { headers: { 'if-none-match': etag } });
  assert.equal(changed.status, 200);
  assert.notEqual(changed.headers.get('etag'), etag);
  const privateStats = await request('/api/stats', users[0]);
  assert.equal(privateStats.headers.get('cache-control'), 'no-store');
  const html = await (await request('/')).text();
  const script = html.match(/\/app\.js\?v=[a-f0-9]+/)[0];
  assert.match((await request(script)).headers.get('cache-control'), /immutable/);
});

test('public responses expose only usage; private endpoints reject missing or wrong tokens', async (t) => {
  const { request } = await fixture(t);
  await request('/api/ingest', users[0], payload('secret-device-name', 100));
  const pub = JSON.stringify(await (await request('/api/public/stats')).json());
  for (const privateString of ['secret-device-name', 'private-hostname', 'private@example.com', 'private-account-key', 'private-session', 'private-project', '/private/folder', users[0].token]) assert.ok(!pub.includes(privateString), privateString);
  for (const route of ['/api/stats', '/api/devices', '/api/history', '/api/subscriptions']) {
    assert.equal((await request(route)).status, 401);
    assert.equal((await request(route, { token: 'incorrect-token' })).status, 401);
  }
  assert.equal((await request('/api/ingest', null, payload('bad', 5))).status, 401);
  assert.equal((await request('/config/users.json')).status, 404);
  assert.equal((await request('/src/server.js')).status, 404);
  assert.equal((await request('/api/health')).status, 200);
});

test('daily archive retains older rows, survives restart, and deletes only the owning user device', async (t) => {
  const { request, app, dir } = await fixture(t);
  const value = payload('laptop', 100);
  value.history.daily.push({ date: '2026-01-01', tokens: 33, perClient: {}, perModel: {} });
  await request('/api/ingest', users[0], value);
  await request('/api/ingest', users[1], payload('laptop', 900));
  await request('/api/ingest', users[0], payload('laptop', 200));
  assert.ok(app.archive.read('user-a').some((row) => row.date === '2026-01-01' && row.tokens === 33));
  const stored = JSON.parse(fs.readFileSync(path.join(dir, 'user-a.json'), 'utf8'));
  assert.equal(stored.devices.laptop.periods.allTime.totalTokens, 200);
  const secondDir = fs.mkdtempSync(path.join(os.tmpdir(), 'token-usage-restore-'));
  for (const name of ['user-a.json', 'user-b.json']) fs.copyFileSync(path.join(dir, name), path.join(secondDir, name));
  app.archive.db.prepare('VACUUM INTO ?').run(path.join(secondDir, 'history.sqlite'));
  const restored = await createApp({ users, dataDir: secondDir });
  try {
    assert.equal(restored.publicSnapshot().users[0].periods.allTime.totalTokens, 200);
    assert.ok(restored.archive.read('user-a').some((row) => row.date === '2026-01-01' && row.tokens === 33));
  } finally { await restored.stop(); }
  assert.equal((await request('/api/devices/laptop', users[0], null, 'DELETE')).status, 200);
  assert.equal(app.archive.read('user-a').length, 0);
  assert.equal(app.hubs.get('user-b').getDevices().length, 1);
});

test('invalid and oversized ingest are rejected without affecting totals', async (t) => {
  const { request, app } = await fixture(t);
  assert.equal((await request('/api/ingest', users[0], {})).status, 400);
  assert.equal((await request('/api/ingest', users[0], { deviceId: 'large', ignored: 'x'.repeat(1048577) })).status, 413);
  assert.equal(app.hubs.get('user-a').getDevices().length, 0);
});

test('uploaded device names are isolated, retained, renamed and restored without duplicating usage', async (t) => {
  const { request, app, dir } = await fixture(t);
  await request('/api/ingest', users[0], { ...payload('same-id', 100), displayName: '台式机 #1' });
  await request('/api/ingest', users[1], { ...payload('same-id', 200), displayName: '工作电脑' });
  await request('/api/ingest', users[0], payload('same-id', 100));
  let data = await (await request('/api/public/stats')).json();
  assert.equal(data.users[0].devices[0].name, '台式机 #1');
  assert.equal(data.users[1].devices[0].name, '工作电脑');
  await request('/api/ingest', users[0], { ...payload('same-id', 150), displayName: '新名称' });
  data = await (await request('/api/public/stats')).json();
  assert.equal(data.users[0].devices[0].name, '新名称');
  assert.equal(data.users[0].devices.length, 1);
  assert.equal(data.users[0].periods.allTime.totalTokens, 150);
  const restoredDir = fs.mkdtempSync(path.join(os.tmpdir(), 'token-device-names-'));
  for (const name of ['user-a.json', 'user-b.json', 'device-names.json']) fs.copyFileSync(path.join(dir, name), path.join(restoredDir, name));
  const restored = await createApp({ users, dataDir: restoredDir });
  try { assert.equal(restored.publicSnapshot().users[0].devices[0].name, '新名称'); } finally { await restored.stop(); }
  await request('/api/devices/same-id', users[0], null, 'DELETE');
  const names = JSON.parse(fs.readFileSync(path.join(dir, 'device-names.json'), 'utf8'));
  assert.ok(!Object.hasOwn(names, 'user-a\u0000same-id'));
  assert.equal(names['user-b\u0000same-id'], '工作电脑');
});

test('daily token components and messages survive archival without inventing missing input data', async (t) => {
  const { request } = await fixture(t);
  const record = payload('components', 100);
  Object.assign(record.history.daily[0], { messages: 3, cacheReadTokens: 60, outputTokens: 10, cacheWriteTokens: 5, tokenComponentsAvailable: true });
  Object.assign(record.history.daily[0].perClient.codex, { cacheReadTokens: 60, outputTokens: 10, cacheWriteTokens: 5 });
  record.history.daily[0].perModel = { model: { tokens: 100, cost: 0, cacheReadTokens: 60, outputTokens: 10, cacheWriteTokens: 5 } };
  Object.assign(record.allTime, { capabilities: { tokenComponents: true }, modelCacheReads: { 'test-model': 60 }, modelCacheWrites: { 'test-model': 5 }, modelOutputs: { 'test-model': 10 } });
  await request('/api/ingest', users[0], record);
  const data = await (await request('/api/public/stats')).json();
  const day = data.history['user-a'].daily[0];
  assert.equal(day.cacheReadTokens, 60);
  assert.equal(day.outputTokens, 10);
  assert.equal(day.messages, 3);
  assert.equal(day.unclassifiedTokens, 0);
  assert.equal(day.perModel.model.cacheReadTokens, 60);
  assert.equal(day.perModel.model.unclassifiedTokens, 0);
  assert.equal(data.users[0].periods.allTime.modelCacheReads['test-model'], 60);
});

test('HTML versions its scripts and stylesheet so cached resources cannot mix layouts', async (t) => {
  const { request } = await fixture(t);
  const html = await (await request('/')).text();
  for (const name of ['app.js', 'style.css']) {
    const match = html.match(new RegExp('/' + name.replace('.', '\\.') + '\\?v=[a-f0-9]+'));
    assert.ok(match, 'Missing resource version: ' + name);
    assert.equal((await request(match[0])).status, 200);
  }
});

test('public device histories stay separate across devices and users', async (t) => {
  const { request } = await fixture(t);
  await request('/api/ingest', users[0], { ...payload('laptop', 100), displayName: 'Laptop' });
  await request('/api/ingest', users[0], { ...payload('desktop', 200), displayName: 'Desktop' });
  await request('/api/ingest', users[1], { ...payload('laptop', 900), displayName: 'Other user' });
  const data = await (await request('/api/public/stats')).json();
  const a = data.users[0], b = data.users[1];
  assert.equal(a.devices.find((d) => d.name === 'Laptop').history.daily[0].tokens, 100);
  assert.equal(a.devices.find((d) => d.name === 'Desktop').history.daily[0].tokens, 200);
  assert.equal(b.devices[0].history.daily[0].tokens, 900);
  assert.notEqual(a.devices.find((d) => d.name === 'Laptop').id, b.devices[0].id);
  assert.equal(data.history['user-a'].daily[0].tokens, 300);
});

test('live upload totals charge every request, isolate users and hide private device IDs', async (t) => {
  const { request } = await fixture(t, { now: () => Date.parse('2026-10-25T12:00:00Z') });
  const a = { ...payload('private-device-id', 100), displayName: '笔记本 🌏' };
  const b = { ...payload('private-device-id', 900), displayName: 'Other laptop' };
  const aBytes = Buffer.byteLength(JSON.stringify(a));
  const bBytes = Buffer.byteLength(JSON.stringify(b));
  await request('/api/ingest', users[0], a);
  const first = await request('/api/public/uploads');
  assert.equal(first.headers.get('cache-control'), 'no-store');
  assert.equal((await first.json()).todayBytes, aBytes);
  await request('/api/ingest', users[0], a);
  await request('/api/ingest', users[1], b);
  const response = await request('/api/public/uploads');
  const raw = await response.text();
  const data = JSON.parse(raw);
  assert.equal(data.todayBytes, 2 * aBytes + bBytes);
  assert.equal(data.monthBytes, data.todayBytes);
  assert.equal(data.remainingBytes, data.dailyLimitBytes - data.todayBytes);
  assert.equal(data.users[0].totalBytes, 2 * aBytes);
  assert.equal(data.users[0].devices[0].monthBytes, 2 * aBytes);
  assert.equal(data.users[1].devices[0].monthBytes, bBytes);
  assert.equal(data.users[0].devices[0].name, '笔记本 🌏');
  const stats = await (await request('/api/public/stats')).json();
  assert.equal(data.users[0].devices[0].id, stats.users[0].devices[0].id);
  assert.notEqual(data.users[0].devices[0].id, data.users[1].devices[0].id);
  for (const secret of ['private-device-id', 'private-hostname', 'private@example.com', 'private-session', users[0].token]) assert.ok(!raw.includes(secret), secret);
  await request('/api/devices/private-device-id', users[0], null, 'DELETE');
  const deleted = await (await request('/api/public/uploads')).json();
  assert.equal(deleted.users[0].devices.length, 0);
  assert.equal(deleted.users[0].totalBytes, 2 * aBytes);
  assert.equal(deleted.monthBytes, data.monthBytes);
});

test('upload details survive restart, preserve legacy totals and roll over at Shanghai month boundary', async (t) => {
  let now = Date.parse('2026-10-31T15:59:59Z');
  const record = payload('laptop', 100);
  const bytes = Buffer.byteLength(JSON.stringify(record));
  const { app, request, dir } = await fixture(t, { now: () => now });
  app.archive.db.prepare('INSERT INTO upload_usage VALUES (?, ?)').run('2026-10-01', 1234);
  await request('/api/ingest', users[0], record);
  const before = await (await request('/api/public/uploads')).json();
  assert.equal(before.monthBytes, bytes + 1234);
  assert.equal(before.users[0].monthBytes, bytes);
  const copy = fs.mkdtempSync(path.join(os.tmpdir(), 'upload-details-restore-'));
  fs.copyFileSync(path.join(dir, 'user-a.json'), path.join(copy, 'user-a.json'));
  app.archive.db.prepare('VACUUM INTO ?').run(path.join(copy, 'history.sqlite'));
  now += 1000;
  const restored = await createApp({ users, dataDir: copy, now: () => now });
  await restored.start(0);
  t.after(() => restored.stop());
  const base = `http://127.0.0.1:${restored.server.address().port}`;
  const read = async () => (await fetch(base + '/api/public/uploads')).json();
  const rolled = await read();
  assert.equal(rolled.day, '2026-11-01');
  assert.equal(rolled.monthBytes, 0);
  assert.equal(rolled.todayBytes, 0);
  assert.equal(rolled.users[0].devices[0].monthBytes, 0);
  assert.equal(rolled.users[0].totalBytes, bytes);
  assert.equal(rolled.trackingSince, before.trackingSince);
  await fetch(base + '/api/ingest', { method: 'POST', headers: { Authorization: `Bearer ${users[0].token}` }, body: JSON.stringify(record) });
  const after = await read();
  assert.equal(after.monthBytes, bytes);
  assert.equal(after.users[0].devices[0].monthBytes, bytes);
  assert.equal(after.users[0].totalBytes, 2 * bytes);
  assert.equal(after.totalBytes, 2 * bytes + 1234);
});

test('chunked, invalid, aborted and rejected uploads report received bytes without assigning failed devices', async (t) => {
  const http = require('node:http');
  const { app, request } = await fixture(t, { dailyUploadLimitBytes: 10 * 1024 * 1024 });
  const body = JSON.stringify({ ...payload('laptop', 100), displayName: '工作电脑' });
  const send = (raw) => new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: app.server.address().port, path: '/api/ingest', method: 'POST', headers: { Authorization: `Bearer ${users[0].token}`, 'transfer-encoding': 'chunked' } }, (res) => { res.resume(); res.on('end', () => resolve(res.statusCode)); });
    req.on('error', reject); req.write(raw); req.end();
  });
  assert.deepEqual(await Promise.all([send(body), send(body), send('{invalid}')]), [200, 200, 400]);
  const data = await (await request('/api/public/uploads')).json();
  const validBytes = Buffer.byteLength(body) * 2;
  assert.equal(data.todayBytes, validBytes + Buffer.byteLength('{invalid}'));
  assert.equal(data.users[0].totalBytes, data.todayBytes);
  assert.equal(data.users[0].devices[0].monthBytes, validBytes);
  await request('/api/ingest', users[0], { deviceId: 'too-big', ignored: 'x'.repeat(1048577) });
  await request('/api/ingest', null, payload('unauthorized', 1));
  assert.equal((await (await request('/api/public/uploads')).json()).totalBytes, data.totalBytes);
  // Keep a request in flight so a query sees its reserved budget, then abort it.
  const partial = '{partial upload';
  const req = http.request({ host: '127.0.0.1', port: app.server.address().port, path: '/api/ingest', method: 'POST', headers: { Authorization: `Bearer ${users[0].token}`, 'transfer-encoding': 'chunked' } });
  req.on('error', () => {}); req.write(partial);
  let pending;
  for (let i = 0; i < 30; i++) {
    pending = await (await request('/api/public/uploads')).json();
    if (pending.todayBytes > data.todayBytes) break;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(pending.todayBytes, data.todayBytes + 1024 * 1024);
  req.destroy();
  let final;
  for (let i = 0; i < 30; i++) {
    final = await (await request('/api/public/uploads')).json();
    if (final.todayBytes === data.todayBytes + Buffer.byteLength(partial)) break;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(final.todayBytes, data.todayBytes + Buffer.byteLength(partial));
  assert.equal(final.users[0].totalBytes, final.todayBytes);
  assert.equal(final.users[0].devices[0].monthBytes, validBytes);
});

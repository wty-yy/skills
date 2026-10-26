'use strict';

const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const root = path.resolve(__dirname, '..');
  const { users } = JSON.parse(fs.readFileSync(path.join(root, 'config/users.json'), 'utf8'));
  const base = JSON.parse(fs.readFileSync(path.join(root, 'config/deployment.json'), 'utf8')).publicUrl;
  const request = (route, user, body) => fetch(base + route, {
    signal: AbortSignal.timeout(20000),
    method: body ? 'POST' : 'GET',
    headers: { ...(user ? { Authorization: `Bearer ${user.token}` } : {}), 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
  const response = await request('/api/public/stats');
  assert.equal(response.status, 200);
  const raw = await response.text();
  const data = JSON.parse(raw);
  assert.equal(data.users.length, users.length);
  const trafficResponse = await request('/api/public/uploads');
  assert.equal(trafficResponse.status, 200);
  if (trafficResponse.headers.get('x-hub-source') === 'cloudflare-kv') {
    assert.match(trafficResponse.headers.get('cache-control'), /^public,/);
    assert.equal(response.headers.get('x-hub-source'), 'cloudflare-kv');
    assert.ok(Date.now() - Date.parse(trafficResponse.headers.get('x-hub-published-at')) < 15 * 60_000);
  } else {
    assert.equal(trafficResponse.headers.get('cache-control'), 'no-store');
  }
  const trafficRaw = await trafficResponse.text();
  const traffic = JSON.parse(trafficRaw);
  assert.equal(traffic.users.length, users.length);
  assert.equal(traffic.dailyLimitBytes, 5_000_000_000);
  assert.equal(traffic.remainingBytes, Math.max(0, traffic.dailyLimitBytes - traffic.todayBytes));
  assert.ok(traffic.trackingSince);
  for (const user of users) {
    assert.ok(!raw.includes(user.token));
    assert.ok(!trafficRaw.includes(user.token));
    const publicDevices = new Set(data.users.find((person) => person.id === user.id).devices.map((device) => device.id));
    assert.ok(traffic.users.find((person) => person.id === user.id).devices.every((device) => publicDevices.has(device.id)));
    assert.equal((await request('/api/stats', user)).status, 200);
    assert.equal((await request('/api/ingest', user, {})).status, 400);
  }
  assert.equal((await request('/api/stats')).status, 401);
  assert.equal((await request('/api/ingest', { token: 'wrong-token' }, {})).status, 401);
  assert.equal((await request('/config/users.json')).status, 404);
  assert.equal((await request('/data/history.sqlite')).status, 404);
  console.log(`Public HTTPS, ${users.length} user tokens, protected routes and invalid upload: verified`);
  console.log('Live devices:', data.users.reduce((sum, user) => sum + user.devices.length, 0));
  console.log('Public upload traffic snapshot and anonymous device IDs: verified');
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });

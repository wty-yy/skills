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
  for (const user of users) {
    assert.ok(!raw.includes(user.token));
    assert.equal((await request('/api/stats', user)).status, 200);
    assert.equal((await request('/api/ingest', user, {})).status, 400);
  }
  assert.equal((await request('/api/stats')).status, 401);
  assert.equal((await request('/api/ingest', { token: 'wrong-token' }, {})).status, 401);
  assert.equal((await request('/config/users.json')).status, 404);
  assert.equal((await request('/data/history.sqlite')).status, 404);
  console.log('Public HTTPS, both user tokens, protected routes and invalid upload: verified');
  console.log('Live devices:', data.users.reduce((sum, user) => sum + user.devices.length, 0));
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });

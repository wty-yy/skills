'use strict';

const path = require('node:path');
const fs = require('node:fs');
const { spawn, spawnSync } = require('node:child_process');

require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });
const encodedName = fs.existsSync(path.join(__dirname, '.env'))
  ? fs.readFileSync(path.join(__dirname, '.env'), 'utf8').match(/^TOKEN_MONITOR_DEVICE_NAME=(.+)$/m)?.[1].trim() : '';
if (encodedName?.startsWith('"')) process.env.TOKEN_MONITOR_DEVICE_NAME = JSON.parse(encodedName);

if (require.main !== module) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (input, options = {}) => {
    if (process.env.TOKEN_MONITOR_DEVICE_NAME && options.method?.toUpperCase() === 'POST'
      && new URL(typeof input === 'string' || input instanceof URL ? input : input.url).pathname === '/api/ingest'
      && typeof options.body === 'string') {
      options = { ...options, body: JSON.stringify({ ...JSON.parse(options.body), displayName: process.env.TOKEN_MONITOR_DEVICE_NAME }) };
    }
    return originalFetch(input, options);
  };
} else {
const root = path.dirname(require.resolve('token-monitor/package.json'));
const prepared = spawnSync(process.execPath, [path.join(root, 'scripts/ensure-vendored-tokscale.js')], {
  cwd: root, env: process.env, stdio: ['ignore', 2, 2]
});
if (prepared.error || prepared.status !== 0) {
  console.error(prepared.error?.message || 'Unable to prepare the collector binary');
  process.exit(prepared.status || 1);
}
const child = spawn(process.execPath, ['--require', __filename, path.join(root, 'src/agent/agent.js'), ...process.argv.slice(2)], {
  cwd: root, env: process.env, stdio: 'inherit'
});
for (const signal of ['SIGTERM', 'SIGINT', 'SIGHUP']) process.on(signal, () => child.kill(signal));
child.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
}

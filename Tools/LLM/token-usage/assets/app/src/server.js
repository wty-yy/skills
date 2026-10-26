'use strict';

const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const https = require('node:https');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { createHub } = require('../vendor/token-monitor/src/hub/server');
const { currentHubBuild } = require('../vendor/token-monitor/src/shared/hubBuildIdentity');
const { readJsonBody, MAX_JSON_BODY_BYTES } = require('../vendor/token-monitor/src/shared/http');
const { readJson, writeJsonAtomic } = require('../vendor/token-monitor/src/shared/config');
const { wantsMinimalResponse } = require('../vendor/token-monitor/src/shared/hubProtocol');
const { publicUser, publicDeviceId, combinePeriods } = require('./public-data');
const { HistoryArchive } = require('./archive');

const ROOT = path.resolve(__dirname, '..');
const deploymentFile = path.join(ROOT, 'config/deployment.json');
const deployment = fs.existsSync(deploymentFile) ? JSON.parse(fs.readFileSync(deploymentFile, 'utf8')) : {};
const PUBLIC_URL = deployment.publicUrl || 'https://usage.example.com';
const TIME_ZONE = deployment.timeZone || 'Asia/Shanghai';
const STATIC_FILES = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']],
  ['/favicon.svg', ['favicon.svg', 'image/svg+xml']],
  ['/figtree.woff2', ['figtree.woff2', 'font/woff2']],
  ['/figtree-OFL.txt', ['figtree-OFL.txt', 'text/plain; charset=utf-8']]
]);

function json(res, status, value, cache = 'no-store') {
  const raw = Buffer.from(JSON.stringify(value));
  const compressed = /\bgzip\b/.test(res.req.headers['accept-encoding'] || '') && raw.length > 1024;
  const body = compressed ? zlib.gzipSync(raw, { level: 1 }) : raw;
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8', 'cache-control': cache,
    'content-length': body.length, 'x-content-type-options': 'nosniff',
    ...(compressed ? { 'content-encoding': 'gzip', vary: 'Accept-Encoding' } : {})
  });
  res.end(body);
}

function readConfig(filename) {
  const { users } = JSON.parse(fs.readFileSync(filename, 'utf8'));
  if (!Array.isArray(users) || users.length === 0) throw new Error('Configure at least one user');
  const ids = new Set();
  const tokens = new Set();
  for (const user of users) {
    if (!/^[a-z0-9-]{1,40}$/.test(user.id) || ids.has(user.id)) throw new Error('User IDs must be unique lowercase identifiers');
    if (typeof user.token !== 'string' || user.token.length < 24 || tokens.has(user.token)) throw new Error('Each user needs a unique random token of at least 24 characters');
    if (typeof user.name !== 'string' || !user.name.trim()) throw new Error('Each user needs a display name');
    ids.add(user.id);
    tokens.add(user.token);
  }
  return users;
}

async function createApp(options = {}) {
  const dailyUploadLimitBytes = options.dailyUploadLimitBytes ?? 5_000_000_000;
  if (!Number.isSafeInteger(dailyUploadLimitBytes) || dailyUploadLimitBytes <= 0) throw new Error('Daily upload limit must be a positive integer');
  const dataDir = options.dataDir || path.join(ROOT, 'data');
  fs.mkdirSync(dataDir, { recursive: true, mode: 0o700 });
  const users = options.users || readConfig(options.configFile || process.env.TOKEN_USAGE_CONFIG || path.join(ROOT, 'config/users.json'));
  const archive = new HistoryArchive(path.join(dataDir, 'history.sqlite'));
  const currentTime = () => options.now ? options.now() : Date.now();
  archive.startUploadTracking(currentTime());
  const namesFile = path.join(dataDir, 'device-names.json');
  const deviceNames = readJson(namesFile, {});
  const nameKey = (userId, deviceId) => `${userId}\u0000${deviceId}`;
  const hubs = new Map();
  const listeners = [];
  let publicCache = null;
  let stopping = false;

  try {
    for (const user of users) {
      const hub = createHub({ host: '127.0.0.1', port: 0, secret: user.token,
        dataFile: path.join(dataDir, `${user.id}.json`), syncSessionTitles: false, staleAfterMs: 2 * 60 * 60 * 1000 });
      await hub.start();
      hubs.set(user.id, hub);
      archive.capture(user.id, hub.getDevices());
      listeners.push(hub.onStats(() => {
        publicCache = null;
        archive.capture(user.id, hub.getDevices());
        const ids = new Set(hub.getDevices().map((device) => nameKey(user.id, device.deviceId)));
        let changed = false;
        for (const key of Object.keys(deviceNames)) {
          if (key.startsWith(user.id + '\u0000') && !ids.has(key)) { delete deviceNames[key]; changed = true; }
        }
        if (changed) writeJsonAtomic(namesFile, deviceNames);
      }));
    }
  } catch (error) {
    await Promise.all([...hubs.values()].map((hub) => hub.stop()));
    archive.close();
    throw error;
  }

  function publicSnapshot() {
    if (publicCache && Date.now() - publicCache.cachedAt < 5000) return publicCache.value;
    const people = users.map((user) => publicUser(user, hubs.get(user.id), (deviceId) => deviceNames[nameKey(user.id, deviceId)], (deviceId) => ({
      daily: archive.read(user.id, 'daily', deviceId), monthly: archive.read(user.id, 'monthly', deviceId)
    })));
    const value = {
      generatedAt: new Date().toISOString(), timeZone: TIME_ZONE, users: people,
      periods: Object.fromEntries(['today', 'month', 'allTime'].map((period) => [period, combinePeriods(people.map((person) => person.periods[period]))])),
      history: Object.fromEntries(users.map((user) => [user.id, {
        daily: archive.read(user.id), monthly: archive.read(user.id, 'monthly')
      }]))
    };
    publicCache = { cachedAt: Date.now(), value };
    return value;
  }

  function authorizedUser(req) {
    const auth = req.headers.authorization || '';
    const token = /^bearer /i.test(auth) ? auth.slice(7).trim() : String(req.headers['x-token-monitor-secret'] || '').trim();
    const digest = crypto.createHash('sha256').update(token).digest();
    return users.find((user) => crypto.timingSafeEqual(digest, crypto.createHash('sha256').update(user.token).digest()));
  }

  function uploadSnapshot() {
    const now = currentTime();
    const day = new Date(now + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);
    const { details, ...totals } = archive.readUploads(day);
    const sum = (rows) => Object.fromEntries(['todayBytes', 'monthBytes', 'totalBytes'].map((key) => [key, rows.reduce((total, row) => total + row[key], 0)]));
    return {
      generatedAt: new Date(now).toISOString(), timeZone: 'Asia/Shanghai', day, month: day.slice(0, 7),
      ...totals, dailyLimitBytes: dailyUploadLimitBytes,
      remainingBytes: Math.max(0, dailyUploadLimitBytes - totals.todayBytes),
      users: users.map((user) => {
        const rows = details.filter((row) => row.user_id === user.id);
        return {
          id: user.id, name: user.name, ...sum(rows),
          devices: hubs.get(user.id).getDevices().map((device, index) => ({
            id: publicDeviceId(user.id, device.deviceId),
            name: user.devices?.[device.deviceId] || deviceNames[nameKey(user.id, device.deviceId)] || `设备 ${String(index + 1).padStart(2, '0')}`,
            ...sum(rows.filter((row) => row.device_id === device.deviceId))
          }))
        };
      })
    };
  }

  function proxyToHub(req, res, user) {
    const upstream = http.request({ host: '127.0.0.1', port: hubs.get(user.id).server.address().port,
      method: req.method, path: req.url,
      headers: { ...req.headers, host: 'localhost', authorization: `Bearer ${user.token}` }
    }, (incoming) => {
      res.writeHead(incoming.statusCode, incoming.headers);
      incoming.pipe(res);
    });
    upstream.on('error', () => {
      if (!res.headersSent) json(res, 502, { error: 'hub_unavailable' });
      else res.destroy();
    });
    req.on('aborted', () => upstream.destroy());
    res.on('close', () => upstream.destroy());
    req.pipe(upstream);
  }

  async function ingest(req, res, user) {
    const now = currentTime();
    const shanghaiTime = now + 8 * 60 * 60 * 1000;
    const day = new Date(shanghaiTime).toISOString().slice(0, 10);
    // Reserve before reading, including concurrent requests. Chunked requests reserve
    // the per-request maximum and return unused bytes when the stream closes.
    const reserved = Number(req.headers['content-length'] ?? MAX_JSON_BODY_BYTES);
    if (reserved > MAX_JSON_BODY_BYTES) return json(res, 413, { error: 'payload_too_large' });
    if (!archive.reserveUpload(day, reserved, dailyUploadLimitBytes)) {
      res.setHeader('retry-after', String(Math.ceil((86400000 - shanghaiTime % 86400000) / 1000)));
      return json(res, 429, { error: 'daily_upload_limit', limitBytes: dailyUploadLimitBytes, day, timeZone: 'Asia/Shanghai' });
    }
    let received = 0;
    let settled = false;
    let finished = false;
    let recorded = false;
    let deviceId = '';
    req.on('data', (chunk) => { received += Buffer.byteLength(chunk); });
    const recordTraffic = () => {
      if (!settled || !finished || recorded) return;
      recorded = true;
      archive.recordUpload(day, user.id, deviceId, received);
    };
    const settle = () => {
      if (settled) return;
      settled = true;
      archive.releaseUpload(day, Math.max(0, reserved - received));
      recordTraffic();
    };
    req.once('end', settle);
    req.once('close', () => {
      if (!req.complete) finished = true;
      settle();
      recordTraffic();
    });
    try {
      const payload = await readJsonBody(req);
      if (Object.hasOwn(payload, 'displayName') && typeof payload.displayName !== 'string') throw new Error('displayName must be a string');
      const hub = hubs.get(user.id);
      const record = hub.ingest(payload);
      deviceId = record.deviceId;
      if (Object.hasOwn(payload, 'displayName')) {
        const name = Array.from(payload.displayName.replace(/[\x00-\x1f\x7f]/g, ' ').trim()).slice(0, 80).join('');
        const key = nameKey(user.id, record.deviceId);
        if (name) deviceNames[key] = name;
        else delete deviceNames[key];
        writeJsonAtomic(namesFile, deviceNames);
        publicCache = null;
      }
      const response = { ok: true, deviceId: record.deviceId };
      return json(res, 200, wantsMinimalResponse(req) ? response : { ...response, stats: hub.getStats() });
    } catch (error) {
      return json(res, error.code === 'payload_too_large' ? 413 : 400, { error: 'bad_request', message: error.message });
    } finally {
      finished = true;
      recordTraffic();
    }
  }

  function handle(req, res) {
    if (stopping) return json(res, 503, { error: 'service_stopping' });
    let url;
    try { url = new URL(req.url, 'http://localhost'); } catch { return json(res, 400, { error: 'bad_request' }); }
    if (url.pathname === '/api/health' && req.method === 'GET') return json(res, 200, {
      ok: true, role: 'hub', runtime: 'node-hub', version: 1, hubBuild: currentHubBuild('node-hub'),
      secretRequired: true, now: new Date().toISOString()
    });
    if (url.pathname === '/api/public/stats' && req.method === 'GET') {
      const value = publicSnapshot();
      const etag = 'W/"' + crypto.createHash('sha256').update(JSON.stringify({ ...value, generatedAt: undefined })).digest('hex').slice(0, 24) + '"';
      const cache = 'public, max-age=60, s-maxage=300, stale-while-revalidate=60';
      res.setHeader('etag', etag);
      res.setHeader('vary', 'Accept-Encoding');
      if (req.headers['if-none-match'] === etag) {
        res.writeHead(304, { 'cache-control': cache });
        return res.end();
      }
      return json(res, 200, value, cache);
    }
    if (url.pathname === '/api/public/uploads' && req.method === 'GET') return json(res, 200, uploadSnapshot());
    if (url.pathname.startsWith('/api/')) {
      const user = authorizedUser(req);
      if (!user) return json(res, 401, { error: 'unauthorized' });
      if (url.pathname === '/api/ingest' && req.method === 'POST') return ingest(req, res, user);
      return proxyToHub(req, res, user);
    }
    const file = STATIC_FILES.get(url.pathname);
    if (!file || !['GET', 'HEAD'].includes(req.method)) return json(res, 404, { error: 'not_found' });
    let body = fs.readFileSync(path.join(ROOT, 'public', file[0]));
    if (file[0] === 'index.html') {
      let html = body.toString('utf8');
      for (const asset of ['app.js', 'style.css']) {
        const version = crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, 'public', asset))).digest('hex').slice(0, 12);
        html = html.replace('/' + asset, '/' + asset + '?v=' + version);
      }
      body = Buffer.from(html);
    }
    res.writeHead(200, {
      'content-type': file[1], 'content-length': body.length,
      'cache-control': file[0] === 'index.html' ? 'no-cache' : url.searchParams.has('v') ? 'public, max-age=31536000, immutable' : 'public, max-age=86400', 'x-content-type-options': 'nosniff',
      'referrer-policy': 'strict-origin-when-cross-origin',
      'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    });
    res.end(req.method === 'HEAD' ? undefined : body);
  }

  const server = http.createServer(handle);
  server.requestTimeout = 30000;
  const externalServers = [];
  return {
    server, hubs, archive, publicSnapshot,
    async start(port = 17320, host = '127.0.0.1') {
      await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, host, resolve); });
    },
    async enableTls(certFile, keyFile, tlsPort = 9443, httpPort = 80) {
      const tlsOptions = () => ({ cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile), minVersion: 'TLSv1.2' });
      const secure = https.createServer(tlsOptions(), handle);
      const plain = http.createServer((req, res) => {
        const match = req.url.match(/^\/\.well-known\/acme-challenge\/([A-Za-z0-9_-]+)$/);
        if (match) {
          const filename = path.join(ROOT, 'deploy/acme/.well-known/acme-challenge', match[1]);
          if (fs.existsSync(filename)) { res.writeHead(200, { 'content-type': 'text/plain' }); return res.end(fs.readFileSync(filename)); }
          res.writeHead(404); return res.end();
        }
        res.writeHead(308, { location: `${PUBLIC_URL}${req.url.startsWith('/') ? req.url : '/'}` });
        res.end();
      });
      for (const [instance, port] of [[secure, tlsPort], [plain, httpPort]]) {
        externalServers.push(instance);
        await new Promise((resolve, reject) => { instance.once('error', reject); instance.listen(port, '0.0.0.0', resolve); });
      }
      process.on('SIGHUP', () => { try { secure.setSecureContext(tlsOptions()); console.log('TLS certificate reloaded'); } catch (error) { console.error('TLS reload failed:', error.message); } });
    },
    async stop() {
      stopping = true;
      const close = (instance) => new Promise((resolve) => { instance.closeAllConnections(); instance.close(resolve); });
      await Promise.all([close(server), ...externalServers.map(close)]);
      listeners.forEach((unsubscribe) => unsubscribe());
      await Promise.all([...hubs.values()].map((hub) => hub.stop()));
      archive.close();
    }
  };
}

if (require.main === module) {
  process.umask(0o077);
  createApp().then(async (app) => {
    await app.start(Number(process.env.PORT || 17320));
    if (process.env.TLS_CERT && process.env.TLS_KEY) await app.enableTls(process.env.TLS_CERT, process.env.TLS_KEY, Number(process.env.TLS_PORT || 9443), Number(process.env.HTTP_PORT || 80));
    console.log('Token Usage is ready');
    for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, () => app.stop().then(() => process.exit(0)).catch((error) => { console.error(error.message); process.exit(1); }));
  }).catch((error) => { console.error(error.message); process.exit(1); });
}

module.exports = { createApp, readConfig };

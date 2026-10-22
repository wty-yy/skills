'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

test('the preload adds the configured display name only to usage uploads', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'token-name-test-'));
  const name = 'yy 的电脑 #1 "测试"';
  fs.copyFileSync(path.join(__dirname, 'run.cjs'), path.join(root, 'run.cjs'));
  fs.writeFileSync(path.join(root, '.env'), 'TOKEN_MONITOR_DEVICE_NAME=' + JSON.stringify(name) + '\n', { mode: 0o600 });
  const script = `
    const http = require('node:http');
    const assert = require('node:assert/strict');
    const server = http.createServer((req,res)=>{
      let raw='';req.on('data',chunk=>raw+=chunk);req.on('end',()=>{res.setHeader('content-type','application/json');res.end(raw);});
    });
    server.listen(0,'127.0.0.1',async()=>{
      const base='http://127.0.0.1:'+server.address().port;
      try {
        const options={method:'POST',body:JSON.stringify({deviceId:'stable-id',value:7})};
        const uploaded=await(await fetch(base+'/api/ingest',options)).json();
        assert.equal(uploaded.displayName,${JSON.stringify(name)});
        assert.equal(uploaded.deviceId,'stable-id');assert.equal(uploaded.value,7);
        const other=await(await fetch(base+'/unrelated',options)).json();
        assert.equal(Object.hasOwn(other,'displayName'),false);
        console.log('name injection verified');
      }catch(e){console.error(e);process.exitCode=1;}finally{server.close();}
    });`;
  const result = spawnSync(process.execPath, ['--require', path.join(root, 'run.cjs'), '-e', script], {
    env: { ...process.env, NODE_PATH: path.dirname(path.dirname(require.resolve('dotenv/package.json'))) },
    encoding: 'utf8', timeout: 10000
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /verified/);
  fs.rmSync(root, { recursive: true });
});

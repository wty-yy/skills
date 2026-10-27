import test from "node:test";
import assert from "node:assert/strict";
import worker from "./cloudflare-worker.js";

function fixture() {
  let reads = 0;
  const env = { USAGE_KV: { async getWithMetadata(key, options) {
    reads++;
    assert.equal(key, "report");
    assert.equal(options.cacheTtl, 60);
    return { value: "<html>report</html>", metadata: { generatedAt: "2026-10-25T12:00:00Z", etag: '\"report-v1\"' } };
  } } };
  const run = (path = "/", options = {}) => worker.fetch(new Request("https://usage.example.com" + path, options), env);
  return { env, run, reads: () => reads };
}

test("cache-busting refreshes share one KV read without Cache API or origin", async () => {
  const { run, reads } = fixture();
  assert.equal((await run("/?_refresh=1")).headers.get("x-report-cache"), "MISS");
  const response = await run("/?_refresh=2", { headers: { "cache-control": "no-cache" } });
  assert.equal(response.headers.get("x-report-cache"), "HIT");
  assert.equal(response.headers.get("cache-control"), "private, max-age=60");
  assert.equal(response.headers.get("x-report-generated-at"), "2026-10-25T12:00:00Z");
  assert.equal(await response.text(), "<html>report</html>");
  assert.equal(reads(), 1);
});

test("cache expires and never crosses KV bindings", async t => {
  const { run, reads } = fixture();
  await run();
  const other = fixture();
  assert.equal((await other.run()).headers.get("x-report-cache"), "MISS");
  assert.equal(other.reads(), 1);
  const now = Date.now;
  t.after(() => { Date.now = now; });
  Date.now = () => now() + 61_000;
  assert.equal((await run()).headers.get("x-report-cache"), "MISS");
  assert.equal(reads(), 2);
});

test("ETag and HEAD responses have no body; unknown requests do not read KV", async () => {
  const { run, reads } = fixture();
  assert.equal((await run("/favicon.ico")).status, 404);
  assert.equal((await run("/", { method: "POST" })).status, 405);
  assert.equal(reads(), 0);
  const first = await run();
  const response = await run("/", { headers: { "if-none-match": "W/" + first.headers.get("etag") } });
  assert.equal(response.status, 304);
  const modified = await run("/", { headers: { "if-modified-since": first.headers.get("last-modified") } });
  assert.equal(modified.status, 304);
  const newer = await run("/", { headers: { "if-none-match": '"different-version"', "if-modified-since": first.headers.get("last-modified") } });
  assert.equal(newer.status, 200);
  assert.equal(await response.text(), "");
  assert.equal(await (await run("/", { method: "HEAD" })).text(), "");
  assert.equal(reads(), 1);
});

test("old metadata-free HTML still works; missing or failed KV is not cached", async () => {
  const { env, run } = fixture();
  let reads = 0;
  env.USAGE_KV.getWithMetadata = async () => { reads++; return { value: null, metadata: null }; };
  assert.equal((await run()).status, 503);
  env.USAGE_KV.getWithMetadata = async () => { reads++; throw new Error("unavailable"); };
  assert.equal((await run()).status, 503);
  env.USAGE_KV.getWithMetadata = async () => { reads++; return { value: "legacy report", metadata: null }; };
  assert.equal(await (await run()).text(), "legacy report");
  assert.equal(reads, 3);
});

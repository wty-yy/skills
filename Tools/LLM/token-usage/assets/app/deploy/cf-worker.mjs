const HUB_HOSTNAME = 'usage.example.com';
const PUBLIC_APIS = new Set(['/api/public/stats', '/api/public/uploads', '/api/health']);
const ASSETS = new Set(['/', '/app.js', '/style.css', '/favicon.svg', '/figtree.woff2', '/figtree-OFL.txt']);

function plain(message, status) {
  return new Response(message, { status, headers: { 'cache-control': 'no-store' } });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // HTTP-01 renewal must still reach the existing webroot on port 80.
    if (url.pathname.startsWith('/.well-known/acme-challenge/') && url.hostname === HUB_HOSTNAME) return fetch(request);
    if (url.protocol === 'http:') {
      url.protocol = 'https:';
      return Response.redirect(url.href, 308);
    }
    const isPublic = PUBLIC_APIS.has(url.pathname);
    const isAsset = ASSETS.has(url.pathname);
    if (!isPublic && !isAsset) {
      if (url.pathname.startsWith('/api/')) {
        if (url.hostname !== HUB_HOSTNAME || !(request.headers.has('authorization') || request.headers.has('x-token-monitor-secret'))) return plain('Unauthorized', 401);
        // A route subrequest goes to the DNS origin, retaining native Hub auth.
        const upstream = await fetch(request);
        const response = new Response(upstream.body, upstream);
        response.headers.set('cache-control', 'no-store');
        return response;
      }
      return plain('Not found', 404);
    }
    if (!['GET', 'HEAD'].includes(request.method)) return plain('Method not allowed', 405);

    // Ignore filter/tracking/cache-busting queries. Only real asset versions vary.
    const version = ['/app.js', '/style.css'].includes(url.pathname) ? url.searchParams.get('v') : null;
    const route = url.pathname + (version ? '?v=' + encodeURIComponent(version) : '');
    const key = new Request(url.origin + route);
    let response = await caches.default.match(key);
    // The zone may still contain assets cached from the previous VPS website.
    if (response?.headers.get('x-hub-source') !== 'cloudflare-kv') response = null;
    const hit = Boolean(response);
    if (!response) {
      try {
        if (isPublic) {
          const snapshot = await env.HUB_PUBLIC.get('snapshot', { type: 'json', cacheTtl: 60 });
          const entry = snapshot?.responses?.[url.pathname];
          if (!entry) return plain('Public snapshot not published yet', 503);
          response = new Response(entry.body, { headers: {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': 'public, max-age=60, s-maxage=60',
            etag: entry.etag, 'x-hub-published-at': snapshot.publishedAt
          } });
        } else {
          const asset = await env.HUB_PUBLIC.getWithMetadata('asset:' + route, { type: 'arrayBuffer', cacheTtl: 60 });
          if (!asset.value) return plain('Asset not published', 503);
          response = new Response(asset.value, { headers: asset.metadata });
        }
        response.headers.set('x-hub-source', 'cloudflare-kv');
        response.headers.set('x-content-type-options', 'nosniff');
        // Browser immutable lifetimes must not pin mutable edge entries.
        const stored = new Response(response.clone().body, response);
        stored.headers.set('cache-control', 'public, max-age=60');
        ctx.waitUntil(caches.default.put(key, stored));
      } catch {
        return plain('Cloudflare snapshot temporarily unavailable', 503);
      }
    }
    response = new Response(response.body, response);
    // cache.put uses a separate TTL; restore the intended browser policy on hits.
    response.headers.set('cache-control', isPublic || route === '/' ? 'public, max-age=60, s-maxage=60' : version ? 'public, max-age=31536000, immutable' : 'public, max-age=3600');
    response.headers.set('x-hub-cache', hit ? 'HIT' : 'MISS');
    const validators = (request.headers.get('if-none-match') || '').split(',').map(value => value.trim());
    const etag = response.headers.get('etag');
    if (etag && (validators.includes('*') || validators.includes(etag) || validators.includes('W/' + etag))) return new Response(null, { status: 304, headers: response.headers });
    return request.method === 'HEAD' ? new Response(null, { headers: response.headers }) : response;
  }
};

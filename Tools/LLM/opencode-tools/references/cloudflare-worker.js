// Each Worker serves one report; cache entries stay within the same KV binding.
let cachedReport;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/") return new Response("Not found", { status: 404 });
    if (!["GET", "HEAD"].includes(request.method)) return new Response("Method not allowed", { status: 405 });

    const hit = cachedReport?.binding === env.USAGE_KV && cachedReport.expiresAt > Date.now();
    let report = hit ? cachedReport : null;
    if (!report) {
      try {
        const { value, metadata } = await env.USAGE_KV.getWithMetadata("report", { type: "text", cacheTtl: 60 });
        if (!value) return new Response("Report not published yet", { status: 503, headers: { "cache-control": "no-store" } });
        report = { binding: env.USAGE_KV, value, metadata, expiresAt: Date.now() + 60_000 };
        cachedReport = report;
      } catch {
        return new Response("Report temporarily unavailable", { status: 503, headers: { "cache-control": "no-store" } });
      }
    }
    const headers = {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "private, max-age=60",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      "x-report-source": "cloudflare-kv",
      "x-report-cache": hit ? "HIT" : "MISS",
    };
    const meta = report.metadata;
    if (meta?.generatedAt) {
      headers["x-report-generated-at"] = meta.generatedAt;
      headers["last-modified"] = new Date(meta.generatedAt).toUTCString();
    }
    if (meta?.etag) headers.etag = meta.etag;
    const validators = (request.headers.get("if-none-match") || "").split(",").map(value => value.trim());
    if (meta?.etag && (validators.includes("*") || validators.includes(meta.etag) || validators.includes("W/" + meta.etag))) return new Response(null, { status: 304, headers });
    // HTML transforms may remove ETag; Last-Modified still permits revalidation.
    const modifiedSince = request.headers.get("if-modified-since");
    if (!request.headers.has("if-none-match") && modifiedSince && headers["last-modified"] && Date.parse(modifiedSince) >= Date.parse(headers["last-modified"])) return new Response(null, { status: 304, headers });
    return new Response(request.method === "HEAD" ? null : report.value, { headers });
  },
};

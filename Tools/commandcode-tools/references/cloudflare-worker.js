export default {
  async fetch(request, env) {
    const html = await env.USAGE_KV.get("report");
    if (!html) {
      return new Response("report not published yet", { status: 404 });
    }
    let generatedAt = "";
    const meta = await env.USAGE_KV.get("report-meta");
    if (meta) {
      try {
        generatedAt = JSON.parse(meta).generatedAt ?? "";
      } catch {}
    }
    const headers = {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "private, max-age=30",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    };
    if (generatedAt) headers["x-report-generated-at"] = generatedAt;
    return new Response(html, { headers });
  },
};

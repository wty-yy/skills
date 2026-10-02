#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Generate a self-contained HTML usage report for commandcode.ai.

Examples:
    uv run usage_report.py
    uv run usage_report.py --out report.html
    uv run usage_report.py --push
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import commandcode_usage as cu

CHARTJS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
CF_API = "https://api.cloudflare.com/client/v4/accounts"


def load_chartjs() -> str:
    try:
        request = urllib.request.Request(
            CHARTJS_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode()
    except Exception:  # noqa: BLE001
        return ""


def kv_put(url: str, body: bytes, content_type: str, token: str) -> None:
    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(0.5 * 2**attempt + random.random())
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            raise RuntimeError(f"KV push failed: HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            continue
        if not payload.get("success"):
            raise RuntimeError(f"KV push failed: {payload.get('errors')}")
        return
    raise RuntimeError(f"KV push failed after retries: {last_error}")


def push_to_cloudflare(html: str, data: dict) -> None:
    account = os.environ.get("CF_ACCOUNT_ID", "")
    namespace = os.environ.get("CF_KV_NAMESPACE_ID", "")
    token = os.environ.get("CF_API_TOKEN", "")
    key = os.environ.get("CF_KV_KEY", "report")
    missing = [
        name
        for name, value in (
            ("CF_ACCOUNT_ID", account),
            ("CF_KV_NAMESPACE_ID", namespace),
            ("CF_API_TOKEN", token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("missing env vars for --push: " + ", ".join(missing))
    base = f"{CF_API}/{account}/storage/kv/namespaces/{namespace}/values/{quote(key, safe='')}"
    kv_put(base, html.encode(), "text/html; charset=utf-8", token)
    meta = {
        "generatedAt": data["generatedAt"],
        "range": data["range"],
        "site": data["site"],
        "bytes": len(html),
    }
    kv_put(
        f"{base}-meta",
        json.dumps(meta, ensure_ascii=False).encode(),
        "application/json; charset=utf-8",
        token,
    )
    print(f"pushed: KV '{key}' + '{key}-meta' ({len(html):,} bytes)")


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Command Code 用量报告</title>
<style>
  :root { color-scheme: dark; --bg:#0f1117; --panel:#171a23; --line:#262b38; --text:#e6e9f0; --muted:#9ba4b8; --hover:#1c2029; --bar-bg:#232838; --wty:#4f8cff; --xfy:#f5a54a; --wt:#3ddc97; --ok:#3ddc97; --warn:#ff6b6b; }
  :root[data-theme="light"] { color-scheme: light; --bg:#f4f6fb; --panel:#ffffff; --line:#e2e6ef; --text:#1b2130; --muted:#626e84; --hover:#f2f4f9; --bar-bg:#e8ebf3; --wty:#2f6fe4; --xfy:#d97f17; --wt:#1f9d6c; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; transition:background .2s, color .2s; }
  main { max-width:1240px; margin:0 auto; padding:36px 24px 60px; }
  header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
  header h1 { margin:0 0 8px; font-size:26px; font-weight:650; letter-spacing:-.4px; }
  header .meta { color:var(--muted); font-size:13px; line-height:1.8; }
  .plan-badge { display:inline-block; margin-left:10px; padding:3px 9px; border:1px solid var(--line); border-radius:6px; color:var(--wty); font-size:11px; letter-spacing:.5px; vertical-align:middle; }
  .theme-toggle { flex:none; background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:9px; padding:8px 14px; font-size:13px; cursor:pointer; transition:border-color .15s, background .2s; }
  .theme-toggle:hover { border-color:var(--muted); }
  h2 { font-size:16px; font-weight:600; margin:0 0 16px; }
  section { margin-top:30px; }
  .cards { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:16px; margin-top:26px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px 22px; min-width:0; }
  .card .label { color:var(--muted); font-size:13px; }
  .card .value { font-size:32px; font-weight:650; margin-top:8px; line-height:1.25; letter-spacing:-.5px; font-variant-numeric:tabular-nums; }
  .card .sub { color:var(--muted); font-size:12px; margin-top:10px; }
  .card.primary { border-color:var(--wty); }
  .card.primary .value { color:var(--wty); }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  .grid2 > * { min-width:0; }
  @media (max-width:900px) { .grid2 { grid-template-columns:1fr; } .cards { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
  @media (max-width:520px) { main { padding:24px 16px 40px; } header h1 { font-size:22px; } .cards { grid-template-columns:1fr; gap:12px; } .card { padding:18px 20px; } .theme-toggle { padding:7px 10px; } .plan-badge { margin-left:0; margin-top:6px; display:table; } .quota-grid { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:22px; overflow-x:auto; }
  .chart-wrap { position:relative; height:280px; }
  canvas { display:block; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:10px 12px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; font-variant-numeric:tabular-nums; }
  th:first-child, td:first-child { text-align:left; }
  thead th { color:var(--muted); font-weight:500; position:sticky; top:0; background:var(--panel); }
  tbody tr:hover { background:var(--hover); }
  tbody tr:last-child td { border-bottom:0; }
  .quota-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }
  .quota { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px 22px; }
  .quota .head { display:flex; justify-content:space-between; align-items:baseline; }
  .quota .pct { font-size:22px; font-weight:600; }
  .bar { height:8px; border-radius:4px; background:var(--bar-bg); margin:12px 0 10px; overflow:hidden; }
  .bar > span { display:block; height:100%; border-radius:4px; }
  .quota .nums { color:var(--muted); font-size:12.5px; display:flex; justify-content:space-between; gap:10px; }
  .footnote { color:var(--muted); font-size:12px; margin-top:12px; line-height:1.7; }
  footer { color:var(--muted); font-size:12px; margin-top:34px; border-top:1px solid var(--line); padding-top:14px; }
  .tag { display:inline-block; padding:1px 7px; border-radius:999px; font-size:11.5px; margin-left:6px; }
  .tag.wty { background:rgba(79,140,255,.18); color:var(--wty); }
  .tag.xfy { background:rgba(245,165,74,.16); color:var(--xfy); }
  .tag.wt { background:rgba(61,220,151,.16); color:var(--wt); }
  .mono { font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
</style>
</head>
<body>
<script>
try {
  const saved = localStorage.getItem("cc-theme");
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
} catch (e) {}
</script>
<main>
  <header>
    <div>
      <h1>Command Code 用量报告<span class="plan-badge" id="planBadge"></span></h1>
      <div class="meta" id="meta"></div>
    </div>
    <button id="themeToggle" class="theme-toggle" type="button">浅色模式</button>
  </header>

  <section class="cards" id="cards"></section>
  <div class="footnote" id="scopeNote"></div>

  <section>
    <h2>额度</h2>
    <div class="quota-grid" id="quota"></div>
    <div class="footnote" id="quotaNote"></div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>每日 Credits 消耗</h2><div class="chart-wrap"><canvas id="costChart"></canvas></div></div>
    <div class="panel"><h2>每日 Token 用量</h2><div class="chart-wrap"><canvas id="tokenChart"></canvas></div></div>
  </section>

  <section class="panel">
    <h2>每日明细</h2>
    <table id="dailyTable"></table>
    <div class="footnote">每日数据来自 Console 用量图表接口（UTC 日 × 模型，按天聚合）；Credits 为计入套餐额度的消耗，API 费用为原价。</div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>按模型</h2><table id="modelTable"></table></div>
    <div class="panel">
      <h2>API 密钥</h2>
      <table id="keyTable"></table>
      <div class="footnote">当前个人账号的用量接口未提供按 API key 的用量拆分，此表仅列出密钥与分组（wty1→wty，wt1→wt，其余→xfy）。</div>
    </div>
  </section>

  <section class="panel">
    <h2>最近 24 小时请求</h2>
    <table id="requestTable"></table>
    <div class="footnote" id="requestNote"></div>
  </section>

  <footer id="footer"></footer>
</main>
<script>__CHARTJS__</script>
<script>
const DATA = __DATA__;
const CHARTJS_FALLBACK = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js";

const fmtInt = v => (v || 0).toLocaleString("en-US");
const fmtTokens = v => {
  v = v || 0;
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return String(v);
};
const fmtTokenMillions = v => (Number(v || 0) / 1e6).toLocaleString("en-US", { maximumFractionDigits: 2 }) + "M";
const fmtUSD = v => "$" + (v || 0).toFixed(4);
const fmtCredits = v => (v || 0).toFixed(2);

const cacheHit = s => {
  const denom = s.tokensIn || 0;
  return denom ? ((s.cacheRead || 0) / denom * 100).toFixed(1) + "%" : "—";
};

function countdown(targetIso) {
  if (!targetIso) return "重置时间未知";
  const ms = new Date(targetIso).getTime() - Date.now();
  if (ms <= 0) return "即将重置";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (d > 0) return d + " 天 " + h + " 小时后重置";
  if (h > 0) return h + " 小时 " + m + " 分钟后重置";
  return m + " 分钟后重置";
}

function el(tag, cls, html) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function fmtLocal(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso || "—";
  const pad = n => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " +
    pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

function renderMeta() {
  const b = DATA.billing;
  const plan = b.planId ? b.planId.toUpperCase() : "—";
  document.getElementById("planBadge").textContent = plan;
  document.getElementById("meta").textContent =
    "当前套餐周期 " + fmtLocal(b.periodStart) + " ~ " + fmtLocal(b.periodEnd);
  document.getElementById("scopeNote").textContent =
    "从本次账单开始统计，截至 " + fmtLocal(DATA.generatedAt) + "（本地时间）；每 10 分钟更新。";
  document.getElementById("footer").textContent =
    "数据来源：Command Code Console · " + plan + " 套餐 · 更新时间 " + fmtLocal(DATA.generatedAt);
}

function renderCards() {
  const cards = document.getElementById("cards");
  const t = DATA.totals;
  const q = DATA.quota;
  const monthly = q.windows.month;
  const period = DATA.billing.summary || {};
  const credits = period.totalCredits ?? period.totalCost ?? 0;
  const daysElapsed = Math.max(1, Math.ceil((new Date(DATA.generatedAt) - new Date(DATA.billing.periodStart)) / 86400000));
  const items = [
    {
      label: "套餐已用 Credits",
      value: fmtCredits(credits),
      sub: "本账单周期累计消耗",
    },
    {
      label: "套餐剩余额度",
      value: monthly ? fmtCredits(q.remaining) : "—",
      sub: monthly ? "总额度 " + fmtCredits(q.granted) + " · 已用 " + monthly.percent + "%" : "未订阅或不可用",
    },
    {
      label: "套餐总 Token",
      value: fmtTokens(period.totalTokens),
      sub: "输入 " + fmtTokens(period.totalTokensIn) + " · 输出 " + fmtTokens(period.totalTokensOut),
      primary: true,
    },
    {
      label: "套餐请求数",
      value: fmtInt(period.totalCount),
      sub: "从账单开始至当前更新",
    },
    {
      label: "缓存命中率",
      value: cacheHit(t),
      sub: "缓存读取 " + fmtTokens(t.cacheRead) + " · 节省 " + fmtUSD(t.cacheSavings),
    },
    {
      label: "日均 Credits",
      value: fmtCredits(credits / daysElapsed),
      sub: "已统计 " + daysElapsed + " 天 · 日均 " + fmtInt(Math.round((period.totalCount || 0) / daysElapsed)) + " 次请求",
    },
  ];
  for (const item of items) {
    cards.append(el("div", "card" + (item.primary ? " primary" : ""),
      '<div class="label">' + item.label + '</div><div class="value">' + item.value + '</div><div class="sub">' + item.sub + "</div>"));
  }
}

function renderQuota() {
  const box = document.getElementById("quota");
  const note = document.getElementById("quotaNote");
  const q = DATA.quota;
  const b = DATA.billing;
  for (const scope of ["fiveHour", "weekly", "month"]) {
    const w = q.windows[scope];
    if (!w) continue;
    const remaining = Math.max(0, w.limit - w.usage);
    const color = w.percent >= 90 ? "#ff6b6b" : w.percent >= 60 ? "#f5a54a" : "#3ddc97";
    const reset = '<span class="countdown" data-reset="' + (w.resetsAt || "") + '">' + countdown(w.resetsAt) + "</span>";
    const node = el("div", "quota");
    node.innerHTML =
      '<div class="head"><strong>' + w.label + '额度</strong><span class="pct" style="color:' + color + '">' + w.percent + "%</span></div>" +
      '<div class="bar"><span style="width:' + Math.min(100, w.percent) + "%;background:" + color + '"></span></div>' +
      '<div class="nums"><span>已用 ' + fmtCredits(w.usage) + " / " + fmtCredits(w.limit) + "</span><span>剩余 " + fmtCredits(remaining) + "</span></div>" +
      '<div class="nums" style="margin-top:6px">' + reset + "</div>";
    box.append(node);
  }
  const period = b.summary || {};
  const end = b.periodEnd ? b.periodEnd.slice(0, 10) : "—";
  const renew = b.cancelAtPeriodEnd ? "到期后不续费" : "自动续费";
  note.textContent =
    "额度窗口：5 小时 = 月额度的 20%，每周 = 50%，每月 = 100%；月度重置时间 = 订阅周期结束（" + end + "，" + renew + "）。" +
    "账单周期内已用 " + fmtCredits(period.totalCost || 0) + " credits、请求 " + fmtInt(period.totalCount || 0) +
    " 次、Token " + fmtTokens(period.totalTokens || 0) + "。";
}

let costChart, tokenChart;

function currentTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function chartPalette() {
  const light = currentTheme() === "light";
  return { text: light ? "#6b7488" : "#8b93a7", grid: light ? "#e2e6ef" : "#262b38" };
}

function renderCharts() {
  if (typeof Chart === "undefined") {
    const s = document.createElement("script");
    s.src = CHARTJS_FALLBACK;
    s.onload = () => renderCharts();
    document.head.append(s);
    return;
  }
  if (costChart) { costChart.destroy(); costChart = undefined; }
  if (tokenChart) { tokenChart.destroy(); tokenChart = undefined; }
  const palette = chartPalette();
  Chart.defaults.color = palette.text;
  Chart.defaults.borderColor = palette.grid;
  const labels = DATA.days.map(d => d.date.slice(5));
  const base = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { boxWidth: 12 } } },
    scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } },
  };
  costChart = new Chart(document.getElementById("costChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Credits",
        data: DATA.days.map(day => day.credits),
        backgroundColor: "#4f8cff",
        borderRadius: 4,
      }],
    },
    options: { ...base, plugins: { ...base.plugins, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ": " + fmtCredits(ctx.parsed.y) } } } },
  });
  tokenChart = new Chart(document.getElementById("tokenChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "输入",
          data: DATA.days.map(day => day.tokensIn),
          backgroundColor: "#4f8cff",
          borderRadius: 4,
        },
        {
          label: "输出",
          data: DATA.days.map(day => day.tokensOut),
          backgroundColor: "#f5a54a",
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...base,
      scales: {
        ...base.scales,
        y: {
          ...base.scales.y,
          title: { display: true, text: "Token（M）" },
          ticks: { callback: value => fmtTokenMillions(value) },
        },
      },
      plugins: {
        ...base.plugins,
        tooltip: {
          callbacks: {
            label: ctx => ctx.dataset.label + ": " + fmtInt(ctx.parsed.y) + " Token（" + fmtTokenMillions(ctx.parsed.y) + "）",
            footer: items => "合计：" + fmtTokenMillions(items.reduce((total, item) => total + item.parsed.y, 0)),
          },
        },
      },
    },
  });
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("cc-theme", theme); } catch (e) {}
  document.getElementById("themeToggle").textContent = theme === "light" ? "深色模式" : "浅色模式";
  renderCharts();
}

function table(containerId, headers, rows) {
  const table = document.getElementById(containerId);
  table.innerHTML =
    "<thead><tr>" + headers.map(h => "<th>" + h + "</th>").join("") + "</tr></thead>" +
    "<tbody>" + rows.map(row => "<tr>" + row.map(cell => "<td>" + cell + "</td>").join("") + "</tr>").join("") + "</tbody>";
}

function renderTables() {
  table("dailyTable",
    ["日期", "请求数", "输入", "输出", "缓存读取", "合计 Tokens", "API 费用", "Credits"],
    DATA.days.slice().reverse().filter(d => d.requests || d.tokens || d.credits).map(d => [
      d.date,
      fmtInt(d.requests),
      fmtInt(d.tokensIn),
      fmtInt(d.tokensOut),
      fmtInt(d.cacheRead),
      "<strong>" + fmtInt(d.tokens) + "</strong>",
      fmtUSD(d.apiCost),
      "<strong>" + fmtCredits(d.credits) + "</strong>",
    ]).concat([[
      "<strong>合计</strong>",
      "<strong>" + fmtInt(DATA.totals.requests) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.tokensIn) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.tokensOut) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.cacheRead) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.tokens) + "</strong>",
      "<strong>" + fmtUSD(DATA.totals.apiCost) + "</strong>",
      "<strong>" + fmtCredits(DATA.totals.credits) + "</strong>",
    ]]));

  table("modelTable",
    ["模型", "供应商", "请求数", "Tokens", "API 费用", "Credits"],
    DATA.models.map(m => [
      m.model,
      (m.providers || []).join(", ") || "—",
      fmtInt(m.requests),
      fmtInt(m.tokens),
      fmtUSD(m.apiCost),
      fmtCredits(m.credits),
    ]));

  if (DATA.keys && DATA.keys.length) {
    table("keyTable",
      ["密钥", "分组", "创建时间"],
      DATA.keys.map(k => [
        k.name + '<span class="tag ' + k.group + '">' + k.group + "</span>",
        k.group,
        (k.createdAt || "").slice(0, 10),
      ]));
  } else {
    document.getElementById("keyTable").outerHTML = '<div class="footnote">未找到 API 密钥。</div>';
  }

  const requests = (DATA.requests || []).slice().sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
  table("requestTable",
    ["时间", "模型", "输入", "输出", "耗时", "状态", "费用", "Trace ID"],
    requests.slice(0, 100).map(r => [
      fmtLocal(r.createdAt),
      r.model || "—",
      fmtInt(r.tokensIn),
      fmtInt(r.tokensOut),
      (r.durationMs / 1000).toFixed(2) + "s",
      r.status === "completed" ? '<span style="color:#3ddc97">完成</span>' : (r.status || "—"),
      fmtUSD(r.cost),
      '<span class="mono">' + (r.traceId ? r.traceId.slice(0, 8) : "—") + "</span>",
    ]));
  document.getElementById("requestNote").textContent =
    "最近 24 小时共 " + requests.length + " 条请求（UTC 时间转本地显示）；更早的逐请求明细接口不提供，仅保留每日聚合。";
}

function tick() {
  document.querySelectorAll(".countdown").forEach(node => {
    node.textContent = countdown(node.dataset.reset || undefined);
  });
}

document.getElementById("themeToggle").addEventListener("click", () => {
  applyTheme(currentTheme() === "light" ? "dark" : "light");
});
document.getElementById("themeToggle").textContent = currentTheme() === "light" ? "深色模式" : "浅色模式";
renderMeta();
renderCards();
renderQuota();
renderCharts();
renderTables();
tick();
setInterval(tick, 30000);
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an HTML usage report")
    parser.add_argument(
        "--profile",
        help="Chrome profile dir path, e.g. ~/.config/google-chrome/Default",
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "usage_report.html")
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="upload the report to Cloudflare KV (needs CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN)",
    )
    args = parser.parse_args()

    try:
        data = cu.build_summary(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    chartjs = load_chartjs()
    html = TEMPLATE.replace("__CHARTJS__", chartjs or "").replace(
        "__DATA__", json.dumps(data, ensure_ascii=False)
    )
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"written: {args.out} ({len(html):,} bytes)")

    if args.push:
        try:
            push_to_cloudflare(html, data)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

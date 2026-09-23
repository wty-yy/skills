#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Generate a self-contained HTML usage report for an opencode.ai workspace.

Examples:
    uv run usage_report.py
    uv run usage_report.py --days 14 --out report.html
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import opencode_usage as ou

CHARTJS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
CF_API = "https://api.cloudflare.com/client/v4/accounts"
TOKEN_FIELDS = ("inputTokens", "outputTokens", "reasoningTokens", "cacheReadTokens")
GO_TOKEN_PRICES = {
    "deepseek-v4.1-flash": [("闲时", 0.15, 0.60, 0.003), ("峰时", 0.30, 1.20, 0.006)],
    "deepseek-v4-pro": [("闲时", 0.66, 1.98, 0.022), ("峰时", 1.32, 3.96, 0.044)],
    "deepseek-v4-flash": [("闲时", 0.15, 0.60, 0.003), ("峰时", 0.30, 1.20, 0.006)],
    "deepseek-v4-flash-vision-exp": [
        ("闲时", 0.15, 0.60, 0.003),
        ("峰时", 0.30, 1.20, 0.006),
    ],
    "glm-5.3-flash": [("", 0.15, 0.50, 0.03)],
    "glm-5.3": [("", 1.40, 4.40, 0.26)],
    "glm-5.2": [("", 1.40, 4.40, 0.26)],
    "glm-5.1": [("", 1.40, 4.40, 0.26)],
    "kimi-k3": [("", 3.00, 15.00, 0.30)],
    "kimi-k2.7-code": [("", 0.95, 4.00, 0.19)],
    "kimi-k2.6": [("", 0.95, 4.00, 0.16)],
    "longcat-2.0": [("", 0.30, 1.20, 0.006)],
    "mimo-v2.5": [("", 0.14, 0.28, 0.0028)],
    "mimo-v2.5-pro": [("", 0.435, 0.87, 0.003625)],
    "minimax-m3": [("", 0.30, 1.20, 0.06)],
    "minimax-m2.7": [("", 0.30, 1.20, 0.06)],
    "minimax-m2.5": [("", 0.30, 1.20, 0.06)],
    "muse-spark-1.3-contributor": [("", 0.10, 0.20, 0.002)],
    "muse-spark-1.2-contributor": [("", 0.10, 0.20, 0.002)],
    "qwen3.8-max": [("", 2.00, 6.00, 0.25)],
    "qwen3.8-flash": [("", 0.15, 0.47, 0.016)],
    "qwen3.7-max": [("", 2.50, 7.50, 0.50)],
    "qwen3.7-plus": [("≤256K", 0.40, 1.60, 0.04), (">256K", 1.20, 4.80, 0.12)],
    "qwen3.6-plus": [("≤256K", 0.50, 3.00, 0.05), (">256K", 2.00, 6.00, 0.20)],
    "hy4-preview": [("", 0.834, 2.501, 0.042)],
    "hy3": [("", 0.14, 0.58, 0.035)],
    "grok-4.6": [("≤200K", 2.00, 6.00, 0.50), (">200K", 4.00, 12.00, 1.00)],
    "gpt-5.6-luna": [("≤272K", 0.20, 1.20, 0.02), (">272K", 0.40, 1.80, 0.04)],
}


def load_chartjs() -> str:
    try:
        request = urllib.request.Request(
            CHARTJS_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode()
    except Exception:  # noqa: BLE001
        return ""


def group_of(name: str) -> str:
    return "wt" if name.endswith("wt") else "yy"


def normalize_key_name(name: str) -> str:
    return name.split(" - ")[-1] if " - " in name else name


def load_history(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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
        "workspace": data["workspace"],
        "bytes": len(html),
    }
    kv_put(
        f"{base}-meta",
        json.dumps(meta, ensure_ascii=False).encode(),
        "application/json; charset=utf-8",
        token,
    )
    print(f"pushed: KV '{key}' + '{key}-meta' ({len(html):,} bytes)")


def empty_stats() -> dict:
    return {"requests": 0, **dict.fromkeys(TOKEN_FIELDS, 0)}


def total_tokens(stats: dict) -> int:
    return sum(stats.get(field) or 0 for field in TOKEN_FIELDS)


def build_data(args) -> dict:
    profile = Path(args.profile).expanduser() if args.profile else None
    headers = ou.api_headers(args.workspace, profile)
    workspace = args.workspace

    today = datetime.now().astimezone().date()
    cutoff = today - timedelta(days=args.days - 1)
    dates = [cutoff + timedelta(days=offset) for offset in range(args.days)]

    history = load_history(Path(args.history)) if args.history else {}
    history_days = {day["date"]: day for day in history.get("days", [])}

    key_names = ou.fetch_key_names(headers)
    records, complete = ou.fetch_records(cutoff, args.max_pages, headers)

    daily_usage: dict[str, dict[str, dict]] = {}
    key_stats: dict[str, dict] = {}
    model_stats: dict[str, dict] = {}
    for record in records:
        day = ou.parse_time(record["createdAt"]).astimezone().date().isoformat()
        if day not in {d.isoformat() for d in dates}:
            continue
        key_id = record.get("serviceApiKeyId")
        name = key_names.get(key_id, {}).get("displayName", key_id or "unknown")
        group = group_of(name)
        cost = int(record.get("costMicroCents") or 0) / ou.COST_SCALE
        bucket = daily_usage.setdefault(
            day,
            {"wt": empty_stats() | {"cost": 0.0}, "yy": empty_stats() | {"cost": 0.0}},
        )[group]
        for stats in (
            bucket,
            key_stats.setdefault(key_id, empty_stats() | {"cost": 0.0}),
            model_stats.setdefault(record["model"], empty_stats() | {"cost": 0.0}),
        ):
            stats["requests"] += 1
            for field in TOKEN_FIELDS:
                stats[field] += record.get(field) or 0
            stats["cost"] += cost

    days = []
    for day in dates:
        iso = day.isoformat()
        entry = {"date": iso, "groups": {}}
        for group in ("wt", "yy"):
            stats = daily_usage.get(iso, {}).get(group, empty_stats() | {"cost": 0.0})
            entry["groups"][group] = {
                **stats,
                "tokens": total_tokens(stats),
                "cost": round(stats["cost"], 6),
            }
        entry["total"] = {
            "requests": entry["groups"]["wt"]["requests"]
            + entry["groups"]["yy"]["requests"],
            "tokens": entry["groups"]["wt"]["tokens"] + entry["groups"]["yy"]["tokens"],
            "cost": round(
                entry["groups"]["wt"]["cost"] + entry["groups"]["yy"]["cost"], 6
            ),
        }
        if not entry["total"]["requests"] and iso in history_days:
            entry = {**history_days[iso], "backfilled": True}
        days.append(entry)

    totals = {"wt": empty_stats() | {"cost": 0.0}, "yy": empty_stats() | {"cost": 0.0}}
    for entry in days:
        for group in ("wt", "yy"):
            stats = entry["groups"][group]
            for field in TOKEN_FIELDS:
                totals[group][field] += stats.get(field) or 0
            totals[group]["requests"] += stats.get("requests") or 0
            totals[group]["cost"] += stats.get("cost") or 0.0
    for group in ("wt", "yy"):
        totals[group]["tokens"] = total_tokens(totals[group])
        totals[group]["cost"] = round(totals[group]["cost"], 6)
    totals["all"] = {
        "requests": totals["wt"]["requests"] + totals["yy"]["requests"],
        "tokens": totals["wt"]["tokens"] + totals["yy"]["tokens"],
        "cost": round(totals["wt"]["cost"] + totals["yy"]["cost"], 6),
        **{field: totals["wt"][field] + totals["yy"][field] for field in TOKEN_FIELDS},
    }

    keys = []
    for key_id, stats in key_stats.items():
        info = key_names.get(key_id, {})
        name = info.get("displayName", key_id)
        if info.get("deleted"):
            name += "（已删除）"
        keys.append(
            {
                "id": key_id,
                "name": name,
                "group": group_of(name),
                **stats,
                "tokens": total_tokens(stats),
                "cost": round(stats["cost"], 6),
            }
        )
    keys.sort(key=lambda entry: (-entry["cost"], entry["name"]))
    keys_by_name = {normalize_key_name(entry["name"]): entry for entry in keys}
    for old in history.get("keys", []):
        name = normalize_key_name(old["name"])
        entry = keys_by_name.get(name)
        if entry is None:
            entry = {
                "id": old.get("id"),
                "name": name,
                "group": group_of(name),
                **empty_stats(),
                "tokens": 0,
                "cost": 0.0,
            }
            keys.append(entry)
            keys_by_name[name] = entry
        entry["requests"] += old.get("requests") or 0
        for field in TOKEN_FIELDS:
            entry[field] += old.get(field) or 0
        entry["tokens"] = total_tokens(entry)
        entry["cost"] = round(entry["cost"] + (old.get("cost") or 0.0), 6)
    keys.sort(key=lambda entry: (-entry["cost"], entry["name"]))

    models = [
        {"model": model, "cost": round(stats["cost"], 6)}
        for model, stats in sorted(model_stats.items(), key=lambda kv: -kv[1]["cost"])
    ]
    models_by_name = {entry["model"]: entry for entry in models}
    for old in history.get("models", []):
        entry = models_by_name.get(old["model"])
        if entry is None:
            entry = {"model": old["model"], "cost": 0.0}
            models.append(entry)
            models_by_name[old["model"]] = entry
        entry["cost"] = round(entry["cost"] + (old.get("cost") or 0.0), 6)
    models.sort(key=lambda entry: -entry["cost"])

    price_rows = []
    for entry in models:
        variants = GO_TOKEN_PRICES.get(entry["model"])
        if not variants:
            price_rows.append(
                {
                    "model": entry["model"],
                    "variant": "",
                    "input": None,
                    "output": None,
                    "cacheRead": None,
                }
            )
            continue
        for variant, price_in, price_out, price_cache in variants:
            price_rows.append(
                {
                    "model": entry["model"],
                    "variant": variant,
                    "input": round(price_in * 100, 4),
                    "output": round(price_out * 100, 4),
                    "cacheRead": round(price_cache * 100, 4),
                }
            )

    quota = ou.fetch_quota(headers)

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": workspace,
        "range": [dates[0].isoformat(), dates[-1].isoformat()],
        "complete": complete,
        "days": days,
        "totals": totals,
        "keys": keys,
        "models": models,
        "priceRows": price_rows,
        "quota": quota,
    }


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>opencode 用量报告</title>
<style>
  :root { color-scheme: dark; --bg:#0f1117; --panel:#171a23; --line:#262b38; --text:#e6e9f0; --muted:#8b93a7; --hover:#1c2029; --bar-bg:#232838; --wt:#4f8cff; --yy:#f5a54a; --ok:#3ddc97; --warn:#ff6b6b; }
  :root[data-theme="light"] { color-scheme: light; --bg:#f4f6fb; --panel:#ffffff; --line:#e2e6ef; --text:#1b2130; --muted:#6b7488; --hover:#f2f4f9; --bar-bg:#e8ebf3; --wt:#2f6fe4; --yy:#d97f17; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; transition:background .2s, color .2s; }
  main { max-width:1180px; margin:0 auto; padding:28px 20px 60px; }
  header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
  header h1 { margin:0 0 6px; font-size:24px; }
  header .meta { color:var(--muted); font-size:13px; }
  .theme-toggle { flex:none; background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:9px; padding:8px 14px; font-size:13px; cursor:pointer; transition:border-color .15s, background .2s; }
  .theme-toggle:hover { border-color:var(--muted); }
  h2 { font-size:16px; margin:0 0 12px; }
  section { margin-top:26px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-top:22px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .card .label { color:var(--muted); font-size:12.5px; }
  .card .value { font-size:26px; font-weight:600; margin-top:6px; }
  .card .sub { color:var(--muted); font-size:12px; margin-top:4px; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  .grid2 > * { min-width:0; }
  @media (max-width:900px) { .grid2 { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px; overflow-x:auto; }
  canvas { max-height:320px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:8px 10px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }
  th:first-child, td:first-child { text-align:left; }
  thead th { color:var(--muted); font-weight:500; position:sticky; top:0; background:var(--panel); }
  tbody tr:hover { background:var(--hover); }
  .quota-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }
  .quota { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .quota .head { display:flex; justify-content:space-between; align-items:baseline; }
  .quota .pct { font-size:22px; font-weight:600; }
  .bar { height:8px; border-radius:4px; background:var(--bar-bg); margin:12px 0 10px; overflow:hidden; }
  .bar > span { display:block; height:100%; border-radius:4px; }
  .quota .nums { color:var(--muted); font-size:12.5px; display:flex; justify-content:space-between; gap:10px; }
  .footnote { color:var(--muted); font-size:12px; margin-top:10px; }
  footer { color:var(--muted); font-size:12px; margin-top:34px; border-top:1px solid var(--line); padding-top:14px; }
  .tag { display:inline-block; padding:1px 7px; border-radius:999px; font-size:11.5px; margin-left:6px; }
  .tag.wt { background:rgba(79,140,255,.18); color:var(--wt); }
  .tag.yy { background:rgba(245,165,74,.16); color:var(--yy); }
</style>
</head>
<body>
<script>
try {
  const saved = localStorage.getItem("oc-theme");
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
} catch (e) {}
</script>
<main>
  <header>
    <div>
      <h1>opencode 用量报告</h1>
      <div class="meta" id="meta"></div>
    </div>
    <button id="themeToggle" class="theme-toggle" type="button">浅色模式</button>
  </header>

  <section class="cards" id="cards"></section>

  <section>
    <h2>OpenCode Go 会员额度</h2>
    <div class="quota-grid" id="quota"></div>
    <div class="footnote" id="quotaNote"></div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>每日费用（USD）</h2><canvas id="costChart"></canvas></div>
    <div class="panel"><h2>每日 Token 用量</h2><canvas id="tokenChart"></canvas></div>
  </section>

  <section class="panel">
    <h2>每日明细</h2>
    <table id="dailyTable"></table>
    <div class="footnote">* 为旧接口（2026-09-22 迁移前）快照回填（9/21 为快照时刻的部分数据）；9/22 起为新 Console API 数据。</div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>按 API 密钥</h2><table id="keyTable"></table></div>
    <div class="panel"><h2>按模型费用（计费口径）</h2><table id="modelTable"></table></div>
  </section>

  <section class="panel">
    <h2>模型 Token 价格（每 100M tokens）</h2>
    <table id="priceTable"></table>
    <div class="footnote">价格来自 OpenCode Go 官方文档；DeepSeek 系列分闲时/峰时两档（峰时为 UTC 周一至周五 01:00-04:00、06:00-10:00）。</div>
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
const fmtUSD = v => "$" + (v || 0).toFixed(4);
const fmtQuotaUSD = v => "$" + ((v || 0) / 1e8).toFixed(2);
const cacheHit = s => {
  const denom = (s.cacheReadTokens || 0) + (s.inputTokens || 0);
  return denom ? ((s.cacheReadTokens || 0) / denom * 100).toFixed(1) + "%" : "—";
};
const GROUP_LABEL = { wt: "wt", yy: "yy（其他密钥）" };
const GROUP_COLOR = { wt: "#4f8cff", yy: "#f5a54a" };

function countdown(targetIso) {
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

function renderMeta() {
  document.getElementById("meta").textContent =
    "工作区 " + DATA.workspace + " · " + DATA.range[0] + " ~ " + DATA.range[1] +
    " · 生成于 " + DATA.generatedAt.replace("T", " ").slice(0, 19);
  document.getElementById("footer").textContent =
    DATA.complete ? "数据完整（usage.list 全部分页已拉取）" : "提示：usage.list 分页达到上限，Token 汇总可能不完整（费用数据不受影响）";
}

function renderCards() {
  const cards = document.getElementById("cards");
  const t = DATA.totals;
  const monthly = DATA.quota.windows.month;
  const items = [
    { label: "总费用（全部密钥）", value: fmtUSD(t.all.cost), sub: "wt " + fmtUSD(t.wt.cost) + " · yy " + fmtUSD(t.yy.cost) },
    {
      label: "Go 月额度剩余",
      value: monthly ? fmtQuotaUSD(monthly.limit - monthly.usage) : "—",
      sub: monthly ? "已用 " + monthly.percent + "% · 总额度 " + fmtQuotaUSD(monthly.limit) : "未订阅或不可用",
    },
    { label: "总 Token（全部）", value: fmtTokens(t.all.tokens), sub: fmtInt(t.all.tokens) + " · wt " + fmtTokens(t.wt.tokens) + " / yy " + fmtTokens(t.yy.tokens) },
    {
      label: "缓存命中率（全部）",
      value: cacheHit(t.all),
      sub: "wt " + cacheHit(t.wt) + " · yy " + cacheHit(t.yy) + " · 缓存读取 ÷（输入 + 缓存读取）",
    },
    { label: "总请求数", value: fmtInt(t.all.requests), sub: "wt " + fmtInt(t.wt.requests) + " · yy " + fmtInt(t.yy.requests) },
    { label: "日均费用", value: fmtUSD(t.all.cost / DATA.days.length), sub: "统计 " + DATA.days.length + " 天" },
  ];
  for (const item of items) {
    cards.append(el("div", "card",
      '<div class="label">' + item.label + '</div><div class="value">' + item.value + '</div><div class="sub">' + item.sub + "</div>"));
  }
}

function renderQuota() {
  const box = document.getElementById("quota");
  const note = document.getElementById("quotaNote");
  if (DATA.quota.error) { box.append(el("div", "card", DATA.quota.error)); return; }
  if (!DATA.quota.subscribed) { box.append(el("div", "card", "当前工作区未订阅 OpenCode Go。")); return; }
  for (const scope of ["fiveHour", "week", "month"]) {
    const w = DATA.quota.windows[scope];
    if (!w) continue;
    const remaining = w.limit - w.usage;
    const color = w.percent >= 90 ? "#ff6b6b" : w.percent >= 60 ? "#f5a54a" : "#3ddc97";
    const reset = w.resetsAt
      ? '<span class="countdown" data-reset="' + w.resetsAt + '">' + countdown(w.resetsAt) + "</span>"
      : '<span style="color:#8b93a7">重置时间未知</span>';
    const node = el("div", "quota");
    node.innerHTML =
      '<div class="head"><strong>' + w.label + '用量</strong><span class="pct" style="color:' + color + '">' + w.percent + "%</span></div>" +
      '<div class="bar"><span style="width:' + Math.min(100, w.percent) + "%;background:" + color + '"></span></div>' +
      '<div class="nums"><span>已用 ' + fmtQuotaUSD(w.usage) + " / " + fmtQuotaUSD(w.limit) + "</span><span>剩余 " + fmtQuotaUSD(remaining) + "</span></div>" +
      '<div class="nums" style="margin-top:6px">' + reset + "</div>";
    box.append(node);
  }
  const end = DATA.quota.endsAt ? DATA.quota.endsAt.slice(0, 10) : "—";
  const renew = DATA.quota.cancelAtPeriodEnd ? "到期后不续费" : "自动续费";
  note.textContent = "额度窗口：5 小时 = 月额度的 20%，每周 = 50%，每月 = 100%；月度额度重置时间 = 订阅周期结束（" + end + "，" + renew + "）。额度统计包含 9/22 迁移前的用量，与下方明细表区间可能不一致。";
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
      datasets: ["wt", "yy"].map(group => ({
        label: GROUP_LABEL[group],
        data: DATA.days.map(d => d.groups[group].cost),
        backgroundColor: GROUP_COLOR[group],
        borderRadius: 4,
      })),
    },
    options: { ...base, plugins: { ...base.plugins, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ": " + fmtUSD(ctx.parsed.y) } } } },
  });
  tokenChart = new Chart(document.getElementById("tokenChart"), {
    type: "bar",
    data: {
      labels,
      datasets: ["wt", "yy"].map(group => ({
        label: GROUP_LABEL[group],
        data: DATA.days.map(d => d.groups[group].tokens),
        backgroundColor: GROUP_COLOR[group],
        borderRadius: 4,
      })),
    },
    options: { ...base, plugins: { ...base.plugins, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ": " + fmtInt(ctx.parsed.y) + " (" + fmtTokens(ctx.parsed.y) + ")" } } } },
  });
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("oc-theme", theme); } catch (e) {}
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
    ["日期", "wt Tokens", "yy Tokens", "合计 Tokens", "wt 费用", "yy 费用", "合计费用", "请求数"],
    DATA.days.slice().reverse().filter(d => d.total.requests || d.total.tokens || d.total.cost).map(d => [
      d.date + (d.backfilled ? " *" : ""),
      fmtInt(d.groups.wt.tokens),
      fmtInt(d.groups.yy.tokens),
      "<strong>" + fmtInt(d.total.tokens) + "</strong>",
      fmtUSD(d.groups.wt.cost),
      fmtUSD(d.groups.yy.cost),
      "<strong>" + fmtUSD(d.total.cost) + "</strong>",
      fmtInt(d.total.requests),
    ]).concat([[
      "<strong>合计</strong>",
      "<strong>" + fmtInt(DATA.totals.wt.tokens) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.yy.tokens) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.all.tokens) + "</strong>",
      "<strong>" + fmtUSD(DATA.totals.wt.cost) + "</strong>",
      "<strong>" + fmtUSD(DATA.totals.yy.cost) + "</strong>",
      "<strong>" + fmtUSD(DATA.totals.all.cost) + "</strong>",
      "<strong>" + fmtInt(DATA.totals.all.requests) + "</strong>",
    ]]));

  table("keyTable",
    ["密钥", "分组", "请求数", "输入", "输出", "推理", "缓存读取", "缓存命中率", "合计 Tokens", "费用"],
    DATA.keys.map(k => [
      k.name + '<span class="tag ' + k.group + '">' + GROUP_LABEL[k.group] + "</span>",
      k.group,
      fmtInt(k.requests),
      fmtInt(k.inputTokens),
      fmtInt(k.outputTokens),
      fmtInt(k.reasoningTokens),
      fmtInt(k.cacheReadTokens),
      cacheHit(k),
      fmtInt(k.tokens),
      fmtUSD(k.cost),
    ]));

  table("modelTable",
    ["模型", "费用", "占比"],
    DATA.models.map(m => [
      m.model,
      fmtUSD(m.cost),
      DATA.totals.all.cost ? ((m.cost / DATA.totals.all.cost) * 100).toFixed(1) + "%" : "0%",
    ]));

  const fmtPrice = v => v === null ? "—" : "$" + v.toFixed(2);
  table("priceTable",
    ["模型", "档位", "输入 / 100M", "输出 / 100M", "缓存读取 / 100M"],
    DATA.priceRows.map(r => [
      r.model,
      r.variant || "—",
      fmtPrice(r.input),
      fmtPrice(r.output),
      fmtPrice(r.cacheRead),
    ]));
}

function tick() {
  document.querySelectorAll(".countdown").forEach(node => {
    node.textContent = countdown(node.dataset.reset);
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
        "--days", type=int, default=14, help="number of days (default 14)"
    )
    parser.add_argument("--workspace", default=ou.DEFAULT_WORKSPACE)
    parser.add_argument("--profile", help="Chrome profile dir name, e.g. Default")
    parser.add_argument(
        "--max-pages", type=int, default=200, help="usage.list page cap"
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "usage_report.html")
    )
    parser.add_argument(
        "--history",
        default=str(Path(__file__).parent / "history.json"),
        help="pre-migration backfill data (JSON)",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="upload the report to Cloudflare KV (needs CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN)",
    )
    args = parser.parse_args()

    try:
        data = build_data(args)
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

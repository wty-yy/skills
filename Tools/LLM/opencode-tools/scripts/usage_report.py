#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Generate a self-contained HTML usage report for an opencode.ai workspace.

Examples:
    uv run usage_report.py
    uv run usage_report.py --days 14 --out report.html
    uv run usage_report.py --accounts ~/.config/opencode-usage/accounts.json

Accounts JSON is a list of {id, name, workspace, apiKeyEnv (optional), profile
(optional)}. Browser sessions are verified and saved beside that file with
owner-only permissions; each workspace has its own usage cache.
"""

import argparse
import calendar
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import opencode_usage as ou

CHARTJS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
CF_API = "https://api.cloudflare.com/client/v4/accounts"
TOKEN_FIELDS = ("inputTokens", "outputTokens", "cacheReadTokens")
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


DATA_FLOOR = date(2026, 9, 13)  # first day covered by the Console v2 usage export
MAX_PERIOD_DAYS = 90
ACCOUNTS_CONFIG = Path.home() / ".config/opencode-usage/accounts.json"
REPORT_CACHE = Path(__file__).parent / "account_reports.json"


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def build_periods(quota: dict, today: date, days: int | None) -> tuple[list[dict], str]:
    """Split the subscription history into billing periods, newest first.

    The current Go billing period is the default view; earlier periods (one
    calendar month each, back to the export floor) stay selectable.
    """
    if days:
        start = today - timedelta(days=days - 1)
        period = {
            "key": "recent",
            "label": f"最近 {days} 天",
            "start": start.isoformat(),
            "end": today.isoformat(),
            "current": False,
        }
        return [period], period["key"]

    start = ou.parse_utc_day(quota.get("startsAt"))
    end = ou.parse_utc_day(quota.get("endsAt"))
    periods: list[dict] = []
    if start and end and start <= end and start <= today:
        periods.append(
            {
                "key": "current",
                "label": "当前套餐周期",
                "start": start.isoformat(),
                "end": min(today, end).isoformat(),
                "current": True,
            }
        )
        for index in range(1, 4):
            period_start = add_months(start, -index)
            period_end = add_months(start, -(index - 1)) - timedelta(days=1)
            if period_start < DATA_FLOOR:
                break
            periods.append(
                {
                    "key": f"prev{index}",
                    "label": "上一套餐周期"
                    if index == 1
                    else f"更早套餐周期（-{index} 个月）",
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "current": False,
                }
            )
    if not periods:
        start, end = ou.subscription_span(quota, today, fallback_days=14)
        periods.append(
            {
                "key": "recent",
                "label": f"最近 {(end - start).days + 1} 天",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "current": False,
            }
        )

    floor = today - timedelta(days=MAX_PERIOD_DAYS - 1)
    if periods[-1]["start"] < floor.isoformat():
        periods = [
            {**period, "start": max(period["start"], floor.isoformat())}
            for period in periods
            if period["end"] >= floor.isoformat()
        ]
        if not periods:
            periods = [
                {
                    "key": "recent",
                    "label": f"最近 {MAX_PERIOD_DAYS} 天",
                    "start": floor.isoformat(),
                    "end": today.isoformat(),
                    "current": False,
                }
            ]
    return periods, periods[0]["key"]


def aggregate_day_models(rows: list[dict], start: date, end: date) -> dict:
    """Per-day, per-model stats so the client can re-slice by billing period."""
    out: dict[str, dict[str, dict]] = {}
    for row in rows:
        day = row["day"]
        if not (start.isoformat() <= day <= end.isoformat()):
            continue
        cost = int(row["cost_micro_cents"] or 0) / ou.COST_SCALE
        stats = out.setdefault(day, {}).setdefault(
            row["model"], {"requests": 0, "tokens": 0, "cost": 0.0}
        )
        stats["requests"] += int(row["requests"] or 0)
        stats["tokens"] += sum(
            int(row[field] or 0)
            for field in ("input_tokens", "output_tokens", "cache_read_tokens")
        )
        stats["cost"] = round(stats["cost"] + cost, 6)
    return out


def load_chartjs() -> str:
    try:
        request = urllib.request.Request(
            CHARTJS_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode()
    except Exception:  # noqa: BLE001
        return ""


def kv_put(url: str, body: bytes, metadata: dict, token: str) -> None:
    """Publish report HTML and its metadata in one KV write."""
    boundary = "usage-report-" + hashlib.sha256(body).hexdigest()[:24]
    multipart = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
        + json.dumps(metadata, ensure_ascii=False).encode()
        + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="value"; filename="report.html"\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'.encode()
        + body
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        url,
        data=multipart,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
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
    body = html.encode()
    meta = {
        "generatedAt": data["generatedAt"],
        "etag": '"' + hashlib.sha256(body).hexdigest() + '"',
        "bytes": len(body),
    }
    kv_put(base, body, meta, token)
    print(f"pushed: KV '{key}' with metadata ({len(body):,} bytes; 1 write)")


def empty_stats() -> dict:
    return {"requests": 0, **dict.fromkeys(TOKEN_FIELDS, 0)}


def total_tokens(stats: dict) -> int:
    return sum(stats.get(field) or 0 for field in TOKEN_FIELDS)


def normalize_key_name(name: str) -> str:
    return name.split(" - ")[-1] if " - " in name else name


def load_history(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_account_data(workspace: str, headers: list[dict], days: int | None) -> dict:
    quota = ou.fetch_quota(headers)
    today = datetime.now().astimezone().date()
    periods, default_period = build_periods(quota, today, days)
    cutoff = date.fromisoformat(periods[-1]["start"])
    last = date.fromisoformat(periods[0]["end"])
    dates = [
        cutoff + timedelta(days=offset) for offset in range((last - cutoff).days + 1)
    ]

    rows = ou.fetch_usage(len(dates), headers)
    daily, _ = ou.aggregate_usage(rows, cutoff, last)
    day_models = aggregate_day_models(rows, cutoff, last)
    key_names = ou.fetch_key_names(headers)
    cache_path = ou.key_cache_path(workspace)
    _, keys_fetched_at, keys_days = ou.fetch_key_stats(
        cutoff, last, headers, cache_path=cache_path
    )

    history = (
        load_history(Path(__file__).parent / "history.json")
        if workspace == ou.DEFAULT_WORKSPACE
        else {}
    )
    history_days = {entry["date"]: entry for entry in history.get("days", [])}
    history_span = [min(history_days), max(history_days)] if history_days else None
    history_costs = {
        entry["date"]: round(entry.get("total", {}).get("cost") or 0.0, 6)
        for entry in history.get("days", [])
    }
    cache_days = ou.load_key_cache(cache_path).get("days", {})

    def empty_group() -> dict:
        return {
            "requests": 0,
            "inputTokens": 0,
            "outputTokens": 0,
            "reasoningTokens": 0,
            "cacheReadTokens": 0,
            "tokens": 0,
            "cost": 0.0,
        }

    def day_groups(iso: str):
        cache_entry = cache_days.get(iso)
        if cache_entry and cache_entry.get("keys"):
            groups: dict[str, dict] = {}
            for key_id, stats in cache_entry["keys"].items():
                name = key_names.get(key_id, {}).get("displayName", key_id)
                bucket = groups.setdefault(ou.group_of(name), empty_group())
                bucket["requests"] += stats.get("requests") or 0
                for field in (
                    "inputTokens",
                    "outputTokens",
                    "reasoningTokens",
                    "cacheReadTokens",
                ):
                    bucket[field] += stats.get(field) or 0
                bucket["tokens"] = (
                    bucket["inputTokens"]
                    + bucket["outputTokens"]
                    + bucket["reasoningTokens"]
                    + bucket["cacheReadTokens"]
                )
                bucket["cost"] += stats.get("cost") or 0.0
            if groups:
                return {
                    group: groups.get(group, empty_group()) for group in ("wt", "yy")
                }
        entry = history_days.get(iso)
        if entry and entry.get("groups"):
            return {
                group: {
                    **(entry["groups"].get(group) or {}),
                    "inputTokens": None,
                    "cacheReadTokens": None,
                }
                for group in ("wt", "yy")
            }
        return None

    days = []
    for day in dates:
        iso = day.isoformat()
        stats = daily.get(iso, empty_stats() | {"cost": 0.0})
        groups = day_groups(iso)
        if groups:
            split_tokens = groups["wt"]["tokens"] + groups["yy"]["tokens"]
            split_cost = groups["wt"]["cost"] + groups["yy"]["cost"]
            if split_tokens:
                groups["wt"]["tokens"] = round(
                    groups["wt"]["tokens"] * total_tokens(stats) / split_tokens
                )
                groups["yy"]["tokens"] = total_tokens(stats) - groups["wt"]["tokens"]
            if split_cost:
                groups["wt"]["cost"] = round(
                    groups["wt"]["cost"] * stats["cost"] / split_cost, 6
                )
                groups["yy"]["cost"] = round(stats["cost"] - groups["wt"]["cost"], 6)
            split_requests = (groups["wt"].get("requests") or 0) + (
                groups["yy"].get("requests") or 0
            )
            if split_requests:
                groups["wt"]["requests"] = round(
                    groups["wt"]["requests"] * stats["requests"] / split_requests
                )
            else:
                split_tokens = groups["wt"]["tokens"] + groups["yy"]["tokens"]
                groups["wt"]["requests"] = (
                    round(stats["requests"] * groups["wt"]["tokens"] / split_tokens)
                    if split_tokens
                    else 0
                )
            groups["yy"]["requests"] = stats["requests"] - groups["wt"]["requests"]
        days.append(
            {
                "date": iso,
                **stats,
                "tokens": total_tokens(stats),
                "cost": round(stats["cost"], 6),
                "groups": groups,
            }
        )

    price_models = [
        {"model": model}
        for model in sorted({model for day in day_models.values() for model in day})
    ]

    price_rows = []
    for entry in price_models:
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

    key_days = {
        iso: entry["keys"]
        for iso, entry in cache_days.items()
        if cutoff.isoformat() <= iso <= last.isoformat() and entry.get("keys")
    }
    keys_meta = {}
    for key_id in {key_id for stats in key_days.values() for key_id in stats}:
        info = key_names.get(key_id, {})
        name = info.get("displayName", key_id)
        keys_meta[key_id] = {
            "name": name + ("（已删除）" if info.get("deleted") else ""),
            "group": ou.group_of(name),
        }
    history_key_costs = {
        normalize_key_name(old_key["name"]): old_key.get("cost") or 0.0
        for old_key in history.get("keys", [])
    }

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": workspace,
        "range": [dates[0].isoformat(), dates[-1].isoformat()],
        "periods": periods,
        "defaultPeriod": default_period,
        "days": days,
        "dayModels": day_models,
        "keyDays": key_days,
        "keysMeta": keys_meta,
        "historyKeyCosts": history_key_costs,
        "historyCosts": history_costs,
        "historySpan": history_span,
        "keysFetchedAt": keys_fetched_at,
        "keysDays": keys_days,
        "priceRows": price_rows,
        "quota": quota,
    }


def build_data(args) -> dict:
    config_path = Path(args.accounts).expanduser()
    if config_path.exists() and not (args.workspace or args.profile):
        configs = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        workspace = args.workspace or ou.DEFAULT_WORKSPACE
        configs = [
            {
                "id": workspace,
                "name": "OpenCode",
                "workspace": workspace,
                "apiKeyEnv": "OPENCODE_API_KEY",
                "profile": args.profile,
            }
        ]
    if not isinstance(configs, list) or not configs:
        raise RuntimeError("accounts config must be a non-empty list")
    ids = [account["id"] for account in configs]
    if len(set(ids)) != len(ids):
        raise RuntimeError("account IDs must be unique")

    cached = load_history(REPORT_CACHE)
    accounts = []
    for config in configs:
        workspace = config["workspace"]
        try:
            profile = config.get("profile")
            headers = ou.auth_header_sets(
                workspace,
                Path(profile).expanduser() if profile else None,
                api_key=os.environ.get(config.get("apiKeyEnv", ""), ""),
                session_path=config_path.parent / f"session-{workspace}.json",
            )
            account = build_account_data(workspace, headers, args.days)
            cached[workspace] = account
        except RuntimeError as exc:
            if workspace not in cached:
                raise RuntimeError(f"{config['name']}: {exc}") from exc
            print(f"warning: {config['name']}: {exc}", file=sys.stderr)
            account = {
                **cached[workspace],
                "warning": "读取失败，正在显示上次成功获取的数据；请重新登录该账号。",
            }
        accounts.append({**account, "id": config["id"], "name": config["name"]})
    REPORT_CACHE.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": accounts[0]["workspace"],
        "range": [
            min(account["range"][0] for account in accounts),
            max(account["range"][1] for account in accounts),
        ],
        "accounts": accounts,
        "defaultAccount": accounts[0]["id"],
    }


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenCode 用量报告</title>
<style>
  :root { color-scheme: dark; --bg:#0f1117; --panel:#171a23; --line:#262b38; --text:#e6e9f0; --muted:#8b93a7; --hover:#1c2029; --bar-bg:#232838; --wt:#4f8cff; --yy:#f5a54a; --ok:#3ddc97; --warn:#ff6b6b; }
  :root[data-theme="light"] { color-scheme: light; --bg:#f4f6fb; --panel:#ffffff; --line:#e2e6ef; --text:#1b2130; --muted:#6b7488; --hover:#f2f4f9; --bar-bg:#e8ebf3; --wt:#2f6fe4; --yy:#d97f17; --ok:#178a56; --warn:#cf3f3f; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; transition:background .2s, color .2s; }
  main { max-width:1180px; margin:0 auto; padding:28px 20px 60px; }
  header { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
  header h1 { margin:0 0 6px; font-size:24px; }
  header .meta { color:var(--muted); font-size:13px; }
  .theme-toggle, .refresh-btn { flex:none; display:inline-flex; align-items:center; gap:6px; background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:9px; padding:8px 14px; font-size:13px; cursor:pointer; transition:border-color .15s, background .2s, color .15s; }
  .theme-toggle:hover, .refresh-btn:hover { border-color:var(--muted); }
  .refresh-btn:disabled { cursor:progress; opacity:.75; }
  .refresh-btn.success { border-color:var(--ok); color:var(--ok); }
  .refresh-btn.failed { border-color:var(--warn); color:var(--warn); }
  .refresh-btn .icon { display:inline-block; font-size:15px; line-height:1; transform-origin:50% 50%; }
  .refresh-btn.loading .icon { animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .refresh-btn.loading .icon { animation:none; } }
  .controls { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
  .period-select { background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:9px; padding:8px 34px 8px 12px; font-size:13px; cursor:pointer; max-width:360px; text-overflow:ellipsis; }
  .period-select:hover { border-color:var(--muted); }
  @media (max-width:980px) { header { flex-wrap:wrap; } .controls { flex-wrap:wrap; } }
  @media (max-width:760px) { .controls { width:100%; } .period-select { flex:1 1 100%; width:100%; max-width:100%; } }
  .badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:11.5px; background:var(--bar-bg); color:var(--muted); margin-left:8px; }
  .badge.live { background:rgba(61,220,151,.16); color:var(--ok); }
  h2 { font-size:16px; margin:0 0 12px; }
  section { margin-top:26px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:14px; margin-top:22px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .card .label { color:var(--muted); font-size:12.5px; }
  .card .value { font-size:26px; font-weight:600; margin-top:6px; }
  .card .sub { color:var(--muted); font-size:12px; margin-top:4px; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  .grid2 > * { min-width:0; }
  @media (max-width:900px) { .grid2 { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px; overflow-x:auto; }
  .chart-wrap { position:relative; height:300px; max-width:100%; margin:0 auto; }
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
      <h1>OpenCode 用量报告</h1>
      <div class="meta" id="meta"></div>
      <div class="footnote" id="accountWarning" role="status" hidden></div>
    </div>
    <div class="controls">
      <select id="accountSelect" class="period-select" aria-label="账号" title="切换账号"></select>
      <select id="periodSelect" class="period-select" aria-label="套餐周期" title="切换查看的套餐周期"></select>
      <button id="refreshBtn" class="refresh-btn" type="button" title="获取最新发布的报告（每 10 分钟自动发布一次）">
        <span class="icon" aria-hidden="true">↻</span><span id="refreshLabel">刷新</span>
      </button>
      <button id="themeToggle" class="theme-toggle" type="button">浅色模式</button>
    </div>
  </header>

  <section class="cards" id="cards"></section>

  <section>
    <h2>当前套餐：OpenCode Go 额度<span class="badge live" id="quotaBadge">实时</span></h2>
    <div class="quota-grid" id="quota"></div>
    <div class="footnote" id="quotaNote"></div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>每日费用（USD）</h2><div class="chart-wrap"><canvas id="costChart"></canvas></div></div>
    <div class="panel"><h2>每日 Token 用量</h2><div class="chart-wrap"><canvas id="tokenChart"></canvas></div></div>
  </section>

  <section class="panel">
    <h2>每日明细</h2>
    <table id="dailyTable"></table>
    <div class="footnote">每日/模型数据来自 Console v2 用量导出（天 × 模型）；wt/yy 拆分来自请求日志（保留 30 天，9/22 起有记录），缺失天数显示「—」并随后台缓存回填逐步补齐。</div>
  </section>

  <section class="panel">
    <h2>按 API 密钥</h2>
    <table id="keyTable"></table>
    <div class="footnote" id="keyNote">按密钥数据来自请求日志（保留 30 天），按天缓存、增量刷新。</div>
  </section>

  <section class="grid2">
    <div class="panel"><h2>按模型费用</h2><table id="modelTable"></table></div>
    <div class="panel">
      <h2>模型 Token 价格（每 100M tokens）</h2>
      <table id="priceTable"></table>
      <div class="footnote">价格来自 OpenCode Go 官方文档；DeepSeek 系列分闲时/峰时两档（峰时为 UTC 周一至周五 01:00-04:00、06:00-10:00）。</div>
    </div>
  </section>

  <footer id="footer"></footer>
</main>
<script type="application/json" id="reportData">__DATA__</script>
<script>__CHARTJS__</script>
<script>
let REPORT = JSON.parse(document.getElementById("reportData").textContent);
let savedAccount;
try { savedAccount = localStorage.getItem("oc-account"); } catch (e) {}
let DATA = REPORT.accounts.find(a => a.id === savedAccount) ||
  REPORT.accounts.find(a => a.id === REPORT.defaultAccount) || REPORT.accounts[0];
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
const GROUP_LABEL = { wt: "wt", yy: "yy（其他密钥）" };
const normKeyName = name => {
  const plain = String(name || "").replace("（已删除）", "");
  return plain.includes(" - ") ? plain.split(" - ").pop() : plain;
};

const state = { account: DATA.id, period: DATA.defaultPeriod, periods: {} };
const currentPeriod = () =>
  DATA.periods.find(p => p.key === state.period) || DATA.periods[0];
const periodDays = () => {
  const p = currentPeriod();
  return DATA.days.filter(d => d.date >= p.start && d.date <= p.end);
};
const emptyTotals = () => ({
  requests: 0, inputTokens: 0, outputTokens: 0, reasoningTokens: 0,
  cacheReadTokens: 0, tokens: 0, cost: 0,
});
const sumDays = days => days.reduce((acc, d) => {
  for (const field of ["requests", "inputTokens", "outputTokens", "reasoningTokens", "cacheReadTokens", "tokens", "cost"]) {
    acc[field] += d[field] || 0;
  }
  return acc;
}, emptyTotals());
const groupSum = (days, group, field) =>
  days.reduce((s, d) => s + (d.groups ? d.groups[group][field] || 0 : 0), 0);
const groupHit = (days, group) => {
  let input = 0, cache = 0;
  for (const d of days) {
    const g = d.groups && d.groups[group];
    if (g && g.inputTokens !== null && g.inputTokens !== undefined) {
      input += g.inputTokens;
      cache += g.cacheReadTokens || 0;
    }
  }
  const denom = input + cache;
  return denom ? ((cache / denom) * 100).toFixed(1) + "%" : "—";
};
const hasKeyTokens = day => {
  const g = day.groups && day.groups.wt;
  return Boolean(g) && g.inputTokens !== null && g.inputTokens !== undefined;
};
const periodHit = days => {
  let input = 0, cache = 0, covered = 0;
  for (const day of days) {
    if (!hasKeyTokens(day)) continue;
    covered += 1;
    for (const group of ["wt", "yy"]) {
      input += day.groups[group].inputTokens || 0;
      cache += day.groups[group].cacheReadTokens || 0;
    }
  }
  const denom = input + cache;
  return { value: denom ? ((cache / denom) * 100).toFixed(1) + "%" : "—", covered };
};

function keyRows(days) {
  const period = currentPeriod();
  const rows = {};
  for (const d of days) {
    const entry = DATA.keyDays[d.date];
    if (!entry) continue;
    for (const [id, s] of Object.entries(entry)) {
      const row = rows[id] || (rows[id] = { id, requests: 0, inputTokens: 0, outputTokens: 0, reasoningTokens: 0, cacheReadTokens: 0, cost: 0 });
      for (const field of ["requests", "inputTokens", "outputTokens", "reasoningTokens", "cacheReadTokens", "cost"]) {
        row[field] += s[field] || 0;
      }
    }
  }
  const hist = DATA.historyCosts || {};
  const histDates = Object.keys(hist);
  const histTotal = histDates.reduce((s, date) => s + (hist[date] || 0), 0);
  const histInside = histDates
    .filter(date => date >= period.start && date <= period.end)
    .reduce((s, date) => s + (hist[date] || 0), 0);
  const legacyFactor = histTotal ? histInside / histTotal : 0;
  return Object.values(rows).map(row => {
    const meta = DATA.keysMeta[row.id] || { name: row.id, group: "yy" };
    const cost = row.cost + (DATA.historyKeyCosts[normKeyName(meta.name)] || 0) * legacyFactor;
    return { ...row, name: meta.name, group: meta.group, tokens: row.inputTokens + row.outputTokens + row.reasoningTokens + row.cacheReadTokens, cost };
  }).sort((a, b) => b.cost - a.cost || a.name.localeCompare(b.name));
}

function modelRows(days) {
  const rows = {};
  for (const d of days) {
    const entry = DATA.dayModels[d.date];
    if (!entry) continue;
    for (const [model, s] of Object.entries(entry)) {
      const row = rows[model] || (rows[model] = { model, requests: 0, tokens: 0, cost: 0 });
      row.requests += s.requests || 0;
      row.tokens += s.tokens || 0;
      row.cost += s.cost || 0;
    }
  }
  return Object.values(rows).sort((a, b) => b.cost - a.cost);
}

const cacheHit = s => {
  const denom = (s.cacheReadTokens || 0) + (s.inputTokens || 0);
  return denom ? ((s.cacheReadTokens || 0) / denom * 100).toFixed(1) + "%" : "—";
};

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
  const q = DATA.quota || {};
  const plan = q.startsAt && q.endsAt
    ? "套餐周期 " + q.startsAt.slice(0, 10) + " ~ " + q.endsAt.slice(0, 10)
    : "套餐周期未知";
  document.getElementById("meta").textContent =
    DATA.name + " · " + plan + " · 生成于 " + DATA.generatedAt.replace("T", " ").slice(0, 19);
  const warning = document.getElementById("accountWarning");
  warning.textContent = DATA.warning || "";
  warning.hidden = !DATA.warning;
  document.getElementById("footer").textContent =
    "数据来源：OpenCode Console v2 用量导出（天 × 模型）；按密钥明细来自请求日志（保留 30 天，9/22 起有记录）。报告每 10 分钟自动发布，点击右上角「刷新」即可载入最新数据。";
}

function renderAccountSelect() {
  const select = document.getElementById("accountSelect");
  select.replaceChildren(...REPORT.accounts.map(account => {
    const option = document.createElement("option");
    option.value = account.id;
    option.textContent = account.name + (account.warning ? "（历史快照）" : "");
    option.selected = account.id === state.account;
    return option;
  }));
  select.hidden = REPORT.accounts.length < 2;
}

function selectAccount(id) {
  state.periods[state.account] = state.period;
  DATA = REPORT.accounts.find(account => account.id === id) || REPORT.accounts[0];
  state.account = DATA.id;
  const previousPeriod = state.periods[DATA.id];
  state.period = DATA.periods.some(period => period.key === previousPeriod)
    ? previousPeriod : DATA.defaultPeriod;
  try { localStorage.setItem("oc-account", DATA.id); } catch (e) {}
  renderAccountSelect();
  renderPeriodSelect();
  renderAll();
}

function renderPeriodSelect() {
  const select = document.getElementById("periodSelect");
  select.innerHTML = DATA.periods.map(p =>
    '<option value="' + p.key + '"' + (p.key === state.period ? " selected" : "") + ">" +
    p.label + " · " + p.start + " ~ " + p.end + "</option>").join("");
}

function renderCards() {
  const cards = document.getElementById("cards");
  const days = periodDays();
  const t = sumDays(days);
  const monthly = (DATA.quota.windows || {}).month;
  const withData = days.filter(d => d.requests || d.tokens || d.cost).length;
  const splitDays = days.filter(d => d.groups).length;
  const hit = periodHit(days);
  const coverage = splitDays && splitDays < withData ? "（wt/yy 覆盖 " + splitDays + "/" + withData + " 天）" : "";
  const hitCoverage = hit.covered && hit.covered < withData ? "（覆盖 " + hit.covered + "/" + withData + " 天）" : "";
  const items = [
    {
      label: "总费用",
      value: fmtUSD(t.cost),
      sub: "wt " + fmtUSD(groupSum(days, "wt", "cost")) + " · yy " + fmtUSD(groupSum(days, "yy", "cost")) + coverage,
    },
    {
      label: "当前套餐月额度剩余",
      value: monthly ? fmtQuotaUSD(monthly.limit - monthly.usage) : "—",
      sub: monthly ? "已用 " + monthly.percent + "% · 总额度 " + fmtQuotaUSD(monthly.limit) + "（实时）" : "未订阅或不可用",
    },
    {
      label: "总 Token",
      value: fmtTokens(t.tokens),
      sub: "wt " + fmtTokens(groupSum(days, "wt", "tokens")) + " · yy " + fmtTokens(groupSum(days, "yy", "tokens")),
    },
    {
      label: "缓存命中率",
      value: hit.covered ? hit.value : cacheHit(t),
      sub: hit.covered
        ? "wt " + groupHit(days, "wt") + " · yy " + groupHit(days, "yy") + hitCoverage
        : "请求日志无记录，按官方导出计算",
    },
    {
      label: "总请求数",
      value: fmtInt(t.requests),
      sub: "wt " + fmtInt(groupSum(days, "wt", "requests")) + " · yy " + fmtInt(groupSum(days, "yy", "requests")),
    },
    {
      label: "日均费用",
      value: fmtUSD(t.cost / (days.length || 1)),
      sub: "wt " + fmtUSD(groupSum(days, "wt", "cost") / (days.length || 1)) + " · yy " + fmtUSD(groupSum(days, "yy", "cost") / (days.length || 1)),
    },
  ];
  cards.innerHTML = "";
  for (const item of items) {
    cards.append(el("div", "card",
      '<div class="label">' + item.label + '</div><div class="value">' + item.value + '</div><div class="sub">' + item.sub + "</div>"));
  }
}

function renderQuota() {
  const box = document.getElementById("quota");
  const note = document.getElementById("quotaNote");
  const badge = document.getElementById("quotaBadge");
  badge.textContent = DATA.warning ? "历史快照" : "实时";
  badge.classList.toggle("live", !DATA.warning);
  box.innerHTML = "";
  if (DATA.quota.error) { box.append(el("div", "card", DATA.quota.error)); return; }
  if (!DATA.quota.subscribed) {
    box.append(el("div", "card", "当前工作区未订阅 OpenCode Go。"));
    document.getElementById("quotaBadge").textContent = "未订阅";
    document.getElementById("quotaBadge").classList.remove("live");
    note.textContent = "";
    return;
  }
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
  note.textContent =
    "额度窗口：5 小时 = 月额度的 20%，每周 = 50%，每月 = 100%。";
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
  const days = periodDays();
  const labels = days.map(d => d.date.slice(5));
  const plotWidth = Math.min(560, Math.max(300, days.length * 56 + 140));
  document.querySelectorAll(".chart-wrap").forEach(node => {
    node.style.maxWidth = plotWidth + "px";
  });
  const bar = { maxBarThickness: 28, borderRadius: 4 };
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
      datasets: ["wt", "yy"].map((group, i) => ({
        label: GROUP_LABEL[group],
        data: days.map(day => day.groups ? day.groups[group].cost : 0),
        backgroundColor: i ? "#f5a54a" : "#4f8cff",
        ...bar,
      })),
    },
    options: { ...base, plugins: { ...base.plugins, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ": " + fmtUSD(ctx.parsed.y) } } } },
  });
  tokenChart = new Chart(document.getElementById("tokenChart"), {
    type: "bar",
    data: {
      labels,
      datasets: ["wt", "yy"].map((group, i) => ({
        label: GROUP_LABEL[group],
        data: days.map(day => day.groups ? day.groups[group].tokens : 0),
        backgroundColor: i ? "#f5a54a" : "#4f8cff",
        ...bar,
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
  const days = periodDays();
  const totals = sumDays(days);
  const rows = days.slice().reverse().filter(d => d.requests || d.tokens || d.cost).map(d => [
    d.date,
    fmtInt(d.requests),
    d.groups ? fmtInt(d.groups.wt.tokens) : "—",
    d.groups ? fmtInt(d.groups.yy.tokens) : "—",
    "<strong>" + fmtInt(d.tokens) + "</strong>",
    d.groups ? fmtUSD(d.groups.wt.cost) : "—",
    d.groups ? fmtUSD(d.groups.yy.cost) : "—",
    "<strong>" + fmtUSD(d.cost) + "</strong>",
  ]);
  if (!rows.length) {
    rows.push(['<span style="color:#8b93a7">该周期暂无用量数据</span>', "", "", "", "", "", "", ""]);
  }
  table("dailyTable",
    ["日期", "请求数", "wt Tokens", "yy Tokens", "合计 Tokens", "wt 费用", "yy 费用", "合计费用"],
    rows.concat([[
      "<strong>合计</strong>",
      "<strong>" + fmtInt(totals.requests) + "</strong>",
      "<strong>" + fmtInt(groupSum(days, "wt", "tokens")) + "</strong>",
      "<strong>" + fmtInt(groupSum(days, "yy", "tokens")) + "</strong>",
      "<strong>" + fmtInt(totals.tokens) + "</strong>",
      "<strong>" + fmtUSD(groupSum(days, "wt", "cost")) + "</strong>",
      "<strong>" + fmtUSD(groupSum(days, "yy", "cost")) + "</strong>",
      "<strong>" + fmtUSD(totals.cost) + "</strong>",
    ]]));

  const keys = keyRows(days);
  if (keys.length) {
    table("keyTable",
      ["密钥", "分组", "请求数", "输入", "输出", "缓存读取", "缓存命中率", "合计 Tokens", "费用(USD)"],
      keys.map(k => [
        k.name + '<span class="tag ' + k.group + '">' + k.group + "</span>",
        k.group,
        fmtInt(k.requests),
        fmtInt(k.inputTokens),
        fmtInt(k.outputTokens),
        fmtInt(k.cacheReadTokens),
        cacheHit(k),
        fmtInt(k.tokens),
        fmtUSD(k.cost),
      ]));
    if (DATA.keysFetchedAt) {
      document.getElementById("keyNote").textContent =
        "按密钥：请求数/Token/缓存命中率来自请求日志（保留 30 天、9/22 起有记录，本周期已缓存 " + DATA.keysDays + " 天），费用另含 9/13~9/21 快照按日折算；缓存时间 " + DATA.keysFetchedAt.replace("T", " ").slice(0, 19) + "。";
    }
  } else {
    table("keyTable", ["密钥", "分组", "请求数", "输入", "输出", "缓存读取", "缓存命中率", "合计 Tokens", "费用(USD)"], [
      ['<span style="color:#8b93a7">该周期暂无按密钥明细（请求日志仅保留 30 天）</span>', "", "", "", "", "", "", "", ""],
    ]);
    document.getElementById("keyNote").textContent =
      "按密钥明细来自请求日志（保留 30 天、9/22 起有记录），该周期内没有可用的密钥级数据。";
  }

  const models = modelRows(days);
  table("modelTable",
    ["模型", "请求数", "Token", "费用", "占比"],
    (models.length ? models : [{ model: null }]).map(m => m.model === null
      ? ['<span style="color:#8b93a7">该周期暂无模型数据</span>', "", "", "", ""]
      : [
        m.model,
        fmtInt(m.requests),
        fmtInt(m.tokens),
        fmtUSD(m.cost),
        totals.cost ? ((m.cost / totals.cost) * 100).toFixed(1) + "%" : "0%",
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

function renderAll() {
  renderMeta();
  renderCards();
  renderQuota();
  renderCharts();
  renderTables();
  tick();
}

function tick() {
  document.querySelectorAll(".countdown").forEach(node => {
    node.textContent = countdown(node.dataset.reset);
  });
}

const REFRESH_IDLE_LABEL = "刷新";
const REFRESH_IDLE_TITLE = "获取最新发布的报告（每 10 分钟自动发布一次）";
let refreshResetTimer;

function setRefreshState(label, { loading = false, failed = false, success = false, title } = {}) {
  const button = document.getElementById("refreshBtn");
  document.getElementById("refreshLabel").textContent = label;
  button.classList.toggle("loading", loading);
  button.classList.toggle("failed", failed);
  button.classList.toggle("success", success);
  button.disabled = loading;
  button.title = title || REFRESH_IDLE_TITLE;
}

function scheduleRefreshReset() {
  clearTimeout(refreshResetTimer);
  refreshResetTimer = setTimeout(() => setRefreshState(REFRESH_IDLE_LABEL), 2600);
}

function parseReportData(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const node = doc.getElementById("reportData");
  if (!node) throw new Error("未找到报告数据，登录可能已过期");
  return JSON.parse(node.textContent);
}

function applyReportData(next) {
  if (!next || !Array.isArray(next.accounts) || !next.accounts.length ||
      next.accounts.some(account => !Array.isArray(account.periods) || !account.periods.length ||
        !Array.isArray(account.days) || !account.dayModels || !account.keyDays || !account.quota)) {
    throw new Error("报告数据格式不完整");
  }
  REPORT = next;
  selectAccount(state.account);
}

async function refreshReport() {
  const button = document.getElementById("refreshBtn");
  if (button.disabled) return;
  if (location.protocol === "file:") {
    location.reload();
    return;
  }
  clearTimeout(refreshResetTimer);
  setRefreshState("刷新中…", { loading: true });
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const url = new URL(location.href);
    url.searchParams.set("_refresh", Date.now().toString(36));
    const response = await fetch(url.toString(), {
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const next = parseReportData(await response.text());
    if (next.generatedAt === REPORT.generatedAt) {
      setRefreshState("已是最新", { success: true });
    } else {
      applyReportData(next);
      setRefreshState("已更新", { success: true });
    }
  } catch (error) {
    if (error.name === "AbortError") error = new Error("请求超时");
    setRefreshState("刷新失败", {
      failed: true,
      title: "刷新失败：" + error.message + "（点击重试）",
    });
  } finally {
    clearTimeout(timeout);
    scheduleRefreshReset();
  }
}

document.getElementById("refreshBtn").addEventListener("click", refreshReport);
document.getElementById("accountSelect").addEventListener("change", event => {
  selectAccount(event.target.value);
});
document.getElementById("themeToggle").addEventListener("click", () => {
  applyTheme(currentTheme() === "light" ? "dark" : "light");
});
document.getElementById("periodSelect").addEventListener("change", event => {
  state.period = event.target.value;
  renderAll();
});
document.getElementById("themeToggle").textContent = currentTheme() === "light" ? "深色模式" : "浅色模式";
renderAccountSelect();
renderPeriodSelect();
renderAll();
setInterval(tick, 30000);
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an HTML usage report")
    parser.add_argument(
        "--days",
        type=int,
        help="number of days (default: current OpenCode Go billing period up to today)",
    )
    parser.add_argument(
        "--workspace", help="query a single workspace instead of accounts"
    )
    parser.add_argument("--profile", help="Chrome profile dir name, e.g. Default")
    parser.add_argument(
        "--accounts", default=str(ACCOUNTS_CONFIG), help="path to accounts JSON config"
    )
    parser.add_argument(
        "--max-pages", type=int, default=200, help="usage.list page cap"
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
        data = build_data(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    chartjs = load_chartjs()
    data_json = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.replace("__CHARTJS__", chartjs or "").replace("__DATA__", data_json)
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

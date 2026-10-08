#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Query commandcode.ai usage through the local Chrome login.

Examples:
    uv run commandcode_usage.py                  # current billing period
    uv run commandcode_usage.py --by-model
    uv run commandcode_usage.py --json > usage.json
"""

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SITE = "commandcode.ai"
COOKIE_HOST = ".commandcode.ai"
API_BASE = "https://api.commandcode.ai"
PAGE_SIZE = 100
CHROME_ROOT = Path(
    os.environ.get("CHROME_CONFIG_DIR", "~/.config/google-chrome")
).expanduser()


def get_keyring_secret() -> bytes:
    try:
        import secretstorage

        bus = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(bus)
        for wanted in ("chrome", "chromium"):
            items = list(collection.search_items({"application": wanted}))
            if items:
                return bytes(items[0].get_secret())
    except Exception:  # noqa: BLE001
        return b"peanuts"
    return b"peanuts"


def decrypt_cookie(encrypted: bytes, secret: bytes) -> str:
    if encrypted[:3] not in (b"v10", b"v11"):
        raise ValueError(f"unsupported cookie encryption: {encrypted[:4]!r}")
    key = hashlib.pbkdf2_hmac("sha1", secret, b"saltysalt", 1, 16)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    plain = decryptor.update(encrypted[3:]) + decryptor.finalize()
    plain = plain[: -plain[-1]]
    for host in (COOKIE_HOST, COOKIE_HOST.lstrip(".")):
        if plain[:32] == hashlib.sha256(host.encode()).digest():
            plain = plain[32:]
            break
    return plain.decode("utf-8", "replace")


def find_profile() -> Path:
    candidates = [CHROME_ROOT / "Default"] + sorted(CHROME_ROOT.glob("Profile *"))
    for profile in candidates:
        db = profile / "Cookies"
        if not db.exists():
            continue
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                found = conn.execute(
                    "select count(*) from cookies where host_key like ?",
                    ("%commandcode%",),
                ).fetchone()[0]
            if found:
                return profile
        except sqlite3.Error:
            continue
    raise RuntimeError(f"no Chrome profile with {SITE} cookies under {CHROME_ROOT}")


def load_cookies(secret: bytes, profile: Path | None = None) -> dict[str, str]:
    profile = profile or find_profile()
    db = profile / "Cookies"
    cookies = {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "select host_key, name, encrypted_value from cookies where host_key like ?",
            ("%commandcode%",),
        )
        for host, name, encrypted in rows:
            cookies[name] = decrypt_cookie(encrypted, secret) if encrypted else ""
    session = {k: v for k, v in cookies.items() if k.startswith("__Secure-")}
    if not session:
        raise RuntimeError(
            f"no console session for {SITE} in {profile}; log in via Chrome first"
        )
    return session


def auth_headers(profile: Path | None = None) -> dict[str, str]:
    cookies = load_cookies(get_keyring_secret(), profile)
    cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return {"Cookie": cookie}


def call_api(
    path: str,
    params: dict | None = None,
    headers: dict | None = None,
    method: str = "GET",
    data: dict | None = None,
) -> dict:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{query}"
    body = json.dumps(data).encode() if data is not None else None
    last_error: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(0.5 * 2**attempt + random.random())
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36",
                "Origin": f"https://{SITE}",
                "Referer": f"https://{SITE}/",
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"HTTP {exc.code} on {path}: {detail}") from exc
            last_error = exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
    raise RuntimeError(f"request failed after retries: {last_error}")


def fetch_charts(start: date, end: date, headers: dict) -> list[dict]:
    data = call_api(
        "/internal/usage/charts",
        {"from": start.isoformat(), "to": end.isoformat(), "granularity": "day"},
        headers,
    )
    return data.get("data", []) if isinstance(data, dict) else []


def fetch_summary(headers: dict) -> dict:
    return call_api("/internal/usage/summary", None, headers)


def fetch_credits(headers: dict) -> dict:
    data = call_api("/internal/billing/credits", None, headers)
    credits = data.get("credits") or {}
    limits = data.get("windowLimits") or {}
    windows = {}
    for scope, label in (("fiveHour", "5 小时"), ("weekly", "每周")):
        meter = limits.get(scope)
        if not meter:
            continue
        cap = float(meter.get("cap") or 0)
        used = float(meter.get("used") or 0)
        reset_at = meter.get("resetAt")
        windows[scope] = {
            "label": label,
            "usage": used,
            "limit": cap,
            "percent": round(used / cap * 100, 1) if cap else 0.0,
            "resetsAt": (
                datetime.fromtimestamp(reset_at / 1000, tz=timezone.utc).isoformat()
                if reset_at
                else None
            ),
        }
    granted = float(credits.get("monthlyCreditsGranted") or 0)
    remaining = float(credits.get("monthlyCredits") or 0)
    used = max(0.0, granted - remaining)
    windows["month"] = {
        "label": "每月",
        "usage": used,
        "limit": granted,
        "percent": round(used / granted * 100, 1) if granted else 0.0,
        "resetsAt": None,
    }
    return {
        "remaining": remaining,
        "purchased": float(credits.get("purchasedCredits") or 0),
        "granted": granted,
        "windows": windows,
    }


def fetch_subscription(headers: dict) -> dict:
    data = call_api("/internal/billing/subscriptions", None, headers)
    return (data.get("data") or {}) if isinstance(data, dict) else {}


def fetch_requests(headers: dict, max_pages: int = 5) -> list[dict]:
    items: list[dict] = []
    cursor: str | None = None
    for _ in range(max_pages):
        params: dict = {"limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        data = call_api("/internal/usage", params, headers)
        page = data.get("items") or data.get("usages") or []
        items.extend(page)
        cursor = data.get("nextCursor")
        if not page or not cursor:
            break
    return items


def fetch_keys(headers: dict) -> list[dict]:
    data = call_api(
        "/internal/api-keys/list", None, headers, method="POST", data={"orgId": None}
    )
    return data if isinstance(data, list) else []


def group_of(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("wty"):
        return "wty"
    if lowered.startswith("wt"):
        return "wt"
    return "xfy"


def empty_stats() -> dict:
    return {
        "requests": 0,
        "tokensIn": 0,
        "tokensOut": 0,
        "cacheRead": 0,
        "cacheCreation": 0,
        "tokens": 0,
        "apiCost": 0.0,
        "credits": 0.0,
        "cacheSavings": 0.0,
    }


def add_row(stats: dict, row: dict) -> None:
    stats["requests"] += int(row.get("requests") or 0)
    stats["tokensIn"] += int(row.get("tokensIn") or 0)
    stats["tokensOut"] += int(row.get("tokensOut") or 0)
    stats["cacheRead"] += int(row.get("cacheReadInputTokens") or 0)
    stats["cacheCreation"] += int(row.get("cacheCreationInputTokens") or 0)
    stats["tokens"] += int(row.get("tokensTotal") or 0)
    stats["apiCost"] += float(row.get("totalCost") or 0.0)
    stats["credits"] += float(row.get("consumedTotal") or 0.0)
    stats["cacheSavings"] += float(row.get("cacheSavings") or 0.0)


def round_stats(stats: dict) -> dict:
    for field in ("apiCost", "credits", "cacheSavings"):
        if stats[field] is not None:
            stats[field] = round(stats[field], 6)
    return stats


def merge_stats(stats: dict, entry: dict) -> None:
    for field in empty_stats():
        if stats[field] is None or entry[field] is None:
            stats[field] = None
        else:
            stats[field] += entry[field]


def billing_totals(summary: dict) -> dict:
    return {
        "requests": int(summary.get("totalCount") or 0),
        "tokensIn": int(summary.get("totalTokensIn") or 0),
        "tokensOut": int(summary.get("totalTokensOut") or 0),
        "tokens": int(summary.get("totalTokens") or 0),
        "credits": float(summary.get("totalCredits", summary.get("totalCost")) or 0),
    }


def build_summary(args) -> dict:
    profile = Path(args.profile).expanduser() if args.profile else None
    headers = auth_headers(profile)
    subscription = fetch_subscription(headers)
    period_start_iso = subscription.get("currentPeriodStart")
    period_end = subscription.get("currentPeriodEnd")
    if not period_start_iso or not period_end:
        raise RuntimeError("no current subscription billing period is available")
    period_start = datetime.fromisoformat(period_start_iso.replace("Z", "+00:00"))
    period_start = period_start.astimezone(timezone.utc)
    today = datetime.now(timezone.utc).date()
    cutoff = period_start.date()
    if cutoff > today:
        raise RuntimeError("subscription billing period has not started yet")
    dates = [
        cutoff + timedelta(days=offset) for offset in range((today - cutoff).days + 1)
    ]
    partial_start_day = period_start.time() != datetime.min.time()

    # Daily chart filters apply to UTC buckets, not individual request timestamps.
    # Read a stable billing summary around the chart query before deriving day one.
    for _ in range(3):
        before = fetch_summary(headers)
        chart_rows = fetch_charts(cutoff, today + timedelta(days=1), headers)
        period_summary = fetch_summary(headers)
        if billing_totals(before) == billing_totals(period_summary):
            break
    else:
        raise RuntimeError(
            "usage changed during collection; retry for a consistent report"
        )
    if period_summary.get("periodBasis") != "billing-period":
        raise RuntimeError(
            "usage summary is not scoped to the subscription billing period"
        )
    exact_totals = billing_totals(period_summary)

    daily: dict[str, dict] = {}
    models: dict[str, dict] = {}
    first_day_rows = []
    for row in chart_rows:
        day = (row.get("timeBucket") or "")[:10]
        if not (cutoff.isoformat() <= day <= today.isoformat()):
            continue
        if partial_start_day and day == cutoff.isoformat():
            first_day_rows.append(row)
            continue
        add_row(daily.setdefault(day, empty_stats()), row)
        bucket = models.setdefault(
            row.get("model") or "unknown", empty_stats() | {"providers": set()}
        )
        add_row(bucket, row)
        if row.get("provider"):
            bucket["providers"].add(row["provider"])

    days = []
    for day in dates:
        iso = day.isoformat()
        stats = daily.get(iso, empty_stats()).copy()
        days.append({"date": iso, **stats})

    if partial_start_day:
        # The exact first-day core metrics are the period total minus later days.
        # Cache and raw API-price fields have no exact billing-period counterpart.
        first_day = empty_stats()
        for field, value in exact_totals.items():
            remainder = value - sum(day[field] for day in days[1:])
            if remainder < -1e-6:
                raise RuntimeError("daily usage exceeds the billing-period summary")
            first_day[field] = max(0, remainder)
        for field in ("cacheRead", "cacheCreation", "apiCost", "cacheSavings"):
            first_day[field] = None
        days[0] = {"date": cutoff.isoformat(), **first_day}

        if first_day["requests"] or first_day["tokens"] or first_day["credits"]:
            first_models = {row.get("model") or "unknown" for row in first_day_rows}
            # A single model for the whole UTC day also identifies its period slice.
            model = (
                next(iter(first_models))
                if len(first_models) == 1
                else "账单首日（模型未拆分）"
            )
            bucket = models.setdefault(model, empty_stats() | {"providers": set()})
            merge_stats(bucket, first_day)
            if len(first_models) == 1:
                bucket["providers"].update(
                    row["provider"] for row in first_day_rows if row.get("provider")
                )

    totals = empty_stats()
    for entry in days:
        merge_stats(totals, entry)
    if any(abs(totals[field] - value) > 1e-6 for field, value in exact_totals.items()):
        raise RuntimeError(
            "daily usage does not match the billing-period summary; retry"
        )
    totals.update(exact_totals)
    totals = round_stats(totals)
    for day in days:
        round_stats(day)

    model_rows = []
    for model, stats in models.items():
        stats = round_stats(stats)
        model_rows.append(
            {
                "model": model,
                "providers": sorted(stats.pop("providers")),
                **stats,
            }
        )
    model_rows.sort(key=lambda entry: -entry["credits"])

    requests = []
    for item in fetch_requests(headers):
        created_at = item.get("createdAt")
        if not created_at:
            continue
        if datetime.fromisoformat(created_at.replace("Z", "+00:00")) < period_start:
            continue
        meta = item.get("meta") or {}
        requests.append(
            {
                "id": item.get("id"),
                "createdAt": item.get("createdAt"),
                "model": meta.get("model"),
                "tokensIn": int(item.get("tokensIn") or 0),
                "tokensOut": int(item.get("tokensOut") or 0),
                "durationMs": int(item.get("durationTotal") or 0),
                "status": item.get("status"),
                "mode": item.get("mode"),
                "cost": float(meta.get("totalCost") or 0.0),
                "traceId": meta.get("traceId"),
            }
        )

    keys = []
    for key in fetch_keys(headers):
        name = key.get("name") or key.get("id") or "unknown"
        keys.append(
            {
                "id": key.get("id"),
                "name": name,
                "group": group_of(name),
                "createdAt": key.get("createdAt"),
                "description": key.get("description") or "",
            }
        )
    keys.sort(key=lambda entry: entry["createdAt"] or "")

    quota = fetch_credits(headers)
    if period_end and "month" in quota["windows"]:
        quota["windows"]["month"]["resetsAt"] = period_end

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "site": SITE,
        "range": [dates[0].isoformat(), dates[-1].isoformat()],
        "days": days,
        "totals": totals,
        "models": model_rows,
        "requests": requests,
        "keys": keys,
        "quota": quota,
        "billing": {
            "planId": subscription.get("planId"),
            "status": subscription.get("status"),
            "cancelAtPeriodEnd": subscription.get("cancelAtPeriodEnd", False),
            "periodStart": period_start_iso,
            "periodEnd": period_end,
            "partialStartDay": partial_start_day,
            "summary": period_summary,
        },
    }


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, width: int, right: bool = False) -> str:
    fill = " " * max(0, width - display_width(text))
    return fill + text if right else text + fill


def print_table(summary: dict, by_model: bool) -> None:
    headers = [
        ("日期", False),
        ("请求数", True),
        ("输入", True),
        ("输出", True),
        ("缓存读取", True),
        ("合计 Tokens", True),
        ("API 费用", True),
        ("Credits", True),
    ]
    align = [a for _, a in headers]
    widths = [max(display_width(h), 12) for h, _ in headers]

    def row(values):
        cells = [pad(str(v), w, a) for v, w, a in zip(values, widths, align)]
        return "  ".join(cells)

    billing = summary["billing"]
    print(
        f"commandcode 套餐用量: {billing['periodStart']} ~ {billing['periodEnd']}"
        f"（截至 {summary['generatedAt']}）"
    )
    print(row([h for h, _ in headers]))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    for day in summary["days"]:
        print(
            row(
                [
                    day["date"],
                    day["requests"],
                    f"{day['tokensIn']:,}",
                    f"{day['tokensOut']:,}",
                    f"{day['cacheRead']:,}" if day["cacheRead"] is not None else "—",
                    f"{day['tokens']:,}",
                    f"${day['apiCost']:.4f}" if day["apiCost"] is not None else "—",
                    f"{day['credits']:.4f}",
                ]
            )
        )
    total = summary["totals"]
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    print(
        row(
            [
                "合计",
                total["requests"],
                f"{total['tokensIn']:,}",
                f"{total['tokensOut']:,}",
                f"{total['cacheRead']:,}" if total["cacheRead"] is not None else "—",
                f"{total['tokens']:,}",
                f"${total['apiCost']:.4f}" if total["apiCost"] is not None else "—",
                f"{total['credits']:.4f}",
            ]
        )
    )
    quota = summary["quota"]
    print(
        f"\n月度额度: 剩余 {quota['remaining']:.2f} / {quota['granted']:.2f} credits"
        f"（已用 {quota['windows']['month']['percent']}%）"
    )
    if by_model and summary["models"]:
        print("\n按模型:")
        for entry in summary["models"]:
            providers = ",".join(entry["providers"])
            api_cost = (
                f"${entry['apiCost']:.4f}" if entry["apiCost"] is not None else "—"
            )
            print(
                f"  {pad(entry['model'], 36)} {pad(providers, 20)}"
                f" {api_cost}  {entry['credits']:.4f} credits"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Query commandcode.ai usage")
    parser.add_argument(
        "--profile",
        help="Chrome profile dir path, e.g. ~/.config/google-chrome/Default",
    )
    parser.add_argument("--by-model", action="store_true", help="show usage per model")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    try:
        summary = build_summary(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_table(summary, args.by_model)


if __name__ == "__main__":
    main()

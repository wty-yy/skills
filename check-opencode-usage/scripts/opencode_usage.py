#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Query opencode.ai console usage through a service API key or Chrome cookies.

Examples:
    uv run opencode_usage.py                  # last 7 days
    uv run opencode_usage.py --days 30
    uv run opencode_usage.py --by-model
    uv run opencode_usage.py --by-key
    uv run opencode_usage.py --json > usage.json
"""

import argparse
import csv
import hashlib
import io
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
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HOST = "opencode.ai"
API_BASE = "https://opencode.ai/console/api"
DEFAULT_WORKSPACE = "wrk_01M28NK08E0YZ4DEHF128QZYH6"
PAGE_SIZE = 100
COST_SCALE = 1e8
CHROME_ROOT = Path(
    os.environ.get("CHROME_CONFIG_DIR", "~/.config/google-chrome")
).expanduser()
TOKEN_FIELDS = ("inputTokens", "outputTokens", "reasoningTokens", "cacheReadTokens")
KEY_CACHE = Path(__file__).parent / "key_cache.json"
KEY_FETCH_BUDGET = 4


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
    if plain[:32] == hashlib.sha256(HOST.encode()).digest():
        plain = plain[32:]
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
                    "select count(*) from cookies where host_key = ?", (HOST,)
                ).fetchone()[0]
            if found:
                return profile
        except sqlite3.Error:
            continue
    raise RuntimeError(f"no Chrome profile with {HOST} cookies under {CHROME_ROOT}")


def load_cookies(secret: bytes, profile: Path | None = None) -> dict[str, str]:
    profile = profile or find_profile()
    db = profile / "Cookies"
    cookies = {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "select name, encrypted_value from cookies where host_key = ?", (HOST,)
        )
        for name, encrypted in rows:
            cookies[name] = decrypt_cookie(encrypted, secret)
    if not ({"__Host-console_session", "auth"} & set(cookies)):
        raise RuntimeError(
            f"no console session for {HOST} in {profile}; log in via Chrome first"
        )
    return cookies


def auth_header_sets(
    workspace: str, profile: Path | None = None
) -> list[dict[str, str]]:
    sets: list[dict[str, str]] = []
    key = os.environ.get("OPENCODE_API_KEY", "")
    if key:
        sets.append({"Authorization": f"Bearer {key}"})
    try:
        cookies = load_cookies(get_keyring_secret(), profile)
        cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())
        sets.append({"Cookie": cookie, "x-org-id": workspace})
    except RuntimeError:
        pass
    if not sets:
        raise RuntimeError("no OPENCODE_API_KEY and no Chrome console session")
    return sets


def call_api(
    path: str,
    params: dict | None = None,
    header_sets: list[dict] | None = None,
    raw: bool = False,
) -> str:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{query}"
    header_sets = header_sets or [{}]
    last_error: Exception | None = None
    for index, headers in enumerate(header_sets):
        for attempt in range(4):
            if attempt:
                time.sleep(0.5 * 2**attempt + random.random())
            request_headers = {
                "Accept": "text/csv" if raw else "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36",
                "Origin": "https://opencode.ai",
                "Referer": "https://opencode.ai/console/",
                **headers,
            }
            try:
                request = urllib.request.Request(url, headers=request_headers)
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = response.read().decode("utf-8", "replace")
                return body if raw else json.loads(body)
            except urllib.error.HTTPError as exc:
                detail = exc.read()[:200].decode("utf-8", "replace")
                if exc.code in (401, 403) and index + 1 < len(header_sets):
                    break
                if exc.code < 500 and exc.code != 429:
                    raise RuntimeError(f"HTTP {exc.code} on {path}: {detail}") from exc
                last_error = exc
            except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
                last_error = exc
    raise RuntimeError(f"request failed after retries: {last_error}")


def usage_range(days: int) -> str:
    if days <= 7:
        return "7d"
    if days <= 30:
        return "30d"
    return "90d"


def fetch_usage(days: int, header_sets: list[dict]) -> list[dict]:
    body = call_api(
        "/v2/usage/export", {"range": usage_range(days)}, header_sets, raw=True
    )
    return list(csv.DictReader(io.StringIO(body)))


def fetch_key_names(header_sets: list[dict]) -> dict[str, dict]:
    data = call_api("/service-accounts", {"page": 1, "pageSize": 100}, header_sets)
    names: dict[str, dict] = {}
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items:
        for key in item.get("keys", []):
            names[key["id"]] = {
                "displayName": key["name"],
                "deleted": key.get("status") != "active",
            }
    return names


def fetch_quota(header_sets: list[dict]) -> dict:
    data = call_api("/go/status", None, header_sets)
    access = data.get("access") or {}
    meters = access.get("meters") or {}
    windows = {}
    for scope, label in (
        ("fiveHour", "5 小时"),
        ("week", "每周"),
        ("month", "每月"),
    ):
        meter = meters.get(scope)
        if not meter:
            continue
        limit = int(meter["limitMicroCents"])
        usage = int(meter["usedMicroCents"])
        resets_at = meter.get("resetsAt")
        if resets_at is None and scope == "month":
            resets_at = access.get("endsAt")
        windows[scope] = {
            "label": label,
            "usage": usage,
            "limit": limit,
            "percent": round(usage / limit * 100, 1) if limit else 0.0,
            "resetsAt": resets_at,
        }
    return {
        "subscribed": bool(access),
        "windows": windows,
        "startsAt": access.get("startsAt"),
        "endsAt": access.get("endsAt"),
        "cancelAtPeriodEnd": access.get("cancelAtPeriodEnd", False),
        "useBalance": data.get("useBalance", False),
    }


def empty_stats() -> dict:
    return {"requests": 0, **dict.fromkeys(TOKEN_FIELDS, 0)}


def total_tokens(stats: dict) -> int:
    return sum(stats.get(field) or 0 for field in TOKEN_FIELDS)


def aggregate_usage(rows: list[dict], cutoff: date, today: date) -> tuple[dict, dict]:
    daily: dict[str, dict] = {}
    models: dict[str, dict] = {}
    for row in rows:
        day = row["day"]
        if not (cutoff.isoformat() <= day <= today.isoformat()):
            continue
        cost = int(row["cost_micro_cents"] or 0) / COST_SCALE
        for stats in (
            daily.setdefault(day, empty_stats() | {"cost": 0.0}),
            models.setdefault(row["model"], empty_stats() | {"cost": 0.0}),
        ):
            stats["requests"] += int(row["requests"] or 0)
            stats["inputTokens"] += int(row["input_tokens"] or 0)
            stats["outputTokens"] += int(row["output_tokens"] or 0)
            stats["cacheReadTokens"] += int(row["cache_read_tokens"] or 0)
            stats["cost"] += cost
    return daily, models


def load_key_cache() -> dict:
    try:
        return json.loads(KEY_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"days": {}}


def save_key_cache(cache: dict) -> None:
    KEY_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def fetch_day_keys(day: str, header_sets: list[dict]) -> dict[str, dict]:
    cursor: str | None = None
    stats: dict[str, dict] = {}
    for _ in range(50):
        params: dict = {"day": day, "category": "inference", "limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        data = call_api("/request-logs", params, header_sets)
        items = data.get("items", []) if isinstance(data, dict) else []
        for item in items:
            key_id = item.get("serviceAPIKeyID") or "unknown"
            bucket = stats.setdefault(key_id, empty_stats() | {"cost": 0.0})
            bucket["requests"] += 1
            for field in TOKEN_FIELDS:
                bucket[field] += item.get(field) or 0
            bucket["cost"] += item.get("cost") or 0.0
        cursor = data.get("nextCursor") if isinstance(data, dict) else None
        if not items or not cursor:
            break
    return stats


def fetch_key_stats(
    cutoff: date, today: date, header_sets: list[dict], budget: int = KEY_FETCH_BUDGET
) -> tuple[dict, str | None]:
    cache = load_key_cache()
    days_cache = cache.setdefault("days", {})
    days = [
        date.fromordinal(o) for o in range(cutoff.toordinal(), today.toordinal() + 1)
    ]
    fetched = 0
    for day in reversed(days):
        iso = day.isoformat()
        is_today = iso == today.isoformat()
        entry = days_cache.get(iso)
        if entry and not is_today:
            continue
        if fetched >= budget:
            break
        try:
            stats = fetch_day_keys(iso, header_sets)
        except RuntimeError:
            break
        days_cache[iso] = {
            "fetchedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "keys": stats,
        }
        fetched += 1
    for iso in list(days_cache):
        if iso < cutoff.isoformat():
            del days_cache[iso]
    save_key_cache(cache)

    key_stats: dict[str, dict] = {}
    fetched_at: str | None = None
    days_count = 0
    for iso, entry in days_cache.items():
        if not (cutoff.isoformat() <= iso <= today.isoformat()):
            continue
        fetched_at = max(fetched_at or "", entry.get("fetchedAt") or "") or None
        if entry.get("keys"):
            days_count += 1
        for key_id, stats in entry.get("keys", {}).items():
            agg = key_stats.setdefault(key_id, empty_stats() | {"cost": 0.0})
            agg["requests"] += stats.get("requests") or 0
            for field in TOKEN_FIELDS:
                agg[field] += stats.get(field) or 0
            agg["cost"] += stats.get("cost") or 0.0
    return key_stats, fetched_at, days_count


def group_of(name: str) -> str:
    return "wt" if name.endswith("wt") else "yy"


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, width: int, right: bool = False) -> str:
    fill = " " * max(0, width - display_width(text))
    return fill + text if right else text + fill


def build_summary(args) -> dict:
    profile = Path(args.profile).expanduser() if args.profile else None
    header_sets = auth_header_sets(args.workspace, profile)
    today = datetime.now().astimezone().date()
    cutoff = today - timedelta(days=args.days - 1)
    dates = [cutoff + timedelta(days=offset) for offset in range(args.days)]

    daily, model_stats = aggregate_usage(
        fetch_usage(args.days, header_sets), cutoff, today
    )

    days = []
    for day in dates:
        iso = day.isoformat()
        stats = daily.get(iso, empty_stats() | {"cost": 0.0})
        days.append(
            {
                "date": iso,
                **stats,
                "tokens": total_tokens(stats),
                "cost": round(stats["cost"], 6),
            }
        )

    totals = empty_stats() | {"cost": 0.0}
    for entry in days:
        for field in TOKEN_FIELDS:
            totals[field] += entry[field]
        totals["requests"] += entry["requests"]
        totals["cost"] += entry["cost"]
    totals["tokens"] = total_tokens(totals)
    totals["cost"] = round(totals["cost"], 6)

    models = [
        {
            "model": model,
            "cost": round(stats["cost"], 6),
            "tokens": total_tokens(stats),
            "requests": stats["requests"],
        }
        for model, stats in sorted(model_stats.items(), key=lambda kv: -kv[1]["cost"])
    ]

    key_stats, keys_fetched_at, _keys_days = fetch_key_stats(cutoff, today, header_sets)
    key_names = fetch_key_names(header_sets)
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

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": args.workspace,
        "range": [dates[0].isoformat(), dates[-1].isoformat()],
        "days": days,
        "totals": totals,
        "keys": keys,
        "keysFetchedAt": keys_fetched_at,
        "models": models,
        "quota": fetch_quota(header_sets),
    }


def print_table(summary: dict, by_model: bool, by_key: bool) -> None:
    headers = [
        ("日期", False),
        ("请求数", True),
        ("输入", True),
        ("输出", True),
        ("缓存读取", True),
        ("合计 Tokens", True),
        ("费用(USD)", True),
    ]
    align = [a for _, a in headers]
    widths = [max(display_width(h), 12) for h, _ in headers]

    def row(values):
        cells = [pad(str(v), w, a) for v, w, a in zip(values, widths, align)]
        return "  ".join(cells)

    print(f"opencode 用量: {summary['range'][0]} ~ {summary['range'][1]}")
    print(row([h for h, _ in headers]))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    for day in summary["days"]:
        print(
            row(
                [
                    day["date"],
                    day["requests"],
                    f"{day['inputTokens']:,}",
                    f"{day['outputTokens']:,}",
                    f"{day['cacheReadTokens']:,}",
                    f"{day['tokens']:,}",
                    f"${day['cost']:.4f}",
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
                f"{total['inputTokens']:,}",
                f"{total['outputTokens']:,}",
                f"{total['cacheReadTokens']:,}",
                f"{total['tokens']:,}",
                f"${total['cost']:.4f}",
            ]
        )
    )
    if by_model and summary["models"]:
        print("\n按模型费用:")
        for entry in summary["models"]:
            print(f"  {pad(entry['model'], 34)} ${entry['cost']:.4f}")
    if by_key:
        if not summary["keys"]:
            print("\n按密钥费用: 暂不可用（请求日志缓存为空）", file=sys.stderr)
        else:
            key_headers = [
                ("密钥", False),
                ("分组", False),
                ("请求数", True),
                ("输入", True),
                ("输出", True),
                ("费用(USD)", True),
            ]
            key_align = [a for _, a in key_headers]
            key_widths = [max(display_width(h), 12) for h, _ in key_headers]
            key_widths[0] = max(
                key_widths[0], *(display_width(e["name"]) for e in summary["keys"])
            )

            def key_row(values):
                cells = [
                    pad(str(v), w, a) for v, w, a in zip(values, key_widths, key_align)
                ]
                return "  ".join(cells)

            print(f"\n按密钥费用（缓存于 {summary.get('keysFetchedAt') or '—'}）:")
            print(key_row([h for h, _ in key_headers]))
            print("-" * (sum(key_widths) + 2 * (len(key_widths) - 1)))
            for entry in summary["keys"]:
                print(
                    key_row(
                        [
                            entry["name"],
                            entry["group"],
                            entry["requests"],
                            f"{entry['inputTokens']:,}",
                            f"{entry['outputTokens']:,}",
                            f"${entry['cost']:.4f}",
                        ]
                    )
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Query opencode.ai workspace usage")
    parser.add_argument(
        "--days", type=int, default=7, help="number of days (default 7, max 90)"
    )
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument(
        "--profile",
        help="Chrome profile dir path, e.g. ~/.config/google-chrome/Default",
    )
    parser.add_argument("--by-model", action="store_true", help="show cost per model")
    parser.add_argument("--by-key", action="store_true", help="show usage per API key")
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
        print_table(summary, args.by_model, args.by_key)


if __name__ == "__main__":
    main()

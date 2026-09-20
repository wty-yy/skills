#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Query opencode.ai workspace usage through Chrome cookies.

Examples:
    uv run opencode_usage.py                  # last 7 days
    uv run opencode_usage.py --days 3
    uv run opencode_usage.py --by-model
    uv run opencode_usage.py --json > usage.json
"""

import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HOST = "opencode.ai"
BASE_URL = "https://opencode.ai"
DEFAULT_WORKSPACE = "wrk_01M28NK08E0YZ4DEHF128QZYH6"
USAGE_LIST_FN = "bfd684bfc2e4eed05cd0b518f5e4eafd3f3376e3938abb9e536e7c03df831e5c"
GET_COSTS_FN = "15702f3a12ff8bff357f8c2aa154a17e65b746d5f6b96adc9002c86ee0c15205"
PAGE_SIZE = 50
COST_SCALE = 1e8
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
    if "auth" not in cookies:
        raise RuntimeError(
            f"no 'auth' cookie for {HOST} in {profile}; log in via Chrome first"
        )
    return cookies


def seroval_args(args: list) -> str:
    nodes = []
    for arg in args:
        if isinstance(arg, bool):
            nodes.append({"t": 2, "s": 2 if arg else 3})
        elif isinstance(arg, (int, float)):
            nodes.append({"t": 0, "s": arg})
        elif isinstance(arg, str):
            nodes.append({"t": 1, "s": arg})
        else:
            raise TypeError(f"cannot serialize {arg!r}")
    return json.dumps(
        {"t": {"t": 9, "i": 0, "l": len(nodes), "a": nodes, "o": 0}, "f": 31, "m": []}
    )


def parse_solid_response(raw: bytes):
    match = re.search(
        r'\$R\[0\]=([\s\S]*)\)\(\$R\["server-fn:0"\]\)\)\s*$', raw.decode()
    )
    if not match:
        raise RuntimeError(f"unexpected response: {raw[:200]!r}")
    expr = match.group(1)
    error = re.search(r'new Error\("([^"]*)"', expr)
    if error:
        raise RuntimeError(error.group(1))
    expr = re.sub(r"\$R\[\d+\]=", "", expr)
    expr = re.sub(r'new Date\("([^"]*)"\)', r'"\1"', expr)
    expr = expr.replace("!0", "true").replace("!1", "false")
    expr = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', expr)
    return json.loads(expr)


def call_server(cookie: str, fn_id: str, args: list):
    request = urllib.request.Request(
        f"{BASE_URL}/_server",
        data=seroval_args(args).encode(),
        headers={
            "Cookie": cookie,
            "Content-Type": "application/json",
            "X-Server-Id": fn_id,
            "X-Server-Instance": "server-fn:0",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/workspace/{args[0]}/usage",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36",
        },
    )
    last_error: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(0.5 * 2**attempt + random.random())
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
            break
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"HTTP {exc.code}: {exc.read()[:200]!r}") from exc
            last_error = exc
    else:
        raise RuntimeError(f"request failed after retries: {last_error}")
    if content_type.startswith("application/json"):
        return json.loads(body)
    return parse_solid_response(body)


def tz_offset_str(at: datetime) -> str:
    offset = at.astimezone().utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_month_costs(cookie: str, workspace: str, year: int, month: int) -> dict:
    mid_month = datetime(year, month, 15, 12, tzinfo=timezone.utc)
    data = call_server(
        cookie, GET_COSTS_FN, [workspace, year, month - 1, tz_offset_str(mid_month)]
    )
    return data if isinstance(data, dict) else {"usage": data, "keys": []}


def fetch_records(
    cookie: str, workspace: str, cutoff: date, max_pages: int, workers: int = 4
) -> tuple[list, bool]:
    records: list = []
    complete = False
    batch = workers * 2
    page = 0
    while page < max_pages:
        pages = list(range(page, min(page + batch, max_pages)))
        with ThreadPoolExecutor(workers) as pool:
            results = list(
                pool.map(
                    lambda p: call_server(cookie, USAGE_LIST_FN, [workspace, p]), pages
                )
            )
        batch_records = [record for chunk in results for record in chunk]
        records.extend(batch_records)
        if any(len(chunk) < PAGE_SIZE for chunk in results):
            complete = True
            break
        oldest = min(parse_time(record["timeCreated"]) for record in batch_records)
        page += batch
        if oldest.astimezone().date() < cutoff:
            complete = True
            break
    return records, complete


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, width: int, right: bool = False) -> str:
    fill = " " * max(0, width - display_width(text))
    return fill + text if right else text + fill


def build_summary(args) -> dict:
    secret = get_keyring_secret()
    profile = Path(args.profile).expanduser() if args.profile else None
    cookies = load_cookies(secret, profile)
    cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())

    today = datetime.now().astimezone().date()
    cutoff = today - timedelta(days=args.days - 1)

    daily = {
        cutoff + timedelta(days=offset): {
            "requests": 0,
            "inputTokens": 0,
            "outputTokens": 0,
            "reasoningTokens": 0,
            "cacheReadTokens": 0,
        }
        for offset in range(args.days)
    }

    key_usage: dict[str, dict] = {}
    records, complete = fetch_records(cookie, args.workspace, cutoff, args.max_pages)
    for record in records:
        day = parse_time(record["timeCreated"]).astimezone().date()
        if day not in daily:
            continue
        bucket = daily[day]
        bucket["requests"] += 1
        bucket["inputTokens"] += record.get("inputTokens") or 0
        bucket["outputTokens"] += record.get("outputTokens") or 0
        bucket["reasoningTokens"] += record.get("reasoningTokens") or 0
        bucket["cacheReadTokens"] += record.get("cacheReadTokens") or 0
        key_bucket = key_usage.setdefault(record["keyID"], dict.fromkeys(bucket, 0))
        key_bucket["requests"] += 1
        key_bucket["inputTokens"] += record.get("inputTokens") or 0
        key_bucket["outputTokens"] += record.get("outputTokens") or 0
        key_bucket["reasoningTokens"] += record.get("reasoningTokens") or 0
        key_bucket["cacheReadTokens"] += record.get("cacheReadTokens") or 0

    cost_by_day: dict[str, float] = {}
    cost_by_model: dict[str, float] = {}
    cost_by_key: dict[str, float] = {}
    key_names: dict[str, dict] = {}
    for year, month in month_range(cutoff, today):
        data = fetch_month_costs(cookie, args.workspace, year, month)
        for key in data.get("keys", []):
            key_names[key["id"]] = key
        for row in data.get("usage", []):
            day = row["date"]
            if not (cutoff.isoformat() <= day <= today.isoformat()):
                continue
            cost_by_day[day] = cost_by_day.get(day, 0.0) + row["totalCost"] / COST_SCALE
            cost_by_model[row["model"]] = (
                cost_by_model.get(row["model"], 0.0) + row["totalCost"] / COST_SCALE
            )
            cost_by_key[row["keyId"]] = (
                cost_by_key.get(row["keyId"], 0.0) + row["totalCost"] / COST_SCALE
            )

    days = []
    for day, bucket in daily.items():
        entry = {
            "date": day.isoformat(),
            **bucket,
            "cost": round(cost_by_day.get(day.isoformat(), 0.0), 6),
        }
        days.append(entry)

    total = {
        key: sum(entry[key] for entry in days)
        for key in (
            "requests",
            "inputTokens",
            "outputTokens",
            "reasoningTokens",
            "cacheReadTokens",
        )
    }
    total["cost"] = round(sum(entry["cost"] for entry in days), 6)

    by_key = []
    empty_bucket = dict.fromkeys(next(iter(daily.values())), 0)
    for key_id in set(cost_by_key) | set(key_usage):
        info = key_names.get(key_id, {})
        name = info.get("displayName", key_id)
        if info.get("deleted"):
            name += "（已删除）"
        bucket = dict(key_usage.get(key_id) or empty_bucket)
        entry = {
            "id": key_id,
            "name": name,
            **bucket,
            "cost": round(cost_by_key.get(key_id, 0.0), 6),
        }
        by_key.append(entry)
    by_key.sort(key=lambda entry: -entry["cost"])

    return {
        "workspace": args.workspace,
        "range": [days[0]["date"], days[-1]["date"]],
        "complete": complete,
        "days": days,
        "total": total,
        "costByModel": cost_by_model,
        "byKey": by_key,
    }


def print_table(summary: dict, by_model: bool, by_key: bool) -> None:
    headers = [
        ("日期", False),
        ("请求数", True),
        ("输入", True),
        ("输出", True),
        ("推理", True),
        ("缓存读取", True),
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
                    f"{day['reasoningTokens']:,}",
                    f"{day['cacheReadTokens']:,}",
                    f"${day['cost']:.4f}",
                ]
            )
        )
    total = summary["total"]
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    print(
        row(
            [
                "合计",
                total["requests"],
                f"{total['inputTokens']:,}",
                f"{total['outputTokens']:,}",
                f"{total['reasoningTokens']:,}",
                f"{total['cacheReadTokens']:,}",
                f"${total['cost']:.4f}",
            ]
        )
    )
    if not summary["complete"]:
        print(
            "\n提示: 记录数过多，tokens 汇总不完整（提高 --max-pages 可拉取更多）",
            file=sys.stderr,
        )
    if by_model and summary["costByModel"]:
        print("\n按模型费用:")
        for model, cost in sorted(
            summary["costByModel"].items(), key=lambda kv: -kv[1]
        ):
            print(f"  {pad(model, 34)} ${cost:.4f}")
    if by_key and summary["byKey"]:
        key_headers = [
            ("密钥", False),
            ("请求数", True),
            ("输入", True),
            ("输出", True),
            ("费用(USD)", True),
        ]
        key_align = [a for _, a in key_headers]
        key_widths = [max(display_width(h), 12) for h, _ in key_headers]
        key_widths[0] = max(
            key_widths[0], *(display_width(e["name"]) for e in summary["byKey"])
        )

        def key_row(values):
            cells = [
                pad(str(v), w, a) for v, w, a in zip(values, key_widths, key_align)
            ]
            return "  ".join(cells)

        print("\n按密钥费用:")
        print(key_row([h for h, _ in key_headers]))
        print("-" * (sum(key_widths) + 2 * (len(key_widths) - 1)))
        for entry in summary["byKey"]:
            print(
                key_row(
                    [
                        entry["name"],
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
        "--days", type=int, default=7, help="number of days (default 7)"
    )
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--profile", help="Chrome profile dir name, e.g. Default")
    parser.add_argument(
        "--max-pages", type=int, default=200, help="usage.list page cap"
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

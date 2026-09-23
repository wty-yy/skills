#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["cryptography", "secretstorage"]
# ///
"""Query opencode.ai console usage through a service API key or Chrome cookies.

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


def api_headers(workspace: str, profile: Path | None = None) -> dict[str, str]:
    key = os.environ.get("OPENCODE_API_KEY", "")
    if key:
        return {"Authorization": f"Bearer {key}"}
    cookies = load_cookies(get_keyring_secret(), profile)
    cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return {"Cookie": cookie, "x-org-id": workspace}


def call_api(
    path: str, params: dict | None = None, headers: dict | None = None
) -> dict | list:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{query}"
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0.0.0 Safari/537.36",
        "Origin": "https://opencode.ai",
        "Referer": "https://opencode.ai/console/",
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(0.5 * 2**attempt + random.random())
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
            last_error = exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
    raise RuntimeError(f"request failed after retries: {last_error}")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_records(cutoff: date, max_pages: int, headers: dict) -> tuple[list, bool]:
    since = (cutoff - timedelta(days=1)).isoformat() + "T00:00:00Z"
    records: list = []
    cursor: str | None = None
    for _ in range(max_pages):
        params: dict = {"since": since, "pageSize": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        data = call_api("/usage/rows", params, headers)
        items = data.get("items", []) if isinstance(data, dict) else []
        records.extend(items)
        cursor = data.get("nextCursor") if isinstance(data, dict) else None
        if not items or not cursor:
            return records, True
        oldest = min(parse_time(item["createdAt"]) for item in items)
        if oldest.astimezone().date() < cutoff:
            return records, True
    return records, False


def fetch_key_names(headers: dict) -> dict[str, dict]:
    data = call_api("/service-accounts", {"page": 1, "pageSize": 100}, headers)
    names: dict[str, dict] = {}
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items:
        for key in item.get("keys", []):
            names[key["id"]] = {
                "displayName": key["name"],
                "deleted": key.get("status") != "active",
            }
    return names


def fetch_quota(headers: dict) -> dict:
    data = call_api("/go/status", None, headers)
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


def group_of(name: str) -> str:
    return "wt" if name.endswith("wt") else "yy"


def empty_stats() -> dict:
    return {"requests": 0, **dict.fromkeys(TOKEN_FIELDS, 0)}


def total_tokens(stats: dict) -> int:
    return sum(stats.get(field) or 0 for field in TOKEN_FIELDS)


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, width: int, right: bool = False) -> str:
    fill = " " * max(0, width - display_width(text))
    return fill + text if right else text + fill


def build_summary(args) -> dict:
    profile = Path(args.profile).expanduser() if args.profile else None
    headers = api_headers(args.workspace, profile)
    today = datetime.now().astimezone().date()
    cutoff = today - timedelta(days=args.days - 1)
    dates = [cutoff + timedelta(days=offset) for offset in range(args.days)]

    key_names = fetch_key_names(headers)
    records, complete = fetch_records(cutoff, args.max_pages, headers)

    daily: dict[str, dict] = {}
    key_stats: dict[str, dict] = {}
    model_stats: dict[str, dict] = {}
    for record in records:
        day = parse_time(record["createdAt"]).astimezone().date()
        if not (cutoff <= day <= today):
            continue
        name = key_names.get(record.get("serviceApiKeyId"), {}).get(
            "displayName", record.get("serviceApiKeyId") or "unknown"
        )
        cost = int(record.get("costMicroCents") or 0) / COST_SCALE
        bucket = daily.setdefault(
            day.isoformat(),
            {"wt": empty_stats() | {"cost": 0.0}, "yy": empty_stats() | {"cost": 0.0}},
        )[group_of(name)]
        for stats in (
            bucket,
            key_stats.setdefault(
                record.get("serviceApiKeyId"), empty_stats() | {"cost": 0.0}
            ),
            model_stats.setdefault(record["model"], empty_stats() | {"cost": 0.0}),
        ):
            stats["requests"] += 1
            for field in TOKEN_FIELDS:
                stats[field] += record.get(field) or 0
            stats["cost"] += cost

    days = []
    totals = {"wt": empty_stats() | {"cost": 0.0}, "yy": empty_stats() | {"cost": 0.0}}
    for day in dates:
        iso = day.isoformat()
        entry = {"date": iso, "groups": {}}
        for group in ("wt", "yy"):
            stats = daily.get(iso, {}).get(group, empty_stats() | {"cost": 0.0})
            entry["groups"][group] = {
                **stats,
                "tokens": total_tokens(stats),
                "cost": round(stats["cost"], 6),
            }
            for field in TOKEN_FIELDS:
                totals[group][field] += stats[field]
            totals[group]["requests"] += stats["requests"]
            totals[group]["cost"] += stats["cost"]
        entry["total"] = {
            "requests": entry["groups"]["wt"]["requests"]
            + entry["groups"]["yy"]["requests"],
            "tokens": entry["groups"]["wt"]["tokens"] + entry["groups"]["yy"]["tokens"],
            "cost": round(
                entry["groups"]["wt"]["cost"] + entry["groups"]["yy"]["cost"], 6
            ),
        }
        days.append(entry)
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

    models = [
        {
            "model": model,
            "cost": round(stats["cost"], 6),
            "tokens": total_tokens(stats),
            "requests": stats["requests"],
        }
        for model, stats in sorted(model_stats.items(), key=lambda kv: -kv[1]["cost"])
    ]

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": args.workspace,
        "range": [dates[0].isoformat(), dates[-1].isoformat()],
        "complete": complete,
        "days": days,
        "totals": totals,
        "keys": keys,
        "models": models,
        "quota": fetch_quota(headers),
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
        stats = day["groups"]
        print(
            row(
                [
                    day["date"],
                    day["total"]["requests"],
                    f"{stats['wt']['inputTokens'] + stats['yy']['inputTokens']:,}",
                    f"{stats['wt']['outputTokens'] + stats['yy']['outputTokens']:,}",
                    f"{stats['wt']['reasoningTokens'] + stats['yy']['reasoningTokens']:,}",
                    f"{stats['wt']['cacheReadTokens'] + stats['yy']['cacheReadTokens']:,}",
                    f"${day['total']['cost']:.4f}",
                ]
            )
        )
    total = summary["totals"]["all"]
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
    if by_model and summary["models"]:
        print("\n按模型费用:")
        for entry in summary["models"]:
            print(f"  {pad(entry['model'], 34)} ${entry['cost']:.4f}")
    if by_key and summary["keys"]:
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
            key_widths[0], *(display_width(e["name"]) for e in summary["keys"])
        )

        def key_row(values):
            cells = [
                pad(str(v), w, a) for v, w, a in zip(values, key_widths, key_align)
            ]
            return "  ".join(cells)

        print("\n按密钥费用:")
        print(key_row([h for h, _ in key_headers]))
        print("-" * (sum(key_widths) + 2 * (len(key_widths) - 1)))
        for entry in summary["keys"]:
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
    parser.add_argument(
        "--profile",
        help="Chrome profile dir path, e.g. ~/.config/google-chrome/Default",
    )
    parser.add_argument(
        "--max-pages", type=int, default=200, help="usage rows page cap"
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

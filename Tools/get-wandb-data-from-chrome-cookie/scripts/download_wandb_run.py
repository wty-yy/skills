"""Download a W&B run (metadata, files, metric history, artifacts) with Chrome cookies.

Overview:
    Reads the wandb.ai cookies from the local Chrome profile (Linux, gnome-keyring),
    authenticates against api.wandb.ai and writes the run metadata, the full metric
    history, the run files and the output artifact files into the output directory.
    History is exported as both JSON and CSV.

Quick Start:
    python scripts/download_wandb_run.py --url https://wandb.ai/<entity>/<project>/runs/<run_id>

Full Command:
    python scripts/download_wandb_run.py --url <run-url> --output <dir> --samples <max-rows>
    python scripts/download_wandb_run.py --url <run-url> --system-metrics

Options:
    --url               W&B run URL.
    --output            Output directory, defaults to the current directory.
    --samples           Max history/event rows requested from the API, defaults 10000000.
    --system-metrics    Also fetch the events stream (system metrics); CSV by default.
    --events-json       With --system-metrics, also write system_metrics.json (large).

Notes:
    Requires `pycryptodome` and `secretstorage`, and the Chrome login session must still
    be valid. Only Chrome profiles listed in CHROME_PROFILES are scanned. API access is
    derived from the cookie session, so no W&B API key is required; do not share the
    extracted cookies.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import http.cookiejar
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import requests
from Crypto.Cipher import AES

import secretstorage

GRAPHQL = "https://api.wandb.ai/graphql"
CHROME_PROFILES = [
    Path.home() / ".config/google-chrome/Default",
    Path.home() / ".config/google-chrome/Profile 1",
    Path.home() / ".config/google-chrome/Profile 2",
]


def chrome_key() -> bytes:
    """Return the Chrome cookie encryption key from the gnome-keyring."""
    conn = secretstorage.dbus_init()
    for collection in secretstorage.get_all_collections(conn):
        for item in collection.get_all_items():
            attrs = dict(item.get_attributes())
            if (
                attrs.get("application") == "chrome"
                and attrs.get("xdg:schema") == "chrome_libsecret_os_crypt_password_v2"
            ):
                secret = item.get_secret()
                return hashlib.pbkdf2_hmac("sha1", secret, b"saltysalt", 1, 16)
    raise RuntimeError("Chrome Safe Storage key not found in keyring")


def decrypt_value(key: bytes, encrypted: bytes) -> str:
    """Decrypt a Chrome v10/v11 cookie value; v11 prepends a 32-byte domain hash."""
    if encrypted[:3] not in (b"v10", b"v11"):
        return encrypted.decode("utf-8", "replace")
    plain = AES.new(key, AES.MODE_CBC, b" " * 16).decrypt(encrypted[3:])
    pad = plain[-1]
    if 1 <= pad <= 16 and plain[-pad:] == bytes([pad]) * pad:
        plain = plain[:-pad]
    if encrypted[:3] == b"v11":
        plain = plain[32:]
    return plain.decode("utf-8", "replace")


def load_cookies(profile: Path, key: bytes) -> list[dict]:
    """Decrypt every cookie stored in a Chrome profile."""
    tmp = Path("/tmp/wandb_cookies_copy.db")
    shutil.copy(profile / "Cookies", tmp)
    con = sqlite3.connect(tmp)
    cookies = [
        {"domain": host, "name": name, "value": decrypt_value(key, enc)}
        for host, name, enc in con.execute("SELECT host_key, name, encrypted_value FROM cookies")
    ]
    con.close()
    tmp.unlink(missing_ok=True)
    return cookies


def build_session() -> requests.Session:
    """Create a requests session authenticated with the Chrome cookie jar."""
    key = chrome_key()
    jar = http.cookiejar.CookieJar()
    for profile in CHROME_PROFILES:
        if not (profile / "Cookies").exists():
            continue
        for cookie in load_cookies(profile, key):
            if not cookie["domain"].endswith("wandb.ai") or not cookie["value"]:
                continue
            jar.set_cookie(
                http.cookiejar.Cookie(
                    version=0,
                    name=cookie["name"],
                    value=cookie["value"],
                    port=None,
                    port_specified=False,
                    domain=cookie["domain"],
                    domain_specified=True,
                    domain_initial_dot=cookie["domain"].startswith("."),
                    path="/",
                    path_specified=True,
                    secure=True,
                    expires=None,
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={},
                )
            )
    session = requests.Session()
    session.trust_env = False
    session.cookies = jar
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Origin": "https://wandb.ai",
            "x-origin": "https://wandb.ai",
        }
    )
    return session


def gql(session: requests.Session, query: str, variables: dict, timeout: int = 600) -> dict:
    response = session.post(
        GRAPHQL,
        json={"query": query, "variables": variables},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


RUN_QUERY = """
query Run($entity: String!, $project: String!, $runId: String!) {
  project(name: $project, entityName: $entity) {
    id
    run(name: $runId) {
      id
      name
      displayName
      state
      createdAt
      heartbeatAt
      config
      summaryMetrics
      historyKeys
      user { username }
      files(first: 1000) {
        edges { node { name sizeBytes mimetype directUrl } }
      }
      outputArtifacts(first: 100) {
        edges {
          node {
            id
            digest
            size
            artifactType { name }
            artifactSequence { name }
            files { edges { node { name sizeBytes directUrl } } }
          }
        }
      }
    }
  }
}
"""

HISTORY_QUERY = """
query RunFullHistory($project: String!, $entity: String!, $name: String!, $samples: Int) {
  project(name: $project, entityName: $entity) {
    run(name: $name) {
      historyLineCount
      history(samples: $samples)
    }
  }
}
"""

EVENTS_QUERY = """
query RunEvents($project: String!, $entity: String!, $name: String!, $samples: Int) {
  project(name: $project, entityName: $entity) {
    run(name: $name) {
      events(samples: $samples)
    }
  }
}
"""


def parse_run_url(url: str) -> tuple[str, str, str]:
    """Extract (entity, project, run_id) from a W&B run URL."""
    parts = [p for p in url.split("wandb.ai/")[-1].split("/") if p]
    if len(parts) < 4 or parts[2] != "runs":
        raise ValueError(f"unrecognized run url: {url}")
    return parts[0], parts[1], parts[3].split("?")[0]


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False))
    print(f"  wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write history rows to CSV; columns are the union of all row keys."""
    all_keys = {key for row in rows for key in row}
    columns = [key for key in ("_step", "_runtime", "_timestamp") if key in all_keys]
    columns += sorted(all_keys - set(columns))
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(
                [
                    json.dumps(row.get(col))
                    if isinstance(row.get(col), (dict, list))
                    else row.get(col)
                    for col in columns
                ]
            )
    print(f"  wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")


def download_file(session: requests.Session, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=600) as response:
        response.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    print(f"  wrote {dest} ({dest.stat().st_size / 1e6:.2f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="W&B run URL")
    parser.add_argument("--output", default=".", help="output directory")
    parser.add_argument("--samples", type=int, default=10_000_000, help="max history/event rows")
    parser.add_argument("--system-metrics", action="store_true", help="also fetch events")
    parser.add_argument("--events-json", action="store_true", help="also write events JSON")
    args = parser.parse_args()

    entity, project, run_id = parse_run_url(args.url)
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"run: {entity}/{project}/{run_id} -> {out}")

    session = build_session()
    viewer = gql(session, "query { viewer { username email } }", {})["viewer"]
    print(f"authenticated as {viewer['username']} <{viewer['email']}>")

    print("run metadata")
    data = gql(
        session,
        RUN_QUERY,
        {"entity": entity, "project": project, "runId": run_id},
    )["project"]["run"]
    files = [edge["node"] for edge in data.pop("files")["edges"]]
    artifacts = [edge["node"] for edge in data.pop("outputArtifacts")["edges"]]
    write_json(out / "run_info.json", data)

    print("full history")
    history = gql(
        session,
        HISTORY_QUERY,
        {"project": project, "entity": entity, "name": run_id, "samples": args.samples},
    )["project"]["run"]
    history_rows = [json.loads(line) for line in history["history"]]
    print(f"  historyLineCount={history['historyLineCount']} rows={len(history_rows)}")
    write_json(out / "history.json", history_rows)
    write_csv(out / "history.csv", history_rows)

    if args.system_metrics:
        print("system metrics")
        events = gql(
            session,
            EVENTS_QUERY,
            {"project": project, "entity": entity, "name": run_id, "samples": args.samples},
        )["project"]["run"]["events"]
        event_rows = [json.loads(line) for line in events]
        if args.events_json:
            write_json(out / "system_metrics.json", event_rows)
        write_csv(out / "system_metrics.csv", event_rows)

    print("files and artifacts")
    for file in files:
        name = file["name"]
        url = file.get("directUrl") or (
            f"https://api.wandb.ai/files/{entity}/{project}/{run_id}/{name}"
        )
        try:
            download_file(session, url, out / "files" / name)
        except requests.HTTPError as exc:
            print(f"  skip {name}: {exc}")
    for artifact in artifacts:
        seq = artifact["artifactSequence"]["name"]
        for file in artifact["files"]["edges"]:
            node = file["node"]
            download_file(session, node["directUrl"], out / "artifacts" / seq / node["name"])
    write_json(out / "artifact_info.json", artifacts)

    print("done")


if __name__ == "__main__":
    sys.exit(main())

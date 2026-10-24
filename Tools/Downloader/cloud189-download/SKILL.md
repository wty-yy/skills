---
name: cloud189-download
description: Download files and folders from Tianyi Cloud (天翼云盘, cloud.189.cn) through its API with QR login, resumable parallel ranges, bounded retries, and cloud MD5 verification. Use for cloud189 downloads, missing-file recovery, or checking downloaded folders. Supports personal-cloud folders; not CTYun object storage or public-share extraction.
---

# Cloud189 Download

Use the API workflow for reliable folder downloads. Browser download clicks can be dropped or blocked; a click or missing `.crdownload` file is not proof of completion.

## Workspace and login

Use the user's requested working/output directories. Keep the CLI, session, manifests, logs, chunks, and downloads in that workspace, **outside the skill/repository**. Do not copy browser cookies or credentials into the skill.

Requires Python 3.10+ and `requests`. Use an existing interpreter with `requests`, or a workspace virtual environment and `pip install requests`.

Resolve `SKILL` to this skill's directory and `TASK` to the task workspace. The examples below are Linux/macOS shell commands; on Windows use `cloud189.exe` and equivalent paths.

```bash
python3 "$SKILL/scripts/setup_client.py" --workdir "$TASK"
mkdir -p "$TASK/work"
chmod 700 "$TASK/work"
(umask 077; "$TASK/bin/cloud189" --config "$TASK/work/config.json" qrlogin)
```

The CLI prints an official `open.e.189.cn` QR image URL. Show/open that URL for the user to scan and confirm with the Tianyi Cloud app. Keep the login process running while awaiting confirmation. Do not claim login until a read-only listing succeeds. Reuse a valid workspace session; do not ask to scan again unnecessarily. Protect `config.json` with mode 600 on POSIX and never print its contents, signed URLs, or request headers.

The helper pins `gowsp/cloud189` v0.7.0 and checks the upstream SHA-256 before extracting only the executable. Do not silently install a different version or globally modify tools.

## Plan and download

Resolve the requested cloud folders using CLI listings. A browser URL's folder ID is not a cloud path: list the relevant parent and match its `file_id`. Restrict traversal to the user's requested scope. Do not create public share links as a login workaround.

```bash
"$TASK/bin/cloud189" --config "$TASK/work/config.json" -j ls /Music

python3 "$SKILL/scripts/cloud189_download.py" plan \
  --cli "$TASK/bin/cloud189" --config "$TASK/work/config.json" \
  --folder /Music/AlbumA --folder /Music/AlbumB \
  --manifest "$TASK/work/manifest.json"

python3 "$SKILL/scripts/cloud189_download.py" download \
  --manifest "$TASK/work/manifest.json" --config "$TASK/work/config.json" \
  --output "$TASK/downloads" --work "$TASK/work"
```

`plan` recursively lists each requested folder and preserves its basename and nested relative paths. Choose a parent folder or separate plans/output directories if requested folders share a basename. Empty directories are not materialized. The helper rejects duplicate destinations and missing cloud MD5 values before downloading.

Defaults: four files × four range connections, 4 MiB chunks, three bounded attempts at file and chunk levels. Adjust `--files`, `--chunks`, `--chunk-mib`, and `--attempts` only when useful; reduce concurrency on throttling or repeated failures. Never run simultaneous downloads against the same work or output directory. After an interrupted process, check that it and its children have stopped before removing a stale `work/download.lock`.

Verified files are skipped. Cached chunks are keyed by file ID, size, MD5, output path, and chunk size. A full-file size and MD5 check gates publication of each final filename. Existing files with different contents are reported as conflicts, not silently overwritten. Resolve those conflicts within the user's authorized scope, then rerun.

Do not treat the manifest as permanently current. If the user uploads or changes files, refresh `plan` **after the active run finishes**, then rerun `download`. This catches additions and changed content without redownloading verified files.

## Verify and report

```bash
python3 "$SKILL/scripts/cloud189_download.py" verify \
  --manifest "$TASK/work/manifest.json" --output "$TASK/downloads" \
  --report "$TASK/work/verification.json"
```

Require all manifest entries to match size and cloud MD5 before reporting completion. Verification also checks local M3U8 references without fetching external URLs. Report missing playlist tracks separately: they may be absent from the source folder, not failed downloads. Non-manifest files are left alone.

Report counts per folder, total bytes, failed/conflicting files, playlist gaps, and the actual output directory. Keep `download_report.json` and `verification.json` for review. Re-run the same download command to resume interrupted work; stop after bounded failures and explain the remaining blocker instead of claiming success.

Only clean old browser downloads when requested. Identify files by this task's manifest/history, prefer the recycle bin, and leave unrelated downloads untouched.

Read [references/api-notes.md](references/api-notes.md) for protocol details, demonstrated pitfalls, and troubleshooting. Use the supplied scripts instead of reconstructing request signing from memory.

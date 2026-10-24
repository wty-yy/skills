# API notes

## Source and tested behavior

- Upstream: [gowsp/cloud189](https://github.com/gowsp/cloud189), Apache-2.0.
- Signing: `pkg/app/api.go`; download URL: `pkg/app/req_file_info.go`; QR login: `internal/invoker/qr_login.go`; session schema: `internal/invoker/config.go`.
- CLI release tested: v0.7.0, Linux amd64. Other packaged platforms are selected by the setup helper but were not integration-tested in this session.
- On 2026-10-11, the API method downloaded 83 files (4,260,566,697 bytes), with all sizes, MD5 values, and both M3U8 playlists verified. These are historical test results, not promises about later runs or network speed.

## API contract

Read `session.sessionKey` and `session.sessionSecret` from the local CLI config. Never include them in reports.

`GET https://api.cloud.189.cn/getFileDownloadUrl.action` uses `fileId`, `rand` (epoch milliseconds), `clientType=TELEPC`, `version=7.1.8.0`, and `channelId=web_cloud.189.cn`.

Headers include `Date`, `SessionKey`, `User-Agent: desktop`, and `Signature`. Signature is lowercase hex HMAC-SHA1 using the session secret and the exact string:

```text
SessionKey=<key>&Operate=GET&RequestURI=/getFileDownloadUrl.action&Date=<same Date header>
```

Use `Accept: application/json;charset=UTF-8`; the server can still return XML. Parse either form and read `fileDownloadUrl`. Send only Range/encoding headers to that signed download URL; do not forward session credentials to download hosts.

A partial response must have status 206, exact `Content-Range`, and exactly the requested byte count. Accept 200 only when the request covers the entire file. Full MD5 verification remains required even after every range succeeds. Empty files can be verified locally against their expected MD5.

## Operational pitfalls

- Browser automatic-download permission does not prove all downloads started or completed. Check actual bytes and cloud checksums.
- Cloud listings may add one or more backslashes before apostrophes/quotes. The planner removes only those escapes, preserving spaces (including double spaces). Use `--literal-names` when literal escaping is intentional; unsupported unsafe names fail validation. Do not globally replace punctuation or infer names from numbering.
- The direct downloader identifies files by ID and avoids CLI path-lookup failures involving escaped quotes.
- Although the upstream README advertises resume, the examined CLI `dl -o` implementation truncates its output. The supplied helper implements resumable chunks itself.
- Expired session: use a read-only CLI listing to refresh or diagnose it; if needed, run `qrlogin` again, then resume. Do not scrape unrelated browser profiles.
- Range failure: lower concurrency, refresh the session or signed URL, and retry within the configured bound. Do not stitch responses whose range metadata differs. A service that does not support ranges needs a whole-file downloader with the same size/MD5 verification.
- `FileExistsError` in `download_report.json` means a differing local destination or a file appearing during transfer. Preserve it, resolve the conflict, then retry.
- Two same-basename source folders can collide in one output tree. Use their common parent or separate manifests and output directories.
- Folder changes require a new manifest. Do not infer missing numbered tracks from a filename sequence alone; compare the actual cloud listing and playlist.

The helper does not implement family-cloud signing, share-code downloads, cookie extraction, upload, delete, or cloud permission changes.

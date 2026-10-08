---
name: youtube-download
description: Download YouTube (and other yt-dlp sites) audio or video with quality selection, bilingual English + Simplified Chinese subtitles, and browser-cookie authentication. Use when the user asks to download a YouTube video, extract music/audio, save a playlist, or fetch subtitles.
---

# YouTube Download

Download audio or video from YouTube with quality selection, using the local browser login to pass bot checks.

## When To Use

- Download a YouTube video (single video or playlist).
- Extract audio as `m4a`, `opus`, `flac`, `mp3`, or the native best stream.
- Fetch subtitles, including bilingual English + Simplified Chinese.
- Any yt-dlp-supported URL (Vimeo, Bilibili, etc.) with the same workflow.

## Before Downloading: Always Ask Quality

Ask the user for the audio/video quality every time before starting a download, unless they already stated it:

- Audio: `m4a` (default), `opus`, `flac`, `mp3`, `best`.
- Video: max height `2160` / `1440` / `1080` (default) / `720` / `480`.

When run directly in a terminal, `youtube_download.py` prompts for mode and quality itself. When driving it from an agent, ask the user with the agent's question tool, then pass the answer as `-f` (audio) or `-r` (video) so the script does not prompt again.

## Quick Start

```bash
pip install -U yt-dlp mutagen      # yt-dlp + cover-art embedding
# ffmpeg and node must be on PATH

# Unified entry: asks audio/video, then quality
python3 scripts/youtube_download.py "URL"

# Audio only, saved to audios/
python3 scripts/yt_audio_downloader.py -f flac "URL"
python3 scripts/yt_audio_downloader.py -f m4a -i urls.md

# Video, saved to videos/, default mkv + bilingual subtitles
python3 scripts/yt_video_downloader.py -r 1080 "URL"
python3 scripts/yt_video_downloader.py -r 2160 --codec av1 "URL"
```

Output layout (relative to the working directory):

```
audios/   # audio downloads
videos/   # video downloads
```

## Defaults

- Video container: `mkv` (stream copy, no re-encode).
- Video subtitles: `--subs auto`, languages `en,zh-Hans`.
- Bilingual subtitle: English on top, Simplified Chinese below, both at font size `38`; written as a `.bilingual.srt` sidecar and embedded as ASS in the mkv.
- Audio: original stream, no re-encode.

## Implementation Details

### Authentication and JS challenges

YouTube returns `Sign in to confirm you're not a bot` for datacenter IPs and headless requests. The scripts pass:

- `--cookies-from-browser chrome` to reuse the local login session.
- `--js-runtimes node:<path>` plus `--remote-components ejs:github` to solve the signature/`n` challenges.

`yd_common.find_node()` also locates nvm installs not on `PATH`.

### Bilingual subtitles

`make_bilingual_subs.py` merges two auto-caption SRT tracks:

1. Parse SRT tolerating blank lines inside cue text.
2. De-roll YouTube's rolling two-line window (each cue repeats the previous line).
3. Align English and Chinese cues by start timestamp.
4. Emit a bilingual `.srt` and a styled `.ass` (English + Chinese stacked via `{\rEN}...\N{\rCN}...`).

`yd_common.postprocess_bilingual()` runs after yt-dlp, then remuxes the ASS into the mkv with `ffmpeg -c copy -c:s ass`.

### Audio format facts

YouTube audio is already lossy (AAC ~128k or Opus ~137k), so `flac`/`wav` only store the lossy source without extra loss, they do not improve quality; it is the largest option. To keep the source exactly, use `best`; for compatibility use `m4a`; for small size use `opus`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Sign in to confirm you're not a bot` | Ensure `--cookies-from-browser chrome` points at a logged-in browser |
| Formats missing / signature errors | Install Node.js; keep `--remote-components ejs:github` |
| Chinese shows as boxes | Install a CJK font such as `Noto Sans CJK SC` |
| `NoneType` thumbnail warning | `pip install mutagen` for ASS/FLAC cover embedding |
| mp4 lacks font styling | Use `mkv`; mp4 converts ASS to `mov_text` and drops the font size |
| Large flac files | Expected: FLAC stores PCM losslessly; use `m4a` for smaller files |

#!/usr/bin/env python3
"""Unified YouTube downloader front-end.

Asks whether to download audio or video, then asks the quality (audio format
or video resolution) unless it is already specified. Audio is saved under
`audios/`, video under `videos/`. Video downloads default to MKV with a
bilingual English + Simplified Chinese subtitle embedded at font size 38.

Examples:
    python3 youtube_download.py --audio URL
    python3 youtube_download.py --video -r 1080 URL
    python3 youtube_download.py URL            # asks interactively
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

import yd_common as yd
import yt_audio_downloader as audio
import yt_video_downloader as video

HELP = """usage: youtube_download.py [--audio | --video] [options] URL [URL ...]

Unified entry point. Without --audio/--video it asks interactively, then asks
for the quality (audio format / video resolution) unless one is given.

Common options:
  --audio                 download audio only (saved to audios/)
  --video                 download video (saved to videos/, default mkv)
  -f, --format FORMAT     audio format: m4a|opus|flac|mp3|best
  -r, --resolution H      video max height: 2160|1440|1080|720|480
  --subs MODE             none|auto|manual|both (default: auto)
  --sub-langs LANGS       subtitle languages (default: en,zh-Hans)
  --en-size / --zh-size   bilingual font sizes (default: 38)
  --no-ask                never prompt; use defaults
  -i, --input-file FILE   read URLs from a text/Markdown file
  -o, --output DIR        override output directory
  -h, --help              show this help

Run `python3 yt_audio_downloader.py --help` or
`python3 yt_video_downloader.py --help` for the full per-mode options.
"""


def detect_mode(argv: List[str]) -> str:
    """Decide audio vs video from flags, else ask (or default to video)."""
    if "--audio" in argv:
        return "audio"
    if "--video" in argv:
        return "video"
    if any(a in argv for a in ("-f", "--format")):
        return "audio"
    if any(a in argv for a in ("-r", "--resolution")):
        return "video"
    if not sys.stdin.isatty():
        return "video"
    return yd.prompt_choice(
        "下载音频还是视频？",
        [
            ("video", "video", "视频（默认 mkv，内嵌中英双语字幕）"),
            ("audio", "audio", "仅音频（m4a/opus/flac/mp3/best）"),
        ],
        "video",
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Parse the mode flag and dispatch to the audio or video downloader."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print(HELP)
        return 0

    mode = detect_mode(argv)
    rest = [a for a in argv if a not in ("--audio", "--video")]
    return audio.main(rest) if mode == "audio" else video.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())

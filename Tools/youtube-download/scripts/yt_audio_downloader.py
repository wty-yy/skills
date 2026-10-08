#!/usr/bin/env python3
"""Download high-quality audio from YouTube (and other yt-dlp sites).

The default profile keeps the original best audio stream and remuxes it into
M4A/AAC without re-encoding, so the output is bit-for-bit faithful to the
source. Audio lands in `audios/` by default. A Node.js runtime plus the EJS
challenge solver work around YouTube's bot checks, and browser cookies are
reused for authentication when available.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import yd_common as yd

DEFAULT_OUTPUT = yd.AUDIO_DIR

FORMAT_PROFILES = {
    "m4a": {
        "selector": "bestaudio[ext=m4a]/bestaudio",
        "extract": "m4a",
        "quality": "0",
        "desc": "原始 AAC 流，不重编码（推荐，兼容性最好）",
    },
    "opus": {
        "selector": "bestaudio[ext=webm]/bestaudio",
        "extract": "opus",
        "quality": "0",
        "desc": "最高码率 Opus，体积小、效率高",
    },
    "flac": {
        "selector": "bestaudio/best",
        "extract": "flac",
        "quality": "0",
        "desc": "无损封装原始流（体积大，音质不提升）",
    },
    "mp3": {
        "selector": "bestaudio/best",
        "extract": "mp3",
        "quality": "0",
        "desc": "重编码 MP3 V0（约 245kbps），兼容性最强",
    },
    "best": {
        "selector": "bestaudio/best",
        "extract": "best",
        "quality": None,
        "desc": "保留原始最佳流，不做任何转换",
    },
}

FORMAT_ORDER = ["m4a", "opus", "flac", "mp3", "best"]


def ask_format(default: str = "m4a") -> str:
    """Interactively ask which audio format to use."""
    options = [(name, name, FORMAT_PROFILES[name]["desc"]) for name in FORMAT_ORDER]
    return yd.prompt_choice("选择音频格式：", options, default)


def build_command(args: argparse.Namespace) -> List[str]:
    """Assemble the yt-dlp command line from parsed arguments."""
    profile = FORMAT_PROFILES[args.format]
    cmd: List[str] = [sys.executable, "-m", "yt_dlp"]
    cmd += yd.network_args(args.cookies_from_browser)
    cmd += [
        "--extract-audio",
        "--audio-format",
        profile["extract"],
        "--format",
        profile["selector"],
        "--embed-metadata",
        "--embed-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--paths",
        str(args.output),
        "--output",
        "%(title)s [%(id)s].%(ext)s",
    ]
    cmd += yd.stability_args()

    if profile["quality"] is not None:
        cmd += ["--audio-quality", profile["quality"]]

    if args.sponsorblock:
        cmd += ["--sponsorblock-remove", "music_offtopic"]

    if args.no_playlist:
        cmd += ["--no-playlist"]

    if args.archive:
        cmd += ["--download-archive", str(args.output / ".audio-archive.txt")]

    if args.extra:
        cmd += args.extra

    cmd += args.urls
    return cmd


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Stable high-quality YouTube audio downloader (output: audios/).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("urls", nargs="*", help="One or more video/playlist URLs")
    parser.add_argument(
        "-f",
        "--format",
        choices=sorted(FORMAT_PROFILES),
        default=None,
        help="Output audio format (default: ask, then m4a)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default="chrome",
        metavar="BROWSER",
        help="Browser to reuse cookies from (default: chrome; use '' to disable)",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        dest="input_files",
        action="append",
        type=Path,
        default=[],
        metavar="FILE",
        help="Read URLs from a text/Markdown file (repeatable)",
    )
    parser.add_argument(
        "--no-playlist",
        action="store_true",
        help="Download only the single video, not the whole playlist",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Skip items already downloaded (writes .audio-archive.txt)",
    )
    parser.add_argument(
        "--sponsorblock",
        action="store_true",
        help="Remove non-music sections using SponsorBlock",
    )
    parser.add_argument(
        "--no-ask",
        action="store_true",
        help="Do not ask interactively; use the default format",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="Print the available format profiles and exit",
    )
    args, extra = parser.parse_known_args(argv)
    args.extra = extra
    return args


def run(args: argparse.Namespace) -> int:
    """Build and run the yt-dlp command for resolved arguments."""
    if args.input_files:
        args.urls = yd.dedupe(list(args.urls) + yd.extract_urls(args.input_files))

    if not args.urls:
        print("error: at least one URL is required", file=sys.stderr)
        return 2

    if len(args.urls) > 1:
        args.no_playlist = True

    if args.format is None:
        args.format = "m4a" if args.no_ask else ask_format()

    args.output = Path(args.output).expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        print("error: ffmpeg is required but was not found on PATH", file=sys.stderr)
        return 2

    if args.extra and args.extra[0] == "--":
        args.extra = args.extra[1:]

    cmd = build_command(args)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: parse arguments and run the download."""
    args = parse_args(argv)
    if args.list_formats:
        for name in FORMAT_ORDER:
            print(f"  {name:<5} {FORMAT_PROFILES[name]['desc']}")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

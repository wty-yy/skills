#!/usr/bin/env python3
"""Download YouTube (and other yt-dlp sites) video with selectable quality.

Video and audio are downloaded separately and merged losslessly (stream copy)
into an MKV by default. When English and Simplified Chinese auto-captions are
available they are merged into a bilingual ASS track (both lines at font size
38) and embedded into the MKV, with a sidecar `.bilingual.srt` written too.
A Node.js runtime plus the EJS challenge solver work around YouTube's bot
checks, and browser cookies are reused for authentication when available.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import yd_common as yd

DEFAULT_OUTPUT = yd.VIDEO_DIR

CODEC_FILTERS = {
    "auto": "",
    "h264": "[vcodec^=avc1]",
    "vp9": "[vcodec^=vp9]",
    "av1": "[vcodec^=av01]",
}

SUBS_MODES = ("none", "auto", "manual", "both")

RESOLUTION_OPTIONS = [
    ("2160p", "2160", "4K，最大画质"),
    ("1440p", "1440", "2K"),
    ("1080p", "1080", "全高清（推荐）"),
    ("720p", "720", "高清，体积小"),
    ("480p", "480", "标清，体积很小"),
]


def ask_resolution(default: int = 1080) -> int:
    """Interactively ask which maximum resolution to use."""
    return int(yd.prompt_choice("选择视频分辨率：", RESOLUTION_OPTIONS, str(default)))


def resolve_container(args: argparse.Namespace) -> str:
    """Choose a merge container, defaulting to mkv."""
    if args.container != "auto":
        return args.container
    if args.codec in ("h264", "av1"):
        return "mp4"
    return "mkv"


def build_format_selector(args: argparse.Namespace) -> str:
    """Build a yt-dlp -f expression for the requested resolution and codec."""
    vfilter = CODEC_FILTERS[args.codec]
    height = args.resolution
    video = f"bv*{vfilter}[height<={height}]"

    container = resolve_container(args)
    afilter = ""
    if container == "mp4":
        afilter = "[ext=m4a]"
    elif container == "webm":
        afilter = "[ext=webm]"

    return (
        f"{video}+ba{afilter}[language^=en]/"
        f"{video}+ba{afilter}/"
        f"{video}+ba/"
        f"bv*[height<={height}]+ba/"
        f"b[height<={height}]/b"
    )


def build_command(args: argparse.Namespace) -> List[str]:
    """Assemble the yt-dlp command line from parsed arguments."""
    cmd: List[str] = [sys.executable, "-m", "yt_dlp"]
    cmd += yd.network_args(args.cookies_from_browser)
    cmd += [
        "--format",
        build_format_selector(args),
        "--merge-output-format",
        resolve_container(args),
        "--embed-metadata",
        "--embed-chapters",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--paths",
        str(args.output),
        "--output",
        "%(title)s [%(id)s].%(ext)s",
    ]
    cmd += yd.stability_args()

    if args.subs != "none":
        cmd += ["--sub-langs", args.sub_langs, "--convert-subs", "srt"]
        if args.subs in ("manual", "both"):
            cmd += ["--write-subs"]
        if args.subs in ("auto", "both"):
            cmd += ["--write-auto-subs"]
        if args.embed_subs:
            cmd += ["--embed-subs"]
    else:
        cmd += ["--no-write-subs"]

    if args.sponsorblock:
        cmd += ["--sponsorblock-remove", "default"]

    if args.playlist:
        if args.playlist_start:
            cmd += ["--playlist-start", str(args.playlist_start)]
        if args.playlist_end:
            cmd += ["--playlist-end", str(args.playlist_end)]
    elif len(args.urls) == 1:
        cmd += ["--no-playlist"]

    if args.archive:
        cmd += ["--download-archive", str(args.output / ".video-archive.txt")]

    if args.extra:
        cmd += args.extra

    cmd += args.urls
    return cmd


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Stable YouTube video downloader (output: videos/, default mkv + bilingual subs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("urls", nargs="*", help="One or more video/playlist URLs")
    parser.add_argument(
        "-r",
        "--resolution",
        type=int,
        default=None,
        metavar="HEIGHT",
        help="Maximum video height in pixels (default: ask, then 1080)",
    )
    parser.add_argument(
        "--codec",
        choices=sorted(CODEC_FILTERS),
        default="auto",
        help="Preferred video codec (default: auto, picks best)",
    )
    parser.add_argument(
        "--container",
        choices=["auto", "mp4", "mkv", "webm"],
        default="mkv",
        help="Output container (default: mkv)",
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
        "--subs",
        choices=SUBS_MODES,
        default="auto",
        help="Subtitle mode: none/auto/manual/both (default: auto)",
    )
    parser.add_argument(
        "--sub-langs",
        default="en,zh-Hans",
        help="Comma-separated subtitle languages to download (default: en,zh-Hans)",
    )
    parser.add_argument(
        "--bilingual-langs",
        default="en,zh-Hans",
        help="English,Chinese pair merged into the bilingual track (default: en,zh-Hans)",
    )
    parser.add_argument(
        "--en-size",
        type=int,
        default=yd.DEFAULT_EN_SIZE,
        help=f"Bilingual English font size (default: {yd.DEFAULT_EN_SIZE})",
    )
    parser.add_argument(
        "--zh-size",
        type=int,
        default=yd.DEFAULT_ZH_SIZE,
        help=f"Bilingual Chinese font size (default: {yd.DEFAULT_ZH_SIZE})",
    )
    parser.add_argument(
        "--no-embed-bilingual",
        action="store_true",
        help="Write bilingual sidecar files but do not embed them into the mkv",
    )
    parser.add_argument(
        "--embed-subs",
        action="store_true",
        help="Also embed the raw single-language subtitles via yt-dlp",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default="chrome",
        metavar="BROWSER",
        help="Browser to reuse cookies from (default: chrome; use '' to disable)",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Download the whole playlist (default: single video)",
    )
    parser.add_argument(
        "--playlist-start",
        type=int,
        default=None,
        help="First playlist item to download (1-based)",
    )
    parser.add_argument(
        "--playlist-end",
        type=int,
        default=None,
        help="Last playlist item to download (1-based)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Skip items already downloaded (writes .video-archive.txt)",
    )
    parser.add_argument(
        "--sponsorblock",
        action="store_true",
        help="Remove sponsor/intro/outro sections using SponsorBlock",
    )
    parser.add_argument(
        "--no-ask",
        action="store_true",
        help="Do not ask interactively; use the default resolution",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="List available formats for the given URL(s) and exit",
    )
    args, extra = parser.parse_known_args(argv)
    args.extra = extra
    return args


def run(args: argparse.Namespace) -> int:
    """Build and run the yt-dlp command, then merge bilingual subtitles."""
    if args.input_files:
        args.urls = yd.dedupe(list(args.urls) + yd.extract_urls(args.input_files))

    if not args.urls:
        print("error: at least one URL is required", file=sys.stderr)
        return 2

    if not shutil.which("ffmpeg"):
        print("error: ffmpeg is required but was not found on PATH", file=sys.stderr)
        return 2

    args.output = Path(args.output).expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)

    if args.list_formats:
        if args.resolution is None:
            args.resolution = 1080
        args.extra += ["--list-formats", "--no-write-thumbnail"]
    elif args.resolution is None:
        args.resolution = 1080 if args.no_ask else ask_resolution()

    before = yd.snapshot(args.output)
    cmd = build_command(args)
    try:
        code = subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130

    if args.subs != "none":
        changed = yd.snapshot(args.output) - before
        en_lang, _, zh_lang = args.bilingual_langs.partition(",")
        yd.postprocess_bilingual(
            args.output,
            changed,
            en_lang=en_lang or "en",
            zh_lang=zh_lang or "zh-Hans",
            en_size=args.en_size,
            zh_size=args.zh_size,
            embed=not args.no_embed_bilingual,
        )
    return code


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: parse arguments and run the download."""
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

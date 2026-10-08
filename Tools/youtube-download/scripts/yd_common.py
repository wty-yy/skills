#!/usr/bin/env python3
"""Shared helpers for the YouTube audio/video downloaders.

Provides the canonical output folders (audios/, videos/), yt-dlp network
arguments (Node runtime + EJS solver + browser cookies), URL extraction,
interactive quality prompts, and the bilingual-subtitle post-processing that
merges English + Simplified Chinese auto-captions and embeds them as ASS.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import make_bilingual_subs as mbs

ROOT = Path.cwd()
AUDIO_DIR = ROOT / "audios"
VIDEO_DIR = ROOT / "videos"

DEFAULT_EN_SIZE = 38
DEFAULT_ZH_SIZE = 38
DEFAULT_ZH_FONT = "Noto Sans CJK SC"
DEFAULT_EN_FONT = "Arial"

URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+")


def find_node() -> Optional[str]:
    """Locate a Node.js executable, including nvm installs not on PATH."""
    found = shutil.which("node")
    if found:
        return found

    candidates: List[Path] = []
    home = Path.home()
    nvm_dir = Path(os.environ.get("NVM_DIR", home / ".nvm"))
    versions = nvm_dir / "versions" / "node"
    if versions.is_dir():
        candidates.extend(sorted(versions.glob("*/bin/node"), reverse=True))
    candidates.extend(
        [
            Path("/usr/local/bin/node"),
            Path("/usr/bin/node"),
            Path("/opt/homebrew/bin/node"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def extract_urls(paths: Iterable[Path]) -> List[str]:
    """Read URLs out of plain-text or Markdown files, preserving order."""
    urls: List[str] = []
    for path in paths:
        text = path.expanduser().read_text(encoding="utf-8", errors="ignore")
        for match in URL_RE.findall(text):
            urls.append(match.rstrip(".,;"))
    return urls


def dedupe(items: Iterable[str]) -> List[str]:
    """Return items with duplicates removed, preserving first-seen order."""
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def network_args(cookies_from_browser: str) -> List[str]:
    """Build the shared yt-dlp arguments for auth and JS challenges."""
    args: List[str] = []
    node = find_node()
    if node:
        args += ["--js-runtimes", f"node:{node}"]
        args += ["--remote-components", "ejs:github"]
    if cookies_from_browser:
        args += ["--cookies-from-browser", cookies_from_browser]
    return args


def stability_args() -> List[str]:
    """Build the shared yt-dlp arguments for reliable downloads."""
    return [
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--file-access-retries",
        "5",
        "--concurrent-fragments",
        "4",
        "--continue",
        "--no-overwrites",
        "--ignore-errors",
        "--newline",
        "--progress",
        "--sleep-requests",
        "1",
    ]


def prompt_choice(title: str, options: Sequence[Tuple[str, str, str]], default: str) -> str:
    """Interactively ask the user to pick an option value.

    options is a sequence of (label, value, description). The prompt is only
    shown when stdin is a terminal; otherwise the default value is returned.
    """
    if not sys.stdin.isatty():
        return default
    print(title)
    for i, (label, _, desc) in enumerate(options, 1):
        print(f"  {i}) {label:<12} {desc}")
    while True:
        raw = input(f"选择 [1-{len(options)}] (默认 {default}): ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][1]
        print("输入无效，请重试。")


def snapshot(directory: Path) -> set:
    """Return the set of file names currently in a directory."""
    return {p.name for p in directory.iterdir()} if directory.is_dir() else set()


def _base_from_subtitle(name: str, langs: Sequence[str]) -> Optional[str]:
    """Strip a known '<base>.<lang>.srt|vtt' suffix and return the base."""
    for lang in langs:
        for suffix in (f".{lang}.srt", f".{lang}.vtt"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
    return None


def _mux_ass(video: Path, ass: Path, language: str) -> Path:
    """Remux a video stream-copying it and embedding an ASS subtitle track."""
    out = video.with_suffix(".mkv")
    tmp = out.with_name(out.stem + ".muxing.mkv")
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(video),
        "-i",
        str(ass),
        "-map",
        "0",
        "-map",
        "1",
        "-c",
        "copy",
        "-c:s",
        "ass",
        "-metadata:s:s:0",
        f"language={language}",
        "-disposition:s:0",
        "default",
        str(tmp),
    ]
    subprocess.check_call(cmd)
    if video != out and video.exists():
        video.unlink()
    tmp.replace(out)
    return out


def postprocess_bilingual(
    output_dir: Path,
    changed: Iterable[str],
    en_lang: str = "en",
    zh_lang: str = "zh-Hans",
    en_size: int = DEFAULT_EN_SIZE,
    zh_size: int = DEFAULT_ZH_SIZE,
    en_font: str = DEFAULT_EN_FONT,
    zh_font: str = DEFAULT_ZH_FONT,
    embed: bool = True,
) -> List[Path]:
    """Merge en+zh auto-captions and embed them as ASS for changed videos.

    Returns the list of produced bilingual ASS files.
    """
    langs = [en_lang, zh_lang]
    video_exts = (".mkv", ".mp4", ".webm")
    bases = set()
    for name in changed:
        base = _base_from_subtitle(name, langs)
        if base is None:
            for ext in video_exts:
                if name.endswith(ext):
                    base = name[: -len(ext)]
                    break
        if base:
            bases.add(base)

    produced: List[Path] = []
    for base in sorted(bases):
        en_path = output_dir / f"{base}.{en_lang}.srt"
        zh_path = output_dir / f"{base}.{zh_lang}.srt"
        if not en_path.exists() and not zh_path.exists():
            continue

        en_cues = mbs.parse_srt(en_path) if en_path.exists() else []
        zh_cues = mbs.parse_srt(zh_path) if zh_path.exists() else []
        bilingual = mbs.build_bilingual(mbs.align(en_cues, zh_cues))

        ass_path = output_dir / f"{base}.bilingual.ass"
        srt_path = output_dir / f"{base}.bilingual.srt"
        mbs.write_srt(srt_path, bilingual)
        mbs.write_ass(ass_path, bilingual, en_font, zh_font, en_size, zh_size)
        produced.append(ass_path)
        print(f"[bilingual] wrote {srt_path.name} ({len(bilingual)} cues)")

        if embed:
            video = None
            for ext in video_exts:
                candidate = output_dir / f"{base}{ext}"
                if candidate.exists():
                    video = candidate
                    break
            if video is not None:
                out = _mux_ass(video, ass_path, "zho")
                print(f"[bilingual] embedded subtitles into {out.name}")
    return produced

#!/usr/bin/env python3
"""Merge two YouTube auto-caption SRT files into one bilingual subtitle.

YouTube auto-captions use a rolling two-line window: each cue repeats the
previous line before showing the new one. This tool de-rolls both tracks,
aligns them by timestamp, and emits either a bilingual SRT or an ASS file
whose font size can be tuned (SRT cannot control font size).
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

TS = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
CUE_RE = re.compile(
    rf"^\s*(\d+)\s*\n{TS}\s*-->\s*{TS}\s*\n(.*?)(?=\n\s*\n\s*\d+\s*\n\d{{2}}:\d{{2}}:\d{{2}},\d{{3}}|\Z)",
    re.S | re.M,
)


@dataclass
class Cue:
    """A single parsed subtitle cue."""

    start: float
    end: float
    lines: List[str]


def to_seconds(h: str, m: str, s: str, ms: str) -> float:
    """Convert SRT timestamp fields into seconds."""
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


SPEAKER_RE = re.compile(r"^(?:>>+|>)\s*")


def clean_line(line: str) -> str:
    """Trim whitespace and strip leading speaker-change markers like '>>'."""
    line = line.strip()
    while True:
        stripped = SPEAKER_RE.sub("", line).strip()
        if stripped == line:
            return line
        line = stripped


def parse_srt(path: Path, strip_marks: bool = True) -> List[Cue]:
    """Parse an SRT file, tolerating blank lines inside cue text."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    cues: List[Cue] = []
    for match in CUE_RE.finditer(text):
        start = to_seconds(*match.group(2, 3, 4, 5))
        end = to_seconds(*match.group(6, 7, 8, 9))
        body = match.group(10)
        if strip_marks:
            lines = [l for l in (clean_line(x) for x in body.splitlines()) if l]
        else:
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        cues.append(Cue(start, end, lines))
    return cues


def deroll(lines: List[str], prev: List[str]) -> List[str]:
    """Return only the new lines, dropping the carried-over rolling lines."""
    if not lines:
        return []
    for k in range(min(len(lines), len(prev)), 0, -1):
        if lines[:k] == prev[-k:]:
            return lines[k:]
    return lines


def align(en: List[Cue], zh: List[Cue], tolerance: float = 0.1) -> List[Tuple[float, float, List[str], List[str]]]:
    """Pair English and Chinese cues by start time."""
    by_start = {round(c.start, 3): c for c in zh}
    starts = sorted(by_start)
    pairs: List[Tuple[float, float, List[str], List[str]]] = []
    for cue in en:
        match = by_start.get(round(cue.start, 3))
        if match is None and starts:
            nearest = min(starts, key=lambda s: abs(s - cue.start))
            if abs(nearest - cue.start) <= tolerance:
                match = by_start[nearest]
        zh_lines = match.lines if match else []
        pairs.append((cue.start, cue.end, cue.lines, zh_lines))
    return pairs


def build_bilingual(pairs: List[Tuple[float, float, List[str], List[str]]]) -> List[Tuple[float, float, str]]:
    """De-roll paired cues and merge them into bilingual blocks."""
    out: List[Tuple[float, float, str]] = []
    prev_en: List[str] = []
    prev_zh: List[str] = []
    for start, end, en_lines, zh_lines in pairs:
        new_en = deroll(en_lines, prev_en)
        new_zh = deroll(zh_lines, prev_zh)
        prev_en, prev_zh = en_lines, zh_lines
        combined = "\n".join(new_en + new_zh)
        if combined:
            out.append((start, end, combined))
    return out


def fmt_srt(seconds: float) -> str:
    """Format seconds as an SRT timestamp."""
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ass(seconds: float) -> str:
    """Format seconds as an ASS timestamp."""
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def write_srt(path: Path, cues: List[Tuple[float, float, str]]) -> None:
    """Write bilingual cues as an SRT file."""
    blocks = []
    for i, (start, end, text) in enumerate(cues, 1):
        blocks.append(f"{i}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def write_ass(
    path: Path,
    cues: List[Tuple[float, float, str]],
    en_font: str,
    zh_font: str,
    en_size: int,
    zh_size: int,
) -> None:
    """Write bilingual cues as an ASS file with per-language styling."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,{en_font},{en_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,45,1
Style: CN,{zh_font},{zh_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,45,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def sanitize(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    events = []
    for start, end, text in cues:
        parts = text.split("\n")
        n_en = 0
        for line in parts:
            if re.search(r"[\u4e00-\u9fff\u3000-\u303f]", line):
                break
            n_en += 1
        en_text = "\\N".join(sanitize(ln) for ln in parts[:n_en])
        zh_text = "\\N".join(sanitize(ln) for ln in parts[n_en:])
        chunks = []
        if en_text:
            chunks.append(f"{{\\rEN}}{en_text}")
        if zh_text:
            chunks.append(f"{{\\rCN}}{zh_text}")
        body = "\\N".join(chunks)
        events.append(f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},CN,,0,0,0,,{body}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Merge two subtitle tracks into a bilingual subtitle.")
    parser.add_argument("en", type=Path, help="English SRT file")
    parser.add_argument("zh", type=Path, help="Chinese SRT file")
    parser.add_argument("-o", "--out-prefix", type=Path, default=None, help="Output path prefix")
    parser.add_argument("--en-font", default="Arial", help="English font name (default: Arial)")
    parser.add_argument("--zh-font", default="Noto Sans CJK SC", help="Chinese font name")
    parser.add_argument("--en-size", type=int, default=38, help="English font size at 1080p (default: 38)")
    parser.add_argument("--zh-size", type=int, default=38, help="Chinese font size at 1080p (default: 38)")
    parser.add_argument(
        "--keep-speaker-marks",
        action="store_true",
        help="Keep leading '>>' speaker-change markers in subtitles",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point: parse, merge and write SRT + ASS outputs."""
    args = parse_args()
    if args.out_prefix:
        prefix = args.out_prefix
    else:
        prefix = Path(str(args.en).replace(".en.srt", ""))

    keep = args.keep_speaker_marks
    en_cues = parse_srt(args.en, strip_marks=not keep)
    zh_cues = parse_srt(args.zh, strip_marks=not keep)
    print(f"parsed {len(en_cues)} English cues, {len(zh_cues)} Chinese cues")

    pairs = align(en_cues, zh_cues)
    bilingual = build_bilingual(pairs)
    print(f"produced {len(bilingual)} bilingual cues")

    srt_path = Path(f"{prefix}.bilingual.srt")
    ass_path = Path(f"{prefix}.bilingual.ass")
    write_srt(srt_path, bilingual)
    write_ass(ass_path, bilingual, args.en_font, args.zh_font, args.en_size, args.zh_size)
    print(f"wrote {srt_path}")
    print(f"wrote {ass_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

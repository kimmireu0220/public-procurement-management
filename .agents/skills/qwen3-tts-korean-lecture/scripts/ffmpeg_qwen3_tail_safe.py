#!/usr/bin/env python3
"""Run FFmpeg while making short MP3 end probes sample-accurate.

FFmpeg input seeking with ``-sseof -0.200`` can return less than 200 ms for an
MP3 because seeking lands on compressed frame boundaries.  The production TTS
verifier intentionally asks for that exact probe.  For only that invocation,
this wrapper decodes the final second and filters it down to the final 200 ms.
All other FFmpeg commands are passed through unchanged.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


TAIL_REQUEST = "-0.200"
SAFE_SEEK = "-1.000"
TAIL_FILTER = "areverse,atrim=duration=0.2,areverse"


def real_ffmpeg() -> str:
    configured = os.environ.get("QWEN3_TTS_REAL_FFMPEG")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise SystemExit(f"QWEN3_TTS_REAL_FFMPEG is not a file: {path}")
    for candidate in (Path("/opt/homebrew/bin/ffmpeg"), Path("/usr/local/bin/ffmpeg")):
        if candidate.is_file():
            return str(candidate)
    located = shutil.which("ffmpeg")
    if located:
        return located
    raise SystemExit("ffmpeg executable not found")


def adjusted_arguments(arguments: list[str]) -> list[str]:
    args = list(arguments)
    try:
        seek_index = args.index("-sseof")
    except ValueError:
        return args
    if seek_index + 1 >= len(args) or args[seek_index + 1] != TAIL_REQUEST:
        return args
    if "-af" in args or "-filter:a" in args:
        raise SystemExit("refusing to combine the tail-safe probe with another audio filter")
    try:
        format_index = args.index("-f")
    except ValueError as exc:
        raise SystemExit("tail-safe probe is missing its output format") from exc
    args[seek_index + 1] = SAFE_SEEK
    args[format_index:format_index] = ["-af", TAIL_FILTER]
    return args


def main() -> None:
    executable = real_ffmpeg()
    arguments = adjusted_arguments(sys.argv[1:])
    os.execv(executable, [executable, *arguments])


if __name__ == "__main__":
    main()

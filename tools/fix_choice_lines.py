#!/usr/bin/env python3
"""agent_extract 객관식·소문항 줄 분리 (①~⑩ 각각 한 줄)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import AGENT_EXTRACT_DIR, SUBJECT_CATALOG  # noqa: E402

QUESTION_RE = re.compile(r"^(\d+\.\s+)(.+)$")
ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답")
MARKER_SPLIT_RE = re.compile(r"(?=[①②③④⑤⑥⑦⑧⑨⑩])")
ALREADY_SPLIT_RE = re.compile(r"^\s+[①②③④⑤⑥⑦⑧⑨⑩]")


def split_question_line(line: str) -> list[str]:
    stripped = line.rstrip()
    if not stripped or stripped.startswith("<!--") or stripped.startswith("#"):
        return [line]
    m = QUESTION_RE.match(stripped)
    if not m:
        return [line]
    prefix, body = m.group(1), m.group(2)
    if "①" not in body or "②" not in body:
        return [line]
    first = body.find("①")
    if first <= 0:
        return [line]
    stem = body[:first].rstrip()
    markers = MARKER_SPLIT_RE.split(body[first:])
    markers = [p.strip() for p in markers if p.strip()]
    if len(markers) < 2:
        return [line]
    out = [f"{prefix}{stem}"]
    for part in markers:
        out.append(f"   {part}")
    return out


def process_text(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    out: list[str] = []
    in_answers = False
    changes = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if ANSWER_HEADING_RE.match(line.strip()):
            in_answers = True
        if in_answers or line.strip().startswith("<!--") or ALREADY_SPLIT_RE.match(line):
            out.append(line)
            i += 1
            continue
        if QUESTION_RE.match(line.strip()) and "①" in line and "②" in line:
            split = split_question_line(line)
            if len(split) > 1:
                changes += 1
                out.extend(split)
                i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out).rstrip() + "\n", changes


def main() -> None:
    parser = argparse.ArgumentParser(description="문항 줄의 ①②③④를 각각 한 줄로 분리합니다.")
    parser.add_argument("--subject", default="4", choices=sorted(SUBJECT_CATALOG))
    parser.add_argument("--part", type=int, default=0, help="0이면 해당 과목 전 Part")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slug = str(SUBJECT_CATALOG[args.subject]["slug"])
    base = AGENT_EXTRACT_DIR / slug
    parts = [base / f"part{args.part}.md"] if args.part else sorted(base.glob("part*.md"))
    total = 0
    for path in parts:
        if not path.is_file():
            continue
        new_text, n = process_text(path.read_text(encoding="utf-8"))
        total += n
        if n and not args.dry_run:
            path.write_text(new_text, encoding="utf-8")
        print(f"{path.name}: {n}문항 분리")
    print(f"합계 {total}문항 분리{' (dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()

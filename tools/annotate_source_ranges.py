#!/usr/bin/env python3
"""출처 주석에 문항 범위 (문항 N~M)를 보강합니다."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import AGENT_EXTRACT_DIR  # noqa: E402

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답")
SOURCE_RE = re.compile(r"^<!--\s*source:\s*(.+?)\s*-->")
QUESTION_RE = re.compile(r"^(\d+)\.\s+")
RANGE_RE = re.compile(r"\(문항\s+\d+")

PART6_DANWON_BLOCKS: list[tuple[str, int, int, str]] = [
    ("## Chapter 01 단원별 출제예상문제", 1, 28, "Part 6/page_0012.jpg ~ page_0018.jpg"),
    ("## Chapter 02 단원별 출제예상문제", 1, 28, "Part 6/page_0025.jpg ~ page_0030.jpg"),
    ("## Chapter 03 단원별 출제예상문제", 1, 28, "Part 6/page_0037.jpg ~ page_0042.jpg"),
    ("## Chapter 04 단원별 출제예상문제", 1, 16, "Part 6/page_0047.jpg ~ page_0049.jpg"),
    ("## Chapter 05 단원별 출제예상문제", 1, 15, "Part 6/page_0056.jpg ~ page_0057.jpg"),
    ("## Chapter 06 단원별 출제예상문제", 1, 13, "Part 6/page_0060.jpg ~ page_0066.jpg"),
]


def insert_part6_danwon_sources(lines: list[str]) -> tuple[list[str], int]:
    inserted = 0
    for heading, start_q, end_q, pages in PART6_DANWON_BLOCKS:
        try:
            idx = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
        except StopIteration:
            continue
        end_idx = next(
            (i for i in range(idx + 1, len(lines)) if lines[i].startswith("## ")),
            len(lines),
        )
        if any(SOURCE_RE.match(ln.strip()) for ln in lines[idx:end_idx]):
            continue
        comment = f"<!-- source: {pages} (문항 {start_q}~{end_q}) -->"
        lines.insert(end_idx, comment)
        inserted += 1
    return lines, inserted


def consolidate_ox_sources(lines: list[str]) -> tuple[list[str], int]:
    """OX 퀴즈: 동일 페이지 연속 문항 → 마지막에 범위 source 1개."""
    out: list[str] = []
    changes = 0
    in_answers = False
    in_ox = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if ANSWER_HEADING_RE.match(line.strip()):
            in_answers = True
        if line.startswith("## "):
            in_ox = "OX" in line or "ox" in line.lower()
        if in_answers or not in_ox:
            out.append(line)
            i += 1
            continue
        qm = QUESTION_RE.match(line.strip())
        if not qm or "(O/X)" not in line:
            out.append(line)
            i += 1
            continue
        start_q = int(qm.group(1))
        group_qs = [line]
        page = None
        j = i + 1
        while j < len(lines):
            if not SOURCE_RE.match(lines[j].strip()):
                break
            pg = SOURCE_RE.match(lines[j].strip()).group(1).split(",")[0].strip()
            if RANGE_RE.search(pg):
                group_qs.append(lines[j])
                j += 1
                break
            if page is None:
                page = pg
            elif pg != page:
                break
            j += 1
            if j >= len(lines):
                break
            nqm = QUESTION_RE.match(lines[j].strip())
            if not nqm or "(O/X)" not in lines[j]:
                break
            group_qs.append(lines[j])
            j += 1
            if j < len(lines) and SOURCE_RE.match(lines[j].strip()):
                continue
            break
        end_q = start_q
        for gl in group_qs[1:]:
            m = QUESTION_RE.match(gl.strip())
            if m:
                end_q = int(m.group(1))
        if page and len(group_qs) > 1:
            out.extend(group_qs)
            rng = f" (문항 {start_q}~{end_q})" if end_q > start_q else f" (문항 {start_q})"
            out.append(f"<!-- source: {page}{rng} -->")
            changes += 1
            i = j
            continue
        out.append(line)
        if j > i + 1 and SOURCE_RE.match(lines[i + 1].strip()):
            pg = SOURCE_RE.match(lines[i + 1].strip()).group(1).split(",")[0].strip()
            if not RANGE_RE.search(lines[i + 1]):
                out.append(f"<!-- source: {pg} (문항 {start_q}) -->")
                changes += 1
            else:
                out.append(lines[i + 1])
            i = j
        else:
            i += 1
    return out, changes


def add_single_source_ranges(lines: list[str]) -> tuple[list[str], int]:
    """이미 있는 단일 source에 (문항 N) 보강."""
    changes = 0
    out: list[str] = []
    in_answers = False
    pending_q: int | None = None
    for line in lines:
        if ANSWER_HEADING_RE.match(line.strip()):
            in_answers = True
        qm = QUESTION_RE.match(line.strip()) if not in_answers else None
        if qm:
            pending_q = int(qm.group(1))
            out.append(line)
            continue
        sm = SOURCE_RE.match(line.strip()) if not in_answers else None
        if sm and pending_q is not None:
            pg = sm.group(1)
            if not RANGE_RE.search(pg):
                out.append(f"<!-- source: {pg} (문항 {pending_q}) -->")
                changes += 1
            else:
                out.append(line)
            pending_q = None
            continue
        if line.startswith("## "):
            pending_q = None
        out.append(line)
    return out, changes


def process_part6(path: Path, dry_run: bool) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    lines, n_dan = insert_part6_danwon_sources(lines)
    lines, n_ox = consolidate_ox_sources(lines)
    lines, n_rng = add_single_source_ranges(lines)
    text = "\n".join(lines).rstrip() + "\n"
    print(f"단원별 {n_dan}건, OX 통합 {n_ox}건, 범위 표기 {n_rng}건")
    if not dry_run:
        path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--part6", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.part6:
        parser.error("--part6 필요")
    path = AGENT_EXTRACT_DIR / "1과목_공공조달의 이해" / "part6.md"
    process_part6(path, args.dry_run)


if __name__ == "__main__":
    main()

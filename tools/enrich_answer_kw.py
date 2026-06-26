#!/usr/bin/env python3
"""agent_extract 정답 섹션 kw 보강 — compact 전개·placeholder 교체."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import SUBJECT_CATALOG  # noqa: E402
from mock_exam_common import (  # noqa: E402
    ANSWER_HEAD,
    CHAPTER_NUM_RE,
    COMPACT_ANSWER_TOKEN_RE,
    EXTRACT,
    FULL_ANSWER_LINE_RE,
    HEADER_LINE_RE,
    PART_HEAD,
    PLACEHOLDER_KW,
    correct_choice_text,
    load_subject_pool,
    parse_section_header,
    stype_from_section_title,
)

CHOICE_FROM_LINES = re.compile(r"^\s*([①②③④⑤])\s*(.+)$")


def pool_key_map(subject_no: str, part: int) -> dict[tuple[int, str, int], object]:
    out: dict[tuple[int, str, int], object] = {}
    for q in load_subject_pool(subject_no):
        if q.part == part:
            out[(q.chapter, q.stype, q.qn)] = q
    return out


def choice_text_from_body(
    body: str, chapter: int, stype: str, qn: int, ans: str
) -> str:
    """extract 본문에서 (chapter, stype, qn) 문항의 정답 선지 텍스트."""
    cur_ch, cur_st = 0, ""
    cur_qn = 0
    cur_ans = ""
    choices: dict[str, str] = {}
    in_q = False

    for raw in body.splitlines():
        line = raw.rstrip()
        header = parse_section_header(raw)
        if header:
            cur_ch, title = header
            st = stype_from_section_title(title)
            if st != "other":
                cur_st = st
            in_q = False
            choices = {}
            continue
        if HEADER_LINE_RE.match(line) and not CHAPTER_NUM_RE.search(line):
            title = HEADER_LINE_RE.sub("", line).strip()
            if title and not re.match(r"Part\s+\d+", title, re.I):
                st = stype_from_section_title(title)
                if st != "other":
                    cur_st = st
            in_q = False
            choices = {}
            continue
        m = re.match(r"^(\d+)\.\s+(.+)", line)
        if m:
            if (
                in_q
                and cur_ch == chapter
                and cur_st == stype
                and cur_qn == qn
                and cur_ans == ans
                and ans in choices
            ):
                return choices[ans]
            cur_qn = int(m.group(1))
            in_q = cur_ch == chapter and cur_st == stype and cur_qn == qn
            choices = {}
            continue
        cm = CHOICE_FROM_LINES.match(line)
        if cm and in_q:
            choices[cm.group(1)] = cm.group(2).strip()

    return ""


def ox_stem_from_body(body: str, chapter: int, qn: int) -> str:
    cur_ch = 0
    for raw in body.splitlines():
        header = parse_section_header(raw)
        if header:
            cur_ch, title = header
            continue
        if HEADER_LINE_RE.match(raw.strip()) and not CHAPTER_NUM_RE.search(raw):
            continue
        m = re.match(r"^(\d+)\.\s+(.+)", raw.strip())
        if m and cur_ch == chapter and int(m.group(1)) == qn:
            stem = m.group(2).strip()
            return re.sub(r"\s*\(O/X\)\s*$", "", stem)
    return ""


def kw_for(
    pool_map: dict,
    body: str,
    part: int,
    chapter: int,
    stype: str,
    qn: int,
    ans: str,
) -> str:
    if stype == "ox":
        text = ox_stem_from_body(body, chapter, qn)
        if text:
            return text
    q = pool_map.get((chapter, stype, qn))
    if q and q.ans == ans:
        text = correct_choice_text(q)
        if text:
            return text
    return choice_text_from_body(body, chapter, stype, qn, ans)


def enrich_file(path: Path, subject_no: str, *, dry_run: bool) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    pm = PART_HEAD.search(text)
    part = int(pm.group(1)) if pm else 0
    acut = ANSWER_HEAD.search(text)
    if not acut or not part:
        return 0, 0

    pool_map = pool_key_map(subject_no, part)
    body = text[: acut.start()]
    answer_lines = text[acut.start() :].splitlines(keepends=True)

    chapter = 0
    stype = ""
    out_lines: list[str] = []
    compact_n = placeholder_n = 0

    for raw in answer_lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped or ANSWER_HEAD.match(stripped):
            out_lines.append(raw)
            continue

        header = parse_section_header(raw)
        if header:
            chapter, title = header
            st = stype_from_section_title(title)
            if st != "other":
                stype = st
            out_lines.append(raw)
            continue

        if HEADER_LINE_RE.match(stripped) and not CHAPTER_NUM_RE.search(stripped):
            title = HEADER_LINE_RE.sub("", stripped).strip()
            if title and not re.match(r"Part\s+\d+", title, re.I):
                st = stype_from_section_title(title)
                if st != "other":
                    stype = st
            out_lines.append(raw)
            continue

        if not chapter or not stype:
            out_lines.append(raw)
            continue

        fm = FULL_ANSWER_LINE_RE.match(stripped)
        if fm:
            n, ans, kw = int(fm.group(1)), fm.group(2), fm.group(3).strip()
            if kw == PLACEHOLDER_KW or not kw:
                new_kw = kw_for(pool_map, body, part, chapter, stype, n, ans)
                if new_kw and new_kw != kw:
                    placeholder_n += 1
                    indent = line[: len(line) - len(line.lstrip())]
                    out_lines.append(f"{indent}{n}. {ans} — {new_kw}\n")
                    continue
            out_lines.append(raw)
            continue

        tokens = COMPACT_ANSWER_TOKEN_RE.findall(stripped)
        if len(tokens) >= 2:
            indent = line[: len(line) - len(line.lstrip())]
            for n_s, ans in tokens:
                n = int(n_s)
                new_kw = kw_for(pool_map, body, part, chapter, stype, n, ans)
                compact_n += 1
                if new_kw:
                    out_lines.append(f"{indent}{n}. {ans} — {new_kw}\n")
                else:
                    out_lines.append(f"{indent}{n}. {ans}\n")
            continue

        out_lines.append(raw)

    if compact_n or placeholder_n:
        if not dry_run:
            path.write_text(body + "".join(out_lines), encoding="utf-8")
    return compact_n, placeholder_n


def main() -> None:
    parser = argparse.ArgumentParser(description="agent_extract 정답 kw 보강")
    parser.add_argument("--subject", type=str, help="과목 번호 1~4")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else [
        sn for sn, info in SUBJECT_CATALOG.items() if info["exam_type"] in ("필기", "실기")
    ]

    total_c = total_p = 0
    for sn in subjects:
        slug = str(SUBJECT_CATALOG[sn]["slug"])
        extract_dir = EXTRACT / slug
        if not extract_dir.is_dir():
            continue
        for path in sorted(extract_dir.glob("part*.md")):
            c, p = enrich_file(path, sn, dry_run=args.dry_run)
            if c or p:
                mode = "would" if args.dry_run else ""
                print(f"{mode} {path.name}: compact={c} placeholder={p}")
            total_c += c
            total_p += p

    print(f"합계: compact {total_c}, placeholder {total_p}")


if __name__ == "__main__":
    main()

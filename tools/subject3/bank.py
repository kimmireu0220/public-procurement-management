"""3과목 문제 은행에서 stable_id로 지문·정답 추출."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from question_bank import QuestionBankParserConfig, parse_question_index

ROOT = Path(__file__).resolve().parents[2]
PROBLEM_MD = ROOT / "output/problem_book_final/3과목_공공계약관리/3과목_문제집.md"
EXTRACT_DIR = ROOT / "output/agent_extract/3과목_공공계약관리"

ANS_LINE = re.compile(r"^(\d+)\.\s+([①②③④OX]+)\s*[—–-]")
CHAPTER_HDR = re.compile(r"^#+\s*(?:CHAPTER|Chapter)\s+(\d+)", re.I)
QUESTION_PARSER = QuestionBankParserConfig(
    subject=3,
    chapter_header=CHAPTER_HDR,
    check_type="cqa",
)


def parse_stable_id(sid: str) -> tuple[int, int, str, int]:
    parts = sid.split(":")
    if len(parts) != 5 or parts[0] != "3":
        raise ValueError(f"invalid stable_id: {sid}")
    return int(parts[1]), int(parts[2]), parts[3], int(parts[4])


@cache
def load_answer_index(part: int) -> dict[tuple[int, str, int], str]:
    path = EXTRACT_DIR / f"part{part}.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    idx: dict[tuple[int, str, int], str] = {}
    chapter = 0
    stype = "exam"
    in_answers = False
    for line in text.splitlines():
        if "정답 및 해설" in line:
            in_answers = True
            chapter = 0
            continue
        if not in_answers:
            continue
        ch = CHAPTER_HDR.match(line)
        if ch:
            chapter = int(ch.group(1))
            if "Check Q&A" in line:
                stype = "cqa"
            elif "단원별 출제예상" in line:
                stype = "exam"
            elif re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I):
                stype = "ox"
            continue
        if "Check Q&A" in line:
            stype = "cqa"
        elif "단원별 출제예상" in line:
            stype = "exam"
        elif re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I):
            stype = "ox"
        m = ANS_LINE.match(line.strip())
        if m and stype != "ox":
            ans = m.group(2)
            if ans in "①②③④":
                idx[(chapter, stype, int(m.group(1)))] = ans
    return idx


@cache
def load_questions_index() -> dict[str, dict]:
    return parse_question_index(PROBLEM_MD.read_text(encoding="utf-8"), QUESTION_PARSER)


def fetch_question(sid: str) -> tuple[dict, str]:
    part, chapter, stype, qn = parse_stable_id(sid)
    questions = load_questions_index()
    if sid not in questions:
        raise KeyError(f"question not in problem book: {sid}")
    answers = load_answer_index(part)
    key = (chapter, stype, qn)
    if key not in answers:
        raise KeyError(f"answer not in agent_extract part{part}: {sid} key={key}")
    return questions[sid], answers[key]

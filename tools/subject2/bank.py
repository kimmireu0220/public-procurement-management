"""2과목 문제 은행에서 stable_id로 지문·정답 추출."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBLEM_MD = ROOT / "output/problem_book_final/2과목_공공조달 계획분석/2과목_문제집.md"
EXTRACT_DIR = ROOT / "output/agent_extract/2과목_공공조달 계획분석"

CHOICE_RE = re.compile(r"^\s*([①②③④])\s+(.+)$")
Q_LINE = re.compile(r"^(\d+)\.\s+(.+)$")
SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")
ANS_LINE = re.compile(r"^(\d+)\.\s+([①②③④OX]+)\s*[—–-]")
CHAPTER_HDR = re.compile(r"^#+\s*\[?(?:CHAPTER|Chapter)\s+(\d+)", re.I)


def parse_stable_id(sid: str) -> tuple[int, int, str, int]:
    parts = sid.split(":")
    if len(parts) != 5 or parts[0] != "2":
        raise ValueError(f"invalid stable_id: {sid}")
    return int(parts[1]), int(parts[2]), parts[3], int(parts[4])


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
                stype = "check"
            elif "단원별 출제예상" in line:
                stype = "exam"
            elif re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I):
                stype = "ox"
            continue
        if "Check Q&A" in line:
            stype = "check"
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


def load_questions_index() -> dict[str, dict]:
    text = PROBLEM_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    part = 0
    chapter = 0
    stype = "exam"
    out: dict[str, dict] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## Part"):
            part = int(re.search(r"Part (\d+)", line).group(1))
            chapter = 0
            i += 1
            continue
        ch = CHAPTER_HDR.match(line)
        if ch:
            chapter = int(ch.group(1))
            if "Check Q&A" in line:
                stype = "check"
            elif "단원별 출제예상" in line:
                stype = "exam"
            elif re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I):
                stype = "ox"
            i += 1
            continue
        if "Check Q&A" in line:
            stype = "check"
            i += 1
            continue
        if "단원별 출제예상" in line:
            stype = "exam"
            i += 1
            continue
        if re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I) and line.startswith("#"):
            stype = "ox"
            i += 1
            continue
        qm = Q_LINE.match(line.strip())
        if qm and "(O/X)" in line:
            i += 1
            continue
        if not qm or stype == "ox":
            i += 1
            continue
        qn = int(qm.group(1))
        stem = qm.group(2).strip()
        if re.match(r"^[①②③④]", stem):
            i += 1
            continue
        choices: list[tuple[str, str]] = []
        source = ""
        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if Q_LINE.match(ln.strip()) or ln.startswith("###") or ln.startswith("##"):
                break
            if ln.strip() == "---":
                break
            sm = SOURCE_RE.search(ln)
            if sm:
                source = sm.group(1).strip()
            cm = CHOICE_RE.match(ln)
            if cm:
                choices.append((cm.group(1), cm.group(2).strip()))
            j += 1
        if len(choices) >= 4 and source:
            sid = f"2:{part}:{chapter}:{stype}:{qn}"
            out[sid] = {
                "stem": stem,
                "choices": choices[:4],
                "source": source,
            }
        i = j
    return out


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

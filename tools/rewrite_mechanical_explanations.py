#!/usr/bin/env python3
"""기계적 P2 해설을 문항·선지 기반 해설로 보강한다."""

from __future__ import annotations

import re
import sys
from pathlib import Path

MECH = re.compile(
    r"혼동한 오답|절차·요건을 뒤바꾼|법령상 효과나 적용 주체를 바꿔|보기와 거리가 있다|이\(가\)\s*정답이다"
)
ANS_SPLIT = re.compile(r"^##\s+Part\s+\d+\s+정답 및 해설", re.M)
CHOICE = re.compile(r"^\s*([①②③④])\s+(.+)$")
Q_START = re.compile(r"^(\d+)\.\s+(.+)$")
ANS_LINE = re.compile(r"^(\d+)\.\s*([①②③④]|O|X)\s*[—–-]\s*(.+)$")
WRONG_Q = re.compile(
    r"옳지 않은|거리가 먼|해당하지 않는|적절하지 않|틀린 것|잘못|부적절|아닌 것"
)
COMBO_Q = re.compile(r"모두 고른|옳은 것만|해당하는 것만")
TAIL_START = re.compile(
    r"\s*[①②③④]의\s+'|이\(가\)\s*정답이다|「[^」]+」에서\s*정답"
)


def parse_questions_in_block(text: str) -> dict[int, dict]:
    lines = text.splitlines()
    questions: dict[int, dict] = {}
    i = 0
    while i < len(lines):
        m = Q_START.match(lines[i])
        if not m:
            i += 1
            continue
        num = int(m.group(1))
        stem_parts = [m.group(2).strip()]
        i += 1
        choices: dict[str, str] = {}
        while i < len(lines):
            line = lines[i]
            if Q_START.match(line) or line.startswith("<!--"):
                break
            if line.startswith("## ") or line.startswith("### ") or line.startswith("#### "):
                break
            if line.strip() == "---":
                break
            cm = CHOICE.match(line)
            if cm:
                choices[cm.group(1)] = cm.group(2).strip()
                i += 1
                continue
            if line.strip() and not line.startswith("#"):
                stem_parts.append(line.strip())
            i += 1
        questions[num] = {"stem": " ".join(stem_parts), "choices": choices}
    return questions


def build_question_index(body: str) -> dict[str, dict[int, dict]]:
    """섹션 키 → 문항 맵. part4의 ###/#### 계층도 지원."""
    index: dict[str, dict[int, dict]] = {}
    lines = body.splitlines()
    sec_key = "_root"
    ch_num = ""
    sub = ""
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, sec_key
        if buf:
            index[sec_key] = parse_questions_in_block("\n".join(buf))
        buf = []

    for line in lines:
        if line.startswith("## Chapter") or line.startswith("## CHAPTER"):
            flush()
            sec_key = line[3:].strip().lower()
            ch_num = ""
            sub = ""
            buf = [line]
            continue
        if line.startswith("### Chapter"):
            flush()
            ch_num = re.search(r"chapter\s*0?(\d+)", line, re.I)
            ch_num = ch_num.group(1) if ch_num else ""
            sub = ""
            sec_key = f"ch{ch_num}"
            continue
        if line.startswith("#### "):
            flush()
            sub = line[5:].strip().lower()
            sec_key = f"ch{ch_num}|{sub}"
            continue
        if line.startswith("## Part") and "정답" in line:
            flush()
            break
        buf.append(line)
    flush()
    return index


def lookup_questions(
    index: dict[str, dict[int, dict]], section_line: str, sub_line: str | None
) -> dict[int, dict]:
    if sub_line:
        m = re.search(r"chapter\s*0?(\d+)", section_line, re.I)
        if m:
            key = f"ch{m.group(1)}|{sub_line.strip().lower()}"
            if key in index:
                return index[key]
    key = section_line[3:].strip().lower() if section_line.startswith("##") else section_line.lower()
    if key in index:
        return index[key]
    # fuzzy: chapter number + subsection keyword
    cm = re.search(r"chapter\s*0?(\d+)", section_line, re.I)
    if cm and sub_line:
        for k, v in index.items():
            if k.startswith(f"ch{cm.group(1)}|") and sub_line.lower() in k:
                return v
    if cm:
        for k, v in index.items():
            if k == f"ch{cm.group(1)}" or k.startswith(f"ch{cm.group(1)}|"):
                return v
    return {}


def explain_from_question(stem: str, choices: dict[str, str], ans: str) -> str:
    correct = choices[ans]
    if COMBO_Q.search(stem):
        return f"보기 조합 문제로, {correct}이(가) 교재상 올바른 조합이다."
    if WRONG_Q.search(stem):
        return f"위 선지는 교재상 옳지 않은 설명이다. ({correct})"
    if re.search(r"가장 적절|가장 옳|가장 기본|가장 거리", stem):
        return f"{correct}이(가) 교재상 가장 적절한 설명이다."
    if "순서" in stem and ("나열" in stem or "바르게" in stem):
        return f"{correct}이(가) 교재상 올바른 순서·단계이다."
    return correct


def strip_mechanical_tail(body: str) -> str:
    parts = TAIL_START.split(body, maxsplit=1)
    core = parts[0].strip().rstrip(".")
    if MECH.search(core):
        return ""
    return core


def rewrite_line(line: str, qmap: dict[int, dict]) -> tuple[str, bool]:
    if not MECH.search(line):
        return line, False
    m = ANS_LINE.match(line)
    if not m:
        return line, False

    num, ans, body = int(m.group(1)), m.group(2), m.group(3)
    if ans in ("O", "X"):
        core = strip_mechanical_tail(body)
        if core and core != body:
            return f"{num}. {ans} — {core}", True
        return line, False

    core = strip_mechanical_tail(body)
    if len(core) >= 12 and not MECH.search(core):
        return f"{num}. {ans} — {core}", True

    q = qmap.get(num)
    if q and ans in q["choices"]:
        expl = explain_from_question(q["stem"], q["choices"], ans)
        return f"{num}. {ans} — {expl}", True

    # 선지 매칭 실패 시 정답 글자 앞 텍스트만 추출
    m2 = re.match(r"^(.+?)이\(가\)\s*정답", body)
    if m2:
        return f"{num}. {ans} — {m2.group(1).strip()}", True
    return line, False


def process_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    split = ANS_SPLIT.search(text)
    if not split:
        print(f"  skip: {path}")
        return 0

    body = text[: split.start()]
    answer = text[split.start() :]
    qindex = build_question_index(body)

    out_lines: list[str] = []
    changed = 0
    current_sec = ""
    current_sub: str | None = None
    in_answer = False

    for line in answer.splitlines():
        if ANS_SPLIT.match(line):
            in_answer = True
            out_lines.append(line)
            continue
        if not in_answer:
            out_lines.append(line)
            continue

        if line.startswith("## Chapter") or line.startswith("## CHAPTER"):
            current_sec = line
            current_sub = None
            out_lines.append(line)
            continue
        if line.startswith("### Chapter"):
            current_sec = line
            current_sub = None
            out_lines.append(line)
            continue
        if line.startswith("#### "):
            current_sub = line[5:].strip()
            out_lines.append(line)
            continue

        qmap = lookup_questions(qindex, current_sec, current_sub)
        new_line, did = rewrite_line(line, qmap)
        if did:
            changed += 1
        out_lines.append(new_line)

    if changed == 0:
        return 0

    path.write_text(body + "\n".join(out_lines), encoding="utf-8")
    return changed


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = sys.argv[1:] or [
        "output/agent_extract/1과목_공공조달의 이해/part1.md",
        "output/agent_extract/1과목_공공조달의 이해/part6.md",
        "output/agent_extract/3과목_공공계약관리/part2.md",
        "output/agent_extract/3과목_공공계약관리/part4.md",
    ]
    total = 0
    for rel in targets:
        p = root / rel
        n = process_file(p)
        print(f"{rel}: {n}")
        total += n
    print(f"total: {total}")


if __name__ == "__main__":
    main()

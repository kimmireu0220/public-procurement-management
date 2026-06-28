#!/usr/bin/env python3
"""3과목 전용 _draft 선별본 → 필기_모의_문제.md · 정답 · manifest.json 병합."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")
ID_RE = re.compile(r"<!--\s*id:\s*([^>]+?)\s*-->")
CHOICE_RE = re.compile(r"^\s*([①②③④])\s+(.+)$")
HEADER_ONLY = re.compile(r"^###\s*(\d+)\.\s*$")
Q_LINE = re.compile(r"^(?:###\s*)?(\d+)\.\s+(.+)$")
ANS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([①②③④])\s*\|")


def is_question_start(line: str) -> bool:
    if line.startswith("## Part") or line.startswith("### Part"):
        return False
    if HEADER_ONLY.match(line):
        return True
    m = Q_LINE.match(line)
    if not m:
        return False
    if re.match(r"^[①②③④]", m.group(2).strip()):
        return False
    return True


def parse_answer_table(text: str) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("## 정답"):
            in_table = True
            continue
        if in_table:
            if line.startswith("## ") and "정답" not in line:
                break
            m = ANS_ROW.match(line.strip())
            if m:
                out[int(m.group(1))] = (m.group(2).strip(), m.group(3))
    return out


def parse_questions(text: str) -> list[dict]:
    m = re.search(r"^## 정답", text, re.M)
    body = text[: m.start()] if m else text
    lines = body.splitlines()
    questions: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        local_no = None
        stem = ""
        ho = HEADER_ONLY.match(line)
        if ho:
            local_no = int(ho.group(1))
            i += 1
        elif is_question_start(line):
            qm = Q_LINE.match(line)
            local_no = int(qm.group(1))
            stem = qm.group(2).strip()
            i += 1
        else:
            i += 1
            continue

        choices: list[tuple[str, str]] = []
        source = ""
        sid = ""
        while i < len(lines):
            ln = lines[i]
            if is_question_start(ln):
                break
            if ln.startswith("## ") and not ln.startswith("## Part"):
                break
            if ln.strip() == "---" and choices:
                break
            sm = SOURCE_RE.search(ln)
            if sm:
                source = sm.group(1).strip()
                i += 1
                continue
            im = ID_RE.search(ln)
            if im:
                sid = im.group(1).strip()
                i += 1
                continue
            if ln.strip().startswith("<!--"):
                i += 1
                continue
            cm = CHOICE_RE.match(ln)
            if cm:
                choices.append((cm.group(1), cm.group(2).strip()))
                i += 1
                continue
            if ln.strip() and not ln.startswith("#"):
                stem = (stem + " " + ln.strip()).strip() if stem else ln.strip()
            i += 1
        if len(choices) >= 4 and stem and local_no is not None:
            questions.append(
                {
                    "local_no": local_no,
                    "stem": stem,
                    "choices": choices[:4],
                    "source": source,
                    "stable_id": sid,
                }
            )
    questions.sort(key=lambda q: q["local_no"])
    return questions


def format_question(exam_no: int, q: dict) -> str:
    lines = [f"{exam_no}. {q['stem']}"]
    for label, text in q["choices"]:
        lines.append(f"   {label} {text}")
    lines.append(f"<!-- source: {q['source']} -->")
    lines.append(f"<!-- id: {q['stable_id']} -->")
    lines.append("")
    return "\n".join(lines)


def merge_round(round_no: int) -> int:
    out = ROOT / "output/mock_exam/3과목" / f"{round_no}회차"
    draft = out / "_draft"
    draft_file = draft / "3과목_선별.md"
    if not draft_file.is_file():
        raise SystemExit(f"missing: {draft_file}")

    text = draft_file.read_text(encoding="utf-8")
    qs = parse_questions(text)
    ans_table = parse_answer_table(text)
    expected = 30
    if len(qs) != expected:
        nums = [q["local_no"] for q in qs]
        raise SystemExit(f"parsed {len(qs)} questions, expected {expected}, nos={nums}")

    problem_parts = [
        f"# 공공조달관리사 3과목 전용 필기 모의 {round_no}회차 — 문제\n",
        "> 3과목 공공계약관리 30문항 · 제한시간 45분 · CBT 4지 택일형\n",
        "\n---\n",
        "\n## 3과목 공공계약관리 (1~30)\n\n",
    ]
    answer_parts = [
        f"# 공공조달관리사 3과목 전용 필기 모의 {round_no}회차 — 정답\n",
        "\n> ※ 정답은 사용자가 답안을 제출한 후 공개합니다.\n",
        "\n---\n",
        "\n## 3과목 (1~30)\n",
    ]
    all_items: list[dict] = []

    for idx, q in enumerate(qs):
        exam_no = idx + 1
        local = q["local_no"]
        if local not in ans_table:
            raise SystemExit(f"missing answer for local {local}")
        sid_ans, answer = ans_table[local]
        q["stable_id"] = sid_ans
        q["answer"] = answer
        problem_parts.append(format_question(exam_no, q))
        answer_parts.append(f"{exam_no}. {q['answer']} — ({q['source']})\n")
        all_items.append(
            {"exam_no": exam_no, "stable_id": q["stable_id"], "answer": q["answer"]}
        )

    manifest = {
        "round": round_no,
        "subject": 3,
        "total": 30,
        "items": all_items,
    }
    (out / "필기_모의_문제.md").write_text("".join(problem_parts), encoding="utf-8")
    (out / "필기_모의_정답.md").write_text("".join(answer_parts), encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(all_items)


def main() -> None:
    parser = argparse.ArgumentParser(description="3과목 전용 mock draft 병합")
    parser.add_argument("round", type=int, nargs="?", default=1, help="회차 번호")
    args = parser.parse_args()
    n = merge_round(args.round)
    print(f"merged {n} questions → output/mock_exam/3과목/{args.round}회차/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""과목별 _draft 선별본 → 필기_모의_문제.md · 필기_모의_정답.md · manifest.json 병합 (통합 80문항)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.draft_merge import (  # noqa: E402
    fix_stable_id,
    format_question,
    parse_answer_table,
    parse_questions,
    write_outputs,
)
from cbt.profiles import FULL_MOCK  # noqa: E402

SUBJECTS = [
    (1, "1과목_선별.md", "공공조달과 법제도 이해", 1, 30),
    (2, "2과목_선별.md", "공공조달계획 수립 및 분석", 31, 50),
    (3, "3과목_선별.md", "공공계약관리", 51, 80),
]


def merge_round(round_no: int) -> int:
    out = FULL_MOCK.round_dir(round_no)
    draft = out / "_draft"
    if not draft.is_dir():
        raise SystemExit(f"missing draft dir: {draft}")

    all_items: list[dict] = []
    problem_parts = [
        f"# 공공조달관리사 1회 필기 모의 {round_no}회차 — 문제\n",
        "> 필기 합계 80문항 · 2시간 · CBT 4지 택일형\n",
        "> 1과목 30문항 · 2과목 20문항 · 3과목 30문항\n",
        "\n---\n",
    ]
    answer_parts = [
        f"# 공공조달관리사 1회 필기 모의 {round_no}회차 — 정답\n",
        "\n> ※ 정답은 사용자가 답안을 제출한 후 공개합니다.\n",
        "\n---\n",
    ]

    for subject, fname, name, start, end in SUBJECTS:
        text = (draft / fname).read_text(encoding="utf-8")
        qs = parse_questions(text, subject=subject)
        ans_table = parse_answer_table(text)
        expected = end - start + 1
        if len(qs) != expected:
            nums = [q["local_no"] for q in qs]
            raise SystemExit(
                f"{fname}: parsed {len(qs)} questions, expected {expected}, nos={nums}"
            )
        problem_parts.append(f"\n## {subject}과목 {name} ({start}~{end})\n\n")
        answer_parts.append(f"\n## {subject}과목 ({start}~{end})\n")
        for idx, q in enumerate(qs):
            exam_no = start + idx
            local = q["local_no"]
            if local not in ans_table:
                raise SystemExit(f"missing answer for {fname} local {local}")
            sid_ans, answer = ans_table[local]
            q["stable_id"] = fix_stable_id(sid_ans, subject)
            q["answer"] = answer
            problem_parts.append(format_question(exam_no, q))
            answer_parts.append(f"{exam_no}. {q['answer']} — ({q['source']})\n")
            all_items.append(
                {"exam_no": exam_no, "stable_id": q["stable_id"], "answer": q["answer"]}
            )

    manifest = {"round": round_no, "total": FULL_MOCK.question_count, "items": all_items}
    return write_outputs(
        out,
        round_no=round_no,
        problem_parts=problem_parts,
        answer_parts=answer_parts,
        manifest=manifest,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="통합 필기 모의 draft 병합 (80문항)")
    parser.add_argument("round", type=int, nargs="?", default=1, help="회차 번호")
    args = parser.parse_args()
    n = merge_round(args.round)
    print(f"merged {n} questions → output/mock_exam/필기/통합/{args.round}회차/")


if __name__ == "__main__":
    main()

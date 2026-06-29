"""1과목 _draft → 필기_모의_문제.md · 정답 · manifest.json."""

from __future__ import annotations

from cbt.draft_merge import format_question, parse_answer_table, parse_questions, write_outputs
from cbt.profiles import SUBJECT1
from subject1.selection import QUESTION_COUNT

DRAFT_NAME = "1과목_선별.md"


def merge_round(round_no: int) -> int:
    out = SUBJECT1.round_dir(round_no)
    draft_file = out / "_draft" / DRAFT_NAME
    if not draft_file.is_file():
        raise SystemExit(f"missing: {draft_file}")

    text = draft_file.read_text(encoding="utf-8")
    qs = parse_questions(text)
    ans_table = parse_answer_table(text)
    if len(qs) != QUESTION_COUNT:
        nums = [q["local_no"] for q in qs]
        raise SystemExit(
            f"parsed {len(qs)} questions, expected {QUESTION_COUNT}, nos={nums}"
        )

    problem_parts = [
        f"# 공공조달관리사 1과목 전용 필기 모의 {round_no}회차 — 문제\n",
        "> 1과목 공공조달과 법제도 이해 30문항 · 제한시간 45분 · CBT 4지 택일형\n",
        "\n---\n",
        "\n## 1과목 공공조달과 법제도 이해 (1~30)\n\n",
    ]
    answer_parts = [
        f"# 공공조달관리사 1과목 전용 필기 모의 {round_no}회차 — 정답\n",
        "\n> ※ 정답은 사용자가 답안을 제출한 후 공개합니다.\n",
        "\n---\n",
        "\n## 1과목 (1~30)\n",
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
        "subject": 1,
        "total": QUESTION_COUNT,
        "items": all_items,
    }
    return write_outputs(
        out,
        round_no=round_no,
        problem_parts=problem_parts,
        answer_parts=answer_parts,
        manifest=manifest,
    )

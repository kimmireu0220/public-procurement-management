"""stable_id 목록으로 1과목 _draft/1과목_선별.md 생성."""

from __future__ import annotations

from pathlib import Path

from cbt.profiles import SUBJECT1
from subject1.bank import fetch_question
from subject1.selection import SELECTIONS

DRAFT_NAME = "1과목_선별.md"


def build_draft(round_no: int, stable_ids: list[str] | None = None) -> Path:
    ids = stable_ids if stable_ids is not None else SELECTIONS.get(round_no)
    if not ids:
        raise SystemExit(f"no stable_id selection for 1과목 round {round_no}")

    out = SUBJECT1.round_dir(round_no) / "_draft"
    out.mkdir(parents=True, exist_ok=True)
    path = out / DRAFT_NAME

    lines = [
        f"# 1과목 전용 모의 {round_no}회차 — 선별 ({len(ids)}문항)\n",
        "\n> Part 1~7 분산 · Check Q&A ≤20% · 오답노트 약점 보강\n",
        "\n---\n\n",
    ]
    answer_rows = ["\n## 정답\n\n", "| 번호 | stable_id | 정답 |\n", "|-----:|-----------|:--:|\n"]

    for i, sid in enumerate(ids, start=1):
        q, ans = fetch_question(sid)
        lines.append(f"### {i}.\n")
        lines.append(f"{i}. {q['stem']}\n")
        for label, text in q["choices"]:
            lines.append(f"   {label} {text}\n")
        lines.append(f"<!-- source: {q['source']} -->\n")
        lines.append(f"<!-- id: {sid} -->\n\n")
        answer_rows.append(f"| {i} | {sid} | {ans} |\n")

    path.write_text("".join(lines + answer_rows), encoding="utf-8")
    return path

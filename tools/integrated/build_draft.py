"""통합 필기 _draft/{1,2,3}과목_선별.md 생성."""

from __future__ import annotations

from pathlib import Path

from cbt.profiles import FULL_MOCK
from integrated.selection import INTEGRATED_SELECTIONS, QUESTION_COUNTS
from subject1.bank import fetch_question as fetch1
from subject2.bank import fetch_question as fetch2
from subject3.bank import fetch_question as fetch3

DRAFT_NAMES = {1: "1과목_선별.md", 2: "2과목_선별.md", 3: "3과목_선별.md"}
FETCH = {1: fetch1, 2: fetch2, 3: fetch3}


def build_draft(round_no: int) -> list[Path]:
    sel = INTEGRATED_SELECTIONS.get(round_no)
    if not sel:
        raise SystemExit(f"no integrated selection for round {round_no}")

    out = FULL_MOCK.round_dir(round_no) / "_draft"
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for subject in (1, 2, 3):
        ids = sel[str(subject)]
        expected = QUESTION_COUNTS[str(subject)]
        if len(ids) != expected:
            raise SystemExit(
                f"subject {subject}: {len(ids)} ids, expected {expected}"
            )
        fname = DRAFT_NAMES[subject]
        path = out / fname
        lines = [
            f"# {subject}과목 — 통합 필기 모의 {round_no}회차 선별 ({len(ids)}문항)\n",
            "\n---\n\n",
        ]
        answer_rows = [
            "\n## 정답\n\n",
            "| 번호 | stable_id | 정답 |\n",
            "|-----:|-----------|:--:|\n",
        ]
        fetch = FETCH[subject]
        for i, sid in enumerate(ids, start=1):
            q, ans = fetch(sid)
            lines.append(f"### {i}.\n")
            lines.append(f"{i}. {q['stem']}\n")
            for label, text in q["choices"]:
                lines.append(f"   {label} {text}\n")
            lines.append(f"<!-- source: {q['source']} -->\n")
            lines.append(f"<!-- id: {sid} -->\n\n")
            answer_rows.append(f"| {i} | {sid} | {ans} |\n")
        path.write_text("".join(lines + answer_rows), encoding="utf-8")
        paths.append(path)
    return paths


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="통합 필기 선별 draft 생성")
    parser.add_argument("round", type=int, nargs="?", default=4)
    args = parser.parse_args()
    paths = build_draft(args.round)
    for p in paths:
        print(f"draft → {p}")


if __name__ == "__main__":
    main()

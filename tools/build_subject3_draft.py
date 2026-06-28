#!/usr/bin/env python3
"""에이전트가 확정한 stable_id 목록으로 3과목 _draft/3과목_선별.md 생성."""

from __future__ import annotations

import argparse
from pathlib import Path

from subject3_bank import fetch_question

ROOT = Path(__file__).resolve().parents[1]

# 3과목 전용 1회차 — 수동 선별 (통합 1~3회차 manifest의 3:* 미사용)
ROUND1_SELECTED = [
    "3:1:1:cqa:2",
    "3:1:1:exam:3",
    "3:1:1:exam:11",
    "3:1:1:exam:23",
    "3:1:2:exam:5",
    "3:1:2:exam:10",
    "3:1:4:exam:12",
    "3:1:4:exam:43",
    "3:2:1:exam:13",
    "3:2:1:exam:24",
    "3:2:1:exam:26",
    "3:2:2:exam:14",
    "3:2:2:exam:31",
    "3:2:2:exam:33",
    "3:2:2:exam:2",
    "3:3:1:cqa:11",
    "3:3:1:exam:17",
    "3:3:2:cqa:4",
    "3:3:2:exam:5",
    "3:3:2:exam:8",
    "3:3:2:exam:12",
    "3:3:2:exam:6",
    "3:3:2:exam:10",
    "3:4:1:cqa:12",
    "3:4:1:exam:30",
    "3:4:2:exam:15",
    "3:4:3:exam:6",
    "3:4:3:exam:12",
    "3:4:3:exam:7",
    "3:4:3:exam:20",
]


def build_draft(round_no: int, stable_ids: list[str]) -> Path:
    out = ROOT / "output/mock_exam/3과목" / f"{round_no}회차" / "_draft"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "3과목_선별.md"

    lines = [
        f"# 3과목 전용 모의 {round_no}회차 — 선별 (30문항)\n",
        "\n> Part 1~4 분산 · Check Q&A 4문항(13%) · 오답노트 약점 보강\n",
        "\n---\n\n",
    ]
    answer_rows = ["\n## 정답\n\n", "| 번호 | stable_id | 정답 |\n", "|-----:|-----------|:--:|\n"]

    for i, sid in enumerate(stable_ids, start=1):
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


def main() -> None:
    parser = argparse.ArgumentParser(description="3과목 선별 draft 생성")
    parser.add_argument("round", type=int, nargs="?", default=1)
    args = parser.parse_args()
    p = build_draft(args.round, ROUND1_SELECTED)
    print(f"draft → {p}")


if __name__ == "__main__":
    main()

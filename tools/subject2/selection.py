"""2과목 전용 회차별 수동 선별 stable_id 목록."""

from __future__ import annotations

# 1회차 — 통합 1~3회차 manifest의 2:* 미사용 · 오답노트 약점(RFQ/RFP/사전규격·적정성·협상) 보강
ROUND1_SELECTED: list[str] = [
    "2:1:1:exam:14",
    "2:1:2:exam:1",
    "2:1:2:exam:6",
    "2:1:1:check:3",
    "2:1:1:exam:15",
    "2:2:2:exam:1",
    "2:2:2:exam:10",
    "2:2:3:exam:3",
    "2:2:4:exam:3",
    "2:2:1:exam:4",
    "2:3:1:exam:1",
    "2:3:1:exam:24",
    "2:3:1:exam:25",
    "2:3:2:exam:3",
    "2:3:4:exam:1",
    "2:4:1:exam:6",
    "2:4:2:exam:11",
    "2:4:3:exam:7",
    "2:4:4:exam:22",
    "2:4:4:exam:5",
]

SELECTIONS: dict[int, list[str]] = {
    1: ROUND1_SELECTED,
}

QUESTION_COUNT = 20

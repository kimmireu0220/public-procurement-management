"""3과목 전용 회차별 수동 선별 stable_id 목록."""

from __future__ import annotations

# 1회차 — 통합 1~3회차 manifest의 3:* 미사용
ROUND1_SELECTED: list[str] = [
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

SELECTIONS: dict[int, list[str]] = {
    1: ROUND1_SELECTED,
}

QUESTION_COUNT = 30

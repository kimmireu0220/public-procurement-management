"""1과목 전용 회차별 수동 선별 stable_id 목록."""

from __future__ import annotations

# 1회차 — 통합 1~3회차 manifest의 1:* 미사용 · 오답노트 약점(기본원칙·전자조달·낙성·부정당) 보강
ROUND1_SELECTED: list[str] = [
    "1:1:1:exam:2",
    "1:1:3:exam:1",
    "1:1:4:exam:1",
    "1:1:4:check:1",
    "1:2:1:exam:1",
    "1:2:1:exam:2",
    "1:2:2:exam:6",
    "1:2:1:check:1",
    "1:3:1:exam:2",
    "1:3:1:exam:27",
    "1:3:2:exam:25",
    "1:3:2:check:1",
    "1:4:1:exam:2",
    "1:4:2:exam:1",
    "1:4:3:exam:1",
    "1:4:4:exam:1",
    "1:5:1:exam:3",
    "1:5:1:exam:8",
    "1:5:2:exam:1",
    "1:5:3:exam:19",
    "1:6:2:check:1",
    "1:6:2:exam:28",
    "1:6:3:exam:28",
    "1:6:4:exam:16",
    "1:6:5:exam:15",
    "1:7:1:exam:1",
    "1:7:2:exam:9",
    "1:7:2:exam:10",
    "1:7:2:exam:15",
    "1:7:2:exam:21",
]

SELECTIONS: dict[int, list[str]] = {
    1: ROUND1_SELECTED,
}

QUESTION_COUNT = 30

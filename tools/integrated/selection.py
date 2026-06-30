"""통합 필기 모의 회차별 수동 선별 stable_id 목록."""

from __future__ import annotations

# 4회차 — 통합 1~3회차 + 과목 단독 manifest의 stable_id 미사용(3과목 Part2/3 exam 제외)
# 오답노트 약점: 1(전자조달·낙성·부정당) · 2(RFQ/RFP·사전규격·협상순서)
#                 3(보증금·MAS·물가·하도급)
# 3과목 Part2/3 exam 풀 고갈 → §A-0b 2차 lap: 3:2:*·3:3:* exam 15건 재출제 (LAP2_REUSE_3)

# Part 분포 5/4/5/4/5/4/3 · check 3건(≤6)
SUBJECT1_ROUND4: list[str] = [
    # Part1 (5)
    "1:1:1:exam:11",
    "1:1:1:exam:17",
    "1:1:2:exam:8",
    "1:1:3:exam:14",
    "1:1:4:exam:5",
    # Part2 (4) — 전자조달·ERA
    "1:2:1:exam:16",
    "1:2:2:exam:9",
    "1:2:2:exam:23",
    "1:2:1:exam:10",
    # Part3 (5) — 전자조달·나라장터·전자입찰/계약
    "1:3:1:exam:3",
    "1:3:1:exam:21",
    "1:3:2:exam:21",
    "1:3:2:exam:22",
    "1:3:2:exam:3",
    # Part4 (4)
    "1:4:1:exam:1",
    "1:4:1:exam:10",
    "1:4:2:exam:10",
    "1:4:3:exam:2",
    # Part5 (5)
    "1:5:1:exam:11",
    "1:5:1:exam:13",
    "1:5:2:exam:2",
    "1:5:3:exam:1",
    "1:5:4:exam:1",
    # Part6 (4) — check 3: 계약유형·전자입찰취소·수의계약 (낙성/요물 exam 풀 소진)
    "1:6:2:check:5",
    "1:6:4:check:2",
    "1:6:5:check:1",
    "1:6:6:exam:13",
    # Part7 (3) — 부정당업자
    "1:7:1:exam:36",
    "1:7:2:exam:23",
    "1:7:1:exam:35",
]

# Part 분포 5/5/5/5 · check 2건(≤4)
SUBJECT2_ROUND4: list[str] = [
    # Part1 (5) — check 1
    "2:1:1:exam:10",
    "2:1:2:exam:26",
    "2:1:2:exam:11",
    "2:1:1:exam:11",
    "2:1:2:check:2",
    # Part2 (5)
    "2:2:1:exam:7",
    "2:2:2:exam:11",
    "2:2:3:exam:10",
    "2:2:4:exam:9",
    "2:2:4:exam:10",
    # Part3 (5) — RFQ·RFP·사전규격
    "2:3:1:exam:29",
    "2:3:2:exam:7",
    "2:3:2:exam:8",
    "2:3:2:exam:12",
    "2:3:3:exam:10",
    # Part4 (5) — 협상·절차순서 · check 1 (RFQ/RFP 대응)
    "2:4:1:exam:9",
    "2:4:2:exam:14",
    "2:4:3:exam:5",
    "2:4:3:exam:8",
    "2:4:1:check:1",
]

# Part 분포 8/7/8/7 · cqa 0건(≤6) · 빈출 cluster 각 2건
SUBJECT3_ROUND4: list[str] = [
    # Part1 (8) — 보증금 cluster 2건
    "3:1:4:exam:22",
    "3:1:4:exam:24",
    "3:1:4:exam:3",
    "3:1:4:exam:7",
    "3:1:4:exam:31",
    "3:1:4:exam:34",
    "3:1:4:exam:35",
    "3:1:4:exam:36",
    # Part2 (7) — 2nd lap exam · 물가 cluster 2건
    "3:2:2:exam:11",
    "3:2:2:exam:13",
    "3:2:2:exam:14",
    "3:2:1:exam:4",
    "3:2:1:exam:10",
    "3:2:2:exam:30",
    "3:2:2:exam:8",
    # Part3 (8) — 2nd lap exam · MAS cluster 2건
    "3:3:2:exam:17",
    "3:3:2:exam:18",
    "3:3:2:exam:5",
    "3:3:2:exam:6",
    "3:3:2:exam:7",
    "3:3:1:exam:1",
    "3:3:1:exam:2",
    "3:3:2:exam:3",
    # Part4 (7) — 하도급 cluster 2건
    "3:4:3:exam:34",
    "3:4:3:exam:41",
    "3:4:1:exam:28",
    "3:4:1:exam:33",
    "3:4:3:exam:13",
    "3:4:2:exam:30",
    "3:4:1:exam:37",
]

# 3과목 Part2/3 exam 2차 lap 재출제 (15건) — 출제_방향.md에 기록
LAP2_REUSE_3: list[str] = [
    "3:2:1:exam:4",
    "3:2:1:exam:10",
    "3:2:2:exam:8",
    "3:2:2:exam:11",
    "3:2:2:exam:13",
    "3:2:2:exam:14",
    "3:2:2:exam:30",
    "3:3:1:exam:1",
    "3:3:1:exam:2",
    "3:3:2:exam:3",
    "3:3:2:exam:5",
    "3:3:2:exam:6",
    "3:3:2:exam:7",
    "3:3:2:exam:17",
    "3:3:2:exam:18",
]

INTEGRATED_SELECTIONS: dict[int, dict[str, list[str]]] = {
    4: {
        "1": SUBJECT1_ROUND4,
        "2": SUBJECT2_ROUND4,
        "3": SUBJECT3_ROUND4,
    },
}

QUESTION_COUNTS = {"1": 30, "2": 20, "3": 30}

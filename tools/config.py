from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AGENT_EXTRACT_DIR = ROOT / "output/agent_extract"
PROBLEM_BOOK_FINAL_DIR = ROOT / "output/problem_book_final"

# 시험 과목 번호 ↔ 과목 slug (필기 1~3, 실기 4)
SUBJECT_CATALOG: dict[str, dict[str, str | int]] = {
    "1": {
        "slug": "1과목_공공조달의 이해",
        "exam_name": "공공조달과 법제도 이해",
        "textbook_name": "공공조달의 이해",
        "exam_type": "필기",
        "parts": 7,
    },
    "2": {
        "slug": "2과목_공공조달 계획분석",
        "exam_name": "공공조달계획 수립 및 분석",
        "textbook_name": "공공조달 계획분석",
        "exam_type": "필기",
        "parts": 4,
    },
    "3": {
        "slug": "3과목_공공계약관리",
        "exam_name": "공공계약관리",
        "textbook_name": "공공계약관리",
        "exam_type": "필기",
        "parts": 4,
    },
    "4": {
        "slug": "4과목_공공조달 관리실무",
        "exam_name": "공공조달관리 실무",
        "textbook_name": "공공조달 관리실무",
        "exam_type": "실기",
        "parts": 8,
    },
}


def subject_extract_dir(subject_no: str) -> Path:
    return AGENT_EXTRACT_DIR / str(SUBJECT_CATALOG[subject_no]["slug"])


def subject_problem_book_dir(subject_no: str) -> Path:
    return PROBLEM_BOOK_FINAL_DIR / str(SUBJECT_CATALOG[subject_no]["slug"])

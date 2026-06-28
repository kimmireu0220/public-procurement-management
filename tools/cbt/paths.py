"""output/mock_exam 디렉터리 레이아웃 (단일 정의)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOCK_ROOT = ROOT / "output" / "mock_exam"
FIELD_ROOT = MOCK_ROOT / "필기"
FULL_MOCK_ROOT = FIELD_ROOT / "통합"
SUBJECT_ROOTS = {
    1: FIELD_ROOT / "1과목",
    2: FIELD_ROOT / "2과목",
    3: FIELD_ROOT / "3과목",
}
PRACTICAL_ROOT = MOCK_ROOT / "실기"
WRONG_NOTE = MOCK_ROOT / "오답노트.md"

ROUND_SUFFIX = "{round}회차"


def full_round_dir(round_no: int) -> Path:
    return FULL_MOCK_ROOT / ROUND_SUFFIX.format(round=round_no)


def subject_round_dir(subject: int, round_no: int) -> Path:
    return SUBJECT_ROOTS[subject] / ROUND_SUFFIX.format(round=round_no)


def practical_round_dir(round_no: int) -> Path:
    return PRACTICAL_ROOT / ROUND_SUFFIX.format(round=round_no)

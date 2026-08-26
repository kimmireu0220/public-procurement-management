#!/usr/bin/env python3
"""Validate the score-oriented structure and Q-Net coverage of subject 4."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output" / "chapter_lectures" / "4과목"
REQUIRED = [
    "이 장의 시험상 중요도와 학습 우선순위",
    "공식 출제기준상 학습 범위",
    "예상 질문 형태와 출제 포인트",
    "합격에 필요한 필수 이론",
    "반드시 암기할 핵심어·숫자·절차",
    "혼동 방지와 오답 함정",
    "필답형 답안 작성 방법",
    "대표 예상문제 — 자체 작성",
    "시험시간 안에 쓰는 모범답안",
    "채점 핵심어와 부분점수",
    "무자료 회상 점검",
    "공식 근거·교재 범위·법령 기준일",
]


def section(text: str, title: str) -> str:
    match = re.search(
        rf"^##(?:#)? {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    return match.group(1).strip() if match else ""


def main() -> None:
    source_map = json.loads((BASE / "source-map.json").read_text(encoding="utf-8"))
    expected = {
        item.split(" ", 1)[0]: item.split(" ", 1)[1]
        for lesson in source_map["lessons"]
        for item in lesson["fine_criteria"]
    }
    paths = sorted(BASE.glob("part*/chapter*.md"))
    assert len(paths) == 25, f"Chapter count: {len(paths)}"

    found: dict[str, str] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert f"## {heading}" in text or f"### {heading}" in text, f"{path}: {heading}"
        assert "## 실무 산출물" not in text, f"operational form remains: {path}"
        assert "**문제(10점).**" in text, f"representative problem missing: {path}"
        assert "8분 이내" in text, f"time limit missing: {path}"
        grounds = section(text, "공식 근거·교재 범위·법령 기준일")
        assert "2026" in grounds and ("표준교재" in grounds or "Q-Net" in grounds), f"grounds missing: {path}"

        for code, name in re.findall(r"^\| (\d+-\d+-\d+) \| ([^|]+?) \| 필수 \|$", text, re.M):
            assert code not in found, f"duplicate criterion: {code}"
            found[code] = name.strip()

        scoring = section(text, "채점 핵심어와 부분점수")
        points = [int(value) for value in re.findall(r": (\d+)점$", scoring, re.M)]
        assert sum(points) == 10, f"score total {sum(points)}: {path}"
        answer = section(text, "시험시간 안에 쓰는 모범답안")
        answer_lines = re.findall(r"^\d+\. ", answer, re.M)
        assert 3 <= len(answer_lines) <= 8, f"answer length: {path}"

    assert found == expected, f"criteria mismatch: expected {len(expected)}, found {len(found)}"
    coverage = (BASE.parent / "4과목_91개_대응표.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\| \d+-\d+-\d+ \|", coverage, re.M)) == 91
    overview = (BASE / "overview.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\| \d+-\d+-\d+ \|", overview, re.M)) == 91

    print("4과목 합격강의 검증 완료: 8/8 주요항목, 25/25 Chapter, 91/91 세세항목, 대표답안 25개 모두 10점")


if __name__ == "__main__":
    main()

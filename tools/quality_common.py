"""validate_extract · audit_problem_book 공통 품질 검사."""

from __future__ import annotations

import re

# 본문에 남아 있으면 안 되는 답안·해설 흔적 (응답은·감점 선지 등 오탐 제외)
ANSWER_TRACE_RE = re.compile(
    r"본문 정답표|정답표|정답은|(?<![응])답은|해설상|"
    r"[①②③④⑤⑥⑦⑧⑨⑩]\s*[-—–](?!\d+점)|"
    r"\b[OX]\s*[-—–]"
)

# OCR 페이지가 문제 구간인지 판별 (느슨한 Check 단독 매칭 제거)
PROBLEM_MARKER_RE = re.compile(
    r"Check\s+[QDOV][&./\s]*A|"
    r"V\s+Check\s|"
    r"단원별\s*출제예상|"
    r"최종점검\s*(?:OX|0X)|"
    r"OX\s*퀴즈|0X\s*퀴즈",
    re.IGNORECASE | re.MULTILINE,
)

OCR_SKIP_PAGE_RE = re.compile(
    r"HOW TO STUDY|구성과 특징|학습목표|KEY\s*WORD",
    re.IGNORECASE,
)

NUMBERED_QUESTION_OCR_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)
EXPLANATION_LINE_RE = re.compile(r"^해설\s*$", re.MULTILINE)

# audit 수동 분류에서 확인된 OCR 오탐 (slug → Part/page 목록)
OCR_KNOWN_FALSE_POSITIVES: dict[str, frozenset[str]] = {
    "3과목_공공계약관리": frozenset(
        {
            "Part 4/page_0046.jpg",
            "Part 4/page_0069.jpg",
            "Part 4/page_0071.jpg",
            "Part 4/page_0083.jpg",
        }
    ),
}


def is_known_ocr_false_positive(slug: str, source: str) -> bool:
    return source in OCR_KNOWN_FALSE_POSITIVES.get(slug, frozenset())


def count_answer_traces(text: str) -> int:
    return len(ANSWER_TRACE_RE.findall(text))


def ocr_page_is_problem_candidate(text: str) -> bool:
    """OCR 텍스트가 문제 누락 후보 페이지인지 판별 (해설·표·이론 인라인 Check 제외)."""
    if not PROBLEM_MARKER_RE.search(text):
        return False
    if OCR_SKIP_PAGE_RE.search(text):
        return False
    haeseol_count = len(EXPLANATION_LINE_RE.findall(text))
    has_numbered = bool(NUMBERED_QUESTION_OCR_RE.search(text))
    if re.search(r"[정징]답", text) and not has_numbered:
        return False
    if haeseol_count >= 2:
        return False
    if haeseol_count >= 1 and not has_numbered:
        return False
    return True

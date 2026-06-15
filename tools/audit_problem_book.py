from __future__ import annotations

import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import (  # noqa: E402
    AUDIT_REPORT,
    CHAPTERS_CLEAN_DIR,
    OCR_DIR,
    PROBLEM_BOOK_FINAL_DIR,
    PROBLEM_BOOK_MD,
    get_project_root,
)

ROOT = get_project_root()
OCR_ROOT = OCR_DIR
FINAL_ROOT = PROBLEM_BOOK_FINAL_DIR
FINAL_MD = PROBLEM_BOOK_MD
REPORT = AUDIT_REPORT

PROBLEM_MARKER_RE = re.compile(r"Check|Q&A|O&A|출제예상|최종점검|OX 퀴즈|0X 퀴즈")
SOURCE_COMMENT_RE = re.compile(r"<!--\s*source:\s*(.*?)\s*-->")
SOURCE_TOKEN_RE = re.compile(r"(Chapter [1-7]/)?page_(\d{4})\.jpg")
ANSWER_RE = re.compile(r"^#{1,4}\s+.*정답|정답 및 해설|^\s*정답\b|^\s*해설\b", re.MULTILINE)
ANSWER_TRACE_RE = re.compile(r"본문 정답표|정답표|정답은|답은|해설상|[①②③④⑤⑥⑦⑧⑨⑩]\s*[-—–]|[OX]\s*[-—–]")
QUESTION_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)


def expand_source_comment(comment: str) -> set[str]:
    sources: set[str] = set()
    current_chapter: str | None = None

    parts = [part.strip() for part in comment.split(",")]
    for part in parts:
        tokens = list(SOURCE_TOKEN_RE.finditer(part))
        if not tokens:
            continue
        first = tokens[0]
        if first.group(1):
            current_chapter = first.group(1).rstrip("/")
        if current_chapter is None:
            continue

        if "~" in part and len(tokens) >= 2:
            start = int(tokens[0].group(2))
            end = int(tokens[-1].group(2))
            for page in range(min(start, end), max(start, end) + 1):
                sources.add(f"{current_chapter}/page_{page:04d}.jpg")
        else:
            for token in tokens:
                if token.group(1):
                    current_chapter = token.group(1).rstrip("/")
                sources.add(f"{current_chapter}/page_{int(token.group(2)):04d}.jpg")

    return sources


def extract_used_sources(final_text: str) -> set[str]:
    used: set[str] = set()
    for comment in SOURCE_COMMENT_RE.findall(final_text):
        used.update(expand_source_comment(comment))
    return used


def main() -> None:
    global OCR_ROOT, FINAL_MD
    if not FINAL_MD.exists():
        matches = sorted(FINAL_ROOT.glob("*문제집.md"))
        if matches:
            FINAL_MD = matches[0]
    if not OCR_ROOT.exists():
        matches = sorted((ROOT / "output" / "ocr").glob("*이해"))
        if matches:
            OCR_ROOT = matches[0]

    final_text = FINAL_MD.read_text(encoding="utf-8")
    used_sources = extract_used_sources(final_text)

    lines = [
        "# 누락 후보 대조",
        "",
        "OCR에서 문제 표식이 감지된 페이지와 최종 문제집의 출처 주석을 대조한 결과입니다.",
        "",
        "| 챕터 | OCR 후보 페이지 | 최종 사용 페이지 | 후보 중 미사용 | 최종 문제 수 |",
        "|---|---:|---:|---:|---:|",
    ]

    total_missing: list[str] = []
    total_questions = 0
    for chapter in range(1, 8):
        chapter_dir = OCR_ROOT / f"Chapter {chapter}"
        candidates: list[str] = []
        for page in sorted(chapter_dir.glob("*.txt")):
            text = page.read_text(encoding="utf-8", errors="ignore")
            if PROBLEM_MARKER_RE.search(text):
                candidates.append(f"Chapter {chapter}/{page.stem}.jpg")

        used = sorted(source for source in used_sources if source.startswith(f"Chapter {chapter}/"))
        missing = [source for source in candidates if source not in used_sources]
        total_missing.extend(missing)

        chapter_clean = CHAPTERS_CLEAN_DIR / f"chapter{chapter}.md"
        q_count = len(QUESTION_RE.findall(chapter_clean.read_text(encoding="utf-8")))
        total_questions += q_count
        lines.append(f"| Chapter {chapter} | {len(candidates)} | {len(used)} | {len(missing)} | {q_count} |")

        if missing:
            lines.append("")
            lines.append(f"## Chapter {chapter} 후보 중 미사용 페이지")
            for source in missing:
                lines.append(f"- {source}")
            lines.append("")

    answer_markers = ANSWER_RE.findall(final_text)
    answer_traces = ANSWER_TRACE_RE.findall(final_text)

    lines.extend([
        "",
        "## 잔류 답안 표식 검사",
        f"- 정답/해설 제목형 표식: {len(answer_markers)}건",
        f"- 인라인 답안 흔적 의심 표식: {len(answer_traces)}건",
        f"- 총 문제 수: {total_questions}",
    ])

    if total_missing:
        lines.extend([
            "",
            "## 주의",
            "미사용 후보 페이지는 OCR 표식 기반 자동 후보입니다. 표지/안내/본문의 문구가 잡힌 오탐일 수 있으므로 최종 검토 시 확인이 필요합니다.",
        ])

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Move separated lecture answers directly below their matching questions.

The chapter lectures use one of two exercise layouts:

* a numbered question list followed by a numbered answer list; or
* numbered multiple-choice blocks followed by a Markdown answer table.

This utility validates that question and answer numbers match before rewriting a
file.  It deliberately refuses unfamiliar layouts instead of making a partial
edit.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ANSWER_HEADING = re.compile(r"(?m)^(#{2,4})[ \t]+정답[^\n]*$")
QUESTION_HEADING = re.compile(r"(?m)^#{2,4}[ \t]+[^\n]*문제[^\n]*$")
LIST_ITEM = re.compile(r"(?m)^([0-9]+)\.[ \t]+([^\n]+)$")
MCQ_HEADING = re.compile(r"(?m)^\*\*([0-9]+)\.[ \t]+[^\n]+\*\*[ \t]*$")
ANSWER_ROW = re.compile(
    r"(?m)^\|[ \t]*([0-9]+)[ \t]*\|[ \t]*([^|]+?)[ \t]*\|[ \t]*(.*)[ \t]*\|[ \t]*$"
)
INLINE_ANSWER = re.compile(r"(?m)^>[ \t]+\*\*정답")


class ConversionError(RuntimeError):
    """Raised when a chapter does not match a supported, safe layout."""


def _section_end(text: str, heading: re.Match[str]) -> int:
    level = len(heading.group(1))
    following = text[heading.end() :]
    next_heading = re.search(rf"(?m)^#{{1,{level}}}[ \t]+", following)
    if next_heading is None:
        return len(text)
    return heading.end() + next_heading.start()


def _question_region_start(text: str, answer_start: int) -> int:
    headings = list(QUESTION_HEADING.finditer(text, 0, answer_start))
    if not headings:
        raise ConversionError("정답 섹션 앞에서 문제 제목을 찾지 못했습니다.")
    return headings[-1].end()


def _normalize_list_answer(body: str) -> tuple[str, str]:
    labels = {
        "정답": "정답·해설",
        "예시답": "정답·해설",
        "채점": "정답·채점",
    }
    match = re.match(r"^\*\*(정답|예시답|채점):\*\*[ \t]*(.*)$", body)
    if match:
        return labels[match.group(1)], match.group(2).strip()
    return "정답·해설", body.strip()


def _convert_numbered_lists(
    text: str,
    question_start: int,
    answer_heading: re.Match[str],
    answer_end: int,
) -> str:
    question_body = text[question_start : answer_heading.start()]
    answer_body = text[answer_heading.end() : answer_end]
    questions = list(LIST_ITEM.finditer(question_body))
    answers = list(LIST_ITEM.finditer(answer_body))
    if not questions or not answers:
        raise ConversionError("번호형 문제 또는 정답을 찾지 못했습니다.")

    question_numbers = [int(match.group(1)) for match in questions]
    answer_numbers = [int(match.group(1)) for match in answers]
    if question_numbers != answer_numbers:
        raise ConversionError(
            f"문제 번호 {question_numbers}와 정답 번호 {answer_numbers}가 일치하지 않습니다."
        )

    if answer_body[: answers[0].start()].strip():
        raise ConversionError("첫 정답 앞에 예상하지 못한 본문이 있습니다.")
    for current, following in zip(answers, answers[1:]):
        if answer_body[current.end() : following.start()].strip():
            raise ConversionError(
                f"정답 {current.group(1)}과 {following.group(1)} 사이에 예상하지 못한 본문이 있습니다."
            )

    answer_map = {int(match.group(1)): match.group(2).strip() for match in answers}
    chunks: list[str] = []
    cursor = 0
    for question in questions:
        chunks.append(question_body[cursor : question.start()])
        chunks.append(f"**문제 {question.group(1)}.** {question.group(2)}")
        label, answer = _normalize_list_answer(answer_map[int(question.group(1))])
        chunks.append(f"\n\n> **{label}:** {answer}\n")
        cursor = question.end()
    chunks.append(question_body[cursor:])
    converted_questions = "".join(chunks).rstrip() + "\n\n"

    trailing = answer_body[answers[-1].end() :].lstrip("\n")
    return (
        text[:question_start]
        + converted_questions
        + trailing
        + text[answer_end:]
    )


def _convert_answer_table(
    text: str,
    question_start: int,
    answer_heading: re.Match[str],
    answer_end: int,
) -> str:
    question_body = text[question_start : answer_heading.start()]
    answer_body = text[answer_heading.end() : answer_end]
    questions = list(MCQ_HEADING.finditer(question_body))
    rows = list(ANSWER_ROW.finditer(answer_body))
    if not questions or not rows:
        raise ConversionError("객관식 문제 또는 정답표 행을 찾지 못했습니다.")

    question_numbers = [int(match.group(1)) for match in questions]
    answer_numbers = [int(match.group(1)) for match in rows]
    if question_numbers != answer_numbers:
        raise ConversionError(
            f"문제 번호 {question_numbers}와 정답 번호 {answer_numbers}가 일치하지 않습니다."
        )

    answer_map = {
        int(row.group(1)): (row.group(2).strip(), row.group(3).strip()) for row in rows
    }
    chunks = [question_body[: questions[0].start()]]
    for index, question in enumerate(questions):
        block_end = questions[index + 1].start() if index + 1 < len(questions) else len(question_body)
        block = question_body[question.start() : block_end].rstrip()
        answer, explanation = answer_map[int(question.group(1))]
        chunks.append(f"{block}\n\n> **정답·해설:** {answer}. {explanation}\n\n")
    converted_questions = "".join(chunks).rstrip() + "\n\n"

    trailing = answer_body[rows[-1].end() :].lstrip("\n")
    return (
        text[:question_start]
        + converted_questions
        + trailing
        + text[answer_end:]
    )


def convert(text: str) -> str:
    answer_headings = list(ANSWER_HEADING.finditer(text))
    if not answer_headings:
        if INLINE_ANSWER.search(text):
            return text
        raise ConversionError("분리된 정답 섹션을 찾지 못했습니다.")
    if len(answer_headings) != 1:
        raise ConversionError(f"정답 섹션이 {len(answer_headings)}개라 변환을 중단합니다.")

    answer_heading = answer_headings[0]
    answer_end = _section_end(text, answer_heading)
    question_start = _question_region_start(text, answer_heading.start())
    answer_body = text[answer_heading.end() : answer_end]

    if LIST_ITEM.search(answer_body):
        converted = _convert_numbered_lists(text, question_start, answer_heading, answer_end)
    elif ANSWER_ROW.search(answer_body):
        converted = _convert_answer_table(text, question_start, answer_heading, answer_end)
    else:
        raise ConversionError("지원하는 번호형 정답이나 정답표를 찾지 못했습니다.")

    if ANSWER_HEADING.search(converted):
        raise ConversionError("변환 뒤에도 분리된 정답 섹션이 남았습니다.")
    if not INLINE_ANSWER.search(converted):
        raise ConversionError("변환 뒤 인라인 정답을 찾지 못했습니다.")
    return converted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="변환 가능성 또는 이미 변환된 상태만 검사하고 파일을 쓰지 않습니다.",
    )
    args = parser.parse_args()

    changed = 0
    for path in args.paths:
        original = path.read_text(encoding="utf-8")
        converted = convert(original)
        if converted != original:
            changed += 1
            if not args.check:
                path.write_text(converted, encoding="utf-8")
        state = "변환 필요" if converted != original else "인라인 확인"
        print(f"{path}: {state}")
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

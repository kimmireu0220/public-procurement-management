"""agent_extract Part별 형식·정답 일치 검증."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import SUBJECT_CATALOG, subject_extract_dir, subject_problem_book_dir  # noqa: E402

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답", re.MULTILINE)
QUESTION_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)
ANSWER_LINE_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
ANSWER_NUM_RE = re.compile(r"(?:^|\s)(\d+)\.")
SOURCE_COMMENT_RE = re.compile(r"<!--\s*source:")
ANSWER_TRACE_RE = re.compile(
    r"본문 정답표|정답표|정답은|답은|해설상|[①②③④⑤⑥⑦⑧⑨⑩]\s*[-—–]|\b[OX]\s*[-—–]"
)
BROKEN_CHAR_RE = re.compile(r"(?<=\s)[l@](?=\s)|\uff00")


def split_body_answer(text: str) -> tuple[str, str, int | None]:
    match = ANSWER_HEADING_RE.search(text)
    if not match:
        return text, "", None
    return text[: match.start()], text[match.start() :], match.start()


COMPRESSED_ANSWER_RE = re.compile(
    r"(?:^|\s)(\d+)\.\s+(?:[①②③④⑤⑥⑦⑧⑨⑩]|[OX]\b)"
)


def count_answer_entries_in_line(line: str) -> int:
    if not ANSWER_LINE_RE.match(line):
        return 0
    m = re.match(r"^\s*(\d+)\.\s+", line)
    if not m:
        return 0
    first = int(m.group(1))
    choice_entries = COMPRESSED_ANSWER_RE.findall(line)
    if len(choice_entries) >= 2:
        return len(choice_entries)
    if first == 1:
        nums = [first]
        for em in re.finditer(r"\s(\d+)\.\s+", line[m.end() :]):
            n = int(em.group(1))
            if n == nums[-1] + 1:
                nums.append(n)
            else:
                break
        if len(nums) > 1:
            return len(nums)
    if choice_entries:
        return 1
    return 1


def count_answers_in_section(section: str) -> int:
    total = 0
    for line in section.splitlines():
        total += count_answer_entries_in_line(line)
    if total:
        return total
    nums = [int(m.group(1)) for m in ANSWER_NUM_RE.finditer(section)]
    return max(nums) if nums else 0


def count_answers(answer: str) -> int:
    if not answer.strip():
        return 0
    parts = re.split(r"^#{2,4}\s+", answer, flags=re.MULTILINE)
    sections = [p for p in parts if p.strip()]
    if not sections:
        sections = [answer]
    return sum(count_answers_in_section(section) for section in sections)


def validate_part(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    body, answer, cut = split_body_answer(text)
    q_body = len(QUESTION_RE.findall(body))
    q_answer = count_answers(answer) if answer else 0
    sources = len(SOURCE_COMMENT_RE.findall(body))
    traces = len(ANSWER_TRACE_RE.findall(body))
    broken = len(BROKEN_CHAR_RE.findall(body))
    return {
        "file": path.name,
        "questions": q_body,
        "answers": q_answer,
        "sources": sources,
        "answer_cut_line": cut,
        "body_traces": traces,
        "broken_chars": broken,
        "ok": cut is not None and q_body == q_answer and q_body > 0,
    }


def validate_subject(subject_no: str) -> tuple[list[dict], Path]:
    extract_dir = subject_extract_dir(subject_no)
    final_dir = subject_problem_book_dir(subject_no)
    final_dir.mkdir(parents=True, exist_ok=True)
    report_path = final_dir / "추출_검증.md"

    rows: list[dict] = []
    for part_file in sorted(extract_dir.glob("part*.md")):
        rows.append(validate_part(part_file))

    total_q = sum(r["questions"] for r in rows)
    total_a = sum(r["answers"] for r in rows)
    issues = [r for r in rows if not r["ok"]]

    lines = [
        "# 추출 검증 리포트",
        "",
        f"- 과목: {subject_no}과목 ({SUBJECT_CATALOG[subject_no]['exam_name']})",
        f"- 입력: `{extract_dir}`",
        "",
        "| Part 파일 | 문항 | 정답 | 출처 주석 | 본문 답안 흔적 | 이상 문자 | 일치 |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        mark = "✅" if r["ok"] else "❌"
        lines.append(
            f"| {r['file']} | {r['questions']} | {r['answers']} | {r['sources']} "
            f"| {r['body_traces']} | {r['broken_chars']} | {mark} |"
        )
    lines.extend(
        [
            "",
            f"- **총 문항:** {total_q}",
            f"- **총 정답:** {total_a}",
            f"- **문항=정답:** {'✅' if total_q == total_a and not issues else '❌'}",
        ]
    )
    if issues:
        lines.extend(["", "## 미일치 Part 파일", ""])
        for r in issues:
            lines.append(
                f"- {r['file']}: 문항 {r['questions']} / 정답 {r['answers']} "
                f"(정답 섹션 시작 줄: {r['answer_cut_line']})"
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows, report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="agent_extract 문항·정답 일치 여부를 검증하고 추출_검증.md를 생성합니다.",
    )
    parser.add_argument("--subject", default="all", help="1~4 or all")
    args = parser.parse_args()
    subjects = list(SUBJECT_CATALOG) if args.subject == "all" else [args.subject]
    for subject_no in subjects:
        rows, report = validate_subject(subject_no)
        status = "OK" if all(r["ok"] for r in rows) else "ISSUES"
        total = sum(r["questions"] for r in rows)
        print(f"{subject_no}과목: {status} ({total}문항) -> {report}")


if __name__ == "__main__":
    main()

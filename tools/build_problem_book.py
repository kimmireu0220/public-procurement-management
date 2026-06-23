from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import (  # noqa: E402
    ROOT,
    SUBJECT_CATALOG,
    subject_extract_dir,
    subject_problem_book_dir,
)
from validate_extract import validate_part  # noqa: E402

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답")

# 과목별 문제 유형 안내 (합본 blockquote)
PROBLEM_TYPE_BLURB: dict[str, str] = {
    "1": "Check Q&A, 단원별 출제예상문제, 최종점검 OX 퀴즈",
    "2": "Check Q&A, 단원별 출제예상문제, 최종점검 OX 퀴즈",
    "3": "Check Q&A, 단원별 출제예상문제, 최종점검 OX 퀴즈",
    "4": "바로 Check, 핵심 최종점검, 서술형·Check Q&A (OX 퀴즈 없음)",
}


def strip_answer_section(text: str) -> tuple[str, int | None]:
    lines = text.splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        if ANSWER_HEADING_RE.match(line.strip()):
            cut_at = i
            break
    if cut_at is None:
        return text.rstrip() + "\n", None
    return "\n".join(lines[:cut_at]).rstrip() + "\n", cut_at + 1


def demote_headings(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.startswith("### "):
            out.append("#### " + line[4:])
        elif line.startswith("## "):
            out.append("### " + line[3:])
        elif line.startswith("# "):
            out.append("## " + line[2:])
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"

def make_html(markdown_text: str, title: str) -> str:
    body_lines: list[str] = []
    in_list = False
    for raw in markdown_text.splitlines():
        line = raw.rstrip()
        if not line:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("<!--"):
            continue
        if line.startswith("# "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("#### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h4>{html.escape(line[5:])}</h4>")
        elif line.startswith("> "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif re.match(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]", line):
            if not in_list:
                body_lines.append("<ul class=\"choices\">")
                in_list = True
            body_lines.append(f"<li>{html.escape(line.strip())}</li>")
        elif re.match(r"^\s*\d+\.\s+", line):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p class=\"question\">{html.escape(line.strip())}</p>")
        elif line == "---":
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append("<hr>")
        else:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p>{html.escape(line.strip())}</p>")
    if in_list:
        body_lines.append("</ul>")

    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
@page { margin: 18mm 16mm; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  line-height: 1.55;
  color: #111;
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
}
h1 { font-size: 28px; margin: 0 0 22px; }
h2 { font-size: 22px; margin: 34px 0 12px; padding-top: 14px; border-top: 2px solid #222; }
h3 { font-size: 18px; margin: 24px 0 10px; }
h4 { font-size: 15px; margin: 18px 0 8px; }
p { margin: 6px 0; }
blockquote { color: #555; border-left: 4px solid #ddd; padding-left: 12px; margin: 8px 0 18px; }
.question { font-weight: 600; margin-top: 14px; break-inside: avoid; }
.choices { list-style: none; padding-left: 22px; margin: 4px 0 12px; break-inside: avoid; }
.choices li { margin: 2px 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
@media print {
  body { max-width: none; padding: 0; }
  h2 { break-before: page; }
  h2:first-of-type { break-before: auto; }
}
</style>
</head>
<body>
""" + "\n".join(body_lines) + """
</body>
</html>
"""


def build_subject(subject_no: str) -> tuple[Path, Path, Path]:
    meta = SUBJECT_CATALOG[subject_no]
    source_dir = subject_extract_dir(subject_no)
    final_dir = subject_problem_book_dir(subject_no)
    parts_dir = final_dir / "parts_clean"
    part_count = int(meta["parts"])

    final_dir.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    book_title = f"{subject_no}과목 {meta['textbook_name']} 문제집"
    combined_parts = [
        f"# {book_title}",
        "",
        f"> {meta['exam_type']} {subject_no}과목({meta['exam_name']}) · 박문각 수험서 「{meta['textbook_name']}」",
        f"> 문제 유형({PROBLEM_TYPE_BLURB[subject_no]})만 모은 학습용 합본입니다.",
        "",
    ]
    source_rel = source_dir.relative_to(ROOT) if source_dir.is_relative_to(ROOT) else source_dir
    final_rel = final_dir.relative_to(ROOT) if final_dir.is_relative_to(ROOT) else final_dir
    report_lines = [
        "# 문제집 생성 검토 요약",
        "",
        f"- 과목: {subject_no}과목 ({meta['exam_name']})",
        f"- 입력: `{source_rel}`",
        f"- 출력: `{final_rel}`",
        "> 문항 수는 `validate_extract.py`와 동일 로직입니다.",
        "",
        "| Part 파일 | 정답 섹션 제거 시작 줄 | 문제 수 | 출처 주석 수 |",
        "|---|---:|---:|---:|",
    ]

    for n in range(1, part_count + 1):
        source = source_dir / f"part{n}.md"
        text = source.read_text(encoding="utf-8")
        stripped, cut_line = strip_answer_section(text)
        clean = demote_headings(stripped)
        clean_path = parts_dir / f"part{n}.md"
        clean_path.write_text(clean, encoding="utf-8")

        v = validate_part(source)
        question_count = v["questions"]
        source_count = v["sources"]
        cut_label = str(cut_line) if cut_line else "-"
        report_lines.append(f"| part{n}.md | {cut_label} | {question_count} | {source_count} |")
        combined_parts.append(clean.rstrip())
        combined_parts.append("")

    combined = "\n".join(combined_parts).rstrip() + "\n"
    md_path = final_dir / f"{subject_no}과목_문제집.md"
    html_path = final_dir / f"{subject_no}과목_문제집.html"
    report_path = final_dir / "검토_요약.md"

    md_path.write_text(combined, encoding="utf-8")
    html_path.write_text(make_html(combined, book_title), encoding="utf-8")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return md_path, html_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="에이전트 추출본에서 문제집(정답 제거)을 생성합니다.")
    parser.add_argument(
        "--subject",
        default="1",
        help="과목 번호 1~4, 또는 all",
    )
    args = parser.parse_args()

    if args.subject == "all":
        subjects = sorted(SUBJECT_CATALOG)
    elif args.subject in SUBJECT_CATALOG:
        subjects = [args.subject]
    else:
        parser.error(f"알 수 없는 과목: {args.subject!r} (1~4 또는 all)")

    for subject_no in subjects:
        md_path, html_path, report_path = build_subject(subject_no)
        print(md_path)
        print(html_path)
        print(report_path)


if __name__ == "__main__":
    main()

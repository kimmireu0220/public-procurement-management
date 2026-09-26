"""숫자 암기표 페이지와 CBT 문항 링크를 생성한다."""

from __future__ import annotations

import html
import re
from pathlib import Path

from build_lecture_pages import article_outline, inline_markup, markdown_to_html, page_shell

NUMBER_MEMORY_GUIDES = (
    (1, "공공조달의 이해", "1과목_공공조달의_이해.md"),
    (2, "공공조달 계획·분석", "2과목_공공조달_계획분석.md"),
    (3, "공공계약관리", "3과목_공공계약관리.md"),
)


def render_number_memory_guide(subject: int, subject_title: str, source: Path) -> str:
    raw = source.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"숫자 암기표의 1단계 제목이 없습니다: {source}")
    title = lines[0][2:].strip()
    body_markdown = "\n".join(re.sub(r"^> ?", "", line) for line in lines[1:]).strip()
    body_markdown = re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"\1", body_markdown)
    def render_cell(header: str, cell: str) -> str:
        if header != "문제":
            return inline_markup(cell)
        return re.sub(
            r"\d+",
            lambda number: (
                f'<a href="../../{subject}과목/?q={number.group(0)}">'
                f'{number.group(0)}번 문제</a>'
            ),
            inline_markup(cell),
        )

    article = markdown_to_html(body_markdown, table_cell_renderer=render_cell)
    outline = article_outline(body_markdown)
    body = (
        '<main class="page" id="main-content" tabindex="-1"><article class="article">'
        '<nav class="breadcrumb" aria-label="현재 위치"><a href="../../">학습센터</a> › '
        f'<span aria-current="page">{subject}과목 숫자 암기표</span></nav>'
        '<span class="eyebrow">NUMBER MEMORY</span>'
        f'<h1>{html.escape(title)}</h1><p class="subtitle">{html.escape(subject_title)} · 기한·비율·금액·구간 집중 복습</p>'
        f'{outline}{article}<nav class="article-nav" aria-label="관련 학습">'
        f'<a class="nav-link prev" href="../../{subject}과목/">← {subject}과목 CBT</a>'
        f'<a class="nav-link next" href="../../lecture/{subject}/">{subject}과목 강의 →</a>'
        '</nav><a class="back-to-top" href="#main-content">↑ 맨 위로</a></article></main>'
    )
    return page_shell(f"{subject}과목 숫자 암기표", body, "../../lecture/")


def write_number_memory_guides(docs: Path) -> None:
    for subject, subject_title, filename in NUMBER_MEMORY_GUIDES:
        source = docs / "학습_숫자암기" / filename
        destination = docs / "학습_숫자암기" / f"{subject}과목" / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_number_memory_guide(subject, subject_title, source), encoding="utf-8"
        )

#!/usr/bin/env python3
"""Build the chapter lecture GitHub Pages site from Markdown sources."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "output" / "chapter_lectures"
OUTPUT_DIR = ROOT / "docs" / "lecture"
REQUIRED_META = {"subject", "subject_title", "part", "part_title", "chapter", "title"}
EXPECTED_CHAPTERS = {
    1: {1: 4, 2: 3, 3: 4, 4: 5, 5: 5, 6: 6, 7: 2},
    2: {1: 5, 2: 4, 3: 5, 4: 14},
    3: {1: 4, 2: 3, 3: 2, 4: 13},
}


@dataclass(frozen=True)
class Lecture:
    source: Path
    subject: int
    subject_title: str
    part: int
    part_title: str
    chapter: int
    title: str
    kind: str
    body: str

    @property
    def is_review(self) -> bool:
        return self.kind == "review"

    @property
    def is_overview(self) -> bool:
        return self.kind == "overview"

    @property
    def is_chapter(self) -> bool:
        return not self.is_review and not self.is_overview

    @property
    def relative_url(self) -> str:
        if self.is_overview:
            return f"{self.subject}/overview/"
        if self.is_review:
            return f"{self.subject}/review/total-review/"
        return f"{self.subject}/part{self.part:02d}/chapter{self.chapter:02d}/"


def parse_front_matter(path: Path) -> Lecture:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"front matter가 없습니다: {path}")
    try:
        raw_meta, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"front matter 종료선이 없습니다: {path}") from exc

    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"잘못된 front matter: {path}: {line}")
        meta[key.strip()] = value.strip()

    missing = REQUIRED_META - meta.keys()
    if missing:
        raise ValueError(f"필수 metadata 누락 {sorted(missing)}: {path}")

    return Lecture(
        source=path,
        subject=int(meta["subject"]),
        subject_title=meta["subject_title"],
        part=int(meta["part"]),
        part_title=meta["part_title"],
        chapter=int(meta["chapter"]),
        title=meta["title"],
        kind=meta.get("kind", "chapter"),
        body=body.strip() + "\n",
    )


def load_lectures() -> list[Lecture]:
    lectures = [
        parse_front_matter(path)
        for path in SOURCE_DIR.glob("*/*.md")
        if path.name != "README.md"
    ]
    lectures.extend(parse_front_matter(path) for path in SOURCE_DIR.glob("*/part*/*.md"))
    lectures.sort(key=lambda item: (item.subject, item.part, item.chapter))
    validate_lectures(lectures)
    return lectures


def validate_lectures(lectures: list[Lecture]) -> None:
    seen: set[tuple[int, int, int, str]] = set()
    by_part: dict[tuple[int, int], list[int]] = {}
    subject_titles: dict[int, str] = {}
    part_titles: dict[tuple[int, int], str] = {}

    for lecture in lectures:
        key = (lecture.subject, lecture.part, lecture.chapter, lecture.kind)
        if key in seen:
            raise ValueError(f"중복 Chapter metadata: {key}")
        seen.add(key)
        if lecture.subject in subject_titles and subject_titles[lecture.subject] != lecture.subject_title:
            raise ValueError(f"과목명이 일치하지 않습니다: {lecture.source}")
        subject_titles[lecture.subject] = lecture.subject_title
        if lecture.is_chapter:
            part_key = (lecture.subject, lecture.part)
            if part_key in part_titles and part_titles[part_key] != lecture.part_title:
                raise ValueError(f"Part명이 일치하지 않습니다: {lecture.source}")
            part_titles[part_key] = lecture.part_title
            by_part.setdefault(part_key, []).append(lecture.chapter)

        required_sections = ("## ① 한눈에 보기", "## ② 차근차근 설명", "## ③ 시험 포인트", "## ④ 암기 체크리스트")
        if lecture.is_chapter and any(section not in lecture.body for section in required_sections):
            raise ValueError(f"강의 필수 섹션이 없습니다: {lecture.source}")

    for part_key, chapters in by_part.items():
        expected = list(range(1, max(chapters) + 1))
        if chapters != expected:
            raise ValueError(f"Chapter 번호가 연속적이지 않습니다: {part_key}: {chapters}")

    for subject, expected_parts in EXPECTED_CHAPTERS.items():
        actual_parts = {
            part: len(chapters)
            for (item_subject, part), chapters in by_part.items()
            if item_subject == subject
        }
        if actual_parts != expected_parts:
            raise ValueError(
                f"{subject}과목 Part·Chapter 구성이 다릅니다: "
                f"expected={expected_parts}, actual={actual_parts}"
            )


def inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    result: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None
    in_code = False
    code_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            result.append(f"<p>{inline_markup(' '.join(part.strip() for part in paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            result.append(f"</{list_kind}>")
            list_kind = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                result.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            close_list()
            headers = split_table_row(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1
            result.append("<div class=\"table-wrap\"><table><thead><tr>")
            result.extend(f"<th>{inline_markup(cell)}</th>" for cell in headers)
            result.append("</tr></thead><tbody>")
            for row in rows:
                result.append("<tr>")
                result.extend(f"<td>{inline_markup(cell)}</td>" for cell in row)
                result.append("</tr>")
            result.append("</tbody></table></div>")
            continue

        heading = re.match(r"^(#{2,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)), 4)
            title = heading.group(2)
            anchor = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-").lower()
            result.append(f"<h{level} id=\"{html.escape(anchor)}\">{inline_markup(title)}</h{level}>")
            index += 1
            continue

        if stripped in {"---", "***"}:
            flush_paragraph()
            close_list()
            result.append("<hr>")
            index += 1
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            close_list()
            result.append(f"<blockquote>{inline_markup(stripped[2:])}</blockquote>")
            index += 1
            continue

        checkbox = re.match(r"^- \[([ xX])\]\s+(.+)$", stripped)
        bullet = re.match(r"^-\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if checkbox or bullet or ordered:
            flush_paragraph()
            desired = "ol" if ordered else "ul"
            if list_kind != desired:
                close_list()
                result.append(f"<{desired}>")
                list_kind = desired
            if checkbox:
                checked = " checked" if checkbox.group(1).lower() == "x" else ""
                result.append(f"<li class=\"check-item\"><input type=\"checkbox\" disabled{checked}> {inline_markup(checkbox.group(2))}</li>")
            else:
                list_match = ordered if ordered is not None else bullet
                assert list_match is not None
                value = list_match.group(1)
                result.append(f"<li>{inline_markup(value)}</li>")
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    if in_code:
        result.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return "\n".join(result)


STYLE = """
:root{--navy:#12375b;--blue:#2563a5;--sky:#eaf3fb;--paper:#fff;--ink:#17212b;--muted:#647383;--line:#d6e0e9;--accent:#f2a93b}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f5f7fa;color:var(--ink);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;line-height:1.72}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}.site-header{background:linear-gradient(135deg,var(--navy),#245f98);color:#fff;padding:1rem 1.25rem;position:sticky;top:0;z-index:5;box-shadow:0 2px 12px #12375b30}.header-inner{max-width:1180px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:1rem}.brand{font-weight:800;color:#fff}.brand:hover{text-decoration:none}.header-note{font-size:.86rem;opacity:.82}
.page{max-width:1180px;margin:0 auto;padding:2rem 1.25rem 4rem}.hero{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:2.2rem;box-shadow:0 10px 30px #12375b10}.eyebrow{color:var(--blue);font-size:.88rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.hero h1{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.2;margin:.35rem 0 .75rem}.hero p{color:var(--muted);margin:0;max-width:760px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;margin-top:1.5rem}.card{display:block;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1.25rem;color:var(--ink);box-shadow:0 4px 16px #12375b0b}.card.available:hover{border-color:var(--blue);transform:translateY(-2px);text-decoration:none}.card h2,.card h3{margin:.2rem 0 .45rem;color:var(--navy)}.card p{margin:0;color:var(--muted);font-size:.92rem}.badge{display:inline-block;border-radius:999px;padding:.2rem .6rem;background:var(--sky);color:var(--blue);font-size:.75rem;font-weight:800}.badge.pending{background:#f0f1f3;color:#737b84}
.subject-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:1.5rem}.sidebar{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1rem;align-self:start;position:sticky;top:5.5rem;max-height:calc(100vh - 7rem);overflow:auto}.sidebar h2{font-size:1rem;color:var(--navy);margin:.4rem 0}.sidebar h3{font-size:.87rem;color:var(--muted);margin:1rem 0 .25rem}.sidebar a{display:block;padding:.3rem .45rem;border-radius:6px;font-size:.86rem;color:#344657}.sidebar a:hover,.sidebar a.current{background:var(--sky);color:var(--navy);text-decoration:none}
.article{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:clamp(1.2rem,4vw,3rem);min-width:0}.breadcrumb{font-size:.84rem;color:var(--muted);margin-bottom:1.2rem}.article h1{font-size:clamp(1.65rem,4vw,2.35rem);line-height:1.25;margin:.2rem 0 .4rem;color:var(--navy)}.subtitle{color:var(--muted);margin-bottom:2rem}.article h2{margin:2.2rem 0 .8rem;padding-bottom:.45rem;border-bottom:2px solid var(--sky);color:var(--navy);font-size:1.35rem}.article h3{color:var(--blue);margin-top:1.7rem}.article p{margin:.8rem 0}.article li{margin:.28rem 0}.article code{background:#eef2f6;padding:.12rem .35rem;border-radius:5px}.article pre{background:#14283b;color:#edf6ff;padding:1rem;border-radius:10px;overflow:auto}.article blockquote{margin:1rem 0;padding:.8rem 1rem;background:#fff8e8;border-left:4px solid var(--accent);color:#4d4331}.article hr{border:0;border-top:1px solid var(--line);margin:2rem 0}.table-wrap{overflow:auto;margin:1rem 0}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{border:1px solid var(--line);padding:.65rem .75rem;text-align:left;vertical-align:top}th{background:var(--sky);color:var(--navy)}.check-item{list-style:none;margin-left:-1.2rem}.check-item input{margin-right:.35rem}
.chapter-list{margin-top:1.5rem}.part-section{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1.2rem 1.35rem;margin:1rem 0}.part-section h2{font-size:1.18rem;color:var(--navy);margin:0 0 .65rem}.chapter-link{display:flex;justify-content:space-between;gap:1rem;padding:.55rem 0;border-top:1px solid #edf1f5}.chapter-link:first-of-type{border-top:0}.chapter-link span:last-child{color:var(--muted);font-size:.82rem}.article-nav{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-top:2.5rem}.nav-link{border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem}.nav-link.next{text-align:right}.footer{text-align:center;color:var(--muted);font-size:.82rem;padding:1.5rem}.back-link{display:inline-block;margin-top:1.25rem}
@media(max-width:820px){.subject-layout{grid-template-columns:1fr}.sidebar{position:static;max-height:none}.header-note{display:none}.page{padding:1rem .75rem 3rem}.hero{padding:1.4rem}.article{padding:1.2rem}.article-nav{grid-template-columns:1fr}.nav-link.next{text-align:left}}
""".strip()


def page_shell(title: str, body: str, asset_prefix: str) -> str:
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 공공조달관리사 Chapter 강의</title>
<link rel="stylesheet" href="{asset_prefix}assets/style.css"></head>
<body><header class="site-header"><div class="header-inner"><a class="brand" href="{asset_prefix}">공공조달관리사 Chapter 강의</a><span class="header-note">이론 · 시험 포인트 · 암기 체크</span></div></header>
{body}<footer class="footer">박문각 수험서·조달청 표준교재 기반 학습자료</footer></body></html>
"""


def sidebar_html(subject_lectures: list[Lecture], current: Lecture, subject_prefix: str) -> str:
    grouped: dict[int, list[Lecture]] = {}
    for lecture in subject_lectures:
        if lecture.is_chapter:
            grouped.setdefault(lecture.part, []).append(lecture)
    chunks = ["<aside class=\"sidebar\"><h2>과목 목차</h2>"]
    overview = next((item for item in subject_lectures if item.is_overview), None)
    if overview:
        current_class = " class=\"current\"" if overview == current else ""
        chunks.append(f'<a{current_class} href="{subject_prefix}overview/">과목 개요</a>')
    for part, items in sorted(grouped.items()):
        chunks.append(f"<h3>Part {part}. {html.escape(items[0].part_title)}</h3>")
        for item in items:
            current_class = " class=\"current\"" if item == current else ""
            href = f"{subject_prefix}part{item.part:02d}/chapter{item.chapter:02d}/"
            chunks.append(f"<a{current_class} href=\"{href}\">Ch {item.chapter}. {html.escape(item.title)}</a>")
    review = next((item for item in subject_lectures if item.is_review), None)
    if review:
        current_class = " class=\"current\"" if review == current else ""
        chunks.append(
            f"<h3>총정리</h3><a{current_class} href=\"{subject_prefix}review/total-review/\">"
            f"{current.subject}과목 총정리</a>"
        )
    chunks.append("</aside>")
    return "".join(chunks)


def render_home(catalog: dict, lectures: list[Lecture]) -> str:
    counts: dict[int, int] = {}
    for lecture in lectures:
        if lecture.is_chapter:
            counts[lecture.subject] = counts.get(lecture.subject, 0) + 1
    cards: list[str] = []
    for subject in catalog["subjects"]:
        subject_id = int(subject["id"])
        count = counts.get(subject_id, 0)
        if count:
            cards.append(
                f'<a class="card available" href="{subject_id}/"><span class="badge">강의 공개</span>'
                f'<h2>{subject_id}과목</h2><h3>{html.escape(subject["title"])}</h3>'
                f'<p>{count}개 Chapter와 과목 총정리</p></a>'
            )
        else:
            cards.append(
                f'<div class="card"><span class="badge pending">추가 예정</span><h2>{subject_id}과목</h2>'
                f'<h3>{html.escape(subject["title"])}</h3><p>같은 구조로 Chapter 강의를 추가할 예정입니다.</p></div>'
            )
    body = f"""<main class="page"><section class="hero"><span class="eyebrow">PUBLIC PROCUREMENT MANAGER</span>
<h1>{html.escape(catalog['site_title'])}</h1><p>과목별·Part별·Chapter별로 정리한 이론 강의입니다. 문제풀이 페이지와 분리해 개념, 시험 포인트, 암기 항목에 집중합니다.</p></section>
<section class="grid">{''.join(cards)}</section><a class="back-link" href="../">← 필기 모의 CBT로 돌아가기</a></main>"""
    return page_shell("강의 홈", body, "")


def render_subject(subject: dict, subject_lectures: list[Lecture]) -> str:
    grouped: dict[int, list[Lecture]] = {}
    review = None
    overview = None
    for lecture in subject_lectures:
        if lecture.is_review:
            review = lecture
        elif lecture.is_overview:
            overview = lecture
        else:
            grouped.setdefault(lecture.part, []).append(lecture)
    sections: list[str] = []
    for part, items in sorted(grouped.items()):
        links = "".join(
            f'<a class="chapter-link" href="part{part:02d}/chapter{item.chapter:02d}/">'
            f'<span>Chapter {item.chapter}. {html.escape(item.title)}</span><span>강의 보기 →</span></a>'
            for item in items
        )
        sections.append(f'<section class="part-section"><h2>Part {part}. {html.escape(items[0].part_title)}</h2>{links}</section>')
    overview_card = ""
    if overview:
        overview_card = (
            '<a class="card available" href="overview/"><span class="badge">START</span>'
            f'<h2>{subject["id"]}과목 개요</h2>'
            '<p>시험 구조와 Part별 학습 지도를 먼저 확인합니다.</p></a>'
        )
    overview_section = f'<section class="grid">{overview_card}</section>' if overview_card else ""
    review_card = ""
    if review:
        part_count = len(grouped)
        review_card = (
            '<a class="card available" href="review/total-review/">'
            '<span class="badge">최종 복습</span>'
            f'<h2>{subject["id"]}과목 총정리</h2>'
            f'<p>Part 1～{part_count} 핵심 개념·숫자·비교를 한 번에 확인합니다.</p></a>'
        )
    body = f"""<main class="page"><section class="hero"><span class="eyebrow">SUBJECT {subject['id']}</span>
<h1>{subject['id']}과목 · {html.escape(subject['title'])}</h1><p>{len([x for x in subject_lectures if x.is_chapter])}개 Chapter를 수험서 순서대로 학습합니다.</p></section>
{overview_section}<section class="chapter-list">{''.join(sections)}</section><section class="grid">{review_card}</section><a class="back-link" href="../">← 전체 과목</a></main>"""
    return page_shell(f"{subject['id']}과목", body, "../")


def render_lecture(lecture: Lecture, subject_lectures: list[Lecture]) -> str:
    def lecture_order(item: Lecture) -> tuple[int, int, int]:
        if item.is_overview:
            return (0, 0, 0)
        if item.is_review:
            return (2, 0, 0)
        return (1, item.part, item.chapter)

    ordered = sorted(subject_lectures, key=lecture_order)
    position = ordered.index(lecture)
    previous = ordered[position - 1] if position else None
    following = ordered[position + 1] if position + 1 < len(ordered) else None

    def nav_link(item: Lecture | None, direction: str) -> str:
        if not item:
            return "<span></span>"
        href = f"{root_prefix}{item.relative_url}"
        label = item.title if not item.is_chapter else f"Part {item.part} · Ch {item.chapter} {item.title}"
        arrow = "← " if direction == "prev" else " →"
        text = f"{arrow}{html.escape(label)}" if direction == "prev" else f"{html.escape(label)}{arrow}"
        return f'<a class="nav-link {direction}" href="{href}">{text}</a>'

    root_prefix = "../../" if lecture.is_overview else "../../../"
    subject_prefix = "../" if lecture.is_overview else "../../"
    if lecture.is_review:
        chapter_label = "총정리"
    elif lecture.is_overview:
        chapter_label = "과목 개요"
    else:
        chapter_label = f"Part {lecture.part} · Chapter {lecture.chapter}"
    article = markdown_to_html(lecture.body)
    body = f"""<main class="page"><div class="subject-layout">{sidebar_html(subject_lectures, lecture, subject_prefix)}
<article class="article"><div class="breadcrumb"><a href="{root_prefix}">전체 과목</a> › <a href="{subject_prefix}">{lecture.subject}과목</a> › {html.escape(chapter_label)}</div>
<span class="eyebrow">{html.escape(chapter_label)}</span><h1>{html.escape(lecture.title)}</h1><p class="subtitle">{html.escape(lecture.subject_title)} · {html.escape(lecture.part_title)}</p>
{article}<nav class="article-nav">{nav_link(previous, 'prev')}{nav_link(following, 'next')}</nav></article></div></main>"""
    return page_shell(lecture.title, body, root_prefix)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(destination: Path) -> dict:
    catalog = json.loads((SOURCE_DIR / "catalog.json").read_text(encoding="utf-8"))
    lectures = load_lectures()
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / "assets" / "style.css", STYLE + "\n")
    write_text(destination / "index.html", render_home(catalog, lectures))

    for subject in catalog["subjects"]:
        subject_id = int(subject["id"])
        subject_lectures = [item for item in lectures if item.subject == subject_id]
        if not subject_lectures:
            continue
        write_text(destination / str(subject_id) / "index.html", render_subject(subject, subject_lectures))
        for lecture in subject_lectures:
            write_text(destination / lecture.relative_url / "index.html", render_lecture(lecture, subject_lectures))

    meta = {
        "subjects": [
            {
                "id": int(subject["id"]),
                "title": subject["title"],
                "chapter_count": len([item for item in lectures if item.subject == int(subject["id"]) and item.is_chapter]),
                "published": any(item.subject == int(subject["id"]) for item in lectures),
            }
            for subject in catalog["subjects"]
        ],
        "total_chapters": len([item for item in lectures if item.is_chapter]),
    }
    write_text(destination / "lecture-meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def compare_trees(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()} if actual.exists() else set()
    errors = [f"누락 공개 파일: {path}" for path in sorted(expected_files - actual_files)]
    errors.extend(f"불필요 공개 파일: {path}" for path in sorted(actual_files - expected_files))
    for relative in sorted(expected_files & actual_files):
        if (expected / relative).read_bytes() != (actual / relative).read_bytes():
            errors.append(f"생성 결과 불일치: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="현재 공개본이 최신 생성 결과와 같은지 확인")
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory(prefix="lecture-pages-") as temp_dir:
            expected = Path(temp_dir) / "lecture"
            meta = build(expected)
            errors = compare_trees(expected, OUTPUT_DIR)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(f"강의 페이지 검증 완료: {meta['total_chapters']}개 Chapter")
        return 0

    with tempfile.TemporaryDirectory(prefix="lecture-pages-") as temp_dir:
        generated = Path(temp_dir) / "lecture"
        meta = build(generated)
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        shutil.copytree(generated, OUTPUT_DIR)
    from site_portal import write_portal

    write_portal()
    print(f"강의 페이지 생성 완료: {meta['total_chapters']}개 Chapter → {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

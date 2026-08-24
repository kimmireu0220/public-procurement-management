from __future__ import annotations

import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_lecture_pages  # noqa: E402


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


class LecturePagesTest(unittest.TestCase):
    def test_markdown_external_links_are_rendered_and_escaped(self) -> None:
        rendered = build_lecture_pages.inline_markup(
            "[공식 원문](https://example.com/rule?a=1&b=2) **확인**"
        )

        self.assertIn(
            '<a href="https://example.com/rule?a=1&amp;b=2">공식 원문</a>',
            rendered,
        )
        self.assertIn("<strong>확인</strong>", rendered)

    def test_sources_are_loadable_without_prescribing_body_structure(self) -> None:
        lectures = build_lecture_pages.load_lectures()

        self.assertTrue(lectures)
        self.assertEqual(len({lecture.source for lecture in lectures}), len(lectures))
        self.assertTrue(any(lecture.is_chapter for lecture in lectures))
        self.assertTrue(all(lecture.body.strip() for lecture in lectures))

    def test_overview_metadata_is_minimal_and_chapter_gaps_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            overview_path = Path(tmp) / "overview.md"
            overview_path.write_text(
                "---\nsubject: 1\nsubject_title: 테스트\ntitle: 자유 개요\nkind: overview\n---\n"
                "\n원하는 형식의 본문\n",
                encoding="utf-8",
            )
            overview = build_lecture_pages.parse_front_matter(overview_path)
            self.assertTrue(overview.is_overview)
            self.assertEqual(overview.part, 0)

        chapters = [
            build_lecture_pages.Lecture(
                source=Path(f"chapter{number}.md"),
                subject=1,
                subject_title="테스트",
                part=1,
                part_title="자유 구성",
                chapter=number,
                title=f"Chapter {number}",
                kind="chapter",
                body="고정 섹션이나 퀴즈 제한이 없는 본문\n",
            )
            for number in (1, 3)
        ]
        build_lecture_pages.validate_lectures(chapters)

    def test_build_emits_a_page_for_every_loaded_lecture(self) -> None:
        lectures = build_lecture_pages.load_lectures()
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            meta = build_lecture_pages.build(destination)

            self.assertEqual(
                meta["total_chapters"],
                len([lecture for lecture in lectures if lecture.is_chapter]),
            )
            self.assertTrue((destination / "index.html").is_file())
            self.assertTrue((destination / "assets" / "style.css").is_file())
            for lecture in lectures:
                self.assertTrue(
                    (destination / lecture.relative_url / "index.html").is_file(),
                    lecture.relative_url,
                )
            for subject in {lecture.subject for lecture in lectures}:
                self.assertTrue((destination / str(subject) / "index.html").is_file())

    def test_all_generated_internal_links_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            build_lecture_pages.build(destination)
            (destination.parent / "index.html").write_text("portal", encoding="utf-8")
            for page in destination.rglob("*.html"):
                parser = LinkParser()
                parser.feed(page.read_text(encoding="utf-8"))
                for href in parser.links:
                    parsed = urlsplit(href)
                    if parsed.scheme or parsed.netloc or href.startswith("#"):
                        continue
                    target = (page.parent / unquote(parsed.path)).resolve()
                    if parsed.path.endswith("/"):
                        target = target / "index.html"
                    self.assertTrue(target.exists(), f"깨진 링크: {page}: {href}")


if __name__ == "__main__":
    unittest.main()

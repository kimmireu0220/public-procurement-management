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
    def test_sources_have_expected_chapter_structure(self) -> None:
        lectures = build_lecture_pages.load_lectures()
        chapters = [lecture for lecture in lectures if lecture.is_chapter]
        reviews = [lecture for lecture in lectures if lecture.is_review]
        overviews = [lecture for lecture in lectures if lecture.is_overview]

        self.assertEqual(len(chapters), 79)
        self.assertEqual(len(reviews), 3)
        self.assertEqual({lecture.subject for lecture in chapters}, {1, 2, 3})
        self.assertEqual({lecture.subject for lecture in reviews}, {1, 2, 3})
        self.assertEqual({lecture.subject for lecture in overviews}, {3})
        subject2 = [lecture for lecture in chapters if lecture.subject == 2]
        self.assertEqual(sorted({lecture.part for lecture in subject2}), [1, 2, 3, 4])
        self.assertEqual(
            {part: len([item for item in subject2 if item.part == part]) for part in range(1, 5)},
            {1: 5, 2: 4, 3: 5, 4: 14},
        )
        subject3 = [lecture for lecture in chapters if lecture.subject == 3]
        self.assertEqual(sorted({lecture.part for lecture in subject3}), [1, 2, 3, 4])
        self.assertEqual(
            {part: len([item for item in subject3 if item.part == part]) for part in range(1, 5)},
            {1: 4, 2: 3, 3: 2, 4: 13},
        )
        self.assertEqual({lecture.subject_title for lecture in subject3}, {"공공계약관리"})
        subject3_review = next(lecture for lecture in reviews if lecture.subject == 3)
        self.assertEqual(subject3_review.kind, "review")
        self.assertEqual(subject3_review.title, "3과목 총정리")

    def test_build_creates_navigation_and_future_subject_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            meta = build_lecture_pages.build(destination)

            self.assertEqual(meta["total_chapters"], 79)
            self.assertTrue((destination / "1" / "part01" / "chapter01" / "index.html").is_file())
            self.assertTrue((destination / "1" / "review" / "total-review" / "index.html").is_file())
            self.assertTrue((destination / "2" / "index.html").is_file())
            self.assertTrue((destination / "2" / "part04" / "chapter14" / "index.html").is_file())
            self.assertTrue((destination / "2" / "review" / "total-review" / "index.html").is_file())
            self.assertTrue((destination / "3" / "index.html").is_file())
            overview = destination / "3" / "overview" / "index.html"
            self.assertTrue(overview.is_file())
            self.assertTrue((destination / "3" / "part01" / "chapter01" / "index.html").is_file())
            last_chapter = destination / "3" / "part04" / "chapter13" / "index.html"
            review = destination / "3" / "review" / "total-review" / "index.html"
            self.assertTrue(last_chapter.is_file())
            self.assertTrue(review.is_file())
            home = (destination / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="1/"', home)
            self.assertIn('href="2/"', home)
            self.assertIn('href="3/"', home)
            self.assertEqual(home.count("추가 예정"), 1)
            subject_home = (destination / "3" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="overview/"', subject_home)
            self.assertIn(
                'href="../../3/part01/chapter01/"',
                overview.read_text(encoding="utf-8"),
            )
            self.assertIn(
                'href="../../../3/review/total-review/"',
                last_chapter.read_text(encoding="utf-8"),
            )
            self.assertIn(
                'href="../../../3/part04/chapter13/"',
                review.read_text(encoding="utf-8"),
            )

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

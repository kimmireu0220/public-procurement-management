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

        self.assertEqual(len(chapters), 97)
        self.assertEqual(len(reviews), 3)
        self.assertEqual({lecture.subject for lecture in chapters}, {1, 2, 3, 4})
        self.assertEqual({lecture.subject for lecture in reviews}, {1, 2, 3})
        self.assertEqual({lecture.subject for lecture in overviews}, {1, 3, 4})
        subject1 = [lecture for lecture in chapters if lecture.subject == 1]
        self.assertEqual(sorted({lecture.part for lecture in subject1}), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(
            {part: len([item for item in subject1 if item.part == part]) for part in range(1, 8)},
            {1: 4, 2: 3, 3: 4, 4: 5, 5: 5, 6: 6, 7: 2},
        )
        for lecture in subject1:
            self.assertIn("## ⑤ 다음 Chapter", lecture.body)
            self.assertNotIn("## ⑤ 확인문제", lecture.body)
            self.assertNotIn("### 문제 ", lecture.body)
            self.assertNotIn("### 정답 및 해설", lecture.body)
        subject1_review = next(lecture for lecture in reviews if lecture.subject == 1)
        self.assertNotIn("## 확인문제", subject1_review.body)
        self.assertNotIn("### 문제 ", subject1_review.body)
        self.assertNotIn("### 정답 및 해설", subject1_review.body)
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
        subject4 = [lecture for lecture in chapters if lecture.subject == 4]
        self.assertEqual(sorted({lecture.part for lecture in subject4}), [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            {part: len([item for item in subject4 if item.part == part]) for part in range(1, 7)},
            {1: 3, 2: 3, 3: 3, 4: 4, 5: 3, 6: 2},
        )
        self.assertEqual({lecture.subject_title for lecture in subject4}, {"공공조달 관리실무"})

    def test_build_creates_navigation_and_future_subject_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            meta = build_lecture_pages.build(destination)

            self.assertEqual(meta["total_chapters"], 97)
            self.assertTrue((destination / "1" / "part01" / "chapter01" / "index.html").is_file())
            self.assertTrue((destination / "1" / "review" / "total-review" / "index.html").is_file())
            subject1_overview = destination / "1" / "overview" / "index.html"
            self.assertTrue(subject1_overview.is_file())
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
            overview4 = destination / "4" / "overview" / "index.html"
            first4 = destination / "4" / "part01" / "chapter01" / "index.html"
            prior4 = destination / "4" / "part04" / "chapter04" / "index.html"
            prior_part5_4 = destination / "4" / "part05" / "chapter01" / "index.html"
            latest_prior_part5_4 = destination / "4" / "part05" / "chapter02" / "index.html"
            latest_prior_part5_ch3_4 = destination / "4" / "part05" / "chapter03" / "index.html"
            latest_prior_part6_ch1_4 = destination / "4" / "part06" / "chapter01" / "index.html"
            current4 = destination / "4" / "part06" / "chapter02" / "index.html"
            self.assertTrue(overview4.is_file())
            self.assertTrue(first4.is_file())
            self.assertTrue(prior4.is_file())
            self.assertTrue(prior_part5_4.is_file())
            self.assertTrue(latest_prior_part5_4.is_file())
            self.assertTrue(latest_prior_part5_ch3_4.is_file())
            self.assertTrue(latest_prior_part6_ch1_4.is_file())
            self.assertTrue(current4.is_file())
            subject4_home = (destination / "4" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn('<section class="grid"></section>', subject4_home)
            style = (destination / "assets" / "style.css").read_text(encoding="utf-8")
            self.assertIn("max-height:18rem", style)
            home = (destination / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="1/"', home)
            self.assertIn('href="2/"', home)
            self.assertIn('href="3/"', home)
            self.assertIn('href="4/"', home)
            self.assertEqual(home.count("추가 예정"), 0)
            subject_home = (destination / "3" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="overview/"', subject_home)
            subject1_home = (destination / "1" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="overview/"', subject1_home)
            self.assertIn(
                'href="../../1/part01/chapter01/"',
                subject1_overview.read_text(encoding="utf-8"),
            )
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
            overview_html = overview4.read_text(encoding="utf-8")
            self.assertIn('href="../../assets/style.css"', overview_html)
            self.assertIn('href="../part01/chapter01/"', overview_html)
            self.assertIn('href="../../4/part01/chapter01/"', overview_html)

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

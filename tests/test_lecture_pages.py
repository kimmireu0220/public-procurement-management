from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_lecture_pages  # noqa: E402


class LecturePagesTest(unittest.TestCase):
    def test_sources_have_expected_chapter_structure(self) -> None:
        lectures = build_lecture_pages.load_lectures()
        chapters = [lecture for lecture in lectures if not lecture.is_review]
        reviews = [lecture for lecture in lectures if lecture.is_review]

        self.assertEqual(len(chapters), 29)
        self.assertEqual(len(reviews), 1)
        self.assertEqual({lecture.subject for lecture in chapters}, {1})
        self.assertEqual(sorted({lecture.part for lecture in chapters}), list(range(1, 8)))

    def test_build_creates_navigation_and_future_subject_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            meta = build_lecture_pages.build(destination)

            self.assertEqual(meta["total_chapters"], 29)
            self.assertTrue((destination / "1" / "part01" / "chapter01" / "index.html").is_file())
            self.assertTrue((destination / "1" / "review" / "total-review" / "index.html").is_file())
            home = (destination / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="1/"', home)
            self.assertEqual(home.count("추가 예정"), 3)


if __name__ == "__main__":
    unittest.main()

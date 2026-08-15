from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import publish_cbt_pages  # noqa: E402
from cbt.profiles import CbtProfile  # noqa: E402
from publish_cbt_pages import render_full_round_list  # noqa: E402


class FakeFullProfile:
    id = "full"

    def __init__(self, source_root: Path, docs_root: Path) -> None:
        self.source_root = source_root
        self.docs_root = docs_root

    def round_dir(self, round_no: int) -> Path:
        return self.source_root / f"{round_no}회차"

    def problem_md(self, round_no: int) -> Path:
        return self.round_dir(round_no) / "필기_모의_문제.md"

    def docs_index(self) -> Path:
        return self.docs_root / "index.html"

    def docs_meta(self) -> Path:
        return self.docs_root / "cbt-meta.json"

    def source_label(self, round_no: int) -> str:
        return f"mock_exam/필기/통합/{round_no}회차/index.html"


class PublishCbtPagesTest(unittest.TestCase):
    def test_full_round_list_links_every_round(self) -> None:
        rendered = render_full_round_list([1, 2, 3])

        for round_no in (1, 2, 3):
            self.assertIn(f'href="mock/{round_no}회차/"', rendered)
            self.assertIn(f"<strong>{round_no}회차</strong>", rendered)
        self.assertIn("공공조달관리사 학습센터", rendered)
        self.assertIn('href="1과목/"', rendered)
        self.assertIn('href="study/1과목-part1-exam/"', rendered)
        self.assertIn('href="lecture/1/part01/chapter01/"', rendered)
        self.assertIn('href="lecture/1/review/total-review/"', rendered)
        self.assertIn('href="lecture/2/part01/chapter01/"', rendered)
        self.assertIn('href="lecture/2/part04/chapter14/"', rendered)
        self.assertIn('href="lecture/2/review/total-review/"', rendered)
        self.assertIn("2과목 총정리", rendered)
        self.assertIn('href="lecture/3/part01/chapter01/"', rendered)
        self.assertIn('href="lecture/3/part04/chapter13/"', rendered)
        self.assertIn('href="lecture/3/review/total-review/"', rendered)
        self.assertIn("3과목 총정리", rendered)
        self.assertEqual(rendered.count("<em>최신</em>"), 1)

    def test_publishing_third_round_keeps_all_rounds_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "output"
            docs_root = root / "docs"
            docs_root.mkdir()
            profile = FakeFullProfile(source_root, docs_root)
            for round_no in (1, 2, 3):
                round_dir = profile.round_dir(round_no)
                round_dir.mkdir(parents=True)
                (round_dir / "index.html").write_text(f"round {round_no}", encoding="utf-8")
                (round_dir / "필기_모의_문제.md").write_text("problem", encoding="utf-8")

            with patch.object(publish_cbt_pages, "DOCS", docs_root):
                selected = publish_cbt_pages.publish_profile(cast(CbtProfile, profile), 3)

            self.assertEqual(selected, 3)
            landing = (docs_root / "index.html").read_text(encoding="utf-8")
            for round_no in (1, 2, 3):
                self.assertIn(f"mock/{round_no}회차/", landing)
                self.assertEqual(
                    (docs_root / "mock" / f"{round_no}회차" / "index.html").read_text(
                        encoding="utf-8"
                    ),
                    f"round {round_no}",
                )


if __name__ == "__main__":
    unittest.main()

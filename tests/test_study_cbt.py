from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_study_cbt  # noqa: E402


class StudyGuideTest(unittest.TestCase):
    def test_build_publishes_subject_cbt_landing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "study"
            build_study_cbt.build(destination)

            actual_files = {
                path.relative_to(destination)
                for path in destination.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual_files, {Path("index.html")})

            landing = (destination / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="../1과목/"', landing)
            self.assertIn("총 1,395문항", landing)
            self.assertNotIn("const QUESTIONS", landing)
            self.assertNotIn("problem_book_final", landing)
            self.assertNotIn("agent_extract", landing)

    def test_build_is_deterministic_and_tree_comparison_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            expected = temp_root / "expected"
            actual = temp_root / "actual"
            build_study_cbt.build(expected)
            build_study_cbt.build(actual)

            self.assertEqual(build_study_cbt.compare_trees(expected, actual), [])
            (actual / "index.html").write_text("stale", encoding="utf-8")
            self.assertIn(
                "생성 결과 불일치: index.html",
                build_study_cbt.compare_trees(expected, actual),
            )
            (actual / "unexpected.txt").write_text("extra", encoding="utf-8")
            self.assertIn(
                "불필요 공개 파일: unexpected.txt",
                build_study_cbt.compare_trees(expected, actual),
            )


if __name__ == "__main__":
    unittest.main()

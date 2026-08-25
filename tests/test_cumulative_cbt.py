from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_cumulative_cbt  # noqa: E402
import site_portal  # noqa: E402


class CumulativeCbtTest(unittest.TestCase):
    def test_builds_all_subject_and_wrong_answer_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "docs"
            counts = build_cumulative_cbt.build(destination)

            self.assertEqual(counts, {1: 670, 2: 335, 3: 390, 4: 1244})
            for subject in range(1, 5):
                self.assertTrue((destination / f"{subject}과목" / "index.html").is_file())
                self.assertTrue((destination / "오답" / f"{subject}과목" / "index.html").is_file())
                self.assertTrue((destination / "assets" / f"subject{subject}-bank.js").is_file())

    def test_written_bank_has_model_answer_for_every_question(self) -> None:
        questions = build_cumulative_cbt.load_written_questions_legacy()
        answers = build_cumulative_cbt.load_written_answers(questions)

        self.assertEqual(len(questions), 1244)
        self.assertEqual(len(answers), 1244)
        self.assertTrue(all(answers[question["id"]].strip() for question in questions))

    def test_client_supports_immediate_grading_and_manual_written_judgement(self) -> None:
        script = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")
        self.assertIn("selected === correct", script)
        self.assertIn('data-judge="correct"', script)
        self.assertIn('data-judge="wrong"', script)
        self.assertIn("wrong.delete(question.id)", script)
        self.assertIn("localStorage.removeItem(wrongKey)", script)

    def test_portal_links_four_full_and_four_wrong_cbts(self) -> None:
        portal = site_portal.render_portal([])
        for subject in range(1, 5):
            self.assertIn(f'href="{subject}과목/"', portal)
            self.assertIn(f'href="오답/{subject}과목/"', portal)
        self.assertNotIn("None</div>", portal)


if __name__ == "__main__":
    unittest.main()

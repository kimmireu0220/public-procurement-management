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
        objective = (ROOT / "docs" / "assets" / "objective-cumulative-cbt.js").read_text(encoding="utf-8")
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")
        self.assertIn("selected === correct", objective)
        self.assertIn("wrong.delete(question.id)", objective)
        self.assertIn("updateWrongCount()", objective)
        self.assertIn("window.setTimeout(() => finishQuestion(true), 350)", objective)
        self.assertIn("(isCorrect ? '' :", objective)
        self.assertIn("localStorage.removeItem(wrongKey)", objective)
        self.assertIn('data-judge="correct"', written)
        self.assertIn('data-judge="wrong"', written)

    def test_objective_and_written_clients_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "docs"
            build_cumulative_cbt.build(destination)
            for subject in (1, 2, 3):
                page = (destination / f"{subject}과목" / "index.html").read_text(encoding="utf-8")
                self.assertIn("objective-cumulative-cbt.js", page)
            written_page = (destination / "4과목" / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="../assets/cumulative-cbt.js"', written_page)
            self.assertNotIn("objective-cumulative-cbt.js", written_page)
            for page_path in destination.glob("*과목/index.html"):
                self.assertNotIn("학습센터 홈", page_path.read_text(encoding="utf-8"))
            for page_path in (destination / "오답").glob("*과목/index.html"):
                self.assertNotIn("학습센터 홈", page_path.read_text(encoding="utf-8"))

    def test_portal_links_four_full_and_four_wrong_cbts(self) -> None:
        portal = site_portal.render_portal([])
        for subject in range(1, 5):
            self.assertIn(f'href="{subject}과목/"', portal)
            self.assertIn(f'href="오답/{subject}과목/"', portal)
        self.assertNotIn("None</div>", portal)
        self.assertNotIn("오답 전체 초기화", portal)
        self.assertNotIn("reset-wrong-all", portal)

    def test_wrong_reset_is_scoped_to_each_subject_page(self) -> None:
        for name in ("objective-cumulative-cbt.js", "cumulative-cbt.js"):
            script = (ROOT / "docs" / "assets" / name).read_text(encoding="utf-8")
            self.assertIn("${config.subject}과목 오답 초기화", script)
            self.assertIn("localStorage.removeItem(wrongKey)", script)
            self.assertNotIn("[1,2,3,4]", script)


if __name__ == "__main__":
    unittest.main()

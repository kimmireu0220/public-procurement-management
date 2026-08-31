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
        self.assertNotIn("window.setTimeout", objective)
        self.assertIn('role="status"', objective)
        self.assertIn('data-action="continue"', objective)
        self.assertIn("focusQuestion()", objective)
        self.assertIn("safeRemove(wrongKey)", objective)
        self.assertIn('data-judge="correct"', written)
        self.assertIn('data-judge="wrong"', written)

    def test_written_answer_enter_reveals_and_shift_enter_adds_a_line(self) -> None:
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")

        self.assertIn("event.key !== 'Enter' || event.shiftKey", written)
        self.assertNotIn("event.isComposing", written)
        self.assertNotIn("event.keyCode === 229", written)
        self.assertIn("event.preventDefault()", written)
        self.assertIn("revealAnswer()", written)
        self.assertNotIn("핵심어와 판단 근거를 적은 뒤", written)

    def test_model_answer_is_inline_without_manual_judgement_prompt(self) -> None:
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")
        styles = (ROOT / "docs" / "assets" / "cumulative-cbt.css").read_text(encoding="utf-8")

        self.assertIn('>\ubaa8\ubc94\ub2f5안:</strong> ${escapeHtml(question.answer)}', written)
        self.assertNotIn("내 답안이 핵심 내용을 충족했는지 직접 판정하세요.", written)
        self.assertNotIn("<strong>내 답안</strong>", written)
        self.assertIn('aria-label="답안 입력"', written)
        self.assertNotIn("border-left: 5px solid var(--blue)", styles)
        self.assertIn("min-height: 120px", styles)

    def test_written_judgement_supports_arrow_navigation_and_enter_activation(self) -> None:
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")

        self.assertIn("app.querySelector('[data-judge=\"correct\"]').focus", written)
        self.assertIn("event.key !== 'ArrowLeft' && event.key !== 'ArrowRight'", written)
        self.assertIn("judgeButtons.indexOf(document.activeElement)", written)
        self.assertIn("judgeButtons[(current + direction + judgeButtons.length) % judgeButtons.length].focus()", written)
        self.assertIn("button.addEventListener('click'", written)
        self.assertIn("app.querySelector('#written-answer')?.focus({preventScroll:true})", written)

    def test_objective_and_written_clients_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "docs"
            build_cumulative_cbt.build(destination)
            for subject in (1, 2, 3):
                page = (destination / f"{subject}과목" / "index.html").read_text(encoding="utf-8")
                self.assertIn("objective-cumulative-cbt.js?v=", page)
            written_page = (destination / "4과목" / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="../assets/cumulative-cbt.js?v=', written_page)
            self.assertNotIn("objective-cumulative-cbt.js", written_page)
            for page_path in destination.glob("*과목/index.html"):
                page = page_path.read_text(encoding="utf-8")
                self.assertNotIn("학습센터 홈", page)
                self.assertIn("← 학습센터", page)
            for page_path in (destination / "오답").glob("*과목/index.html"):
                page = page_path.read_text(encoding="utf-8")
                self.assertNotIn("학습센터 홈", page)
                self.assertIn("← 학습센터", page)

    def test_toolbar_uses_editable_current_progress_for_direct_navigation(self) -> None:
        for name in ("objective-cumulative-cbt.js", "cumulative-cbt.js"):
            script = (ROOT / "docs" / "assets" / name).read_text(encoding="utf-8")

            self.assertNotIn('class="jump-label"', script)
            self.assertIn('<strong><input class="progress-jump"', script)
            self.assertIn("app.querySelector('.progress-jump')", script)
            self.assertIn("jump?.addEventListener('change', jumpToQuestion)", script)
            self.assertIn("event.key !== 'Enter'", script)

    def test_portal_links_four_full_and_four_wrong_cbts(self) -> None:
        portal = site_portal.render_portal()
        for subject in range(1, 5):
            self.assertIn(f'href="{subject}과목/"', portal)
            self.assertIn(f'href="오답/{subject}과목/"', portal)
        self.assertNotIn("None</div>", portal)
        self.assertNotIn("오답 전체 초기화", portal)
        self.assertNotIn("reset-wrong-all", portal)

    def test_published_portal_matches_renderer(self) -> None:
        published = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

        self.assertEqual(published, site_portal.render_portal())

    def test_wrong_reset_is_scoped_to_each_subject_page(self) -> None:
        for name in ("objective-cumulative-cbt.js", "cumulative-cbt.js"):
            script = (ROOT / "docs" / "assets" / name).read_text(encoding="utf-8")
            self.assertIn("${config.subject}과목 오답 초기화", script)
            self.assertIn("safeRemove(wrongKey)", script)
            self.assertNotIn("[1,2,3,4]", script)


if __name__ == "__main__":
    unittest.main()

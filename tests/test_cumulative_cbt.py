from __future__ import annotations

import sys
import json
import re
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_cumulative_cbt  # noqa: E402
import number_memory  # noqa: E402
import site_portal  # noqa: E402
import import_photo_questions  # noqa: E402


class CumulativeCbtTest(unittest.TestCase):
    def test_subject3_restored_choice_order_matches_printed_answers(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject3.json").read_text(encoding="utf-8"))
        chapter = {int(q["source"].get("verifiedPrintedNumber", q["source"]["answerPrintedNumber"])): q
                   for q in questions if q["group"] == "Part 4 · Chapter 2"}
        for number, answer, text in ((19, "2", "지역참여비율"), (23, "3", "자재 및 인력"),
                                     (26, "4", "80.495%"), (27, "2", "접근성")):
            question = chapter[number]
            self.assertEqual(question["answer"], answer)
            self.assertIn(text, question["choices"][int(answer) - 1]["text"])
            self.assertTrue(question["source"]["answerPhoto"])

    def test_subject2_manually_recovered_chapters_are_complete(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject2.json").read_text(encoding="utf-8"))
        totals = {(1, 1): 31, (1, 2): 30, (1, 4): 24, (2, 1): 28, (2, 2): 27, (2, 3): 21,
                  (2, 4): 20, (2, 5): 26, (3, 1): 16, (3, 2): 25, (3, 3): 26, (3, 4): 38, (3, 5): 18}
        for (part, chapter), total in totals.items():
            chapter_questions = [q for q in questions if q["group"] == f"Part {part} · Chapter {chapter}"]
            numbers = [int(q["source"].get("verifiedPrintedNumber", q["source"]["answerPrintedNumber"])) for q in chapter_questions]
            self.assertEqual(sorted(numbers), list(range(1, total + 1)))
            self.assertTrue(all(q["answer"] in ("1", "2", "3", "4") for q in chapter_questions))

    def test_subject1_verified_answers_have_evidence(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject1.json").read_text(encoding="utf-8"))
        for number, answer in ((176, "1"), (181, "3"), (221, "2"), (236, "2"), (261, "3"), (282, "1"), (286, "3"), (352, "1")):
            question = questions[number - 1]
            self.assertEqual(question["answer"], answer)
            self.assertEqual(question["source"]["answerResolution"]["answer"], answer)

    def test_published_photo_subjects_are_all_automatically_gradable(self) -> None:
        for subject in (1, 2, 3):
            questions = json.loads((ROOT / f"output/new_question_bank/subject{subject}.json").read_text(encoding="utf-8"))
            self.assertTrue(questions)
            self.assertTrue(all(q["answer"] in {choice["key"] for choice in q["choices"]} for q in questions))

    def test_mock2_rephotographed_available_questions_are_complete(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/mock2.json").read_text(encoding="utf-8"))
        printed = {
            int(question["source"].get("verifiedPrintedNumber", question["source"].get("answerPrintedNumber", question["source"]["printedNumberOcr"]))): question
            for question in questions
        }
        self.assertEqual(sorted(printed), [2, *range(4, 81)])
        for number, answer in ((4, "4"), (6, "1"), (77, "4"), (78, "2"), (79, "4"), (80, "4")):
            self.assertEqual(printed[number]["answer"], answer)
        self.assertTrue(printed[48]["choices"][1]["text"].startswith("가격평가"))
        self.assertTrue(printed[70]["choices"][2]["text"].startswith("용역"))
        self.assertTrue(printed[78]["choices"][2]["text"].endswith("있다."))

    def test_rephotographed_subject2_first_chapters_are_complete(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject2.json").read_text(encoding="utf-8"))
        for chapter, total in ((1, 31), (2, 30)):
            numbers = [
                int(question["source"].get("verifiedPrintedNumber", question["source"].get("answerPrintedNumber", question["source"]["printedNumberOcr"])))
                for question in questions if question["group"] == f"Part 1 · Chapter {chapter}"
            ]
            self.assertEqual(sorted(numbers), list(range(1, total + 1)))

    def test_rephotographed_subject2_final_chapter_is_complete(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject2.json").read_text(encoding="utf-8"))
        chapter = {
            int(question["source"].get("verifiedPrintedNumber", question["source"].get("answerPrintedNumber", question["source"]["printedNumberOcr"]))): question
            for question in questions if question["group"] == "Part 3 · Chapter 5"
        }
        self.assertEqual(sorted(chapter), list(range(1, 19)))
        self.assertEqual(chapter[17]["answer"], "2")
        self.assertEqual(chapter[17]["choices"][1]["text"], "구체적 문제 제시")
        self.assertEqual(chapter[18]["answer"], "3")
        self.assertIn("단순 의견", chapter[18]["choices"][2]["text"])

    def test_verified_two_column_choice_order_matches_answer_keys(self) -> None:
        subject1 = json.loads((ROOT / "output/new_question_bank/subject1.json").read_text(encoding="utf-8"))
        subject2 = json.loads((ROOT / "output/new_question_bank/subject2.json").read_text(encoding="utf-8"))
        for questions, number, expected in ((subject1, 37, "소액구매"), (subject2, 9, "우선순위 설정")):
            question = questions[number - 1]
            selected = next(choice for choice in question["choices"] if choice["key"] == question["answer"])
            self.assertEqual(selected["text"], expected)

    def test_conflicting_printed_answer_does_not_reorder_original_choices(self) -> None:
        questions = json.loads((ROOT / "output/new_question_bank/subject1.json").read_text(encoding="utf-8"))
        question = questions[71]
        self.assertEqual(question["source"]["answerPrintedNumber"], 22)
        self.assertEqual([choice["text"] for choice in question["choices"]], ["품명신설 요청", "계약체결", "대금지급", "납품검사"])
        self.assertEqual(question["answer"], "1")
        self.assertEqual(question["source"]["printedAnswer"], "2")
        self.assertTrue(question["source"]["answerConflict"])
        resolution = question["source"]["answerResolution"]
        self.assertEqual(resolution["answer"], question["answer"])
        self.assertTrue(resolution["verifiedAt"])
        self.assertTrue(any("law.go.kr" in source.get("url", "") for source in resolution["sources"]))

    def test_photo_banks_have_stable_identifiers_and_source_mapping(self) -> None:
        for path in (ROOT / "output" / "new_question_bank").glob("*.json"):
            questions = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len({q["id"] for q in questions}), len(questions), path.name)
            self.assertEqual([q["no"] for q in questions], list(range(1, len(questions) + 1)), path.name)
            for question in questions:
                self.assertEqual([choice["key"] for choice in question["choices"]], ["1", "2", "3", "4"])
                self.assertIn(question["answer"], (None, "1", "2", "3", "4"))
                if question["answer"] is not None:
                    source = question["source"]
                    if source.get("answerPhoto"):
                        self.assertTrue(source["answerVerifiedAt"])
                    else:
                        resolution = source["answerResolution"]
                        self.assertEqual(resolution["answer"], question["answer"])
                        self.assertTrue(resolution["nature"])
                        self.assertTrue(resolution["reason"])
                        self.assertTrue(resolution["verifiedAt"])
                        self.assertTrue(resolution["sources"])
                        self.assertTrue(all(item.get("url") or item.get("path") for item in resolution["sources"]))
                self.assertTrue(question["source"]["photo"].endswith(".jpg"))
                self.assertTrue(question["source"]["permission"])

    def test_verified_photo_questions_are_not_duplicated_by_rephotographing(self) -> None:
        for path in (ROOT / "output" / "new_question_bank").glob("*.json"):
            questions = json.loads(path.read_text(encoding="utf-8"))
            identities = [
                (question["group"], int(question["source"].get("verifiedPrintedNumber", question["source"].get("answerPrintedNumber", question["source"]["printedNumberOcr"]))))
                for question in questions
            ]
            self.assertEqual(len(identities), len(set(identities)), path.name)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for client runtime test")
    def test_objective_client_unknown_answer_runtime(self) -> None:
        subprocess.run(["node", "tests/objective_cbt_runtime.cjs"], cwd=ROOT, check=True, capture_output=True, text=True)

    def test_photo_import_requires_complete_boundary_and_keeps_unknown_answer(self) -> None:
        draft = {"photo": "page_0001.jpg", "column": 1, "printed_no_ocr": "03", "group": "단원", "raw_question_text": "문제는?\n① 하나\n② 둘\n③ 셋\n④ 넷"}
        questions, rejected = import_photo_questions.extract_questions([draft, draft], "book1", 1)
        self.assertEqual(len(questions), 1)
        self.assertEqual(rejected, [])
        self.assertIsNone(questions[0]["answer"])
        self.assertEqual(questions[0]["source"]["printedNumberOcr"], "03")
        broken = dict(draft, raw_question_text="문제는?\n① 하나\n② 둘\n③ 셋")
        self.assertEqual(len(import_photo_questions.extract_questions([broken], "book1", 1)[1]), 1)
        two_column = dict(draft, raw_question_text="문제는?\n① 하나\n③ 셋\n② 둘\n④ 넷")
        reordered = import_photo_questions.extract_questions([two_column], "book1", 1)[0][0]
        self.assertEqual([choice["text"] for choice in reordered["choices"]], ["하나", "둘", "셋", "넷"])
        duplicate_label = dict(draft, raw_question_text="문제는?\n① 하나\n② 둘\n③ 셋\n① 넷")
        self.assertEqual(len(import_photo_questions.extract_questions([duplicate_label], "book1", 1)[1]), 1)

    def test_mock_exams_keep_independent_storage_and_resolve_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "docs"
            build_cumulative_cbt.build(destination)
            for exam in (1, 2):
                for mode in ("all", "wrong"):
                    directory = destination / "new-bank" / "모의고사" / f"{exam}회"
                    if mode == "wrong":
                        directory /= "오답"
                    page = (directory / "index.html").read_text(encoding="utf-8")
                    match = re.search(r"window.CBT_CONFIG=(.*?);</script>", page)
                    config = json.loads(match.group(1))  # type: ignore[union-attr]
                    self.assertEqual(config["storageNamespace"], f"mock{exam}")
                    self.assertEqual(config["exam"], exam)
                    for url in re.findall(r'(?:src|href)="([^"#]+)"', page):
                        self.assertTrue((directory / url.split("?", 1)[0]).exists(), url)

    def test_new_bank_has_independent_subject_and_wrong_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "docs"
            build_cumulative_cbt.build(destination)
            portal = site_portal.render_portal()
            for subject in range(1, 5):
                bank = destination / "assets" / f"new-bank-subject{subject}-bank.js"
                source = json.loads((ROOT / "output" / "new_question_bank" / f"subject{subject}.json").read_text(encoding="utf-8"))
                self.assertEqual(json.loads(bank.read_text(encoding="utf-8").removeprefix("window.CBT_BANK=").rstrip(";\n")), source)
                for mode in ("all", "wrong"):
                    directory = destination / "new-bank"
                    if mode == "wrong":
                        directory /= "오답"
                    directory /= f"{subject}과목"
                    page = (directory / "index.html").read_text(encoding="utf-8")
                    match = re.search(r"window.CBT_CONFIG=(.*?);</script>", page)
                    self.assertIsNotNone(match)
                    config = json.loads(match.group(1))  # type: ignore[union-attr]
                    self.assertEqual(config["storageNamespace"], "new-bank")
                    self.assertEqual(config["mode"], mode)
                    self.assertEqual(config["subject"], subject)
                    self.assertTrue((directory / config["allUrl"] / "index.html").is_file())
                    self.assertIn(f'href="{directory.relative_to(destination)}/"', portal)
                    for url in re.findall(r'(?:src|href)="([^"#]+)"', page):
                        target = url.split("?", 1)[0]
                        self.assertTrue((directory / target).exists(), target)

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

    def test_corrected_public_contract_question_has_prompt_and_four_clean_choices(self) -> None:
        questions = build_cumulative_cbt.load_objective_questions(1)
        question = next(item for item in questions if item["id"] == "1:6:2:exam:1")

        self.assertIn("㉠ 전형계약", question["stem"])
        self.assertIn("㉤ 유상계약", question["stem"])
        self.assertEqual([choice["text"] for choice in question["choices"]], [
            "㉠, ㉣, ㉥, ㉧",
            "㉠, ㉢, ㉤, ㉦",
            "㉡, ㉢, ㉤, ㉦",
            "㉠, ㉢, ㉥, ㉧",
        ])
        self.assertEqual(question["answer"], "2")

    def test_client_supports_immediate_grading_and_manual_written_judgement(self) -> None:
        objective = (ROOT / "docs" / "assets" / "objective-cumulative-cbt.js").read_text(encoding="utf-8")
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")
        self.assertIn("selected === correct", objective)
        self.assertIn("wrong.delete(question.id)", objective)
        self.assertIn("updateWrongCount()", objective)
        self.assertNotIn("window.setTimeout", objective)
        self.assertIn('role="status"', objective)
        self.assertIn('data-action="continue"', objective)
        self.assertNotIn("오답입니다. 정답은", objective)
        self.assertNotIn("정답입니다.", objective)
        self.assertIn("focusQuestion()", objective)
        self.assertIn("safeRemove(wrongKey)", objective)
        self.assertIn('data-judge="correct"', written)
        self.assertIn('data-judge="wrong"', written)
        self.assertIn('aria-label="맞혔어요">O</button>', written)
        self.assertIn('aria-label="틀렸어요">X</button>', written)

    def test_written_answer_enter_reveals_and_shift_enter_adds_a_line(self) -> None:
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")

        self.assertIn("event.key !== 'Enter' || event.shiftKey", written)
        self.assertNotIn("event.isComposing", written)
        self.assertNotIn("event.keyCode === 229", written)
        self.assertNotIn("if (!answer.value.trim())", written)
        self.assertIn("event.preventDefault()", written)
        self.assertIn("revealAnswer({focusJudge:false})", written)
        self.assertIn("'#model-answer-title'", written)
        self.assertIn("app.querySelector('.answer-actions').classList.add('hidden')", written)
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
        self.assertIn("font-size: 1.1rem", styles)

    def test_written_judgement_supports_arrow_navigation_and_enter_activation(self) -> None:
        written = (ROOT / "docs" / "assets" / "cumulative-cbt.js").read_text(encoding="utf-8")

        self.assertIn("focusJudge ? '[data-judge=\"correct\"]' : '#model-answer-title'", written)
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

    def test_objective_cbt_accepts_direct_question_links(self) -> None:
        script = (ROOT / "docs" / "assets" / "objective-cumulative-cbt.js").read_text(encoding="utf-8")

        self.assertIn("new URLSearchParams(window.location.search).get('q')", script)
        self.assertIn("requested >= 1 && requested <= bank.length", script)

    def test_portal_links_four_full_and_four_wrong_cbts(self) -> None:
        portal = site_portal.render_portal()
        for subject in range(1, 5):
            self.assertIn(f'href="{subject}과목/"', portal)
            self.assertIn(f'href="오답/{subject}과목/"', portal)
        self.assertNotIn("None</div>", portal)
        self.assertNotIn("오답 전체 초기화", portal)
        self.assertNotIn("reset-wrong-all", portal)

    def test_portal_links_three_number_memory_guides(self) -> None:
        portal = site_portal.render_portal()
        for subject, title, filename in site_portal.NUMBER_MEMORY_GUIDES:
            self.assertIn(f'href="학습_숫자암기/{subject}과목/"', portal)
            self.assertTrue((ROOT / "docs" / "학습_숫자암기" / filename).is_file())
            published = ROOT / "docs" / "학습_숫자암기" / f"{subject}과목" / "index.html"
            self.assertEqual(
                published.read_text(encoding="utf-8"),
                number_memory.render_number_memory_guide(
                    subject,
                    title,
                    ROOT / "docs" / "학습_숫자암기" / filename,
                ),
            )
            self.assertIn(f'href="../../{subject}과목/?q=', published.read_text(encoding="utf-8"))

    def test_published_portal_matches_renderer(self) -> None:
        published = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

        self.assertEqual(published, site_portal.render_portal())

    def test_wrong_reset_is_scoped_to_each_subject_page(self) -> None:
        for name in ("objective-cumulative-cbt.js", "cumulative-cbt.js"):
            script = (ROOT / "docs" / "assets" / name).read_text(encoding="utf-8")
            label = "${escapeHtml(subjectLabel)}" if name == "objective-cumulative-cbt.js" else "${config.subject}과목"
            self.assertIn(f"{label} 오답 초기화", script)
            self.assertIn("safeRemove(wrongKey)", script)
            self.assertNotIn("[1,2,3,4]", script)


if __name__ == "__main__":
    unittest.main()

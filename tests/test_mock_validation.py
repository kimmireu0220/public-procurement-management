from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from cbt.builder import OUTPUT_HTML_NAMES, inline_json, render_html  # noqa: E402
from cbt.parser import parse_questions  # noqa: E402
from cbt.profiles import FULL_MOCK  # noqa: E402
from cbt.validation import (  # noqa: E402
    validate_all,
    validate_first_lap_stable_id_reuse,
    validate_practical_round,
    validate_round,
    validate_written_bank_inventory,
)
from question_bank import QuestionBankParseError  # noqa: E402
import subject1.bank as subject1_bank  # noqa: E402
import subject2.bank as subject2_bank  # noqa: E402
import subject3.bank as subject3_bank  # noqa: E402


class MockValidationTest(unittest.TestCase):
    BANK_MODULES = (
        (1, subject1_bank),
        (2, subject2_bank),
        (3, subject3_bank),
    )

    def load_bank_text(self, module: ModuleType, path: Path, text: str) -> dict[str, dict]:
        path.write_text(text, encoding="utf-8")
        module.load_questions_index.cache_clear()
        try:
            with patch.object(module, "PROBLEM_MD", path):
                return module.load_questions_index()
        finally:
            module.load_questions_index.cache_clear()

    def make_practical_round(self, directory: Path, id_template: str = "4:1:1:essay:{number}") -> None:
        problems = ["# 실기 문제\n"]
        answers = ["# 실기 정답\n"]
        for number in range(1, 21):
            problems.append(
                f"### {number}. 테스트 문제\n"
                "<!-- source: Part 1/page_0001.jpg -->\n"
                f"<!-- id: {id_template.format(number=number)} -->\n"
            )
            answers.append(f"### {number}.\n\n테스트 정답\n")
        (directory / "실기_모의_문제.md").write_text("\n".join(problems), encoding="utf-8")
        (directory / "실기_모의_정답.md").write_text("\n".join(answers), encoding="utf-8")

    def write_manifest(self, path: Path, stable_id: str, *, lap: int | None = None) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "round": 1,
            "total": 1,
            "items": [{"exam_no": 1, "stable_id": stable_id, "answer": "①"}],
        }
        if lap is not None:
            manifest["lap"] = lap
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return path

    def make_round(self, directory: Path, *, source: str = "Part 1/page_0001.jpg") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        problem = """# 문제

## 1과목 테스트 (1~1)
1. 테스트 문항은?
   ① 하나
   ② 둘
   ③ 셋
   ④ 넷
<!-- source: SOURCE -->
<!-- id: 1:1:1:exam:1 -->
""".replace("SOURCE", source)
        (directory / "필기_모의_문제.md").write_text(problem, encoding="utf-8")
        (directory / "필기_모의_정답.md").write_text(
            "# 정답\n\n1. ① — (Part 1/page_0001.jpg)\n", encoding="utf-8"
        )
        manifest = {
            "round": 1,
            "total": 1,
            "items": [{"exam_no": 1, "stable_id": "1:1:1:exam:1", "answer": "①"}],
        }
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        for name in OUTPUT_HTML_NAMES:
            (directory / name).write_text("ok", encoding="utf-8")
        return manifest_path

    def make_full_profile_round(self, root: Path) -> Path:
        directory = root / "output" / "mock_exam" / "필기" / "통합" / "1회차"
        directory.mkdir(parents=True)
        problem_parts = ["# 문제\n"]
        answer_parts = ["# 정답\n"]
        items = []
        ranges = ((1, 1, 30), (2, 31, 50), (3, 51, 80))
        for subject, start, end in ranges:
            problem_parts.append(f"\n## {subject}과목 테스트 ({start}~{end})\n")
            for exam_no in range(start, end + 1):
                stable_id = f"{subject}:1:1:exam:{exam_no}"
                problem_parts.append(
                    f"{exam_no}. 테스트 문항 {exam_no}은?\n"
                    "   ① 하나\n"
                    "   ② 둘\n"
                    "   ③ 셋\n"
                    "   ④ 넷\n"
                    "<!-- source: Part 1/page_0001.jpg -->\n"
                    f"<!-- id: {stable_id} -->\n"
                )
                answer_parts.append(f"{exam_no}. ① — (Part 1/page_0001.jpg)\n")
                items.append({"exam_no": exam_no, "stable_id": stable_id, "answer": "①"})

        problem = "".join(problem_parts)
        (directory / "필기_모의_문제.md").write_text(problem, encoding="utf-8")
        (directory / "필기_모의_정답.md").write_text(
            "".join(answer_parts), encoding="utf-8"
        )
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(
            json.dumps({"round": 1, "total": 80, "items": items}, ensure_ascii=False),
            encoding="utf-8",
        )
        html = render_html(parse_questions(problem), 1, FULL_MOCK)
        for name in OUTPUT_HTML_NAMES:
            (directory / name).write_text(html, encoding="utf-8")
        return manifest_path

    def test_unknown_profile_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp) / "1회차")
            messages = [issue.message for issue in validate_round(path)]
            self.assertTrue(any("지원하지 않는 필기 프로필 경로" in message for message in messages))

    def test_valid_full_profile_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_full_profile_round(Path(tmp))
            self.assertEqual(validate_round(path), [])

    def test_empty_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp) / "1회차", source="")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("source 주석 누락 또는 빈 값", messages)

    def test_source_part_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp) / "1회차", source="Part 2/page_0001.jpg")
            messages = [issue.message for issue in validate_round(path)]
            self.assertTrue(any("stable_id Part와 source Part 불일치" in message for message in messages))

    def test_non_string_stable_id_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp) / "1회차")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["items"][0]["stable_id"] = {"invalid": True}
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            messages = [issue.message for issue in validate_round(path, ROOT)]
            self.assertIn("stable_id 형식 오류 또는 누락", messages)
            self.assertIn("stable_id 형식 오류로 source 검증 불가", messages)

    def test_manifest_answer_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "1회차"
            path = self.make_round(directory)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["items"][0]["answer"] = "②"
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("정답지와 manifest 정답 불일치", messages)

    def test_profile_question_count_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_full_profile_round(Path(tmp))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["items"] = manifest["items"][:1]
            manifest["total"] = 1
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("full 프로필은 80문항이어야 함", messages)

    def test_manifest_round_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_full_profile_round(Path(tmp))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["round"] = 123
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            messages = [issue.message for issue in validate_round(path)]
            self.assertTrue(any("디렉터리 회차=1 불일치" in message for message in messages))

    def test_stale_html_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_full_profile_round(Path(tmp))
            (path.parent / "index.html").write_text("stale", encoding="utf-8")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("CBT HTML이 문제지 또는 현재 빌드 자산과 불일치", messages)

    def test_all_written_bank_questions_have_answers(self) -> None:
        self.assertEqual(validate_written_bank_inventory(ROOT), [])

    def test_bank_loaders_reject_silent_candidate_omissions(self) -> None:
        cases = {
            "missing-source": (
                "1. source가 없는 후보 문항은?\n"
                "   ① 하나\n   ② 둘\n   ③ 셋\n   ④ 넷\n",
                "source 주석 누락",
            ),
            "incomplete-choices": (
                "1. 선지가 부족한 후보 문항은?\n"
                "   ① 하나\n   ② 둘\n   ③ 셋\n"
                "<!-- source: Part 1/page_0001.jpg -->\n",
                "선지는 ①②③④ 각 1개여야 함",
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for subject, module in self.BANK_MODULES:
                for case, (question, expected) in cases.items():
                    with self.subTest(subject=subject, case=case):
                        text = (
                            "## Part 1 문제집\n\n"
                            "### CHAPTER 01 테스트 — 단원별 출제예상문제\n\n"
                            f"{question}"
                        )
                        path = Path(tmp) / f"subject{subject}-{case}.md"
                        with self.assertRaises(QuestionBankParseError) as caught:
                            self.load_bank_text(module, path, text)
                        self.assertIn(expected, str(caught.exception))

    def test_bank_loaders_reject_duplicate_stable_ids(self) -> None:
        question = (
            "1. 첫 번째 문항은?\n"
            "   ① 하나\n   ② 둘\n   ③ 셋\n   ④ 넷\n"
            "<!-- source: Part 1/page_0001.jpg -->\n\n"
            "1. 같은 번호의 두 번째 문항은?\n"
            "   ① 하나\n   ② 둘\n   ③ 셋\n   ④ 넷\n"
            "<!-- source: Part 1/page_0002.jpg -->\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            for subject, module in self.BANK_MODULES:
                with self.subTest(subject=subject):
                    text = (
                        "## Part 1 문제집\n\n"
                        "### CHAPTER 01 테스트 — 단원별 출제예상문제\n\n"
                        f"{question}"
                    )
                    path = Path(tmp) / f"subject{subject}-duplicate.md"
                    with self.assertRaises(QuestionBankParseError) as caught:
                        self.load_bank_text(module, path, text)
                    self.assertIn("duplicate stable_id", str(caught.exception))

    def test_bank_parser_ignores_short_answer_and_binary_ox_rows(self) -> None:
        text = (
            "## Part 1 문제집\n\n"
            "### CHAPTER 01 테스트 — 단원별 출제예상문제\n\n"
            "1. 계약기간은 ( )일이다. (단답)\n"
            "<!-- source: Part 1/page_0001.jpg -->\n\n"
            "2. 다음 설명은 옳다.\n"
            "   ① O\n   ② X\n"
            "<!-- source: Part 1/page_0002.jpg -->\n\n"
            "3. 정상 선택형 문항은?\n"
            "   ① 하나\n   ② 둘\n   ③ 셋\n   ④ 넷\n"
            "<!-- source: Part 1/page_0003.jpg -->\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            index = self.load_bank_text(subject1_bank, Path(tmp) / "subject1.md", text)
        self.assertEqual(list(index), ["1:1:1:exam:3"])

    def test_inventory_reports_each_bank_parse_issue(self) -> None:
        text = (
            "## Part 1 문제집\n\n"
            "### CHAPTER 01 테스트 — 단원별 출제예상문제\n\n"
            "1. 선지가 부족한 후보 문항은?\n"
            "   ① 하나\n   ② 둘\n   ③ 셋\n"
            "<!-- source: Part 1/page_0001.jpg -->\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subject1-invalid.md"
            path.write_text(text, encoding="utf-8")
            subject1_bank.load_questions_index.cache_clear()
            try:
                with patch.object(subject1_bank, "PROBLEM_MD", path):
                    messages = [issue.message for issue in validate_written_bank_inventory(ROOT)]
            finally:
                subject1_bank.load_questions_index.cache_clear()
        self.assertTrue(any(message.startswith("문제은행 파싱 오류:") for message in messages))
        self.assertTrue(any("선지는 ①②③④ 각 1개여야 함" in message for message in messages))

    def test_inline_json_cannot_close_script(self) -> None:
        rendered = inline_json({"stem": "</script><img src=x onerror=alert(1)>"})
        self.assertNotIn("</script>", rendered)
        self.assertIn("\\u003c/script\\u003e", rendered)

    def test_valid_practical_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.make_practical_round(directory)
            self.assertEqual(validate_practical_round(directory), [])

    def test_malformed_practical_ids_are_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.make_practical_round(directory, id_template="malformed-{number}")
            messages = [issue.message for issue in validate_practical_round(directory, ROOT)]
        self.assertIn("실기 id 주석 누락 또는 형식 오류", messages)

    def test_first_lap_reuse_is_rejected_but_later_lap_reuse_is_allowed(self) -> None:
        stable_id = "1:1:1:exam:1"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.write_manifest(
                root / "output/mock_exam/필기/통합/1회차/manifest.json",
                stable_id,
            )
            same_lap = self.write_manifest(
                root / "output/mock_exam/필기/1과목/1회차/manifest.json",
                stable_id,
                lap=1,
            )
            later_lap = self.write_manifest(
                root / "output/mock_exam/필기/1과목/2회차/manifest.json",
                stable_id,
                lap=2,
            )

            direct_issues = validate_first_lap_stable_id_reuse([first, same_lap])
            self.assertEqual(len(direct_issues), 1)
            self.assertIn("1차 lap stable_id 재사용", direct_issues[0].message)
            self.assertEqual(validate_first_lap_stable_id_reuse([first, later_lap]), [])

            _, _, _, all_issues = validate_all(root)
            reuse_messages = [
                issue.message for issue in all_issues if "1차 lap stable_id 재사용" in issue.message
            ]
            self.assertEqual(len(reuse_messages), 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from cbt.builder import OUTPUT_HTML_NAMES, inline_json, render_html  # noqa: E402
from cbt.parser import parse_questions  # noqa: E402
from cbt.profiles import FULL_MOCK  # noqa: E402
from cbt.validation import (  # noqa: E402
    validate_practical_round,
    validate_round,
    validate_written_bank_inventory,
)


class MockValidationTest(unittest.TestCase):
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
        for name in ("index.html", "필기_응시.html", "필기_모의_응시.html", "교차검수.md"):
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
        (directory / "교차검수.md").write_text("ok", encoding="utf-8")
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
            self.assertIn("CBT HTML 3종의 내용이 서로 다름", messages)
            self.assertIn("CBT HTML이 문제지 또는 현재 빌드 자산과 불일치", messages)

    def test_all_written_bank_questions_have_answers(self) -> None:
        self.assertEqual(validate_written_bank_inventory(ROOT), [])

    def test_inline_json_cannot_close_script(self) -> None:
        rendered = inline_json({"stem": "</script><img src=x onerror=alert(1)>"})
        self.assertNotIn("</script>", rendered)
        self.assertIn("\\u003c/script\\u003e", rendered)

    def test_valid_practical_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            problems = ["# 실기 문제\n"]
            answers = ["# 실기 정답\n"]
            for number in range(1, 21):
                problems.append(
                    f"### {number}. 테스트 문제\n"
                    "<!-- source: Part 1/page_0001.jpg -->\n"
                    f"<!-- id: 4:1:1:essay:{number} -->\n"
                )
                answers.append(f"### {number}.\n\n테스트 정답\n")
            (directory / "실기_모의_문제.md").write_text("\n".join(problems), encoding="utf-8")
            (directory / "실기_모의_정답.md").write_text("\n".join(answers), encoding="utf-8")
            self.assertEqual(validate_practical_round(directory), [])


if __name__ == "__main__":
    unittest.main()

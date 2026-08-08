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

from cbt.builder import inline_json  # noqa: E402
from cbt.validation import validate_practical_round, validate_round  # noqa: E402


class MockValidationTest(unittest.TestCase):
    def make_round(self, directory: Path, *, source: str = "Part 1/page_0001.jpg") -> Path:
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

    def test_valid_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp))
            self.assertEqual(validate_round(path), [])

    def test_empty_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_round(Path(tmp), source="")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("source 주석 누락 또는 빈 값", messages)

    def test_manifest_answer_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = self.make_round(directory)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["items"][0]["answer"] = "②"
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            messages = [issue.message for issue in validate_round(path)]
            self.assertIn("정답지와 manifest 정답 불일치", messages)

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

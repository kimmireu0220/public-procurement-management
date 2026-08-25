from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "qwen3-tts-korean-lecture" / "scripts" / "prepare_subject4_narrations.py"


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("prepare_subject4_narrations", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PrepareSubject4NarrationsTest(unittest.TestCase):
    module: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_front_matter_and_chapter_mapping(self) -> None:
        chapters = self.module.load_chapters(ROOT / "output" / "chapter_lectures" / "4과목")
        self.assertEqual(len(chapters), 25)
        self.assertEqual((chapters[0].part, chapters[0].chapter), (1, 1))
        self.assertEqual((chapters[-1].part, chapters[-1].chapter), (8, 2))
        self.assertEqual(chapters[0].stem, "4과목_Part01_Chapter01_공공조달_참여_준비하기")

    def test_table_is_spoken_without_markdown_pipes(self) -> None:
        body = """# 강의

## 1. 구분

| 항목 | 의미 | 기한 |
|---|---|---:|
| 제조물품 | 직접 제조 | 3년 |

## 근거와 기준일
- https://example.com
"""
        spoken = self.module.body_to_spoken(body, "강의")
        self.assertIn("제조물품", spoken)
        self.assertIn("의미는 직접 제조", spoken)
        self.assertIn("기한은 3년", spoken)
        self.assertNotIn("|", spoken)
        self.assertNotIn("https://", spoken)
        self.assertNotIn("근거와 기준일", spoken)

    def test_inline_markdown_and_answer_language(self) -> None:
        value = self.module.strip_inline_markdown("**O/X** [규정](https://example.com) ① → ②")
        self.assertEqual(value, "진위형 규정 1번, 2번")
        answer = self.module.normalize_answer_language("정답·해설: X. 자동 등록이 아닙니다.")
        self.assertEqual(answer, "정답과 해설. 틀립니다. 자동 등록이 아닙니다.")

    def test_rendered_chapter_has_no_screen_markup(self) -> None:
        chapters = self.module.load_chapters(ROOT / "output" / "chapter_lectures" / "4과목")
        narration = self.module.render_narration(chapters[1])
        self.assertEqual(self.module.validate_narration(chapters[1], narration), [])
        self.assertNotIn("https://", narration)
        self.assertNotIn("|---|", narration)
        self.assertIn("문제 10", narration)
        self.assertIn("2026년 8월 24일", narration)

    def test_manual_lesson_is_explicitly_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manual.txt"
            path.write_text("수동 대본", encoding="utf-8")
            self.assertIn("PPM4-P01-L01", self.module.MANUAL_LESSON_IDS)

    def test_high_risk_numeric_tokens_are_preserved(self) -> None:
        chapters = self.module.load_chapters(ROOT / "output" / "chapter_lectures" / "4과목")
        narration = self.module.render_narration(chapters[1])
        self.assertEqual(self.module.missing_numeric_tokens(chapters[1], narration), [])
        self.assertEqual(
            self.module.high_risk_numeric_tokens("기준은 80%입니다."),
            self.module.high_risk_numeric_tokens("기준은 80퍼센트입니다."),
        )
        self.assertEqual(
            self.module.high_risk_numeric_tokens("대표자 1명과 10자리 번호"),
            self.module.high_risk_numeric_tokens("대표자 한 명과 열 자리 번호"),
        )
        self.assertEqual(
            self.module.high_risk_numeric_tokens("문제 5. 6억원 용역"),
            self.module.high_risk_numeric_tokens("6억원 용역"),
        )


if __name__ == "__main__":
    unittest.main()

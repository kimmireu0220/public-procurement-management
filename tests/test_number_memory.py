from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from number_memory import render_number_memory_guide  # noqa: E402


class NumberMemoryTest(unittest.TestCase):
    def test_only_problem_column_links_even_when_columns_move(self) -> None:
        markdown = """# 숫자 암기표

| 문제 | 금액 |
|---|---|
| 17, 19 | 300만원 |

| 주제 | 문제 |
|---|---|
| <script> | 583의 비교값 |

| 주제 | 기간 |
|---|---|
| 계약 | 30일 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "guide.md"
            source.write_text(markdown, encoding="utf-8")
            page = render_number_memory_guide(2, "계획분석", source)

        for question in (17, 19, 583):
            self.assertIn(f'href="../../2과목/?q={question}"', page)
        self.assertNotIn("?q=300", page)
        self.assertNotIn("?q=30", page)
        self.assertIn("</a>의 비교값", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()

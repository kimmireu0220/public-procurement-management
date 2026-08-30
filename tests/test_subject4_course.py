from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "output" / "chapter_lectures" / "4과목"
CHAPTERS = sorted(COURSE.glob("part*/chapter*.md"))
OFFICIAL_CRITERIA_SHA256 = (
    "e74567b03d107faaa5e4d0c4ecd96f4b7f7f129a490e567a8e7388f6f49c1e36"
)


class Subject4CourseQualityTests(unittest.TestCase):
    def test_official_scope_mapping_stays_complete_and_unique(self) -> None:
        source_map = json.loads((COURSE / "source-map.json").read_text(encoding="utf-8"))
        lessons = source_map["lessons"]
        criterion_ids = [
            criterion.split(" ", 1)[0]
            for lesson in lessons
            for criterion in lesson["fine_criteria"]
        ]

        self.assertEqual(len(lessons), 25)
        self.assertEqual(len(criterion_ids), 91)
        self.assertEqual(len(set(criterion_ids)), 91)
        criteria_digest = hashlib.sha256(
            "\n".join(
                criterion for lesson in lessons for criterion in lesson["fine_criteria"]
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(criteria_digest, OFFICIAL_CRITERIA_SHA256)
        self.assertEqual(
            Counter(int(path.parent.name.removeprefix("part")) for path in CHAPTERS),
            Counter({1: 3, 2: 3, 3: 3, 4: 4, 5: 3, 6: 4, 7: 3, 8: 2}),
        )

    def test_every_chapter_has_a_deliberate_retrieval_feedback_loop(self) -> None:
        copied_prompt = (
            "의 수행절차를 설명하고, 각 단계에서 확인할 판단기준과 "
            "남겨야 할 결과를 쓰시오"
        )
        for path in CHAPTERS:
            with self.subTest(chapter=path.relative_to(COURSE)):
                markdown = path.read_text(encoding="utf-8")
                self.assertEqual(
                    markdown.count("## 실전 인출·피드백 — 자체 작성"), 1
                )
                self.assertNotIn(copied_prompt, markdown)
                self.assertIn("**변형 1.**", markdown)
                self.assertEqual(markdown.count(":::answer"), 1)
                self.assertRegex(markdown, r"(?:10점 자체 채점|자체 채점\(10점\))")
                for error_tag in ("개념", "혼동", "숫자", "적용"):
                    self.assertRegex(
                        markdown,
                        rf"(?:\*\*{error_tag}:\*\*|\| {error_tag} \|)",
                    )
                for interval in ("D+1", "D+3", "D+7"):
                    self.assertIn(interval, markdown)
                self.assertIn("8점 이상", markdown)
                self.assertNotRegex(markdown, r"6\s*점\s*이상")
                self.assertEqual(
                    markdown.count(
                        "> 숫자는 반드시 적용기관·계약유형·기산점·시행일과 함께 쓴다."
                    ),
                    1,
                )

    def test_answer_blocks_are_balanced_and_integrated_review_is_hidden(self) -> None:
        paths = [*CHAPTERS, COURSE / "total-review.md"]
        for path in paths:
            with self.subTest(source=path.relative_to(COURSE)):
                markdown = path.read_text(encoding="utf-8")
                openings = len(re.findall(r"^:::answer(?: .+)?$", markdown, re.MULTILINE))
                closings = len(re.findall(r"^:::$", markdown, re.MULTILINE))
                self.assertEqual(openings, closings)

        review = (COURSE / "total-review.md").read_text(encoding="utf-8")
        self.assertEqual(review.count(":::answer"), 8)

    def test_contract_chapters_require_direct_work_products(self) -> None:
        expected_outputs = {
            "part04/chapter01.md": "수정 계약서(안)의 핵심행",
            "part04/chapter02.md": "4열",
            "part04/chapter03.md": "변경계약 핵심표",
            "part04/chapter04.md": "검사조서",
            "part05/chapter01.md": "공사 특화 계약조건표",
            "part05/chapter02.md": "일반 단가계약",
            "part05/chapter03.md": "용역 특화 계약조건표",
        }
        for relative, work_product in expected_outputs.items():
            with self.subTest(source=relative):
                markdown = (COURSE / relative).read_text(encoding="utf-8")
                self.assertEqual(markdown.count("**수행동사 보강 소문항"), 1)
                self.assertEqual(markdown.count("**보강 채점(4점).**"), 1)
                self.assertIn(work_product, markdown)
                for interval in ("D+1", "D+3", "D+7"):
                    self.assertRegex(
                        markdown,
                        rf"(?m)^- \[ \] \*\*{re.escape(interval)}:\*\* .+$",
                    )

    def test_legal_cutoff_matches_the_frozen_source_bundle(self) -> None:
        manifest = json.loads(
            (ROOT / "sources" / "현행_법령_근거" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        expected = manifest["retrieved_at"]
        for path in [*CHAPTERS, COURSE / "overview.md", COURSE / "total-review.md"]:
            with self.subTest(source=path.relative_to(COURSE)):
                markdown = path.read_text(encoding="utf-8")
                self.assertRegex(markdown, rf"(?m)^legal_cutoff: {re.escape(expected)}$")

    def test_verified_high_risk_values_do_not_regress(self) -> None:
        expected_fragments = {
            "part01/chapter02.md": (
                "개별 품목정보·물품식별번호",
                "필요한 품목등록·식별번호 발급 절차",
            ),
            "part03/chapter01.md": (
                "공사 15%, 제조·구매 25%, 수입물품 구매 10%, 용역 10%",
                "재정경제부예규 제171호, 2026년 8월 25일 시행",
            ),
            "part03/chapter02.md": ("85% 이상", "E의 70% 미만", "배점한도의 30%"),
            "part04/chapter03.md": ("90일 이상", "지수조정률이 3% 이상 증감"),
            "part04/chapter01.md": (
                "기간특례가 허용하는 5% 이상 범위",
                "기간특례 고시와 계약조건이 보증률을 5%로 정한 사실",
            ),
            "part04/chapter02.md": (
                "2026년 8월 25일 시행 `정부 입찰·계약 집행기준` 제34조",
                "재정경제부예규 제172호, 2026년 8월 25일 시행",
                "100억원 이상 30 / 20억원 이상 100억원 미만 40 / 20억원 미만 50",
                "10억원 이상 30 / 3억원 이상 10억원 미만 40 / 3억원 미만 50",
                "20억원 미만 70 / 20억원 이상 50",
            ),
            "part04/chapter04.md": (
                "분할납품을 요구·허용해 그 이행을 완료한 경우",
                "기납부분에 해당하는 계약보증금은 당초 계약보증금에서 제외",
                "재정경제부계약예규 제170호, 2026년 8월 25일 시행",
                "재정경제부예규 제172호, 2026년 8월 25일 시행",
            ),
            "part05/chapter02.md": (
                "2026년 8월 25일 시행 정부 입찰·계약 집행기준상",
                "국가계약 선금의 일반 상한은 계약금액의 70%",
            ),
            "part07/chapter02.md": (
                "30일 이내 또는 안 날부터 25일 이내",
                "20일 이내 또는 안 날부터 15일 이내",
            ),
            "part07/chapter03.md": (
                "장애인기업제품 | 1% 이상",
                "중증장애인생산품 | 2026년 1.1%",
            ),
        }
        for relative, fragments in expected_fragments.items():
            markdown = (COURSE / relative).read_text(encoding="utf-8")
            for fragment in fragments:
                with self.subTest(source=relative, fragment=fragment):
                    self.assertIn(fragment, markdown)


if __name__ == "__main__":
    unittest.main()

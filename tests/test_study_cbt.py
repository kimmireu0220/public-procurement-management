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

import build_study_cbt  # noqa: E402
import site_portal  # noqa: E402


def questions_from_html(rendered: str) -> list[dict]:
    _, separator, remainder = rendered.partition("const QUESTIONS = ")
    if not separator:
        raise AssertionError("QUESTIONS payload not found")
    payload, separator, _ = remainder.partition(";\nconst STORAGE_KEY = ")
    if not separator:
        raise AssertionError("STORAGE_KEY marker not found")
    value = json.loads(payload)
    if not isinstance(value, list):
        raise AssertionError("QUESTIONS payload is not a list")
    return value


class StudyCbtTest(unittest.TestCase):
    def test_collects_discovered_parts_in_stable_order(self) -> None:
        pages = build_study_cbt.collect_pages()

        self.assertTrue(pages)
        page_keys = [(page.subject.subject, page.part) for page in pages]
        self.assertEqual(page_keys, sorted(set(page_keys)))
        for page in pages:
            self.assertTrue(page.questions)
            self.assertEqual(
                [question["no"] for question in page.questions],
                list(range(1, len(page.questions) + 1)),
            )
            self.assertTrue(all(question["id"].split(":")[3] == "exam" for question in page.questions))

        generated: dict[int, tuple[tuple[int, int], ...]] = {}
        for subject in build_study_cbt.SUBJECTS:
            generated[subject.subject] = tuple(
                (page.part, len(page.questions))
                for page in pages
                if page.subject.subject == subject.subject
            )
        rendered = site_portal._study_groups(generated)
        for page in pages:
            self.assertIn(f'href="study/{page.slug}/"', rendered)
            self.assertIn(f"{len(page.questions)}문항", rendered)

    def test_build_publishes_only_question_data_and_generated_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "study"
            pages = build_study_cbt.build(destination)

            expected_files = {Path("index.html")}
            for page in pages:
                expected_files.add(Path(page.slug) / "index.html")
                expected_files.add(Path(page.slug) / "study-meta.json")
            actual_files = {
                path.relative_to(destination)
                for path in destination.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual_files, expected_files)

            landing = (destination / "index.html").read_text(encoding="utf-8")
            for page in pages:
                self.assertIn(f'href="{page.slug}/"', landing)
                self.assertIn(f">{len(page.questions)}문항</span>", landing)

                page_dir = destination / page.slug
                rendered = (page_dir / "index.html").read_text(encoding="utf-8")
                public_questions = questions_from_html(rendered)
                self.assertEqual(len(public_questions), len(page.questions))
                for question in public_questions:
                    self.assertEqual(
                        set(question),
                        {"no", "subject", "subjectName", "stem", "choices", "id"},
                    )
                    self.assertNotIn("answer", question)
                    self.assertEqual(len(question["choices"]), 4)
                    for choice in question["choices"]:
                        self.assertEqual(set(choice), {"key", "label", "text"})

                meta = json.loads((page_dir / "study-meta.json").read_text(encoding="utf-8"))
                self.assertEqual(meta["kind"], "study")
                self.assertEqual(meta["subject"], page.subject.subject)
                self.assertEqual(meta["part"], page.part)
                self.assertEqual(meta["stype"], "exam")
                self.assertEqual(meta["total"], len(page.questions))
                self.assertTrue((ROOT / meta["source"]).is_file())
                self.assertNotIn("answer", meta)

    def test_build_is_deterministic_and_tree_comparison_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            expected = temp_root / "expected"
            actual = temp_root / "actual"
            build_study_cbt.build(expected)
            build_study_cbt.build(actual)

            self.assertEqual(build_study_cbt.compare_trees(expected, actual), [])
            (actual / "index.html").write_text("stale", encoding="utf-8")
            self.assertIn(
                "생성 결과 불일치: index.html",
                build_study_cbt.compare_trees(expected, actual),
            )
            (actual / "unexpected.txt").write_text("extra", encoding="utf-8")
            self.assertIn(
                "불필요 공개 파일: unexpected.txt",
                build_study_cbt.compare_trees(expected, actual),
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_lecture_pages  # noqa: E402


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


class LecturePagesTest(unittest.TestCase):
    def test_markdown_external_links_are_rendered_and_escaped(self) -> None:
        rendered = build_lecture_pages.inline_markup(
            "[공식 원문](https://example.com/rule?a=1&b=2) **확인**"
        )

        self.assertIn(
            '<a href="https://example.com/rule?a=1&amp;b=2">공식 원문</a>',
            rendered,
        )
        self.assertIn("<strong>확인</strong>", rendered)

    def test_markdown_hard_breaks_render_without_enabling_raw_html(self) -> None:
        space_break = build_lecture_pages.markdown_to_html(
            "① 첫 번째 보기  \n② 두 번째 보기\n\n원문 <br> 표기"
        )
        backslash_break = build_lecture_pages.markdown_to_html(
            "① 첫 번째 보기\\\n② 두 번째 보기"
        )

        self.assertIn("<p>① 첫 번째 보기<br>② 두 번째 보기</p>", space_break)
        self.assertIn("<p>① 첫 번째 보기<br>② 두 번째 보기</p>", backslash_break)
        self.assertIn("원문 &lt;br&gt; 표기", space_break)

    def test_answers_are_collapsed_for_recall_practice(self) -> None:
        for label in ("정답·해설", "정답·채점"):
            with self.subTest(label=label):
                rendered = build_lecture_pages.markdown_to_html(
                    f"**문제 1.** 설명은?\n\n> **{label}:** 핵심 답안"
                )

                self.assertIn('<details class="answer-disclosure">', rendered)
                self.assertIn("정답·해설 보기", rendered)
                self.assertIn("핵심 답안", rendered)

    def test_multi_paragraph_answer_blocks_are_collapsed(self) -> None:
        markdown = """**사례 1.** 먼저 답을 쓰시오.

:::answer 모범답안·채점 보기
### 모범답안

1. 결론을 쓴다.
2. 사실을 적용한다.

### 채점

- 결론: 2점
- 적용: 8점
:::

## 다음 학습
"""
        rendered = build_lecture_pages.markdown_to_html(markdown)
        outline = build_lecture_pages.article_outline(markdown)

        self.assertIn(
            '<details class="answer-disclosure answer-block">', rendered
        )
        self.assertIn("<summary>모범답안·채점 보기</summary>", rendered)
        self.assertIn("<h3", rendered)
        self.assertIn("결론을 쓴다.", rendered)
        self.assertIn("다음 학습", outline)
        self.assertNotIn("모범답안", outline)
        self.assertNotIn("채점", outline)

    def test_answer_markers_inside_fenced_code_do_not_close_the_block(self) -> None:
        markdown = """:::answer 답안 보기
```text
:::
```
### 답안 내부 제목
:::

## 다음 학습
"""
        rendered = build_lecture_pages.markdown_to_html(markdown)
        outline = build_lecture_pages.article_outline(markdown)

        self.assertIn("<code>:::</code>", rendered)
        self.assertIn("답안 내부 제목", rendered)
        self.assertIn('id="다음-학습"', rendered)
        self.assertNotIn('id="답안-내부-제목"', rendered)
        self.assertNotIn("답안 내부 제목", outline)
        self.assertIn("다음 학습", outline)

    def test_answer_content_does_not_duplicate_heading_or_checkbox_ids(self) -> None:
        markdown = """:::answer 답안 보기
### 중복 제목
- [ ] 같은 체크
:::

## 중복 제목
- [ ] 같은 체크
"""
        rendered = build_lecture_pages.markdown_to_html(markdown)
        heading_ids = re.findall(r'<h[2-6] id="([^"]+)"', rendered)
        check_ids = re.findall(r'data-study-check="([^"]+)"', rendered)

        self.assertEqual(heading_ids, ["중복-제목"])
        self.assertEqual(len(check_ids), 2)
        self.assertEqual(len(set(check_ids)), 2)

    def test_unclosed_answer_block_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "종료선"):
            build_lecture_pages.markdown_to_html(
                ":::answer 모범답안 보기\n끝나지 않은 답안"
            )

    def test_orphan_and_nested_answer_markers_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "대응하는"):
            build_lecture_pages.markdown_to_html("본문\n:::\n")
        with self.assertRaisesRegex(ValueError, "중첩"):
            build_lecture_pages.markdown_to_html(
                ":::answer 바깥\n:::answer 안쪽\n:::\n:::\n"
            )

    def test_checklists_render_as_persistent_controls(self) -> None:
        rendered = build_lecture_pages.markdown_to_html(
            "- [ ] 첫 복습\n- [x] 완료한 복습"
        )

        self.assertEqual(rendered.count('type="checkbox"'), 2)
        self.assertEqual(rendered.count("data-study-check="), 2)
        self.assertIn(" checked", rendered)
        self.assertNotIn("□", rendered)
        self.assertIn("lectureStudyChecks", build_lecture_pages.STUDY_PROGRESS_SCRIPT)

    def test_progress_summary_uses_source_defaults_and_stable_page_key(self) -> None:
        lecture = build_lecture_pages.Lecture(
            source=Path("chapter.md"),
            subject=1,
            subject_title="테스트",
            part=1,
            part_title="Part",
            chapter=1,
            title="진행률",
            kind="chapter",
            body="- [ ] 첫 복습\n- [x] 완료한 복습\n",
        )

        rendered = build_lecture_pages.render_lecture(lecture, [lecture])

        self.assertIn('aria-live="polite">1 / 2</strong>', rendered)
        self.assertIn("endsWith('/index.html')", build_lecture_pages.STUDY_PROGRESS_SCRIPT)
        self.assertIn("!Array.isArray(v)", build_lecture_pages.STUDY_PROGRESS_SCRIPT)

    def test_header_omits_decorative_training_tagline(self) -> None:
        rendered = build_lecture_pages.page_shell("강의", "<main></main>", "")

        self.assertNotIn("출제기준 · 실무 판단 · 답안 훈련", rendered)
        self.assertNotIn("header-note", rendered)
        self.assertIn("학습센터", rendered)

    def test_duplicate_headings_receive_unique_anchors(self) -> None:
        markdown = "## 개념\n본문\n\n## 개념\n다른 본문"
        rendered = build_lecture_pages.markdown_to_html(markdown)
        outline = build_lecture_pages.article_outline(markdown)

        self.assertIn('id="개념"', rendered)
        self.assertIn('id="개념-2"', rendered)
        self.assertIn('href="#개념-2"', outline)

    def test_sources_are_loadable_without_prescribing_body_structure(self) -> None:
        lectures = build_lecture_pages.load_lectures()

        self.assertTrue(lectures)
        self.assertEqual(len({lecture.source for lecture in lectures}), len(lectures))
        self.assertTrue(any(lecture.is_chapter for lecture in lectures))
        self.assertTrue(all(lecture.body.strip() for lecture in lectures))

    def test_learning_questions_keep_answers_in_the_same_block(self) -> None:
        question_pattern = re.compile(r"^\*\*(?:(?:문제|회상|O/X|사례) )?\d+\.")
        review_case_pattern = re.compile(r"^### 사례 \d+\.")
        answer_pattern = re.compile(r"^> \*\*(?:정답(?:·해설|·채점)?|모범답안):")
        separate_answer_heading = re.compile(
            r"^#{2,4} .*?(?:정답|모범답안·채점요소)\s*$",
            re.MULTILINE,
        )

        for subject in ("1과목", "2과목", "3과목", "4과목"):
            for source in sorted((build_lecture_pages.SOURCE_DIR / subject).rglob("*.md")):
                markdown = source.read_text(encoding="utf-8")
                visible_markdown = re.sub(
                    r"^:::answer(?: .+)?\n.*?^:::\s*$",
                    "",
                    markdown,
                    flags=re.MULTILINE | re.DOTALL,
                )
                self.assertIsNone(
                    separate_answer_heading.search(visible_markdown),
                    f"분리 정답 섹션이 남아 있습니다: {source}",
                )
                lines = markdown.splitlines()

                def is_question(line: str) -> bool:
                    if question_pattern.match(line):
                        return True
                    if source.name == "total-review.md":
                        return bool(re.match(r"^\d+\. ", line) or review_case_pattern.match(line))
                    return False

                question_indexes = [
                    index for index, line in enumerate(lines) if is_question(line)
                ]
                for position, question_index in enumerate(question_indexes):
                    block_end = (
                        question_indexes[position + 1]
                        if position + 1 < len(question_indexes)
                        else len(lines)
                    )
                    answer_lines = lines[question_index + 1 : block_end]
                    inline_answer = any(
                        answer_pattern.match(line) for line in answer_lines
                    )
                    answer_block = any(
                        line.startswith(":::answer") for line in answer_lines
                    ) and any(
                        re.match(r"^\*\*(?:모범답안|정답|채점요소)", line)
                        for line in answer_lines
                    )
                    self.assertTrue(
                        inline_answer or answer_block,
                        f"문제 바로 뒤 블록에 정답이 없습니다: {source}:{question_index + 1}",
                    )

    def test_overview_metadata_is_minimal_and_chapter_gaps_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            overview_path = Path(tmp) / "overview.md"
            overview_path.write_text(
                "---\nsubject: 1\nsubject_title: 테스트\ntitle: 자유 개요\nkind: overview\n---\n"
                "\n원하는 형식의 본문\n",
                encoding="utf-8",
            )
            overview = build_lecture_pages.parse_front_matter(overview_path)
            self.assertTrue(overview.is_overview)
            self.assertEqual(overview.part, 0)

        chapters = [
            build_lecture_pages.Lecture(
                source=Path(f"chapter{number}.md"),
                subject=1,
                subject_title="테스트",
                part=1,
                part_title="자유 구성",
                chapter=number,
                title=f"Chapter {number}",
                kind="chapter",
                body="고정 섹션이나 퀴즈 제한이 없는 본문\n",
            )
            for number in (1, 3)
        ]
        build_lecture_pages.validate_lectures(chapters)

    def test_body_rejects_a_duplicate_level_one_title(self) -> None:
        lecture = build_lecture_pages.Lecture(
            source=Path("duplicate-title.md"),
            subject=1,
            subject_title="테스트",
            part=1,
            part_title="자유 구성",
            chapter=1,
            title="중복 제목",
            kind="chapter",
            body="# 중복 제목\n\n본문\n",
        )

        with self.assertRaisesRegex(ValueError, "metadata title과 중복"):
            build_lecture_pages.validate_lectures([lecture])

    def test_subject_index_uses_the_correct_exam_type(self) -> None:
        def chapter(subject: int) -> build_lecture_pages.Lecture:
            return build_lecture_pages.Lecture(
                source=Path(f"subject{subject}.md"),
                subject=subject,
                subject_title="테스트",
                part=1,
                part_title="Part",
                chapter=1,
                title="Chapter",
                kind="chapter",
                body="본문\n",
            )

        written = build_lecture_pages.render_subject(
            {"id": 3, "title": "공공계약관리"}, [chapter(3)]
        )
        practical = build_lecture_pages.render_subject(
            {"id": 4, "title": "공공조달 관리실무"}, [chapter(4)]
        )

        self.assertIn("필기 출제기준", written)
        self.assertNotIn("실기 출제기준", written)
        self.assertIn("실기 출제기준", practical)

    def test_build_emits_a_page_for_every_loaded_lecture(self) -> None:
        lectures = build_lecture_pages.load_lectures()
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            meta = build_lecture_pages.build(destination)

            self.assertEqual(
                meta["total_chapters"],
                len([lecture for lecture in lectures if lecture.is_chapter]),
            )
            self.assertTrue((destination / "index.html").is_file())
            self.assertTrue((destination / "assets" / "style.css").is_file())
            for lecture in lectures:
                self.assertTrue(
                    (destination / lecture.relative_url / "index.html").is_file(),
                    lecture.relative_url,
                )
            for subject in {lecture.subject for lecture in lectures}:
                self.assertTrue((destination / str(subject) / "index.html").is_file())

    def test_all_generated_internal_links_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "lecture"
            build_lecture_pages.build(destination)
            (destination.parent / "index.html").write_text("portal", encoding="utf-8")
            for page in destination.rglob("*.html"):
                parser = LinkParser()
                parser.feed(page.read_text(encoding="utf-8"))
                for href in parser.links:
                    parsed = urlsplit(href)
                    if parsed.scheme or parsed.netloc or href.startswith("#"):
                        continue
                    target = (page.parent / unquote(parsed.path)).resolve()
                    if parsed.path.endswith("/"):
                        target = target / "index.html"
                    self.assertTrue(target.exists(), f"깨진 링크: {page}: {href}")


if __name__ == "__main__":
    unittest.main()

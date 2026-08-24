#!/usr/bin/env python3
"""문제은행 1~3과목의 Part별 exam 문항을 학습용 CBT로 일괄 생성한다."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.builder import inline_json, load_asset  # noqa: E402
from cbt.profiles import DOCS, ROOT  # noqa: E402
from subject1.bank import PROBLEM_MD as SUBJECT1_PROBLEM_MD  # noqa: E402
from subject1.bank import load_questions_index as load_subject1_questions  # noqa: E402
from subject2.bank import PROBLEM_MD as SUBJECT2_PROBLEM_MD  # noqa: E402
from subject2.bank import load_questions_index as load_subject2_questions  # noqa: E402
from subject3.bank import PROBLEM_MD as SUBJECT3_PROBLEM_MD  # noqa: E402
from subject3.bank import load_questions_index as load_subject3_questions  # noqa: E402

OUTPUT_DIR = DOCS / "study"
CHOICE_KEYS = {"①": "1", "②": "2", "③": "3", "④": "4"}


@dataclass(frozen=True)
class StudySubject:
    subject: int
    title: str
    problem_md: Path
    load_questions: Callable[[], dict[str, dict]]
    question_types: frozenset[str] = frozenset({"exam"})


@dataclass(frozen=True)
class StudyPage:
    subject: StudySubject
    part: int
    questions: list[dict]

    @property
    def slug(self) -> str:
        return f"{self.subject.subject}과목-part{self.part}-exam"

    @property
    def title(self) -> str:
        return f"{self.subject.subject}과목 Part{self.part} EXAM 학습"

    @property
    def subtitle(self) -> str:
        return f"{self.subject.title} · 문제은행 exam 전체"

    @property
    def storage_key(self) -> str:
        return f"study_{self.subject.subject}_p{self.part}_exam_answers"


SUBJECTS = (
    StudySubject(
        subject=1,
        title="공공조달과 법제도 이해",
        problem_md=SUBJECT1_PROBLEM_MD,
        load_questions=load_subject1_questions,
    ),
    StudySubject(
        subject=2,
        title="공공조달계획 수립 및 분석",
        problem_md=SUBJECT2_PROBLEM_MD,
        load_questions=load_subject2_questions,
    ),
    StudySubject(
        subject=3,
        title="공공계약관리",
        problem_md=SUBJECT3_PROBLEM_MD,
        load_questions=load_subject3_questions,
    ),
)


def _stable_id_parts(stable_id: str) -> tuple[int, int, int, str, int]:
    parts = stable_id.split(":")
    if len(parts) != 5:
        raise ValueError(f"잘못된 stable_id: {stable_id}")
    try:
        subject, part, chapter, question_number = (
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
            int(parts[4]),
        )
    except ValueError as exc:
        raise ValueError(f"잘못된 stable_id: {stable_id}") from exc
    return subject, part, chapter, parts[3], question_number


def _public_question(
    exam_no: int,
    subject: StudySubject,
    part: int,
    chapter: int,
    stable_id: str,
    bank_question: dict,
) -> dict:
    choices = bank_question.get("choices")
    if not isinstance(choices, list) or len(choices) != 4:
        raise ValueError(f"{stable_id}: 선지가 정확히 4개가 아님")

    public_choices: list[dict[str, str]] = []
    labels: list[str] = []
    for choice in choices:
        if not isinstance(choice, tuple) or len(choice) != 2:
            raise ValueError(f"{stable_id}: 선지 형식 오류")
        label, text = choice
        if label not in CHOICE_KEYS or not isinstance(text, str):
            raise ValueError(f"{stable_id}: 선지 형식 오류")
        labels.append(label)
        public_choices.append({"key": CHOICE_KEYS[label], "label": label, "text": text})
    if labels != list(CHOICE_KEYS):
        raise ValueError(f"{stable_id}: 선지 번호가 ①~④ 순서가 아님")

    stem = bank_question.get("stem")
    if not isinstance(stem, str) or not stem.strip():
        raise ValueError(f"{stable_id}: 지문 누락")
    return {
        "no": exam_no,
        "subject": subject.subject,
        "subjectName": f"Part{part} Ch{chapter}",
        "stem": stem,
        "choices": public_choices,
        "id": stable_id,
    }


def collect_subject_pages(subject: StudySubject) -> list[StudyPage]:
    grouped: dict[int, list[tuple[int, int, str, dict]]] = {}
    for stable_id, bank_question in subject.load_questions().items():
        sid_subject, part, chapter, question_type, question_number = _stable_id_parts(stable_id)
        if sid_subject != subject.subject:
            raise ValueError(
                f"{stable_id}: {subject.subject}과목 문제은행에 다른 과목 ID가 포함됨"
            )
        if question_type not in subject.question_types:
            continue
        grouped.setdefault(part, []).append((chapter, question_number, stable_id, bank_question))

    pages: list[StudyPage] = []
    for part in sorted(grouped):
        entries = sorted(grouped[part], key=lambda item: (item[0], item[1], item[2]))
        questions = [
            _public_question(index, subject, part, chapter, stable_id, bank_question)
            for index, (chapter, _number, stable_id, bank_question) in enumerate(entries, 1)
        ]
        pages.append(StudyPage(subject=subject, part=part, questions=questions))
    return pages


def collect_pages() -> list[StudyPage]:
    return [page for subject in SUBJECTS for page in collect_subject_pages(subject)]


def render_study_html(page: StudyPage) -> str:
    rendered = load_asset("study_shell.html")
    replacements = {
        "__TITLE__": html.escape(page.title),
        "__SUBTITLE__": html.escape(page.subtitle),
        "__QUESTION_COUNT__": str(len(page.questions)),
        "__INITIAL_SUBJECT_LABEL__": html.escape(
            f"{page.subject.subject}과목 Part{page.part}"
        ),
        "__STORAGE_KEY_JSON__": inline_json(page.storage_key),
        "__STYLES__": load_asset("styles.css"),
        "__EXAM_JS__": load_asset("exam.js"),
        "__UI_JS__": load_asset("ui.js"),
    }
    for marker, value in replacements.items():
        if marker not in rendered:
            raise ValueError(f"study shell placeholder 누락: {marker}")
        rendered = rendered.replace(marker, value)
    if "__QUESTIONS_JSON__" not in rendered:
        raise ValueError("study shell placeholder 누락: __QUESTIONS_JSON__")
    return rendered.replace("__QUESTIONS_JSON__", inline_json(page.questions))


def render_landing(pages: list[StudyPage]) -> str:
    sections: list[str] = []
    for subject in SUBJECTS:
        subject_pages = [page for page in pages if page.subject.subject == subject.subject]
        cards = "\n".join(
            f'      <a class="card" href="{page.slug}/"><span class="part">Part '
            f'{page.part}</span><span class="count">{len(page.questions)}문항</span>'
            '<span class="start">학습 시작 →</span></a>'
            for page in subject_pages
        )
        sections.append(
            "  <section class=\"subject\">\n"
            f"    <h2>{subject.subject}과목 · {html.escape(subject.title)}</h2>\n"
            "    <div class=\"cards\">\n"
            f"{cards}\n"
            "    </div>\n"
            "  </section>"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>문제은행 학습 CBT</title>
<style>
:root {{ --bg:#f4f7fb; --panel:#fff; --primary:#164a86; --primary-dark:#0f3460; --border:#dbe3ed; --text:#17202a; --muted:#637083; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:"Apple SD Gothic Neo","Malgun Gothic",sans-serif; line-height:1.6; }}
.page {{ max-width:920px; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
.back {{ display:inline-block; margin-bottom:1.25rem; color:var(--primary); text-decoration:none; font-weight:600; }}
.back:hover {{ text-decoration:underline; }}
.hero {{ margin-bottom:2.5rem; }}
.hero h1 {{ margin:0 0 .55rem; color:var(--primary-dark); font-size:clamp(1.65rem,4vw,2.15rem); }}
.hero p {{ margin:0; color:var(--muted); font-size:1.02rem; }}
.subject {{ margin-top:2.4rem; }}
.subject h2 {{ margin:0 0 1rem; color:var(--primary-dark); font-size:1.25rem; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.9rem; }}
.card {{ display:block; min-height:128px; padding:1.15rem; border:1px solid var(--border); border-radius:12px; background:var(--panel); color:inherit; text-decoration:none; box-shadow:0 3px 12px rgba(20,49,83,.05); transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease; }}
.card:hover,.card:focus-visible {{ transform:translateY(-2px); border-color:#8eb1d8; box-shadow:0 7px 18px rgba(20,49,83,.11); outline:none; }}
.part {{ display:block; color:var(--primary-dark); font-size:1.12rem; font-weight:700; }}
.count {{ display:block; margin-top:.3rem; color:var(--muted); font-size:.92rem; }}
.start {{ display:block; margin-top:.85rem; color:var(--primary); font-size:.9rem; font-weight:700; }}
@media (max-width:520px) {{ .page {{ padding:1.5rem 1rem 3rem; }} .cards {{ grid-template-columns:1fr 1fr; gap:.7rem; }} .card {{ min-height:120px; padding:1rem; }} }}
</style>
</head>
<body>
<main class="page">
  <a class="back" href="../">← 모의고사 홈</a>
  <header class="hero">
    <h1>문제은행 학습 CBT</h1>
    <p>학습할 과목과 Part를 선택하세요. Part별 문제를 처음부터 끝까지 연습할 수 있습니다.</p>
  </header>

{(chr(10) * 2).join(sections)}
</main>
</body>
</html>
"""


def page_meta(page: StudyPage) -> dict:
    question_types = sorted({question["id"].split(":")[3] for question in page.questions})
    return {
        "kind": "study",
        "subject": page.subject.subject,
        "part": page.part,
        "stype": question_types[0] if len(question_types) == 1 else "mixed",
        "total": len(page.questions),
        "source": str(page.subject.problem_md.relative_to(ROOT)),
        "note": "GitHub Pages — 문제은행 학습 CBT (정답 미포함)",
    }


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(destination: Path) -> list[StudyPage]:
    pages = collect_pages()
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / "index.html", render_landing(pages))
    for page in pages:
        page_dir = destination / page.slug
        write_text(page_dir / "index.html", render_study_html(page))
        write_text(
            page_dir / "study-meta.json",
            json.dumps(page_meta(page), ensure_ascii=False, indent=2) + "\n",
        )
    return pages


def compare_trees(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = (
        {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()}
        if actual.exists()
        else set()
    )
    errors = [f"누락 공개 파일: {path}" for path in sorted(expected_files - actual_files)]
    errors.extend(f"불필요 공개 파일: {path}" for path in sorted(actual_files - expected_files))
    for relative in sorted(expected_files & actual_files):
        if (expected / relative).read_bytes() != (actual / relative).read_bytes():
            errors.append(f"생성 결과 불일치: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="현재 공개본이 최신 생성 결과와 같은지 확인")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-cbt-") as temp_dir:
        generated = Path(temp_dir) / "study"
        pages = build(generated)
        question_count = sum(len(page.questions) for page in pages)
        if args.check:
            errors = compare_trees(generated, OUTPUT_DIR)
            if errors:
                for error in errors:
                    print(error)
                return 1
            print(
                f"학습 CBT 검증 완료: {len(pages)}개 Part · {question_count}문항"
            )
            return 0

        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        shutil.copytree(generated, OUTPUT_DIR)

    print(f"학습 CBT 생성 완료: {len(pages)}개 Part · {question_count}문항 → {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

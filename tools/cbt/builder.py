"""CBT HTML 빌드 (템플릿 조립·파일 출력)."""

from __future__ import annotations

import json
from pathlib import Path

from cbt.parser import parse_questions
from cbt.profiles import CbtProfile

ASSETS = Path(__file__).resolve().parent / "assets"
OUTPUT_HTML_NAMES = ("index.html",)


def load_asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def inline_json(value: object) -> str:
    """HTML script 블록을 닫을 수 없도록 JSON을 직렬화한다."""

    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(questions: list[dict], round_no: int, profile: CbtProfile) -> str:
    shell = load_asset(profile.shell_html)
    css = load_asset("styles.css")
    exam_js = load_asset("exam.js")
    ui_js = load_asset("ui.js")

    html = (
        shell.replace("__ROUND__", str(round_no))
        .replace("__STYLES__", css)
        .replace("__QUESTIONS_JSON__", inline_json(questions))
        .replace("__STORAGE_KEY__", profile.storage_key(round_no))
        .replace("__EXAM_JS__", exam_js)
        .replace("__UI_JS__", ui_js)
    )
    if profile.inject_duration:
        html = html.replace("__DURATION_SEC__", str(profile.duration_sec))
    return html


def build_for_profile(round_no: int, profile: CbtProfile) -> tuple[Path, int]:
    md_path = profile.problem_md(round_no)
    out_dir = profile.round_dir(round_no)
    if not md_path.is_file():
        raise SystemExit(f"not found: {md_path}")

    text = md_path.read_text(encoding="utf-8")
    questions = parse_questions(text)
    if len(questions) != profile.question_count:
        raise SystemExit(
            f"expected {profile.question_count} questions, got {len(questions)}"
        )
    expected_numbers = list(range(1, profile.question_count + 1))
    if [question["no"] for question in questions] != expected_numbers:
        raise SystemExit("question numbers must be sequential from 1")
    if any(len(question["choices"]) != 4 for question in questions):
        raise SystemExit("every question must have exactly four choices")
    ids = [question["id"] for question in questions]
    if any(not qid for qid in ids) or len(ids) != len(set(ids)):
        raise SystemExit("question ids must be present and unique")

    html = render_html(questions, round_no, profile)
    for name in OUTPUT_HTML_NAMES:
        (out_dir / name).write_text(html, encoding="utf-8")
    return out_dir, len(questions)

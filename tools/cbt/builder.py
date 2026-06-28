"""CBT HTML 빌드 (템플릿 조립·파일 출력)."""

from __future__ import annotations

import json
from pathlib import Path

from cbt.parser import parse_questions
from cbt.profiles import CbtProfile, FULL_MOCK, SUBJECT3

ASSETS = Path(__file__).resolve().parent / "assets"
OUTPUT_HTML_NAMES = ("index.html", "필기_응시.html", "필기_모의_응시.html")


def load_asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def render_html(questions: list[dict], round_no: int, profile: CbtProfile) -> str:
    shell = load_asset(profile.shell_html)
    css = load_asset("styles.css")
    exam_js = load_asset("exam.js")
    ui_js = load_asset("ui.js")

    html = (
        shell.replace("__ROUND__", str(round_no))
        .replace("__STYLES__", css)
        .replace("__QUESTIONS_JSON__", json.dumps(questions, ensure_ascii=False))
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

    html = render_html(questions, round_no, profile)
    for name in OUTPUT_HTML_NAMES:
        (out_dir / name).write_text(html, encoding="utf-8")
    return out_dir, len(questions)


def build_round(round_no: int) -> tuple[Path, int]:
    """통합 필기 80문항."""
    return build_for_profile(round_no, FULL_MOCK)


def build_subject3_round(round_no: int) -> tuple[Path, int]:
    """3과목 전용 30문항."""
    return build_for_profile(round_no, SUBJECT3)

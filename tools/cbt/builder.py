"""CBT HTML 빌드 (템플릿 조립·파일 출력)."""

from __future__ import annotations

import json
from pathlib import Path

from cbt.parser import EXPECTED_QUESTION_COUNT, SUBJECT3_QUESTION_COUNT, parse_questions

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
OUTPUT_HTML_NAMES = ("index.html", "필기_응시.html", "필기_모의_응시.html")
SUBJECT3_DURATION_SEC = 45 * 60


def round_paths(round_no: int) -> tuple[Path, Path]:
    out_dir = ROOT / f"output/mock_exam/{round_no}회차"
    md = out_dir / "필기_모의_문제.md"
    if not md.is_file():
        raise SystemExit(f"not found: {md}")
    return md, out_dir


def storage_key(round_no: int) -> str:
    return f"mock_exam_{round_no}_answers"


def subject3_storage_key(round_no: int) -> str:
    return f"mock_exam_3s{round_no}_answers"


def subject3_paths(round_no: int) -> tuple[Path, Path]:
    out_dir = ROOT / f"output/mock_exam/3과목/{round_no}회차"
    md = out_dir / "필기_모의_문제.md"
    if not md.is_file():
        raise SystemExit(f"not found: {md}")
    return md, out_dir


def load_asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def render_html(
    questions: list[dict],
    round_no: int,
    *,
    subject3: bool = False,
    storage_key_name: str | None = None,
) -> str:
    shell_name = "subject3_shell.html" if subject3 else "shell.html"
    shell = load_asset(shell_name)
    css = load_asset("styles.css")
    exam_js = load_asset("exam.js")
    ui_js = load_asset("ui.js")
    key = storage_key_name or (
        subject3_storage_key(round_no) if subject3 else storage_key(round_no)
    )
    duration = SUBJECT3_DURATION_SEC if subject3 else 120 * 60

    html = (
        shell.replace("__ROUND__", str(round_no))
        .replace("__STYLES__", css)
        .replace("__QUESTIONS_JSON__", json.dumps(questions, ensure_ascii=False))
        .replace("__STORAGE_KEY__", key)
        .replace("__EXAM_JS__", exam_js)
        .replace("__UI_JS__", ui_js)
    )
    if subject3:
        html = html.replace("__DURATION_SEC__", str(duration))
    return html


def build_round(round_no: int) -> tuple[Path, int]:
    md_path, out_dir = round_paths(round_no)
    text = md_path.read_text(encoding="utf-8")
    questions = parse_questions(text)
    if len(questions) != EXPECTED_QUESTION_COUNT:
        raise SystemExit(f"expected {EXPECTED_QUESTION_COUNT} questions, got {len(questions)}")

    html = render_html(questions, round_no)
    for name in OUTPUT_HTML_NAMES:
        (out_dir / name).write_text(html, encoding="utf-8")
    return out_dir, len(questions)


def build_subject3_round(round_no: int) -> tuple[Path, int]:
    md_path, out_dir = subject3_paths(round_no)
    text = md_path.read_text(encoding="utf-8")
    questions = parse_questions(text)
    if len(questions) != SUBJECT3_QUESTION_COUNT:
        raise SystemExit(
            f"expected {SUBJECT3_QUESTION_COUNT} questions, got {len(questions)}"
        )

    html = render_html(questions, round_no, subject3=True)
    for name in OUTPUT_HTML_NAMES:
        (out_dir / name).write_text(html, encoding="utf-8")
    return out_dir, len(questions)

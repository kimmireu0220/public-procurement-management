from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=True)
        return
    except ImportError:
        pass
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value


_DEFAULT_ROOT = Path(__file__).resolve().parents[1]
_load_env_file(_DEFAULT_ROOT / ".env")


def get_project_root() -> Path:
    return Path(os.environ.get("PROJECT_ROOT", _DEFAULT_ROOT)).expanduser().resolve()


def get_path(name: str, default: str) -> Path:
    value = os.environ.get(name, default)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = get_project_root() / path
    return path.resolve()


ROOT = get_project_root()

# 시험 과목 번호 ↔ 과목 slug (필기 1~3, 실기 4)
SUBJECT_CATALOG: dict[str, dict[str, str | int]] = {
    "1": {
        "slug": "1과목_공공조달의 이해",
        "exam_name": "공공조달과 법제도 이해",
        "textbook_name": "공공조달의 이해",
        "exam_type": "필기",
        "parts": 7,
    },
    "2": {
        "slug": "2과목_공공조달 계획분석",
        "exam_name": "공공조달계획 수립 및 분석",
        "textbook_name": "공공조달 계획분석",
        "exam_type": "필기",
        "parts": 4,
    },
    "3": {
        "slug": "3과목_공공계약관리",
        "exam_name": "공공계약관리",
        "textbook_name": "공공계약관리",
        "exam_type": "필기",
        "parts": 4,
    },
    "4": {
        "slug": "4과목_공공조달 관리실무",
        "exam_name": "공공조달관리 실무",
        "textbook_name": "공공조달 관리실무",
        "exam_type": "실기",
        "parts": 8,
    },
}

AGENT_EXTRACT_DIR = get_path("AGENT_EXTRACT_DIR", "output/agent_extract")
PROBLEM_BOOK_FINAL_DIR = get_path("PROBLEM_BOOK_FINAL_DIR", "output/problem_book_final")


def subject_extract_dir(subject_no: str) -> Path:
    return AGENT_EXTRACT_DIR / str(SUBJECT_CATALOG[subject_no]["slug"])


def subject_problem_book_dir(subject_no: str) -> Path:
    return PROBLEM_BOOK_FINAL_DIR / str(SUBJECT_CATALOG[subject_no]["slug"])

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
TEXTBOOK_IMAGES_DIR = get_path("TEXTBOOK_IMAGES_DIR", "교재/공공조달의 이해")
OCR_DIR = get_path("OCR_DIR", "output/ocr/공공조달의_이해")
AGENT_EXTRACT_DIR = get_path("AGENT_EXTRACT_DIR", "output/agent_extract")
PROBLEM_BOOK_FINAL_DIR = get_path("PROBLEM_BOOK_FINAL_DIR", "output/problem_book_final")
CHAPTERS_CLEAN_DIR = PROBLEM_BOOK_FINAL_DIR / "chapters_clean"
PROBLEM_BOOK_MD = PROBLEM_BOOK_FINAL_DIR / "공공조달의_이해_문제집.md"
AUDIT_REPORT = PROBLEM_BOOK_FINAL_DIR / "누락_후보_대조.md"
BUILD_REPORT = PROBLEM_BOOK_FINAL_DIR / "검토_요약.md"

#!/usr/bin/env python3
"""최신 회차 CBT index.html → docs/ (GitHub Pages). 정답·md 산출물은 복사하지 않음."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK_ROOT = ROOT / "output" / "mock_exam"
DOCS = ROOT / "docs"
ROUND_DIR = re.compile(r"^(\d+)회차$")


def find_latest_round() -> int:
    rounds: list[int] = []
    for p in MOCK_ROOT.iterdir():
        if not p.is_dir():
            continue
        m = ROUND_DIR.match(p.name)
        if m and (p / "index.html").is_file() and (p / "필기_모의_문제.md").is_file():
            rounds.append(int(m.group(1)))
    if not rounds:
        raise SystemExit(f"no mock exam round with CBT under {MOCK_ROOT}")
    return max(rounds)


def publish_subject3(round_no: int | None = None) -> int:
    k = round_no if round_no is not None else find_latest_subject3_round()
    src = MOCK_ROOT / "3과목" / f"{k}회차" / "index.html"
    if not src.is_file():
        raise SystemExit(
            f"not found: {src} (run build_cbt_viewer.py --subject3 --round {k} first)"
        )

    dest_dir = DOCS / "3과목"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / "index.html")
    (DOCS / ".nojekyll").touch()

    meta = {
        "round": k,
        "subject": 3,
        "total": 30,
        "source": f"output/mock_exam/3과목/{k}회차/index.html",
        "note": "GitHub Pages — 3과목 전용 필기 모의 CBT (정답 미포함)",
    }
    (dest_dir / "cbt-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return k


def find_latest_subject3_round() -> int:
    base = MOCK_ROOT / "3과목"
    rounds: list[int] = []
    if not base.is_dir():
        raise SystemExit(f"no 3과목 mock dir: {base}")
    for p in base.iterdir():
        if not p.is_dir():
            continue
        m = ROUND_DIR.match(p.name)
        if m and (p / "index.html").is_file() and (p / "필기_모의_문제.md").is_file():
            rounds.append(int(m.group(1)))
    if not rounds:
        raise SystemExit(f"no 3과목 mock round with CBT under {base}")
    return max(rounds)


def publish(round_no: int | None = None) -> int:
    k = round_no if round_no is not None else find_latest_round()
    src = MOCK_ROOT / f"{k}회차" / "index.html"
    if not src.is_file():
        raise SystemExit(f"not found: {src} (run build_cbt_viewer.py --round {k} first)")

    DOCS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DOCS / "index.html")
    (DOCS / ".nojekyll").touch()

    meta = {
        "round": k,
        "source": f"output/mock_exam/{k}회차/index.html",
        "note": "GitHub Pages 루트 — 최신 회차 필기 모의 CBT (정답 미포함)",
    }
    (DOCS / "cbt-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return k


def main() -> None:
    parser = argparse.ArgumentParser(description="최신(또는 지정) 회차 CBT → docs/ for GitHub Pages")
    parser.add_argument(
        "--round",
        "-r",
        type=int,
        default=None,
        help="회차 (생략 시 최신 회차)",
    )
    parser.add_argument(
        "--subject3",
        action="store_true",
        help="3과목 전용 → docs/3과목/index.html",
    )
    args = parser.parse_args()
    if args.subject3:
        k = publish_subject3(args.round)
        print(f"GitHub Pages: 3과목 round {k} → docs/3과목/index.html")
    else:
        k = publish(args.round)
        print(f"GitHub Pages: round {k} → docs/index.html")


if __name__ == "__main__":
    main()

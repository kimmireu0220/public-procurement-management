#!/usr/bin/env python3
"""최신 회차 CBT index.html → docs/ (GitHub Pages). 정답·md 산출물은 복사하지 않음."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.paths import FULL_MOCK_ROOT
from cbt.profiles import DOCS, FULL_MOCK, PROFILES  # noqa: E402

ROUND_DIR = re.compile(r"^(\d+)회차$")


def find_latest_round() -> int:
    rounds: list[int] = []
    if not FULL_MOCK_ROOT.is_dir():
        raise SystemExit(f"no integrated mock dir: {FULL_MOCK_ROOT}")
    for p in FULL_MOCK_ROOT.iterdir():
        if not p.is_dir():
            continue
        m = ROUND_DIR.match(p.name)
        if m and (p / "index.html").is_file() and (p / "필기_모의_문제.md").is_file():
            rounds.append(int(m.group(1)))
    if not rounds:
        raise SystemExit(f"no mock exam round with CBT under {FULL_MOCK_ROOT}")
    return max(rounds)


def publish_full(round_no: int | None = None) -> int:
    k = round_no if round_no is not None else find_latest_round()
    src = FULL_MOCK.round_dir(k) / "index.html"
    if not src.is_file():
        raise SystemExit(f"not found: {src} (run build_cbt_viewer.py --round {k} first)")

    DOCS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, FULL_MOCK.docs_index())
    (DOCS / ".nojekyll").touch()

    FULL_MOCK.docs_meta().write_text(
        json.dumps(FULL_MOCK.publish_meta(k), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return k


def publish(round_no: int | None = None) -> int:
    """통합 필기 모의 → docs/index.html"""
    return publish_full(round_no)


def main() -> None:
    parser = argparse.ArgumentParser(description="CBT → docs/ for GitHub Pages")
    parser.add_argument("--round", "-r", type=int, default=None, help="회차 (생략 시 최신)")
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES.keys()),
        default="full",
        help="배포 프로필 (기본 full)",
    )
    parser.add_argument(
        "--subject3",
        action="store_true",
        help="(호환) --profile subject3 와 동일",
    )
    args = parser.parse_args()

    profile_id = "subject3" if args.subject3 else args.profile
    if profile_id == "subject3":
        from subject3.publish import publish as publish_subject3  # noqa: E402

        k = publish_subject3(args.round)
        print(f"GitHub Pages: 3과목 round {k} → docs/3과목/index.html")
    else:
        k = publish_full(args.round)
        print(f"GitHub Pages: round {k} → docs/index.html")


if __name__ == "__main__":
    main()

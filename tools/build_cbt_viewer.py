#!/usr/bin/env python3
"""필기_모의_문제.md → CBT 응시 HTML 생성."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.builder import build_round, build_subject3_round  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="필기_모의_문제.md → CBT HTML")
    parser.add_argument(
        "--round",
        "-r",
        type=int,
        default=1,
        metavar="K",
        help="회차 번호 (기본 1 → output/mock_exam/K회차/ 또는 3과목/K회차/)",
    )
    parser.add_argument(
        "--subject3",
        action="store_true",
        help="3과목 전용 30문항 (output/mock_exam/3과목/K회차/)",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="빌드 후 GitHub Pages용 docs/ 복사",
    )
    args = parser.parse_args()
    if args.round < 1:
        raise SystemExit("--round must be >= 1")

    if args.subject3:
        out_dir, count = build_subject3_round(args.round)
        label = f"3과목/{args.round}회차"
    else:
        out_dir, count = build_round(args.round)
        label = f"{args.round}회차"
    print(f"CBT viewer: {label}, {count} questions → {out_dir}")

    if args.pages:
        if args.subject3:
            from publish_cbt_pages import publish_subject3  # noqa: E402

            k = publish_subject3(args.round)
            print(f"GitHub Pages: docs/3과목/index.html ← 3과목 round {k}")
        else:
            from publish_cbt_pages import publish  # noqa: E402

            k = publish()
            print(f"GitHub Pages: docs/index.html ← round {k}")


if __name__ == "__main__":
    main()

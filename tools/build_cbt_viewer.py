#!/usr/bin/env python3
"""필기_모의_문제.md → CBT 응시 HTML 생성."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.builder import build_round  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="필기_모의_문제.md → CBT HTML")
    parser.add_argument(
        "--round",
        "-r",
        type=int,
        default=1,
        metavar="K",
        help="모의 회차 번호 (기본 1 → output/mock_exam/K회차/)",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="빌드 후 최신 회차 CBT를 docs/index.html 로 복사 (GitHub Pages)",
    )
    args = parser.parse_args()
    if args.round < 1:
        raise SystemExit("--round must be >= 1")

    out_dir, count = build_round(args.round)
    print(f"CBT viewer: round {args.round}, {count} questions → {out_dir}")

    if args.pages:
        from publish_cbt_pages import publish  # noqa: E402

        k = publish()
        print(f"GitHub Pages: docs/index.html ← round {k}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""3과목 전용 draft 병합 — `tools/subject3/merge.py` 진입점."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from subject3.merge import merge_round  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="3과목 전용 mock draft 병합")
    parser.add_argument("round", type=int, nargs="?", default=1, help="회차 번호")
    args = parser.parse_args()
    n = merge_round(args.round)
    print(f"merged {n} questions → output/mock_exam/필기/3과목/{args.round}회차/")


if __name__ == "__main__":
    main()

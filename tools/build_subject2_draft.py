#!/usr/bin/env python3
"""2과목 선별 draft 생성 — `tools/subject2/build_draft.py` 진입점."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from subject2.build_draft import build_draft  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="2과목 선별 draft 생성")
    parser.add_argument("round", type=int, nargs="?", default=1)
    args = parser.parse_args()
    p = build_draft(args.round)
    print(f"draft → {p}")


if __name__ == "__main__":
    main()

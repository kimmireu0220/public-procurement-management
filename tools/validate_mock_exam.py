#!/usr/bin/env python3
"""필기·실기 모의고사와 GitHub Pages 배포본을 일괄 검증한다."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.validation import validate_all  # noqa: E402


def main() -> None:
    root = TOOLS_DIR.parent
    rounds, items, practical_rounds, issues = validate_all(root)
    if issues:
        print(
            f"검증 실패: 필기 {rounds}회차 · {items}문항 · "
            f"실기 {practical_rounds}회차 · {len(issues)}건"
        )
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)
    print(
        f"검증 통과: 필기 {rounds}회차 · {items}문항 · "
        f"실기 {practical_rounds}회차 · Pages 4종"
    )


if __name__ == "__main__":
    main()

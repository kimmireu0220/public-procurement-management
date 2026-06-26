#!/usr/bin/env python3
"""에이전트 draft → 필기_모의_문제.md / 필기_모의_정답.md / manifest.json 병합."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from mock_exam_common import (  # noqa: E402
    MOCK_ROOT_DEFAULT,
    build_mock_exam_player_for_round,
    collect_prior_ids,
    collect_prior_stems,
    coverage_report,
    load_all_pools,
    load_from_draft,
    validate_selected,
    write_round_files,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge agent draft into final mock exam")
    parser.add_argument("round", type=int)
    parser.add_argument("--mock-root", type=Path, default=MOCK_ROOT_DEFAULT)
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="병합만 하고 validate 생략 (권장하지 않음)",
    )
    parser.add_argument(
        "--note",
        type=str,
        default=None,
        help="문제지 상단 선별 기준 한 줄 (markdown blockquote 내용)",
    )
    args = parser.parse_args()

    round_dir = args.mock_root / f"{args.round}회차"
    pools = load_all_pools()
    selected = load_from_draft(round_dir, pools)

    if not args.skip_validate:
        errors = validate_selected(
            selected,
            prior_ids=collect_prior_ids(args.mock_root, args.round),
            prior_stems=collect_prior_stems(args.mock_root, args.round),
        )
        if errors:
            print("Draft 검증 실패 (병합 중단):")
            for e in errors:
                print(f"  - {e}")
            raise SystemExit(1)

    note = args.note or (
        "> 선별: 에이전트 검토 후 확정 · merge_mock_draft.py"
        + (
            ""
            if args.round <= 1
            else f" · {args.round - 1}회차 이전 미출제"
        )
    )
    write_round_files(args.round, selected, round_dir, method="agent", note=note)
    print(coverage_report(selected))
    print(f"Wrote {round_dir}/필기_모의_문제.md, 필기_모의_정답.md, manifest.json")
    html = build_mock_exam_player_for_round(args.round, mock_root=args.mock_root)
    print(f"응시 UI: {html}")


if __name__ == "__main__":
    main()

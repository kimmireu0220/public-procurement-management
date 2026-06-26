#!/usr/bin/env python3
"""모의고사 회차 검증 (생성 없음) — 형식·중복·상한."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from mock_exam_common import (  # noqa: E402
    MOCK_ROOT_DEFAULT,
    backfill_manifest,
    collect_prior_ids,
    collect_prior_stems,
    coverage_report,
    load_all_pools,
    load_from_draft,
    load_manifest,
    match_questions_from_problem_md,
    questions_from_ids,
    validate_selected,
)


def load_from_manifest(round_dir: Path, pools: dict) -> dict:
    manifest = load_manifest(round_dir)
    if not manifest:
        raise FileNotFoundError(f"{round_dir}/manifest.json 없음")
    by_subject: dict[str, list[str]] = {"1": [], "2": [], "3": []}
    for item in manifest.get("items", []):
        sn = str(item["subject"])
        by_subject[sn].append(str(item["id"]))
    selected: dict = {}
    for sn in ("1", "2", "3"):
        selected[sn] = questions_from_ids(sn, by_subject[sn], pools[sn])
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate mock exam round")
    parser.add_argument("round", type=int, help="Round number")
    parser.add_argument("--mock-root", type=Path, default=MOCK_ROOT_DEFAULT)
    parser.add_argument(
        "--source",
        choices=("final", "draft", "manifest"),
        default="final",
        help="검증 대상: final=필기_모의_문제.md, draft=_draft/, manifest=manifest.json",
    )
    parser.add_argument(
        "--backfill-manifest",
        action="store_true",
        help="manifest 없으면 필기_모의_문제.md에서 소급 생성",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="스크립트 생성 구회차용: 클러스터 상한 검증 생략",
    )
    args = parser.parse_args()

    round_dir = args.mock_root / f"{args.round}회차"
    pools = load_all_pools()

    if args.backfill_manifest:
        data = backfill_manifest(round_dir, pools)
        if data:
            print(f"Wrote manifest.json ({data['total']} items)")
        else:
            print("Backfill skipped (no problem file or not 80 questions)")

    prior_ids = collect_prior_ids(args.mock_root, args.round)
    prior_stems = collect_prior_stems(args.mock_root, args.round)

    if args.source == "draft":
        selected = load_from_draft(round_dir, pools)
    elif args.source == "manifest":
        selected = load_from_manifest(round_dir, pools)
    else:
        if load_manifest(round_dir) and (round_dir / "필기_모의_문제.md").is_file():
            try:
                selected = load_from_manifest(round_dir, pools)
            except (KeyError, ValueError):
                selected = match_questions_from_problem_md(
                    round_dir / "필기_모의_문제.md", pools
                )
        else:
            selected = match_questions_from_problem_md(
                round_dir / "필기_모의_문제.md", pools
            )

    errors = validate_selected(
        selected,
        prior_ids=prior_ids,
        prior_stems=prior_stems,
        check_clusters=not args.legacy,
    )
    print(coverage_report(selected))

    if errors:
        print("\n검증 실패:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)

    total = sum(len(selected[sn]) for sn in ("1", "2", "3"))
    print(f"\nOK: {args.round}회차 {total}문항 ({args.source})")


if __name__ == "__main__":
    main()

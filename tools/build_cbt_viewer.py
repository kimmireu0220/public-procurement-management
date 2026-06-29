#!/usr/bin/env python3
"""필기_모의_문제.md → CBT 응시 HTML 생성."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.builder import build_for_profile  # noqa: E402
from cbt.profiles import FULL_MOCK, PROFILES, SUBJECT1, SUBJECT2, SUBJECT3  # noqa: E402


def resolve_profile(args: argparse.Namespace):
    if args.profile:
        if args.profile not in PROFILES:
            raise SystemExit(f"unknown profile: {args.profile} (choose: {', '.join(PROFILES)})")
        return PROFILES[args.profile]
    if args.subject3:
        return SUBJECT3
    return FULL_MOCK


def main() -> None:
    parser = argparse.ArgumentParser(description="필기_모의_문제.md → CBT HTML")
    parser.add_argument(
        "--round",
        "-r",
        type=int,
        default=1,
        metavar="K",
        help="회차 번호",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES.keys()),
        default=None,
        help="CBT 프로필 (full=통합 80문항, subject1=1과목 30, subject2=2과목 20, subject3=3과목 30)",
    )
    parser.add_argument(
        "--subject3",
        action="store_true",
        help="(호환) --profile subject3 와 동일",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="빌드 후 GitHub Pages용 docs/ 복사",
    )
    args = parser.parse_args()
    if args.round < 1:
        raise SystemExit("--round must be >= 1")

    profile = resolve_profile(args)
    out_dir, count = build_for_profile(args.round, profile)
    print(f"CBT viewer: {profile.id} round {args.round}, {count} questions → {out_dir}")

    if args.pages:
        if profile.id == "subject1":
            from subject1.publish import publish  # noqa: E402

            k = publish(args.round)
            print(f"GitHub Pages: docs/1과목/index.html ← 1과목 round {k}")
        elif profile.id == "subject2":
            from subject2.publish import publish  # noqa: E402

            k = publish(args.round)
            print(f"GitHub Pages: docs/2과목/index.html ← 2과목 round {k}")
        elif profile.id == "subject3":
            from subject3.publish import publish  # noqa: E402

            k = publish(args.round)
            print(f"GitHub Pages: docs/3과목/index.html ← 3과목 round {k}")
        else:
            from publish_cbt_pages import publish  # noqa: E402

            k = publish(args.round)
            print(f"GitHub Pages: docs/index.html ← round {k}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""회차별 CBT index.html을 GitHub Pages용 docs/에 배포한다."""

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

from cbt.profiles import CbtProfile, DOCS, PROFILES  # noqa: E402
from site_portal import render_portal  # noqa: E402

ROUND_DIR = re.compile(r"^(\d+)회차$")


def find_rounds(profile: CbtProfile) -> list[int]:
    base = profile.round_dir(1).parent
    rounds: list[int] = []
    if not base.is_dir():
        raise SystemExit(f"no {profile.id} mock dir: {base}")
    for path in base.iterdir():
        match = ROUND_DIR.match(path.name) if path.is_dir() else None
        if match is None:
            continue
        round_no = int(match.group(1))
        if (path / "index.html").is_file() and profile.problem_md(round_no).is_file():
            rounds.append(round_no)
    if not rounds:
        raise SystemExit(f"no {profile.id} mock round with CBT under {base}")
    return sorted(rounds)


def find_latest_round(profile: CbtProfile) -> int:
    return find_rounds(profile)[-1]


def full_round_index(round_no: int) -> Path:
    return DOCS / "mock" / f"{round_no}회차" / "index.html"


def render_full_round_list(rounds: list[int]) -> str:
    """이전 호출부와 호환되는 통합 학습 홈 렌더러."""

    return render_portal(rounds)


def publish_full_profile(profile: CbtProfile, selected_round: int) -> None:
    rounds = find_rounds(profile)
    if selected_round not in rounds:
        raise SystemExit(f"full mock round {selected_round} has no built CBT")

    published_rounds: list[dict[str, object]] = []
    for round_no in rounds:
        source = profile.round_dir(round_no) / "index.html"
        destination = full_round_index(round_no)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        published_rounds.append(
            {
                "round": round_no,
                "source": f"output/{profile.source_label(round_no)}",
                "published": str(destination.relative_to(DOCS)),
            }
        )

    profile.docs_index().write_text(render_full_round_list(rounds), encoding="utf-8")
    profile.docs_meta().write_text(
        json.dumps(
            {
                "rounds": published_rounds,
                "note": "GitHub Pages 루트 — 통합 필기 모의고사 회차 선택",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def publish_profile(profile: CbtProfile, round_no: int | None = None) -> int:
    """CBT를 프로필별 docs 경로에 배포한다."""

    selected_round = round_no if round_no is not None else find_latest_round(profile)
    source = profile.round_dir(selected_round) / "index.html"
    if not source.is_file():
        raise SystemExit(
            f"not found: {source} "
            f"(run build_cbt_viewer.py --profile {profile.id} --round {selected_round} first)"
        )

    (DOCS / ".nojekyll").touch()
    if profile.id == "full":
        publish_full_profile(profile, selected_round)
        return selected_round

    destination = profile.docs_index()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    profile.docs_meta().write_text(
        json.dumps(profile.publish_meta(selected_round), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return selected_round


def main() -> None:
    parser = argparse.ArgumentParser(description="CBT → docs/ for GitHub Pages")
    parser.add_argument("--round", "-r", type=int, default=None, help="회차 (생략 시 최신)")
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="full",
        help="배포 프로필 (기본 full)",
    )
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    round_no = publish_profile(profile, args.round)
    print(f"GitHub Pages: {profile.id} round {round_no} → {profile.docs_index()}")


if __name__ == "__main__":
    main()

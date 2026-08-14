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
    """통합 필기 모의고사의 GitHub Pages 회차 선택 화면을 만든다."""

    latest = max(rounds)
    items = "\n".join(
        f'<li><a href="mock/{round_no}회차/">필기 모의고사 {round_no}회차</a>'
        f" — 80문항 · 120분{' · 최신' if round_no == latest else ''}</li>"
        for round_no in rounds
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>공공조달관리사 필기 모의고사 CBT</title>
<style>
body {{ font-family: "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
h1 {{ color: #0f3460; font-size: 1.5rem; }}
h2 {{ color: #1a4d8f; font-size: 1.15rem; margin-top: 1.75rem; border-bottom: 2px solid #c5d0de; padding-bottom: .35rem; }}
a {{ color: #1a4d8f; }}
ul {{ padding-left: 1.25rem; }}
li {{ margin: .55rem 0; }}
.note {{ background: #f0f6fc; border-left: 4px solid #1a4d8f; padding: .75rem 1rem; margin: 1rem 0; font-size: .92rem; }}
</style>
</head>
<body>
<h1>공공조달관리사 필기 모의고사 CBT</h1>
<p>응시할 회차를 선택하세요. 회차별 답안은 브라우저에 각각 따로 저장됩니다.</p>
<div class="note">통합 모의고사 · 80문항(1과목 30, 2과목 20, 3과목 30) · 120분</div>
<h2>회차 선택</h2>
<ul>
{items}
</ul>
<h2>다른 학습</h2>
<ul>
<li><a href="lecture/"><strong>과목별·Chapter별 이론 강의</strong></a> — 1과목 29개 Chapter 및 총정리</li>
<li><a href="study/">문제은행 Part별 학습 CBT</a></li>
<li><a href="1과목/">1과목 전용 모의 CBT</a></li>
<li><a href="2과목/">2과목 전용 모의 CBT</a></li>
<li><a href="3과목/">3과목 전용 모의 CBT</a></li>
</ul>
</body>
</html>
"""


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

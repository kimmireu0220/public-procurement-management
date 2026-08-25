#!/usr/bin/env python3
"""민간 문제은행을 공개하지 않고 자체 강의 연습문제로 안내하는 페이지를 생성한다."""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

from cbt.profiles import DOCS

OUTPUT_DIR = DOCS / "study"

LANDING_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="공공조달관리사 1·2·3과목 전체 문제은행 CBT">
<title>과목별 전체 문제은행 CBT</title>
<style>
:root { --bg:#f4f7fb; --paper:#fff; --navy:#102f50; --blue:#1763a6; --line:#dbe4ee; --muted:#647386; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:#172331; font-family:"Apple SD Gothic Neo","Malgun Gothic",sans-serif; line-height:1.65; }
main { max-width:760px; margin:0 auto; padding:clamp(1.5rem,5vw,4rem) 1rem; }
.card { padding:clamp(1.4rem,4vw,2.4rem); border:1px solid var(--line); border-radius:16px; background:var(--paper); box-shadow:0 8px 24px rgba(16,47,80,.08); }
h1 { margin:.2rem 0 .8rem; color:var(--navy); font-size:clamp(1.7rem,5vw,2.35rem); }
p { margin:.75rem 0; }
.note { color:var(--muted); }
.actions { display:flex; flex-wrap:wrap; gap:.7rem; margin-top:1.5rem; }
a { display:inline-block; padding:.72rem 1rem; border-radius:9px; background:var(--blue); color:#fff; text-decoration:none; font-weight:700; }
a.secondary { border:1px solid var(--line); background:#fff; color:var(--navy); }
</style>
</head>
<body>
<main><section class="card">
  <span>PUBLIC PROCUREMENT MANAGER</span>
  <h1>과목별 전체 문제은행 CBT</h1>
  <p>1·2·3과목의 전체 문제를 Part별 CBT로 학습합니다.</p>
  <p class="note">총 1,395문항이며 답안을 제출하면 점수와 문항별 선택답·정답을 바로 확인할 수 있습니다.</p>
  <div class="actions"><a href="../1과목/">1과목 · 670문항</a><a href="../2과목/">2과목 · 335문항</a><a href="../3과목/">3과목 · 390문항</a><a class="secondary" href="../">학습센터 홈</a></div>
</section></main>
</body>
</html>
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / "index.html", LANDING_HTML)


def compare_trees(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = (
        {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()}
        if actual.exists()
        else set()
    )
    legacy_cbt = re.compile(r"[123]과목-part\d+-exam/index\.html")
    actual_files = {path for path in actual_files if not legacy_cbt.fullmatch(path.as_posix())}
    errors = [f"누락 공개 파일: {path}" for path in sorted(expected_files - actual_files)]
    errors.extend(f"불필요 공개 파일: {path}" for path in sorted(actual_files - expected_files))
    for relative in sorted(expected_files & actual_files):
        if (expected / relative).read_bytes() != (actual / relative).read_bytes():
            errors.append(f"생성 결과 불일치: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="현재 공개본이 최신 생성 결과와 같은지 확인")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-guide-") as temp_dir:
        generated = Path(temp_dir) / "study"
        build(generated)
        if args.check:
            errors = compare_trees(generated, OUTPUT_DIR)
            if errors:
                for error in errors:
                    print(error)
                return 1
            print("학습 안내 검증 완료: 민간 문제은행 공개물 0개")
            return 0

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated / "index.html", OUTPUT_DIR / "index.html")

    print(f"학습 안내 생성 완료: 자체 강의 연습문제로 연결 → {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""과목별 필기 CBT와 실기 문제은행 안내 페이지를 생성한다."""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT_DIR = DOCS / "study"

LANDING_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="공공조달관리사 1·2·3과목 필기 CBT와 4과목 실기 문제은행">
<meta name="theme-color" content="#123b66">
<title>과목별 전체 문제은행 CBT</title>
<style>
:root { --bg:#f4f7fb; --paper:#fff; --navy:#0b2b4b; --blue:#1769aa; --line:#d5e0eb; --muted:#5d6e81; --focus:#f2a93b; }
* { box-sizing:border-box; }
body { min-height:100vh; margin:0; background:linear-gradient(145deg,#edf4fa,var(--bg) 42%); color:#172535; font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif; line-height:1.65; word-break:keep-all; }
main { max-width:900px; margin:0 auto; padding:clamp(1.25rem,5vw,4rem) 1rem; }
.card { padding:clamp(1.35rem,4vw,2.6rem); border:1px solid var(--line); border-radius:18px; background:var(--paper); box-shadow:0 12px 34px rgba(16,47,80,.09); }
.eyebrow { color:var(--blue); font-size:.78rem; font-weight:850; letter-spacing:.1em; }
h1 { margin:.3rem 0 .8rem; color:var(--navy); font-size:clamp(1.8rem,5vw,2.55rem); line-height:1.2; letter-spacing:-.025em; }
p { margin:.75rem 0; }
.note { color:var(--muted); }
.actions { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.7rem; margin-top:1.5rem; }
a { display:flex; min-height:52px; align-items:center; justify-content:space-between; padding:.72rem 1rem; border:1px solid #8fb6d6; border-radius:10px; background:#f7fbfe; color:var(--navy); text-decoration:none; font-weight:800; }
a::after { content:"→"; color:var(--blue); }
a:hover { border-color:var(--blue); background:#eaf4fc; }
a.secondary { grid-column:1/-1; justify-content:center; border-color:var(--line); background:#fff; }
a.secondary::after { content:""; }
a:focus-visible { outline:3px solid var(--focus); outline-offset:3px; }
@media(max-width:560px){.actions{grid-template-columns:1fr}.card{border-radius:14px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
</head>
<body>
<main><section class="card">
  <span class="eyebrow">PUBLIC PROCUREMENT MANAGER</span>
  <h1>과목별 전체 문제은행 CBT</h1>
  <p>1·2·3과목 필기 문제와 4과목 서술형 문제를 과목별로 한 번에 학습합니다.</p>
  <p class="note">전체 2,639문항입니다. 필기는 답안 선택 즉시 채점하며, 4과목은 모범답안과 비교해 직접 판정합니다.</p>
  <div class="actions"><a href="../1과목/">1과목 · 670문항</a><a href="../2과목/">2과목 · 335문항</a><a href="../3과목/">3과목 · 390문항</a><a href="../4과목/">4과목 · 1,244문항</a><a class="secondary" href="../">학습센터 홈</a></div>
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
            print("학습 안내 페이지 검증 완료")
            return 0

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated / "index.html", OUTPUT_DIR / "index.html")

    print(f"학습 안내 생성 완료: 1~4과목 문제은행 연결 → {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

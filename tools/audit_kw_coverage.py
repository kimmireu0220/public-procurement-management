#!/usr/bin/env python3
"""문제 풀 kw 커버리지 감사 리포트."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import ROOT  # noqa: E402
from mock_exam_common import (  # noqa: E402
    PLACEHOLDER_KW,
    load_all_pools,
    load_manifest,
    MOCK_ROOT_DEFAULT,
)


def audit(mock_root: Path) -> str:
    pools = load_all_pools()
    total = sum(len(p) for p in pools.values())
    no_kw = no_ans = placeholder = stem_dup = short_kw = 0
    by_subject = Counter()
    issues: list[str] = []

    for sn, pool in pools.items():
        for qid, q in pool.items():
            kw = (q.kw or "").strip()
            if not q.ans:
                no_ans += 1
                by_subject[f"{sn} no_ans"] += 1
            if not kw:
                no_kw += 1
                by_subject[f"{sn} no_kw"] += 1
            elif kw == PLACEHOLDER_KW:
                placeholder += 1
            elif kw == q.stem.strip():
                stem_dup += 1
                issues.append(f"- `{qid}` stem==kw")
            elif len(kw) < 12:
                short_kw += 1

    used_no_kw = 0
    for d in sorted(mock_root.glob("*회차")):
        m = load_manifest(d)
        if not m:
            continue
        for item in m.get("items", []):
            q = pools[item["subject"]][item["id"]]
            if not (q.kw or "").strip():
                used_no_kw += 1

    lines = [
        f"# kw 커버리지 리포트 ({date.today().isoformat()})",
        "",
        "## 요약",
        "",
        f"| 항목 | 문항 수 |",
        f"|------|--------:|",
        f"| 전체 풀 | {total} |",
        f"| kw 없음 | {no_kw} |",
        f"| 정답 없음 | {no_ans} |",
        f"| placeholder | {placeholder} |",
        f"| kw==지문 | {stem_dup} |",
        f"| kw 12자 미만 | {short_kw} |",
        f"| 모의 출제 kw 없음 | {used_no_kw} |",
        "",
        "## 과목별 kw 없음",
        "",
    ]
    for sn in ("1", "2", "3"):
        n = sum(1 for q in pools[sn].values() if not (q.kw or "").strip())
        lines.append(f"- {sn}과목: {n}/{len(pools[sn])}")
    if issues[:20]:
        lines += ["", "## kw==지문 샘플", ""] + issues[:20]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "output/kw_커버리지.md",
    )
    parser.add_argument("--mock-root", type=Path, default=MOCK_ROOT_DEFAULT)
    args = parser.parse_args()
    report = audit(args.mock_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out}")
    print(report.split("## 요약")[1][:400])


if __name__ == "__main__":
    main()

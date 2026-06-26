#!/usr/bin/env python3
"""문제 풀 kw 커버리지·품질 감사 리포트."""

from __future__ import annotations

import argparse
import json
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
    correct_choice_text,
    load_all_pools,
    load_manifest,
    MOCK_ROOT_DEFAULT,
)

TEMPLATE_MARK = "오답 선지는 요건·효과·주체를 혼동하거나 반대로 서술했다."


def collect_stats(mock_root: Path) -> dict:
    pools = load_all_pools()
    total = sum(len(p) for p in pools.values())
    no_kw = no_ans = placeholder = stem_dup = short_kw = choice_only = template_kw = 0
    choice_items: list[str] = []
    short_items: list[str] = []
    template_items: list[str] = []
    mock_choice: list[str] = []
    mock_template: list[str] = []

    for sn, pool in pools.items():
        for qid, q in pool.items():
            kw = (q.kw or "").strip()
            ct = correct_choice_text(q)
            if not q.ans:
                no_ans += 1
            if not kw:
                no_kw += 1
            elif kw == PLACEHOLDER_KW:
                placeholder += 1
            elif kw == q.stem.strip():
                stem_dup += 1
            elif ct and kw == ct:
                choice_only += 1
                choice_items.append(qid)
            elif TEMPLATE_MARK in kw:
                template_kw += 1
                template_items.append(qid)
            elif len(kw) < 12 and q.stype != "ox":
                short_kw += 1
                short_items.append(f"{qid}: {kw!r}")

    for d in sorted(mock_root.glob("*회차")):
        m = load_manifest(d)
        if not m:
            continue
        for item in m.get("items", []):
            q = pools[item["subject"]][item["id"]]
            kw = (q.kw or "").strip()
            if not kw:
                mock_choice.append(f"{d.name} #{item['exam_num']} kw없음")
            else:
                ct = correct_choice_text(q)
                if ct and kw == ct:
                    mock_choice.append(f"{d.name} #{item['exam_num']} {item['id']}")
                elif TEMPLATE_MARK in kw:
                    mock_template.append(f"{d.name} #{item['exam_num']} {item['id']}")

    return {
        "total": total,
        "no_kw": no_kw,
        "no_ans": no_ans,
        "placeholder": placeholder,
        "stem_dup": stem_dup,
        "short_kw": short_kw,
        "choice_only": choice_only,
        "template_kw": template_kw,
        "choice_items": choice_items,
        "template_items": template_items,
        "short_items": short_items,
        "mock_issues": mock_choice,
        "mock_template": mock_template,
        "pools": pools,
    }


def audit_basic(stats: dict) -> str:
    pools = stats["pools"]
    lines = [
        f"# kw 커버리지 리포트 ({date.today().isoformat()})",
        "",
        "## 요약",
        "",
        "| 항목 | 문항 수 |",
        "|------|--------:|",
        f"| 전체 풀 | {stats['total']} |",
        f"| kw 없음 | {stats['no_kw']} |",
        f"| 정답 없음 | {stats['no_ans']} |",
        f"| placeholder | {stats['placeholder']} |",
        f"| kw==지문 | {stats['stem_dup']} |",
        f"| kw==정답선지 | {stats['choice_only']} |",
        f"| craft_kw 템플릿 | {stats['template_kw']} |",
        f"| kw 12자 미만 (OX 제외) | {stats['short_kw']} |",
        f"| 모의 kw 이슈 | {len(stats['mock_issues'])} |",
        f"| 모의 템플릿 | {len(stats['mock_template'])} |",
        "",
        "## 과목별 kw 없음",
        "",
    ]
    for sn in ("1", "2", "3"):
        n = sum(1 for q in pools[sn].values() if not (q.kw or "").strip())
        lines.append(f"- {sn}과목: {n}/{len(pools[sn])}")
    return "\n".join(lines) + "\n"


def audit_quality(stats: dict) -> str:
    lines = [
        f"# kw 품질 리포트 ({date.today().isoformat()})",
        "",
        "## 요약",
        "",
        f"| 항목 | 문항 수 |",
        f"|------|--------:|",
        f"| kw==정답선지 | {stats['choice_only']} |",
        f"| craft_kw 템플릿 | {stats['template_kw']} |",
        f"| kw 12자 미만 | {stats['short_kw']} |",
        f"| 모의 이슈 | {len(stats['mock_issues'])} |",
        f"| 모의 템플릿 | {len(stats['mock_template'])} |",
        "",
    ]
    if stats["template_items"][:30]:
        lines += ["## 템플릿 kw 샘플 (30)", ""]
        for qid in stats["template_items"][:30]:
            lines.append(f"- `{qid}`")
    if stats["mock_issues"]:
        lines += ["## 모의 출제 (kw==선지 또는 없음)", ""]
        for row in stats["mock_issues"]:
            lines.append(f"- {row}")
    if stats["choice_items"][:30]:
        lines += ["", "## kw==선지 샘플 (30)", ""]
        for qid in stats["choice_items"][:30]:
            lines.append(f"- `{qid}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="리포트 경로 (미지정 시 stdout 요약만)",
    )
    parser.add_argument("--mock-root", type=Path, default=MOCK_ROOT_DEFAULT)
    parser.add_argument(
        "--quality",
        action="store_true",
        help="품질 모드 (kw==선지·짧은 kw·모의 목록)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="통계 JSON 저장 (품질 대상 추출용)",
    )
    args = parser.parse_args()

    stats = collect_stats(args.mock_root)
    report = audit_quality(stats) if args.quality else audit_basic(stats)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in stats.items() if k != "pools"}
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(report.split("## 요약")[1][:500])


if __name__ == "__main__":
    main()

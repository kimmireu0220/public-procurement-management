#!/usr/bin/env python3
"""모의고사 K회차 에이전트 출제용 브리핑·후보 shortlist 생성."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import SUBJECT_CATALOG  # noqa: E402
from mock_exam_common import (  # noqa: E402
    CLUSTER_MAX,
    FILGI_COUNTS,
    MOCK_ROOT_DEFAULT,
    TOPIC_MAX,
    backfill_manifest,
    collect_prior_ids,
    collect_prior_stems,
    format_candidate_entry,
    hint_rank,
    load_all_pools,
    load_subject_pool,
)

AGENT_WORKFLOW = """\
## 에이전트 워크플로 (K회차)

1. **과목별 선별** — `_candidates/{N}과목_part*.md` 에서만 고른다.
   - 산출: `_draft/{N}과목_선별.md` (문항 전문 + `<!-- id: ... -->` 유지)
   - 또는 `_draft/manifest.json` 에 id 목록만 기록
2. **교차 검수** — `docs/문제집_프롬프트/시험모의_선별.md` A-3 프롬프트
3. **병합** — `python3 tools/merge_mock_draft.py {K}` (HTML + 브라우저 자동 열기)
4. **검증** — `python3 tools/validate_mock_exam.py {K}`

급할 때 초안: `python3 tools/select_mock_exam.py {K} --importance` 후 에이전트가 10~15문항만 교체.
"""


def subject_slug(sn: str) -> str:
    return str(SUBJECT_CATALOG[sn]["slug"])


def build_briefing(
    round_num: int,
    prior_ids: set[str],
    prior_stems_count: int,
    pool_stats: dict[str, dict],
    mock_root: Path,
) -> str:
    prior_line = (
        "- 이전 회차 없음 (첫 회차)"
        if round_num <= 1
        else f"- 이전 회차({round_num - 1}회차까지) 사용 id **{len(prior_ids)}개** 제외"
    )
    prior_stem_line = (
        "- 이전 회차 사용 지문 없음"
        if round_num <= 1
        else f"- 이전 회차 사용 지문 **{prior_stems_count}개** 제외"
    )
    lines = [
        f"# 모의고사 {round_num}회차 — 에이전트 출제 브리핑",
        "",
        f"> 생성: `prepare_mock_round.py {round_num}`",
        "",
        "## 시험 규모",
        "",
        "| 과목 | 문항 | 번호 |",
        "|------|-----:|------|",
        "| 1 공공조달과 법제도 | 30 | 1~30 |",
        "| 2 계획 수립·분석 | 20 | 31~50 |",
        "| 3 공공계약관리 | 30 | 51~80 |",
        "",
        "## 금지·상한",
        "",
        "- OX / (O/X) 문항 제외",
        "- Check Q&A: 과목당 20% 이하",
        prior_line,
        prior_stem_line,
        "",
        "### 주제 상한 (회차 전체 80문항)",
        "",
    ]
    for tag, mx in sorted(TOPIC_MAX.items()):
        lines.append(f"- `{tag}`: 최대 {mx}문항")
    lines.append("")
    lines.append("### 의미 클러스터 상한")
    lines.append("")
    for tag, mx in sorted(CLUSTER_MAX.items()):
        lines.append(f"- `{tag}`: 최대 {mx}문항")
    lines.append("")
    lines.append("## 과목별 후보 풀 (이번 회차 선별 가능)")
    lines.append("")
    for sn in ("1", "2", "3"):
        st = pool_stats[sn]
        lines.append(
            f"- **{sn}과목** ({subject_slug(sn)}): "
            f"전체 {st['total']} · 정답있음 {st['with_ans']} · "
            f"**선별가능 {st['eligible']}** / 목표 {FILGI_COUNTS[sn]}"
        )
    lines.append("")
    lines.append("## 후보 파일")
    lines.append("")
    lines.append("`_candidates/{N}과목_part{NN}.md` — Part별 eligible 문항 (`hint_rank` 높을수록 우선 검토)")
    lines.append("")
    lines.append("## 참고 문서")
    lines.append("")
    lines.append("- `docs/문제집_프롬프트/시험모의_선별.md`")
    lines.append("- `docs/시험_안내.md`")
    lines.append("- `_draft/README.md`")
    lines.append("")
    lines.append(AGENT_WORKFLOW.replace("{K}", str(round_num)))
    return "\n".join(lines)


def write_candidates(
    round_dir: Path,
    prior_ids: set[str],
    prior_stems: set[str],
) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    cand_dir = round_dir / "_candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)

    for sn in ("1", "2", "3"):
        pool = load_subject_pool(sn)
        eligible = [
            q
            for q in pool
            if q.ans
            and q.stable_id() not in prior_ids
            and q.stem not in prior_stems
        ]
        by_part: dict[int, list] = defaultdict(list)
        for q in eligible:
            by_part[q.part].append(q)
        for part in sorted(by_part):
            ranked = sorted(
                by_part[part],
                key=lambda q, s=sn: hint_rank(q, s),
                reverse=True,
            )
            slug = subject_slug(sn).replace(" ", "_")
            out_path = cand_dir / f"{sn}과목_part{part:02d}.md"
            header = [
                f"# {sn}과목 Part {part:02d} — 선별 후보",
                "",
                f"> eligible {len(ranked)}문항 · 목표 과목 합계 {FILGI_COUNTS[sn]}",
                "> `_candidates` 에서만 선별. 각 문항 `<!-- id: ... -->` 를 manifest에 기록.",
                "",
            ]
            body = [format_candidate_entry(q, sn, hint_rank(q, sn)) for q in ranked]
            out_path.write_text("\n".join(header + body), encoding="utf-8")

        stats[sn] = {
            "total": len(pool),
            "with_ans": sum(1 for q in pool if q.ans),
            "eligible": len(eligible),
        }
    return stats


def write_draft_readme(round_dir: Path, round_num: int) -> None:
    draft = round_dir / "_draft"
    draft.mkdir(parents=True, exist_ok=True)
    text = f"""# {round_num}회차 초안 폴더

에이전트가 과목별 선별 결과를 여기에 둔다.

## 방식 A (권장): manifest.json

```json
{{
  "round": {round_num},
  "subjects": {{
    "1": ["1:1:1:exam:3", "..."],
    "2": ["2:1:2:check:5", "..."],
    "3": ["3:2:1:exam:1", "..."]
  }}
}}
```

## 방식 B: 과목별 MD

- `1과목_선별.md` (30문항)
- `2과목_선별.md` (20문항)
- `3과목_선별.md` (30문항)

각 문항에 `<!-- id: 과목:part:chapter:stype:qn -->` 필수.

## 다음 단계

```bash
python3 tools/merge_mock_draft.py {round_num}   # HTML + 브라우저 자동 열기
python3 tools/validate_mock_exam.py {round_num}
```
"""
    (draft / "README.md").write_text(text, encoding="utf-8")


def write_manifest_template(round_dir: Path, round_num: int) -> None:
    template = {
        "round": round_num,
        "method": "agent",
        "subjects": {"1": [], "2": [], "3": []},
        "notes": "에이전트가 id 목록을 채운 뒤 merge_mock_draft.py 실행",
    }
    path = round_dir / "_manifest.template.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def backfill_prior_manifests(mock_root: Path, before_round: int) -> list[str]:
    pools = load_all_pools()
    done: list[str] = []
    for d in sorted(mock_root.glob("*회차")):
        m = re.match(r"(\d+)회차", d.name)
        if not m or int(m.group(1)) >= before_round:
            continue
        if backfill_manifest(d, pools):
            done.append(d.name)
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare agent mock exam round")
    parser.add_argument("round", type=int, help="Mock round number (e.g. 5)")
    parser.add_argument(
        "--mock-root",
        type=Path,
        default=MOCK_ROOT_DEFAULT,
        help="Mock exam root (default: output/mock_exam)",
    )
    parser.add_argument(
        "--backfill-prior",
        action="store_true",
        help="Create manifest.json for prior rounds missing it",
    )
    args = parser.parse_args()

    mock_root = args.mock_root
    round_dir = mock_root / f"{args.round}회차"

    if args.backfill_prior:
        filled = backfill_prior_manifests(mock_root, args.round)
        if filled:
            print("Backfilled manifest:", ", ".join(filled))

    prior_ids = collect_prior_ids(mock_root, args.round)
    prior_stems = collect_prior_stems(mock_root, args.round)
    round_dir.mkdir(parents=True, exist_ok=True)

    pool_stats = write_candidates(round_dir, prior_ids, prior_stems)
    briefing = build_briefing(
        args.round, prior_ids, len(prior_stems), pool_stats, mock_root
    )
    (round_dir / "_briefing.md").write_text(briefing, encoding="utf-8")
    write_draft_readme(round_dir, args.round)
    write_manifest_template(round_dir, args.round)

    print(f"Prepared {round_dir}/")
    print(f"  _briefing.md")
    print(f"  _candidates/ ({sum(1 for _ in (round_dir / '_candidates').glob('*.md'))} files)")
    print(f"  _draft/README.md")
    for sn, st in pool_stats.items():
        print(
            f"  {sn}과목: eligible {st['eligible']}/{st['with_ans']} "
            f"(target {FILGI_COUNTS[sn]})"
        )


if __name__ == "__main__":
    main()

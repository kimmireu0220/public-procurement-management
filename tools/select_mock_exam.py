#!/usr/bin/env python3
"""자동 초안 생성기 — 에이전트 검수 전 스크립트 선별 (권장 기본 경로 아님)."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import ROOT, SUBJECT_CATALOG  # noqa: E402
from mock_exam_common import (  # noqa: E402
    DEDUP_NOTE,
    FILGI_COUNTS,
    MOCK_ROOT_DEFAULT,
    Question,
    build_mock_exam_player_for_round,
    cluster_at_limit,
    cluster_tags,
    collect_prior_stems,
    coverage_report,
    keyword_score,
    load_subject_pool,
    topic_at_limit,
    topic_tags,
    strict_source_dedup,
    source_key,
    validate_selected,
    write_round_files,
)

# re-export for tests
__all__ = ["select", "build_round"]


def _complexity(q: Question) -> int:
    stem = q.stem
    score = len(stem)
    if any(x in stem for x in ("㉠", "빈칸", "( )", "ㄱ", "ㄴ", "조합", "복수")):
        score += 80
    if any(x in stem for x in ("설명으로", "비교", "차이", "절차", "순서", "적용")):
        score += 30
    return score


def _sort_key(
    q: Question, harder: bool, *, importance: bool = False, subject_no: str = ""
) -> tuple:
    if importance:
        type_rank = {"exam": 4, "multi": 3, "other": 2, "check": 1}.get(q.stype, 1)
        return (
            -keyword_score(q, subject_no),
            -type_rank,
            -_complexity(q),
            q.part,
            q.chapter,
            q.qn,
        )
    if harder:
        type_rank = {"multi": 4, "exam": 3, "other": 2, "check": 0}.get(q.stype, 1)
        return (-type_rank, -_complexity(q), q.part, q.chapter, q.qn)
    return (-q.pri, q.chapter, q.qn)


def select(
    pool: list[Question],
    count: int,
    used_stems: set[str],
    *,
    harder: bool = False,
    importance: bool = False,
    subject_no: str = "",
    topic_counts: Counter[str] | None = None,
    cluster_counts: Counter[str] | None = None,
    used_sources: set[str] | None = None,
) -> list[Question]:
    max_check = 0 if harder else max(1, int(count * 0.2))
    elig = [q for q in pool if q.ans and q.stem not in used_stems]
    by_part: dict[int, list[Question]] = defaultdict(list)
    for q in elig:
        by_part[q.part].append(q)
    for p in by_part:
        by_part[p].sort(
            key=lambda x, sn=subject_no: _sort_key(
                x, harder, importance=importance, subject_no=sn
            )
        )
    selected: list[Question] = []
    check_n = 0
    if topic_counts is None:
        topic_counts = Counter()
    if cluster_counts is None:
        cluster_counts = Counter()
    if used_sources is None:
        used_sources = set()
    idx = {p: 0 for p in by_part}
    parts = sorted(by_part)

    def would_duplicate(q: Question) -> bool:
        if topic_at_limit(topic_tags(q), topic_counts):
            return True
        if cluster_at_limit(cluster_tags(q), cluster_counts):
            return True
        if strict_source_dedup(q):
            sk = source_key(q.source)
            if sk and f"{subject_no}:{sk}" in used_sources:
                return True
        return False

    def accept(q: Question, *, enforce_dedup: bool) -> bool:
        if enforce_dedup and would_duplicate(q):
            return False
        selected.append(q)
        used_stems.add(q.stem)
        for tag in topic_tags(q):
            topic_counts[tag] += 1
        for tag in cluster_tags(q):
            cluster_counts[tag] += 1
        if strict_source_dedup(q):
            sk = source_key(q.source)
            if sk:
                used_sources.add(f"{subject_no}:{sk}")
        return True

    while len(selected) < count:
        progressed = False
        for p in parts:
            if len(selected) >= count:
                break
            while idx[p] < len(by_part[p]):
                q = by_part[p][idx[p]]
                idx[p] += 1
                if q.stype == "check" and check_n >= max_check:
                    continue
                if accept(q, enforce_dedup=True):
                    if q.stype == "check":
                        check_n += 1
                    progressed = True
                    break
        if not progressed:
            for p in parts:
                if len(selected) >= count:
                    break
                while idx[p] < len(by_part[p]):
                    q = by_part[p][idx[p]]
                    idx[p] += 1
                    if accept(q, enforce_dedup=False):
                        break
            if not progressed:
                break
    return selected[:count]


def build_round(
    round_num: int,
    mock_root: Path | None = None,
    *,
    harder: bool = False,
    importance: bool = False,
) -> tuple[dict[str, list[Question]], dict[str, dict]]:
    mock_root = mock_root or MOCK_ROOT_DEFAULT
    used_stems = collect_prior_stems(mock_root, round_num)
    topic_counts: Counter[str] = Counter()
    cluster_counts: Counter[str] = Counter()
    used_sources: set[str] = set()
    selected: dict[str, list[Question]] = {}
    stats: dict[str, dict] = {}

    for sn, slug_info in SUBJECT_CATALOG.items():
        if slug_info["exam_type"] != "필기":
            continue
        cnt = FILGI_COUNTS[sn]
        pool = load_subject_pool(sn)
        sel = select(
            pool,
            cnt,
            used_stems,
            harder=harder,
            importance=importance,
            subject_no=sn,
            topic_counts=topic_counts,
            cluster_counts=cluster_counts,
            used_sources=used_sources,
        )
        if len(sel) < cnt:
            raise RuntimeError(
                f"{sn}과목: {len(sel)}/{cnt}문항만 선별됨 (풀 {len(pool)}, "
                f"정답매칭 {sum(1 for q in pool if q.ans)})"
            )
        selected[sn] = sel
        stats[sn] = {
            "pool": len(pool),
            "with_ans": sum(1 for q in pool if q.ans),
            "parts": dict(sorted(Counter(q.part for q in sel).items())),
            "types": dict(Counter(q.stype for q in sel)),
            "keyword_hits": sum(1 for q in sel if keyword_score(q, sn) > 0),
        }

    errors = validate_selected(selected)
    if errors:
        raise RuntimeError("회차 중복 검증 실패:\n" + "\n".join(errors))
    return selected, stats


def selection_note(
    round_num: int, *, harder: bool, importance: bool
) -> str:
    if importance:
        return (
            f"> 선별(초안): 스크립트 · OX 제외 · 빈출 키워드 · "
            f"{DEDUP_NOTE} · {round_num - 1}회차 이전 미출제 · **에이전트 검수 권장**"
        )
    if harder:
        return (
            f"> 선별(초안): 스크립트 · ㉠㉡·빈칸 우선 · "
            f"{DEDUP_NOTE} · {round_num - 1}회차 이전 미출제 · **에이전트 검수 권장**"
        )
    return (
        f"> 선별(초안): 스크립트 · 단원별 출제예상 중심 · "
        f"{DEDUP_NOTE} · {round_num - 1}회차 이전 미출제 · **에이전트 검수 권장**"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-draft mock exam (use prepare_mock_round + agent for production)"
    )
    parser.add_argument("round", type=int, help="Mock round number (e.g. 2)")
    parser.add_argument("--mock-root", type=Path, default=MOCK_ROOT_DEFAULT)
    parser.add_argument("--harder", action="store_true")
    parser.add_argument("--importance", action="store_true")
    args = parser.parse_args()
    importance = args.importance or (args.round >= 3 and not args.harder)
    selected, stats = build_round(
        args.round, mock_root=args.mock_root, harder=args.harder, importance=importance
    )
    out = args.mock_root / f"{args.round}회차"
    write_round_files(
        args.round,
        selected,
        out,
        method="script",
        note=selection_note(args.round, harder=args.harder, importance=importance),
    )
    for sn, st in stats.items():
        print(
            f"{sn}과목: pool={st['pool']} parts={st['parts']} "
            f"types={st['types']} keyword_hits={st['keyword_hits']}"
        )
    print(coverage_report(selected))
    print(f"Wrote {out}/필기_모의_문제.md (script draft — agent review recommended)")
    html = build_mock_exam_player_for_round(args.round, mock_root=args.mock_root)
    print(f"응시 UI: {html}")


if __name__ == "__main__":
    main()

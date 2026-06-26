#!/usr/bin/env python3
"""2차 kw 품질 보강 — 선지 복사 kw를 해설형 문장으로 교체."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import ROOT, SUBJECT_CATALOG  # noqa: E402
from mock_exam_common import (  # noqa: E402
    ANSWER_HEAD,
    EXTRACT,
    FULL_ANSWER_LINE_RE,
    HEADER_LINE_RE,
    CHAPTER_NUM_RE,
    PART_HEAD,
    correct_choice_text,
    load_all_pools,
    load_subject_pool,
    parse_section_header,
    stype_from_section_title,
)

# Q1 + 수동 검수 우선 (stable_id → 해설)
MANUAL_KW: dict[str, str] = {
    "1:1:4:exam:13": (
        "「국가계약법」과 「지방계약법」 적용 구분의 핵심은 계약 주체가 국가인지 "
        "지방자치단체인지(계약 주체의 성격)이며, 계약 금액·목적만으로는 구분하지 않는다."
    ),
    "1:1:2:exam:14": (
        "전략적 공공조달 관점에서 수요자(조달기관)는 단순 구매자가 아니라 "
        "정책 목표 달성을 위해 조달 수단을 전략적으로 운용하는 행위자이다."
    ),
    "1:1:1:exam:10": (
        "공공조달 인식은 단순 물자 구매(단순 구매)에서 행정·재정 효율 중심의 "
        "행정 조달을 거쳐 정책·사회적 가치를 반영하는 전략적 조달로 발전해 왔다."
    ),
    "3:2:2:exam:40": (
        "공사이행기간 변경과 물가변동 조정은 별도 제도이며, 기간 변경만으로 "
        "물가변동에 따른 계약금액 조정을 자동 적용한다고 볼 수 없다(②가 옳지 않음)."
    ),
    "3:2:2:exam:13": (
        "물가변동 90일 산정은 설계변경으로 금액을 조정한 경우에도 원칙적으로 "
        "당초 계약 체결일 또는 직전 조정기준일을 기준으로 한다."
    ),
    "3:2:2:exam:36": (
        "발주기관이 계약금액 조정을 해야 하는 경우 조정 기한은 "
        "계약상대자의 조정 청구를 받은 날부터 30일 이내이다."
    ),
    "3:2:2:exam:30": (
        "Turn-Key(설계·시공 일괄) 계약은 설계·시공 리스크가 계약상대자에 있어 "
        "설계변경에 따른 증액은 정부 책임·천재지변 등 불가항력적 사유에 한정된다."
    ),
    "3:2:2:exam:33": (
        "공사비 절감 효과가 현저한 신기술·공법 도입은 설계변경 사유가 될 수 있으며, "
        "계약상대자는 관련 서류를 첨부해 설계변경을 요청할 수 있다."
    ),
    "3:2:2:exam:32": (
        "설계도면과 공사시방서가 상이할 때 물량내역서를 우선 기준으로 설계를 확정한다는 "
        "진술은 틀렸다(③이 옳지 않은 설명)."
    ),
}


def craft_kw(q) -> str:
    """선지 전문을 반복하지 않는 기본 해설(배치 자동용)."""
    stem = re.sub(r"^\d+\.\s+", "", q.stem.split("\n")[0]).rstrip("?").strip()
    topic = stem[:70] + ("…" if len(stem) > 70 else "")
    return (
        f"「{topic}」 문항에서 정답 {q.ans}는 법령·계약예규 및 교재 설명과 "
        f"일치하는 진술이며, 오답 선지는 요건·효과·주체를 혼동하거나 반대로 서술했다."
    )


def pool_maps() -> tuple[dict[str, object], dict[tuple, object]]:
    by_id: dict[str, object] = {}
    by_key: dict[tuple, object] = {}
    for sn, pool in load_all_pools().items():
        for qid, q in pool.items():
            by_id[qid] = q
            by_key[(sn, q.part, q.chapter, q.stype, q.qn)] = q
    return by_id, by_key


def kw_for_question(q, by_id: dict) -> str | None:
    choice = correct_choice_text(q)
    kw = (q.kw or "").strip()
    if not choice or kw != choice:
        if q.stable_id() in MANUAL_KW and kw == choice:
            return MANUAL_KW[q.stable_id()]
        return None
    sid = q.stable_id()
    if sid in MANUAL_KW:
        return MANUAL_KW[sid]
    return craft_kw(q)


def enrich_extract_file(path: Path, subject_no: str, *, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    pm = PART_HEAD.search(text)
    part = int(pm.group(1)) if pm else 0
    acut = ANSWER_HEAD.search(text)
    if not acut or not part:
        return 0

    _, by_key = pool_maps()
    chapter, stype = 0, ""
    out: list[str] = []
    changed = 0

    for raw in text[acut.start() :].splitlines(keepends=True):
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped or ANSWER_HEAD.match(stripped):
            out.append(raw)
            continue

        header = parse_section_header(raw)
        if header:
            chapter, title = header
            st = stype_from_section_title(title)
            if st != "other":
                stype = st
            out.append(raw)
            continue

        if HEADER_LINE_RE.match(stripped) and not CHAPTER_NUM_RE.search(stripped):
            title = HEADER_LINE_RE.sub("", stripped).strip()
            if title and not re.match(r"Part\s+\d+", title, re.I):
                st = stype_from_section_title(title)
                if st != "other":
                    stype = st
            out.append(raw)
            continue

        fm = FULL_ANSWER_LINE_RE.match(stripped)
        if fm and chapter and stype:
            n, ans, old_kw = int(fm.group(1)), fm.group(2), fm.group(3).strip()
            q = by_key.get((subject_no, part, chapter, stype, n))
            if q:
                new_kw = kw_for_question(q, {})
                if new_kw and new_kw != old_kw:
                    indent = line[: len(line) - len(line.lstrip())]
                    out.append(f"{indent}{n}. {ans} — {new_kw}\n")
                    changed += 1
                    continue
        out.append(raw)

    if changed and not dry_run:
        path.write_text(text[: acut.start()] + "".join(out), encoding="utf-8")
    return changed


def export_targets(out: Path) -> None:
    by_id, _ = pool_maps()
    choice_only: list[dict] = []
    short_kw: list[dict] = []
    for qid, q in by_id.items():
        kw = (q.kw or "").strip()
        ct = correct_choice_text(q)
        if ct and kw == ct:
            choice_only.append(
                {"id": qid, "subject": q.subject_no, "part": q.part, "source": q.source}
            )
        elif kw and len(kw) < 12 and q.stype != "ox":
            short_kw.append({"id": qid, "kw": kw, "source": q.source})

    mock_choice: list[dict] = []
    from mock_exam_common import load_manifest, MOCK_ROOT_DEFAULT

    for d in sorted(MOCK_ROOT_DEFAULT.glob("*회차")):
        m = load_manifest(d)
        if not m:
            continue
        for item in m.get("items", []):
            q = by_id[item["id"]]
            ct = correct_choice_text(q)
            if ct and (q.kw or "").strip() == ct:
                mock_choice.append(
                    {"round": d.name, "exam_num": item["exam_num"], "id": item["id"]}
                )

    out.write_text(
        json.dumps(
            {
                "choice_only_count": len(choice_only),
                "short_kw_count": len(short_kw),
                "mock_choice_only": mock_choice,
                "choice_only": choice_only,
                "short_kw": short_kw,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="2차 kw 품질 보강")
    parser.add_argument("--subject", type=str, help="과목 번호")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--export-targets",
        type=Path,
        help="품질 대상 JSON (기본: output/kw_품질_대상.json)",
        nargs="?",
        const=ROOT / "output/kw_품질_대상.json",
    )
    args = parser.parse_args()

    if args.export_targets is not None:
        export_targets(args.export_targets)
        print(f"Wrote {args.export_targets}")
        return

    subjects = [args.subject] if args.subject else ["1", "2", "3"]
    total = 0
    for sn in subjects:
        slug = str(SUBJECT_CATALOG[sn]["slug"])
        for path in sorted((EXTRACT / slug).glob("part*.md")):
            n = enrich_extract_file(path, sn, dry_run=args.dry_run)
            if n:
                print(f"{'[dry] ' if args.dry_run else ''}{path.name}: {n} lines")
            total += n
    print(f"합계 {total} lines updated")


if __name__ == "__main__":
    main()

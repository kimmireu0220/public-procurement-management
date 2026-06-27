#!/usr/bin/env python3
"""3차 kw 보강 — craft_kw 템플릿을 문항별 시험형 해설로 교체."""

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
from enrich_kw_quality import MANUAL_KW  # noqa: E402
from mock_exam_common import (  # noqa: E402
    ANSWER_HEAD,
    CHOICE_FULL,
    EXTRACT,
    FULL_ANSWER_LINE_RE,
    HEADER_LINE_RE,
    CHAPTER_NUM_RE,
    PART_HEAD,
    correct_choice_text,
    load_all_pools,
    parse_section_header,
    stype_from_section_title,
)

TEMPLATE_MARK = "오답 선지는 요건·효과·주체를 혼동하거나 반대로 서술했다."
KW_DB_PATH = TOOLS_DIR / "kw_db.json"

NEGATIVE_STEM = re.compile(
    r"거리가\s*먼|옳지\s*않|적절하지\s*않|어려운\s*것|틀린|보기\s*어려운|"
    r"해당하지\s*않|맞지\s*않|부적절"
)
SEQUENCE_STEM = re.compile(r"순서|단계|흐름|나열|절차.*순")
COMBO_STEM = re.compile(r"㉠|㉡|㉢|고른\s*것|조합")


def load_kw_db() -> dict[str, str]:
    if KW_DB_PATH.is_file():
        return json.loads(KW_DB_PATH.read_text(encoding="utf-8"))
    return {}


def choice_map(q) -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in q.lines:
        m = CHOICE_FULL.match(ln.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def explain_key(text: str, max_len: int = 42) -> str:
    t = text.strip().rstrip(".")
    if len(t) <= max_len:
        return t
    for sep in ("이며", "하고", "하여", "이나", ",", "·"):
        if sep in t:
            head = t.split(sep)[0].strip()
            if len(head) >= 12:
                return head + "…"
    return t[: max_len - 1] + "…"


def first_wrong_label(choices: dict[str, str], ans: str) -> tuple[str, str] | None:
    for label in sorted(choices):
        if label != ans:
            return label, choices[label]
    return None


def obj_particle(phrase: str) -> str:
    if not phrase:
        return "을(를)"
    last = phrase[-1]
    if not (0xAC00 <= ord(last) <= 0xD7A3):
        return "을(를)"
    return "을" if (ord(last) - 0xAC00) % 28 else "를"


TRAP_PHRASES = (
    "은(는) 개념·요건을 혼동한 오답이다",
    "은(는) 법령상 효과나 적용 주체를 바꿔 놓았다",
    "은(는) 절차·요건을 뒤바꾼 설명이다",
)


def build_explain(q) -> str:
    sid = q.stable_id()
    db = load_kw_db()
    if sid in MANUAL_KW:
        return MANUAL_KW[sid]
    if sid in db:
        return db[sid]

    stem = re.sub(r"^\d+\.\s+", "", q.stem.split("\n")[0]).strip().rstrip("?")
    choices = choice_map(q)
    correct = choices.get(q.ans) or correct_choice_text(q) or ""
    core = explain_key(correct)
    trap = first_wrong_label(choices, q.ans)

    if NEGATIVE_STEM.search(stem):
        if trap:
            trap_core = explain_key(trap[1], 30)
            return (
                f"「{stem}」에서 정답 {q.ans}는 해당 주제와 맞지 않는 설명이다. "
                f"예를 들어 {trap[0]}의 '{trap_core}'는 오히려 관련 개념에 해당한다."
            )
        return f"「{stem}」에서 정답 {q.ans}는 보기와 거리가 있거나 틀린 설명이다."

    if SEQUENCE_STEM.search(stem):
        return (
            f"「{stem}」의 올바른 순서·절차를 묻는 문제로, "
            f"{q.ans}({core})가 교재상 제시된 흐름과 일치한다."
        )

    if COMBO_STEM.search(stem):
        return (
            f"보기 조합 문제로 {q.ans}가 요건·개념을 올바르게 결합한다. "
            f"핵심 근거는 {core}이다."
        )

    if trap:
        trap_core = explain_key(trap[1], 28)
        trap_tail = TRAP_PHRASES[q.qn % len(TRAP_PHRASES)]
        return (
            f"정답 {q.ans}는 {core}{obj_particle(core)} 핵심으로 한다. "
            f"{trap[0]}의 '{trap_core}'{trap_tail}."
        )

    return f"정답 {q.ans}는 {core}{obj_particle(core)} 정확히 반영한 설명이다."


MECHANICAL_MARK = "혼동한 함정이다"
MECHANICAL_PATTERNS = (
    "을(를) 핵심으로",
    "혼동한 오답이다",
    "요건·효과·주체를 혼동",
    "은(는) 개념·요건을 혼동",
    "은(는) 법령상 효과나 적용 주체",
    "은(는) 절차·요건을 뒤바꾼",
    "이(가) 정답이다.",
    "해당 주제와 맞지 않는 설명이다",
    "교재상 제시된 흐름과 일치",
    "오히려 관련 개념에 해당",
)


def is_mechanical_kw(kw: str) -> bool:
    return any(p in kw for p in MECHANICAL_PATTERNS) or TEMPLATE_MARK in kw


def build_explain_clean(q) -> str:
    """기계적 패턴 없이 교재형 해설."""
    sid = q.stable_id()
    db = load_kw_db()
    if sid in MANUAL_KW:
        return MANUAL_KW[sid]
    if sid in db:
        return db[sid]

    stem = re.sub(r"^\d+\.\s+", "", q.stem.split("\n")[0]).strip().rstrip("?")
    choices = choice_map(q)
    correct = choices.get(q.ans) or correct_choice_text(q) or ""
    core = explain_key(correct, 58)
    trap = first_wrong_label(choices, q.ans)

    if NEGATIVE_STEM.search(stem):
        if trap:
            return (
                f"「{stem[:45]}…」에서 정답 {q.ans}는 보기와 거리가 있다. "
                f"{trap[0]}의 '{explain_key(trap[1], 28)}' 등은 관련 개념에 해당한다."
            )
        return f"「{stem[:50]}」에서 정답 {q.ans}는 틀리거나 해당 주제와 맞지 않는 설명이다."

    if SEQUENCE_STEM.search(stem):
        return f"「{stem[:45]}…」의 올바른 절차·순서로, {q.ans}({core})가 교재상 흐름과 일치한다."

    if COMBO_STEM.search(stem):
        return (
            f"보기 조합 문제로 {q.ans}가 요건·개념을 올바르게 결합한다. "
            f"핵심 근거는 {core}이다."
        )

    if trap:
        trap_core = explain_key(trap[1], 28)
        trap_tail = TRAP_PHRASES[q.qn % len(TRAP_PHRASES)]
        return (
            f"{core}이(가) 정답이다. "
            f"{trap[0]}의 '{trap_core}'{trap_tail}."
        )
    return f"{core}이(가) 법령·교재상 옳은 설명이다."


def needs_replace(kw: str, *, mechanical: bool = False) -> bool:
    if mechanical:
        return is_mechanical_kw(kw)
    return TEMPLATE_MARK in kw or MECHANICAL_MARK in kw


def pool_by_key() -> dict[tuple, object]:
    by_key: dict[tuple, object] = {}
    for sn, pool in load_all_pools().items():
        for q in pool.values():
            by_key[(sn, q.part, q.chapter, q.stype, q.qn)] = q
    return by_key


def replace_in_file(path: Path, subject_no: str, *, dry_run: bool, mechanical: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    pm = PART_HEAD.search(text)
    part = int(pm.group(1)) if pm else 0
    acut = ANSWER_HEAD.search(text)
    if not acut or not part:
        return 0

    by_key = pool_by_key()
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
        if fm and chapter and stype and needs_replace(fm.group(3), mechanical=mechanical):
            n, ans = int(fm.group(1)), fm.group(2)
            q = by_key.get((subject_no, part, chapter, stype, n))
            if q:
                new_kw = build_explain_clean(q) if mechanical else build_explain(q)
                ct = correct_choice_text(q)
                if new_kw and new_kw != fm.group(3).strip() and new_kw != ct:
                    indent = line[: len(line) - len(line.lstrip())]
                    out.append(f"{indent}{n}. {ans} — {new_kw}\n")
                    changed += 1
                    continue
        out.append(raw)

    if changed and not dry_run:
        path.write_text(text[: acut.start()] + "".join(out), encoding="utf-8")
    return changed


def export_template_targets(out: Path) -> None:
    by_key = pool_by_key()
    items: list[dict] = []
    for path in sorted(EXTRACT.glob("*/*part*.md")):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if TEMPLATE_MARK not in line and MECHANICAL_MARK not in line:
                continue
            fm = FULL_ANSWER_LINE_RE.match(line.strip())
            if not fm:
                continue
            items.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "line": i,
                    "qn": int(fm.group(1)),
                    "ans": fm.group(2),
                    "kw_preview": fm.group(3)[:80],
                }
            )
    out.write_text(
        json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="3차 kw 템플릿 → 실해설 교체")
    parser.add_argument("--subject", type=str, help="과목 번호")
    parser.add_argument("--file", type=Path, help="단일 part*.md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mechanical",
        action="store_true",
        help="을(를) 핵심으로 등 기계적 해설만 교체",
    )
    parser.add_argument(
        "--export-template",
        type=Path,
        nargs="?",
        const=ROOT / "output/kw_템플릿_대상.json",
        help="템플릿 대상 JSON",
    )
    args = parser.parse_args()

    if args.export_template is not None:
        export_template_targets(args.export_template)
        print(f"Wrote {args.export_template}")
        return

    total = 0
    if args.file:
        sn = args.subject
        if not sn:
            for s, info in SUBJECT_CATALOG.items():
                if info["slug"] in str(args.file):
                    sn = s
                    break
        if not sn:
            raise SystemExit("--file 사용 시 --subject 필요")
        n = replace_in_file(args.file, sn, dry_run=args.dry_run, mechanical=args.mechanical)
        print(f"{'[dry] ' if args.dry_run else ''}{args.file.name}: {n} lines")
        total = n
    else:
        subjects = [args.subject] if args.subject else ["1", "2", "3"]
        for sn in subjects:
            slug = str(SUBJECT_CATALOG[sn]["slug"])
            for path in sorted((EXTRACT / slug).glob("part*.md")):
                n = replace_in_file(path, sn, dry_run=args.dry_run, mechanical=args.mechanical)
                if n:
                    print(f"{'[dry] ' if args.dry_run else ''}{path.name}: {n} lines")
                total += n
    print(f"합계 {total} lines updated")


if __name__ == "__main__":
    main()

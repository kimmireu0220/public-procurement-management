#!/usr/bin/env python3
"""Select 필기 mock exam questions from problem bank (parts_clean + agent_extract answers)."""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
import sys

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import ROOT, SUBJECT_CATALOG  # noqa: E402

CLEAN = ROOT / "output/problem_book_final"
EXTRACT = ROOT / "output/agent_extract"

SOURCE_RE = re.compile(r"<!--\s*source:\s*(.+?)\s*-->")
QUESTION_START = re.compile(r"^(\d+)\.\s+(.+)")
ANSWER_SECTION_RE = re.compile(r"^#{2,3}\s+(?:\[)?CHAPTER?\s+(\d+)", re.I)
SECTION_RE = re.compile(r"^#{2,3}\s+(?:\[)?CHAPTER?\s+(\d+)\s+(.+)$", re.I)
PART_HEAD = re.compile(r"^## Part (\d+)", re.M)
ANSWER_HEAD = re.compile(r"^## Part \d+ 정답", re.M)
CHOICE_LINE = re.compile(r"^\s*[①②③④⑤]")

SUBJECT_NAMES = {
    "1": "공공조달과 법제도 이해",
    "2": "공공조달계획 수립 및 분석",
    "3": "공공계약관리",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def classify_section(name: str) -> tuple[str, int]:
    if "OX" in name.upper() or "O/X" in name:
        return "ox", -1
    if "단원별 출제예상" in name:
        return "exam", 3
    if "Check" in name or "Q&A" in name or "O&A" in name:
        return "check", 1
    if any(x in name for x in ["㉠", "복수", "빈칸", "조합", "ㄱ", "ㄴ"]):
        return "multi", 2
    return "other", 2


def parse_answers_from_extract(text: str, part_num: int) -> dict[tuple[int, int, str, int], tuple[str, str]]:
    """(part, chapter, stype, qnum) -> (answer, keyword)"""
    acut = ANSWER_HEAD.search(text)
    if not acut:
        return {}
    out: dict[tuple[int, int, str, int], tuple[str, str]] = {}
    chapter = 0
    stype = ""
    for line in text[acut.start() :].splitlines():
        sm = ANSWER_SECTION_RE.match(line.strip())
        if sm:
            chapter = int(sm.group(1))
            stype, _ = classify_section(line)
            continue
        if not chapter or stype == "ox":
            continue
        m = re.match(r"^(\d+)\.\s+([①②③④])\s*(?:—\s*(.+))?$", line.strip())
        if m:
            out[(part_num, chapter, stype, int(m.group(1)))] = (
                m.group(2),
                (m.group(3) or "").strip(),
            )
            continue
        for im in re.finditer(r"(\d+)\.\s+([①②③④])", line):
            out[(part_num, chapter, stype, int(im.group(1)))] = (im.group(2), "")
    return out


def split_giyeok_items(stem: str) -> str:
    """Split inline ㉠㉡ sub-items onto separate lines (extraction_guide)."""
    if "㉠" not in stem or "\n   ㉠" in stem:
        return stem
    # split after question mark / before first ㉠
    m = re.search(r"([?？])\s*(㉠.+)$", stem)
    if not m:
        return stem
    head, tail = stem[: m.end(1)], stem[m.start(2) :]
    parts = re.split(r"(?=㉠)", tail)
    return head + "\n   " + "\n   ".join(p.strip() for p in parts if p.strip())


@dataclass
class Question:
    stem: str
    lines: list[str]
    source: str
    part: int
    chapter: int
    stype: str
    pri: int
    qn: int
    ans: str = ""
    kw: str = ""


def parse_questions_from_clean(
    clean_file: Path, answers: dict[tuple[int, int, str, int], tuple[str, str]]
) -> list[Question]:
    text = clean_file.read_text(encoding="utf-8")
    pm = PART_HEAD.search(text)
    part = int(pm.group(1)) if pm else 0
    qs: list[Question] = []
    chapter = 0
    stype, pri = "other", 1
    lines = text.splitlines()
    i = 0
    section_batch: list[Question] = []

    def trailing_source_before(idx: int) -> str:
        j = idx - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j >= 0:
            m = SOURCE_RE.search(lines[j])
            if m and not QUESTION_START.match(lines[j]):
                return m.group(1).strip()
        return ""

    def flush_batch(trailing_source: str = "") -> None:
        nonlocal section_batch
        if not section_batch:
            return
        if trailing_source:
            for q in section_batch:
                if not q.source:
                    q.source = trailing_source
        qs.extend(section_batch)
        section_batch = []

    while i < len(lines):
        line = lines[i]
        sm = SECTION_RE.match(line)
        if sm:
            flush_batch(trailing_source=trailing_source_before(i))
            chapter = int(sm.group(1))
            stype, pri = classify_section(sm.group(2))
            i += 1
            continue
        if SOURCE_RE.search(line) and not QUESTION_START.match(line):
            src = SOURCE_RE.search(line).group(1).strip()
            flush_batch(trailing_source=src)
            i += 1
            continue
        qm = QUESTION_START.match(line)
        if qm and stype != "ox":
            qn = int(qm.group(1))
            stem_raw = qm.group(2).strip()
            if "(O/X)" in stem_raw:
                i += 1
                continue
            block = [line]
            i += 1
            source = ""
            while i < len(lines):
                if SECTION_RE.match(lines[i]) or QUESTION_START.match(lines[i]):
                    break
                if SOURCE_RE.search(lines[i]):
                    source = SOURCE_RE.search(lines[i]).group(1).strip()
                    block.append(lines[i])
                    i += 1
                    break
                block.append(lines[i])
                i += 1
            choice_lines = [l for l in block if CHOICE_LINE.match(l)]
            if len(choice_lines) < 4:
                continue
            ans, kw = answers.get((part, chapter, stype, qn), ("", ""))
            stem = norm(stem_raw.split("\n")[0])
            section_batch.append(
                Question(
                    stem=stem,
                    lines=block,
                    source=source,
                    part=part,
                    chapter=chapter,
                    stype=stype,
                    pri=pri,
                    qn=qn,
                    ans=ans,
                    kw=kw,
                )
            )
            continue
        i += 1
    flush_batch()
    return qs


def load_used_stems(round_dir: Path) -> set[str]:
    prob = round_dir / "필기_모의_문제.md"
    if not prob.is_file():
        return set()
    stems: set[str] = set()
    for block in re.split(r"\n(?=\d+\. )", prob.read_text(encoding="utf-8")):
        m = re.match(r"\d+\.\s+(.+)", block)
        if m:
            stems.add(norm(m.group(1).split("\n")[0]))
    return stems


def select(pool: list[Question], count: int, used_stems: set[str]) -> list[Question]:
    max_check = max(1, int(count * 0.2))
    elig = [q for q in pool if q.ans and q.stem not in used_stems]
    by_part: dict[int, list[Question]] = defaultdict(list)
    for q in elig:
        by_part[q.part].append(q)
    for p in by_part:
        by_part[p].sort(key=lambda x: (-x.pri, x.chapter, x.qn))
    selected: list[Question] = []
    check_n = 0
    idx = {p: 0 for p in by_part}
    parts = sorted(by_part)
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
                selected.append(q)
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
                    selected.append(q)
                    break
            if not progressed:
                break
    return selected[:count]


def format_question(num: int, q: Question) -> str:
    stem = re.sub(r"^\d+\.\s+", "", q.lines[0])
    stem = split_giyeok_items(stem)
    out = [f"{num}. {stem}"]
    for ln in q.lines[1:]:
        if SOURCE_RE.search(ln):
            continue
        out.append(ln)
    out.append(f"<!-- source: {q.source} -->")
    return "\n".join(out)


def keyword_line(q: Question) -> str:
    if q.kw:
        t = q.kw.strip()
        return t[:50] + ("…" if len(t) > 50 else "")
    return q.stem[:35] + ("…" if len(q.stem) > 35 else "")


def collect_prior_stems(mock_root: Path, exclude_round: int) -> set[str]:
    stems: set[str] = set()
    for d in sorted(mock_root.glob("*회차")):
        m = re.match(r"(\d+)회차", d.name)
        if m and int(m.group(1)) < exclude_round:
            stems |= load_used_stems(d)
    return stems


def build_round(
    round_num: int,
    mock_root: Path | None = None,
) -> tuple[dict[str, list[Question]], dict[str, dict]]:
    mock_root = mock_root or ROOT / "output/mock_exam"
    used_stems = collect_prior_stems(mock_root, round_num)
    counts = {"1": 30, "2": 20, "3": 30}
    selected: dict[str, list[Question]] = {}
    stats: dict[str, dict] = {}

    for sn, slug_info in SUBJECT_CATALOG.items():
        if slug_info["exam_type"] != "필기":
            continue
        slug = str(slug_info["slug"])
        cnt = counts[sn]
        clean_dir = CLEAN / slug / "parts_clean"
        extract_dir = EXTRACT / slug
        all_answers: dict[tuple[int, int, str, int], tuple[str, str]] = {}
        for ef in sorted(extract_dir.glob("part*.md")):
            pm = PART_HEAD.search(ef.read_text(encoding="utf-8"))
            part = int(pm.group(1)) if pm else 0
            all_answers.update(parse_answers_from_extract(ef.read_text(encoding="utf-8"), part))
        pool: list[Question] = []
        for cf in sorted(clean_dir.glob("part*.md")):
            pool.extend(parse_questions_from_clean(cf, all_answers))
        sel = select(pool, cnt, used_stems)
        if len(sel) < cnt:
            raise RuntimeError(
                f"{sn}과목: {len(sel)}/{cnt}문항만 선별됨 (풀 {len(pool)}, "
                f"정답매칭 {sum(1 for q in pool if q.ans)}, 미출제 {len([q for q in pool if q.ans and q.stem not in used_stems])})"
            )
        selected[sn] = sel
        stats[sn] = {
            "pool": len(pool),
            "with_ans": sum(1 for q in pool if q.ans),
            "parts": dict(sorted(Counter(q.part for q in sel).items())),
            "types": dict(Counter(q.stype for q in sel)),
        }
    return selected, stats


def write_round(round_num: int, selected: dict[str, list[Question]], mock_root: Path | None = None) -> Path:
    mock_root = mock_root or ROOT / "output/mock_exam"
    out = mock_root / f"{round_num}회차"
    out.mkdir(parents=True, exist_ok=True)

    prob = [
        f"# 공공조달관리사 1회 필기 모의 {round_num}회차 — 문제",
        "",
        "> 필기 합계 80문항 · 2시간 · CBT 4지 택일형",
        "> 1과목 30문항 · 2과목 20문항 · 3과목 30문항",
        "",
        "> 출제 기준: docs/시험_안내.md, docs/문제집_프롬프트/시험모의_선별.md",
        "",
        f"> 선별 기준: OX 제외, 단원별 출제예상문제 중심, {round_num - 1}회차 이전 미출제 지문 우선",
        "",
    ]
    ans = [
        f"# 공공조달관리사 1회 필기 모의 {round_num}회차 — 정답",
        "",
        "> 1과목 1~30 · 2과목 31~50 · 3과목 51~80",
        "",
    ]
    offsets = {"1": 0, "2": 30, "3": 50}
    ends = {"1": 30, "2": 50, "3": 80}
    for sn in ("1", "2", "3"):
        start = offsets[sn] + 1
        end = ends[sn]
        ename = SUBJECT_NAMES[sn]
        prob += [f"## {sn}과목 {ename} ({start}~{end})", ""]
        ans += [f"## {sn}과목 ({start}~{end})", ""]
        for i, q in enumerate(selected[sn], start):
            prob.append(format_question(i, q))
            prob.append("")
            src = f" ({q.source})" if q.source else ""
            ans.append(f"{i}. {q.ans} — {keyword_line(q)}{src}")
        ans.append("")

    (out / "필기_모의_문제.md").write_text("\n".join(prob).rstrip() + "\n", encoding="utf-8")
    (out / "필기_모의_정답.md").write_text("\n".join(ans).rstrip() + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Select mock exam from problem bank")
    parser.add_argument("round", type=int, help="Mock round number (e.g. 2)")
    parser.add_argument(
        "--mock-root",
        type=Path,
        default=ROOT / "output/mock_exam",
        help="Mock exam root directory (default: output/mock_exam)",
    )
    args = parser.parse_args()
    selected, stats = build_round(args.round, mock_root=args.mock_root)
    out = write_round(args.round, selected, mock_root=args.mock_root)
    for sn, st in stats.items():
        print(
            f"{sn}과목: pool={st['pool']} parts={st['parts']} types={st['types']}"
        )
    print(f"Wrote {out}/필기_모의_문제.md, 필기_모의_정답.md")


if __name__ == "__main__":
    main()

"""공통 모의고사 유틸 — 풀 파싱, stable ID, 검증, 산출물 형식."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import ROOT, SUBJECT_CATALOG

CLEAN = ROOT / "output/problem_book_final"
EXTRACT = ROOT / "output/agent_extract"
MOCK_ROOT_DEFAULT = ROOT / "output/mock_exam"

FILGI_COUNTS = {"1": 30, "2": 20, "3": 30}
FILGI_OFFSETS = {"1": 0, "2": 30, "3": 50}
FILGI_ENDS = {"1": 30, "2": 50, "3": 80}

SUBJECT_NAMES = {
    "1": "공공조달과 법제도 이해",
    "2": "공공조달계획 수립 및 분석",
    "3": "공공계약관리",
}

SOURCE_RE = re.compile(r"<!--\s*source:\s*(.+?)\s*-->")
ID_RE = re.compile(r"<!--\s*id:\s*([^\s>]+)\s*-->")
QUESTION_START = re.compile(r"^(\d+)\.\s+(.+)")
ANSWER_SECTION_RE = re.compile(r"^#{2,3}\s+(?:\[)?CHAPTER?\s+(\d+)", re.I)
SECTION_RE = re.compile(r"^#{2,3}\s+(?:\[)?CHAPTER?\s+(\d+)\s+(.+)$", re.I)
PART_HEAD = re.compile(r"^## Part (\d+)", re.M)
ANSWER_HEAD = re.compile(r"^## Part \d+ 정답", re.M)
CHOICE_LINE = re.compile(r"^\s*[①②③④⑤]")
CHOICE_FULL = re.compile(r"^\s*([①②③④⑤])\s*(.+)$")

TOPIC_MAX: dict[str, int] = {
    "pareto": 1,
    "mas_2stage_threshold": 1,
    "mas_2stage": 2,
    "해제_해지": 2,
    "지체상금": 2,
    "물가변동": 2,
    "입찰보증금": 1,
    "계약보증금": 1,
    "포터": 1,
}

TOPIC_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"파레토"), "pareto"),
    (re.compile(r"MAS.*2단계.*기준금액|2단계\s*경쟁.*기준금액"), "mas_2stage_threshold"),
    (
        re.compile(
            r"(?:MAS|다수공급자계약).*(?:2단계|경쟁)|"
            r"(?:2단계|경쟁).*(?:MAS|다수공급자계약)"
        ),
        "mas_2stage",
    ),
    (re.compile(r"해제.*해지|해지.*해제"), "해제_해지"),
    (re.compile(r"지체상금"), "지체상금"),
    (re.compile(r"물가변동"), "물가변동"),
    (re.compile(r"입찰보증금"), "입찰보증금"),
    (re.compile(r"계약보증금"), "계약보증금"),
    (re.compile(r"포터"), "포터"),
]

CLUSTER_MAX: dict[str, int] = {
    "기술적_적정성": 3,
    "예정가격_원가": 4,
    "발주계획_절차": 4,
    "MAS_일반": 3,
}

CLUSTER_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"기술적\s*적정성|기술적\s*요건\s*준수"), "기술적_적정성"),
    (re.compile(r"예정가격|원가계산|원가구성|원가상환|원가기반"), "예정가격_원가"),
    (re.compile(r"발주계획|구매결의|사전규격|시장조사.*발주"), "발주계획_절차"),
    (re.compile(r"\bMAS\b|다수공급자계약"), "MAS_일반"),
]

DEDUP_NOTE = (
    "동일 주제·동일 원본페이지 중복 금지 "
    "(파레토·MAS기준금액 등 회차당 1문항)"
)

IMPORTANCE_KEYWORDS: dict[str, list[str]] = {
    "1": [
        "국가계약법", "지방계약법", "경쟁입찰", "수의계약", "입찰보증금", "계약보증금",
        "부정당업자", "이의신청", "재심청구", "해제", "해지", "낙성", "요물",
        "일반경쟁", "제한경쟁", "지명경쟁", "협상", "적격심사", "종합심사",
        "전자조달", "나라장터", "MAS", "2단계", "중소기업", "녹색", "혁신",
        "전략적", "공개경쟁", "붙임", "공고문", "참가자격", "기준일",
    ],
    "2": [
        "발주계획", "발주", "구매결의", "사전규격", "수요", "RFP", "원가", "비용",
        "적정", "협상", "가격", "분석", "계획", "입찰공고", "추정", "원가상환", "인센티브",
    ],
    "3": [
        "하도급", "검사", "검수", "설계변경", "이행보증", "계약보증금", "15%",
        "적격심사", "협상", "Turn-Key", "설계서", "시방서", "MAS", "이의제기",
        "변동", "준공", "대금", "지급", "보증", "해제", "해지",
    ],
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def stem_key(s: str) -> str:
    s = norm(s)
    s = re.split(r"\s*㉠", s)[0].strip()
    return re.sub(r"^\d+\.\s+", "", s)


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
    subject_no: str = ""

    def stable_id(self) -> str:
        return f"{self.subject_no}:{self.part}:{self.chapter}:{self.stype}:{self.qn}"

    def question_text(self) -> str:
        return "\n".join(self.lines)


def parse_stable_id(sid: str) -> tuple[str, int, int, str, int]:
    parts = sid.split(":")
    if len(parts) != 5:
        raise ValueError(f"invalid stable id: {sid}")
    return parts[0], int(parts[1]), int(parts[2]), parts[3], int(parts[4])


def parse_answers_from_extract(text: str, part_num: int) -> dict[tuple[int, int, str, int], tuple[str, str]]:
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
    if "㉠" not in stem or "\n   ㉠" in stem:
        return stem
    m = re.search(r"([?？])\s*(㉠.+)$", stem)
    if not m:
        return stem
    head, tail = stem[: m.end(1)], stem[m.start(2) :]
    parts = re.split(r"(?=㉠)", tail)
    return head + "\n   " + "\n   ".join(p.strip() for p in parts if p.strip())


def parse_questions_from_clean(
    clean_file: Path,
    answers: dict[tuple[int, int, str, int], tuple[str, str]],
    *,
    subject_no: str = "",
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
            choice_lines = [ln for ln in block if CHOICE_LINE.match(ln)]
            if len(choice_lines) < 4:
                continue
            ans, kw = answers.get((part, chapter, stype, qn), ("", ""))
            stem = stem_key(stem_raw.split("\n")[0])
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
                    subject_no=subject_no,
                )
            )
            continue
        i += 1
    flush_batch()
    return qs


def load_subject_answers(subject_no: str) -> dict[tuple[int, int, str, int], tuple[str, str]]:
    slug = str(SUBJECT_CATALOG[subject_no]["slug"])
    extract_dir = EXTRACT / slug
    all_answers: dict[tuple[int, int, str, int], tuple[str, str]] = {}
    for ef in sorted(extract_dir.glob("part*.md")):
        pm = PART_HEAD.search(ef.read_text(encoding="utf-8"))
        part = int(pm.group(1)) if pm else 0
        all_answers.update(parse_answers_from_extract(ef.read_text(encoding="utf-8"), part))
    return all_answers


def load_subject_pool(subject_no: str) -> list[Question]:
    slug = str(SUBJECT_CATALOG[subject_no]["slug"])
    clean_dir = CLEAN / slug / "parts_clean"
    answers = load_subject_answers(subject_no)
    pool: list[Question] = []
    for cf in sorted(clean_dir.glob("part*.md")):
        pool.extend(parse_questions_from_clean(cf, answers, subject_no=subject_no))
    return pool


def load_all_pools() -> dict[str, dict[str, Question]]:
    """subject_no -> stable_id -> Question"""
    out: dict[str, dict[str, Question]] = {}
    for sn, info in SUBJECT_CATALOG.items():
        if info["exam_type"] != "필기":
            continue
        out[sn] = {q.stable_id(): q for q in load_subject_pool(sn)}
    return out


def topic_tags(q: Question) -> list[str]:
    text = q.stem + " " + " ".join(q.lines)
    return [tag for pat, tag in TOPIC_RULES if pat.search(text)]


def topic_at_limit(tags: list[str], counts: Counter[str]) -> bool:
    return any(counts.get(tag, 0) >= TOPIC_MAX[tag] for tag in tags if tag in TOPIC_MAX)


def cluster_tags(q: Question) -> list[str]:
    text = q.stem + " " + " ".join(q.lines)
    return [tag for pat, tag in CLUSTER_RULES if pat.search(text)]


def cluster_at_limit(tags: list[str], counts: Counter[str]) -> bool:
    return any(counts.get(tag, 0) >= CLUSTER_MAX[tag] for tag in tags if tag in CLUSTER_MAX)


def strict_source_dedup(q: Question) -> bool:
    tags = topic_tags(q)
    return any(TOPIC_MAX.get(tag, 99) == 1 for tag in tags)


def source_key(source: str) -> str:
    if not source:
        return ""
    m = re.search(r"Part\s*\d+/[^\s),]+", source)
    return norm(m.group(0)) if m else norm(source)


def keyword_score(q: Question, subject_no: str) -> int:
    text = q.stem + " " + " ".join(q.lines)
    score = 0
    for kw in IMPORTANCE_KEYWORDS.get(subject_no, []):
        if kw in text:
            score += 12
    for kw in (q.kw or "").split():
        if len(kw) >= 2:
            score += 3
    return score


def hint_rank(q: Question, subject_no: str) -> int:
    type_rank = {"exam": 40, "multi": 30, "other": 20, "check": 10}.get(q.stype, 10)
    return keyword_score(q, subject_no) + type_rank + q.pri * 5


def load_used_stems(round_dir: Path) -> set[str]:
    prob = round_dir / "필기_모의_문제.md"
    if not prob.is_file():
        return set()
    stems: set[str] = set()
    for block in re.split(r"\n(?=\d+\. )", prob.read_text(encoding="utf-8")):
        m = re.match(r"\d+\.\s+(.+)", block)
        if m:
            stems.add(stem_key(m.group(1).split("\n")[0]))
    return stems


def load_manifest(round_dir: Path) -> dict[str, Any] | None:
    path = round_dir / "manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_from_selected(
    round_num: int,
    selected: dict[str, list[Question]],
    *,
    method: str = "agent",
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    num = 0
    for sn in ("1", "2", "3"):
        for q in selected[sn]:
            num += 1
            items.append(
                {
                    "exam_num": num,
                    "subject": sn,
                    "id": q.stable_id(),
                    "part": q.part,
                    "chapter": q.chapter,
                    "stype": q.stype,
                    "source": q.source,
                    "stem_preview": q.stem[:60],
                }
            )
    return {
        "round": round_num,
        "method": method,
        "counts": {sn: len(selected[sn]) for sn in ("1", "2", "3")},
        "total": sum(len(selected[sn]) for sn in ("1", "2", "3")),
        "items": items,
    }


def write_manifest(round_dir: Path, data: dict[str, Any]) -> Path:
    path = round_dir / "manifest.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def match_questions_from_problem_md(
    prob_path: Path, pools: dict[str, dict[str, Question]]
) -> dict[str, list[Question]]:
    """필기_모의_문제.md → 과목별 Question (manifest 없을 때 소급용)."""
    text = prob_path.read_text(encoding="utf-8")
    selected: dict[str, list[Question]] = {"1": [], "2": [], "3": []}
    current_sn = ""
    block_lines: list[str] = []

    def flush() -> None:
        nonlocal block_lines
        if not block_lines or not current_sn:
            block_lines = []
            return
        first = block_lines[0]
        qm = QUESTION_START.match(first)
        if not qm:
            block_lines = []
            return
        source = ""
        for ln in block_lines:
            sm = SOURCE_RE.search(ln)
            if sm:
                source = sm.group(1).strip()
        stem = stem_key(qm.group(2).split("\n")[0])
        pool = pools.get(current_sn, {})
        matched: Question | None = None
        for q in pool.values():
            if q.stem == stem and (not source or not q.source or source in q.source or q.source in source):
                matched = q
                break
        if matched is None:
            for q in pool.values():
                if q.stem == stem:
                    matched = q
                    break
        if matched:
            selected[current_sn].append(
                Question(
                    stem=matched.stem,
                    lines=block_lines.copy(),
                    source=source or matched.source,
                    part=matched.part,
                    chapter=matched.chapter,
                    stype=matched.stype,
                    pri=matched.pri,
                    qn=matched.qn,
                    ans=matched.ans,
                    kw=matched.kw,
                    subject_no=current_sn,
                )
            )
        block_lines = []

    for line in text.splitlines():
        if re.match(r"^##\s+1과목", line):
            flush()
            current_sn = "1"
            continue
        if re.match(r"^##\s+2과목", line):
            flush()
            current_sn = "2"
            continue
        if re.match(r"^##\s+3과목", line):
            flush()
            current_sn = "3"
            continue
        qm = QUESTION_START.match(line)
        if qm:
            flush()
            block_lines = [line]
            continue
        if block_lines:
            block_lines.append(line)
    flush()
    return selected


def collect_prior_ids(mock_root: Path, exclude_round: int) -> set[str]:
    ids: set[str] = set()
    for d in sorted(mock_root.glob("*회차")):
        m = re.match(r"(\d+)회차", d.name)
        if not m or int(m.group(1)) >= exclude_round:
            continue
        manifest = load_manifest(d)
        if manifest:
            for item in manifest.get("items", []):
                ids.add(str(item["id"]))
    return ids


def collect_prior_stems(mock_root: Path, exclude_round: int) -> set[str]:
    stems: set[str] = set()
    for d in sorted(mock_root.glob("*회차")):
        m = re.match(r"(\d+)회차", d.name)
        if m and int(m.group(1)) < exclude_round:
            stems |= load_used_stems(d)
    return stems


def questions_from_ids(
    subject_no: str, ids: list[str], pool: dict[str, Question]
) -> list[Question]:
    out: list[Question] = []
    for sid in ids:
        q = pool.get(sid)
        if q is None:
            raise KeyError(f"{subject_no}과목: pool에 없는 id {sid}")
        out.append(q)
    return out


def validate_selected(
    selected: dict[str, list[Question]],
    *,
    prior_ids: set[str] | None = None,
    prior_stems: set[str] | None = None,
    check_clusters: bool = True,
) -> list[str]:
    errors: list[str] = []
    topic_counts: Counter[str] = Counter()
    cluster_counts: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    stems: set[str] = set()
    ids: set[str] = set()
    num = 0

    for sn in ("1", "2", "3"):
        expected = FILGI_COUNTS[sn]
        if len(selected.get(sn, [])) != expected:
            errors.append(f"{sn}과목: {len(selected.get(sn, []))}/{expected}문항")
        for q in selected.get(sn, []):
            num += 1
            if not q.ans:
                errors.append(f"{num}번: 정답 없음 (id={q.stable_id()})")
            choice_lines = [ln for ln in q.lines if CHOICE_LINE.match(ln)]
            if len(choice_lines) < 4:
                errors.append(f"{num}번: 선지 4개 미만")
            if q.stype == "ox" or "(O/X)" in q.question_text():
                errors.append(f"{num}번: OX 문항 혼입")
            if not q.source:
                errors.append(f"{num}번: source 주석 없음")
            if q.stem in stems:
                errors.append(f"{num}번: 동일 지문 stem 중복")
            stems.add(q.stem)
            sid = q.stable_id()
            if sid in ids:
                errors.append(f"{num}번: stable ID 중복 ({sid})")
            ids.add(sid)
            if prior_ids and sid in prior_ids:
                errors.append(f"{num}번: 이전 회차 사용 id ({sid})")
            if prior_stems and q.stem in prior_stems:
                errors.append(f"{num}번: 이전 회차 사용 지문")
            for tag in topic_tags(q):
                topic_counts[tag] += 1
                if topic_counts[tag] > TOPIC_MAX.get(tag, 99):
                    errors.append(
                        f"{num}번: 주제 '{tag}' 상한 초과 "
                        f"({topic_counts[tag]}/{TOPIC_MAX[tag]})"
                    )
            for tag in cluster_tags(q):
                cluster_counts[tag] += 1
                if check_clusters and cluster_counts[tag] > CLUSTER_MAX.get(tag, 99):
                    errors.append(
                        f"{num}번: 클러스터 '{tag}' 상한 초과 "
                        f"({cluster_counts[tag]}/{CLUSTER_MAX[tag]})"
                    )
            sk = source_key(q.source)
            if sk and strict_source_dedup(q):
                scoped = f"{sn}:{sk}"
                sources[scoped] += 1
                if sources[scoped] > 1:
                    errors.append(f"{num}번: 원본 페이지 중복 ({scoped})")

        check_n = sum(1 for q in selected.get(sn, []) if q.stype == "check")
        max_check = max(1, int(expected * 0.2))
        if check_n > max_check:
            errors.append(
                f"{sn}과목: Check Q&A {check_n}문항 (상한 {max_check})"
            )

    total = sum(len(selected.get(sn, [])) for sn in ("1", "2", "3"))
    if total != 80:
        errors.append(f"합계 {total}/80문항")
    return errors


def format_question(num: int, q: Question) -> str:
    stem = re.sub(r"^\d+\.\s+", "", q.lines[0])
    stem = split_giyeok_items(stem)
    out = [f"{num}. {stem}"]
    for ln in q.lines[1:]:
        if SOURCE_RE.search(ln) or ID_RE.search(ln):
            continue
        out.append(ln)
    out.append(f"<!-- id: {q.stable_id()} -->")
    out.append(f"<!-- source: {q.source} -->")
    return "\n".join(out)


def correct_choice_text(q: Question) -> str:
    for ln in q.lines:
        m = CHOICE_FULL.match(ln)
        if m and m.group(1) == q.ans:
            return m.group(2).strip()
    return ""


def keyword_line(q: Question) -> str:
    if q.kw:
        return q.kw.strip()
    return correct_choice_text(q)


def coverage_report(selected: dict[str, list[Question]]) -> str:
    lines = ["## Part·Chapter 분포"]
    for sn in ("1", "2", "3"):
        cnt: Counter[tuple[int, int]] = Counter()
        for q in selected[sn]:
            cnt[(q.part, q.chapter)] += 1
        parts = ", ".join(f"P{p}Ch{c}:{n}" for (p, c), n in sorted(cnt.items()))
        lines.append(f"- {sn}과목 ({len(selected[sn])}문항): {parts}")
    return "\n".join(lines)


def write_round_files(
    round_num: int,
    selected: dict[str, list[Question]],
    round_dir: Path,
    *,
    method: str = "agent",
    note: str | None = None,
) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    default_note = (
        f"> 선별: 에이전트 검토 후 확정 · validate_mock_exam.py 통과 · "
        f"{round_num - 1}회차 이전 미출제"
    )
    prob = [
        f"# 공공조달관리사 1회 필기 모의 {round_num}회차 — 문제",
        "",
        "> 필기 합계 80문항 · 2시간 · CBT 4지 택일형",
        "> 1과목 30문항 · 2과목 20문항 · 3과목 30문항",
        "",
        "> 출제 기준: docs/시험_안내.md, docs/문제집_프롬프트/시험모의_선별.md",
        "",
        note or default_note,
        "",
    ]
    ans = [
        f"# 공공조달관리사 1회 필기 모의 {round_num}회차 — 정답",
        "",
        "> 1과목 1~30 · 2과목 31~50 · 3과목 51~80",
        "",
    ]
    for sn in ("1", "2", "3"):
        start = FILGI_OFFSETS[sn] + 1
        end = FILGI_ENDS[sn]
        ename = SUBJECT_NAMES[sn]
        prob += [f"## {sn}과목 {ename} ({start}~{end})", ""]
        ans += [f"## {sn}과목 ({start}~{end})", ""]
        for i, q in enumerate(selected[sn], start):
            prob.append(format_question(i, q))
            prob.append("")
            src = f" ({q.source})" if q.source else ""
            ans.append(f"{i}. {q.ans} — {keyword_line(q)}{src}")
        ans.append("")

    (round_dir / "필기_모의_문제.md").write_text("\n".join(prob).rstrip() + "\n", encoding="utf-8")
    (round_dir / "필기_모의_정답.md").write_text("\n".join(ans).rstrip() + "\n", encoding="utf-8")
    write_manifest(round_dir, manifest_from_selected(round_num, selected, method=method))


def format_candidate_entry(q: Question, subject_no: str, rank: int) -> str:
    lines = [
        f"<!-- id: {q.stable_id()} -->",
        f"<!-- hint_rank: {rank} -->",
        f"<!-- stype: {q.stype} -->",
        f"<!-- source: {q.source} -->",
    ]
    for ln in q.lines:
        if SOURCE_RE.search(ln):
            continue
        lines.append(ln)
    lines.append("")
    return "\n".join(lines)


def backfill_manifest(round_dir: Path, pools: dict[str, dict[str, Question]]) -> dict[str, Any] | None:
    if load_manifest(round_dir):
        return load_manifest(round_dir)
    prob = round_dir / "필기_모의_문제.md"
    if not prob.is_file():
        return None
    m = re.match(r"(\d+)회차", round_dir.name)
    round_num = int(m.group(1)) if m else 0
    selected = match_questions_from_problem_md(prob, pools)
    if sum(len(selected[sn]) for sn in ("1", "2", "3")) != 80:
        return None
    data = manifest_from_selected(round_num, selected, method="backfill")
    write_manifest(round_dir, data)
    return data


def load_from_draft(round_dir: Path, pools: dict[str, dict[str, Question]]) -> dict[str, list[Question]]:
    draft = round_dir / "_draft"
    manifest_path = draft / "manifest.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        selected: dict[str, list[Question]] = {}
        for sn in ("1", "2", "3"):
            ids = data.get("subjects", {}).get(sn, [])
            selected[sn] = questions_from_ids(sn, ids, pools[sn])
        return selected

    selected: dict[str, list[Question]] = {"1": [], "2": [], "3": []}
    for sn in ("1", "2", "3"):
        path = draft / f"{sn}과목_선별.md"
        if not path.is_file():
            raise FileNotFoundError(f"draft 없음: {path}")
        ids: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            m = ID_RE.search(line)
            if m:
                ids.append(m.group(1).strip())
        if len(ids) != FILGI_COUNTS[sn]:
            raise ValueError(f"{sn}과목 draft: id {len(ids)}개 (목표 {FILGI_COUNTS[sn]})")
        selected[sn] = questions_from_ids(sn, ids, pools[sn])
    return selected


def open_mock_exam_html(html_path: Path) -> bool:
    """기본 브라우저에서 필기_응시.html 연다 (macOS: open)."""
    import subprocess
    import sys

    path = html_path.resolve()
    if not path.is_file():
        return False
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform == "win32":
        subprocess.run(["cmd", "/c", "start", "", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
    return True


def build_mock_exam_player_for_round(
    round_num: int,
    mock_root: Path | None = None,
    *,
    open_browser: bool = True,
) -> Path:
    """필기_응시.html 생성 후 (기본) 브라우저에서 연다."""
    import subprocess
    import sys

    mock_root = mock_root or MOCK_ROOT_DEFAULT
    tools_dir = Path(__file__).resolve().parent
    root = tools_dir.parent
    cmd = [
        sys.executable,
        str(tools_dir / "build_mock_exam_player.py"),
        "--round",
        str(round_num),
        "--mock-root",
        str(mock_root),
    ]
    if not open_browser:
        cmd.append("--no-open")
    subprocess.run(cmd, cwd=root, check=True)
    return mock_root / f"{round_num}회차" / "필기_응시.html"

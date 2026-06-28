"""_draft 선별본 파싱·병합 공통 로직 (통합 80문항 · 과목 전용 공용)."""

from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")
ID_RE = re.compile(r"<!--\s*id:\s*([^>]+?)\s*-->")
CHOICE_RE = re.compile(r"^\s*([①②③④])\s+(.+)$")
HEADER_ONLY = re.compile(r"^###\s*(\d+)\.\s*$")
Q_LINE = re.compile(r"^(?:###\s*)?(\d+)\.\s+(.+)$")
ANS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([①②③④])\s*\|")


def fix_stable_id(sid: str, subject: int) -> str:
    parts = sid.strip().split(":")
    if len(parts) != 5:
        return sid.strip()
    if subject == 1 and parts[0] != "1":
        parts[0] = "1"
    return ":".join(parts)


def parse_answer_table(text: str) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("## 정답"):
            in_table = True
            continue
        if in_table:
            if line.startswith("## ") and "정답" not in line:
                break
            m = ANS_ROW.match(line.strip())
            if m:
                out[int(m.group(1))] = (m.group(2).strip(), m.group(3))
    return out


def is_question_start(line: str) -> bool:
    if line.startswith("## Part") or line.startswith("### Part"):
        return False
    if HEADER_ONLY.match(line):
        return True
    m = Q_LINE.match(line)
    if not m:
        return False
    if re.match(r"^[①②③④]", m.group(2).strip()):
        return False
    return True


def parse_questions(text: str, *, subject: int | None = None) -> list[dict]:
    m = re.search(r"^## 정답", text, re.M)
    body = text[: m.start()] if m else text
    lines = body.splitlines()
    questions: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        local_no = None
        stem = ""
        ho = HEADER_ONLY.match(line)
        if ho:
            local_no = int(ho.group(1))
            i += 1
        elif is_question_start(line):
            qm = Q_LINE.match(line)
            local_no = int(qm.group(1))
            stem = qm.group(2).strip()
            i += 1
        else:
            i += 1
            continue

        choices: list[tuple[str, str]] = []
        source = ""
        sid = ""
        while i < len(lines):
            ln = lines[i]
            if is_question_start(ln):
                break
            if ln.startswith("## ") and not ln.startswith("## Part"):
                break
            if ln.strip() == "---" and choices:
                break
            sm = SOURCE_RE.search(ln)
            if sm:
                source = sm.group(1).strip()
                i += 1
                continue
            im = ID_RE.search(ln)
            if im:
                raw = im.group(1).strip()
                sid = fix_stable_id(raw, subject) if subject is not None else raw
                i += 1
                continue
            if ln.strip().startswith("<!--"):
                i += 1
                continue
            cm = CHOICE_RE.match(ln)
            if cm:
                choices.append((cm.group(1), cm.group(2).strip()))
                i += 1
                continue
            if ln.strip() and not ln.startswith("#"):
                stem = (stem + " " + ln.strip()).strip() if stem else ln.strip()
            i += 1
        if len(choices) >= 4 and stem and local_no is not None:
            questions.append(
                {
                    "local_no": local_no,
                    "stem": stem,
                    "choices": choices[:4],
                    "source": source,
                    "stable_id": sid,
                }
            )
    questions.sort(key=lambda q: q["local_no"])
    return questions


def format_question(exam_no: int, q: dict) -> str:
    lines = [f"{exam_no}. {q['stem']}"]
    for label, text in q["choices"]:
        lines.append(f"   {label} {text}")
    lines.append(f"<!-- source: {q['source']} -->")
    lines.append(f"<!-- id: {q['stable_id']} -->")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    out_dir: Path,
    *,
    round_no: int,
    problem_parts: list[str],
    answer_parts: list[str],
    manifest: dict,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "필기_모의_문제.md").write_text("".join(problem_parts), encoding="utf-8")
    (out_dir / "필기_모의_정답.md").write_text("".join(answer_parts), encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(manifest["items"])

#!/usr/bin/env python3
"""1~4과목 전체·누적 오답 CBT 공개 페이지를 생성한다."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STUDY = DOCS / "study"
ASSETS = DOCS / "assets"
PRACTICAL_BANK = (
    ROOT
    / "output"
    / "problem_book_final"
    / "4과목_공공조달 관리실무"
    / "4과목_문제집.md"
)
PRACTICAL_EXTRACT = ROOT / "output" / "agent_extract" / "4과목_공공조달 관리실무"

SUBJECTS = {
    1: ("공공조달과 법제도 이해", 7),
    2: ("공공조달계획 수립 및 분석", 4),
    3: ("공공계약관리", 4),
    4: ("공공조달 관리실무", 8),
}
ACTIVE_SUBJECTS = (1, 2, 3, 4)
SYMBOL_TO_KEY = {"①": "1", "②": "2", "③": "3", "④": "4"}
QUESTION_RE = re.compile(r"const QUESTIONS = (\[.*?\]);\nconst STORAGE_KEY", re.DOTALL)
ANSWER_RE = re.compile(r"window\.CBT_ANSWER_KEY=(\[.*?\]);")
PART_RE = re.compile(r"^(\d+)과목-part(\d+)-exam$")
SECTION_RE = re.compile(
    r"(?ms)^### CHAPTER (\d+) (.*?) — (.*?)\n(.*?)(?=^### |^## Part |\Z)"
)
ITEM_RE = re.compile(
    r"(?ms)^(\d+)\.\s+(.*?)(?=^<!--\s*source:|^\d+\.\s+|\Z)"
)
SOURCE_RE = re.compile(r"<!--\s*source:\s*(.*?)\s*-->")
TYPE_SLUG = {
    "Check Q&A": "cqa",
    "바로 Check": "check",
    "핵심 최종점검": "final",
    "서술형 출제예상문제": "essay",
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def load_written_questions() -> list[dict]:
    text = PRACTICAL_BANK.read_text(encoding="utf-8")
    questions: list[dict] = []
    part = 0
    cursor = 0
    part_matches = list(re.finditer(r"(?m)^## Part (\d+) 문제집\s*$", text))
    for part_index, part_match in enumerate(part_matches):
        part = int(part_match.group(1))
        end = part_matches[part_index + 1].start() if part_index + 1 < len(part_matches) else len(text)
        part_text = text[part_match.end():end]
        for section in SECTION_RE.finditer(part_text):
            chapter = int(section.group(1))
            section_title = section.group(3).strip()
            question_type = TYPE_SLUG.get(section_title, "custom")
            body = section.group(4)
            for item in ITEM_RE.finditer(body):
                number = int(item.group(1))
                stem = re.sub(r"\s+", " ", item.group(2)).strip()
                source_tail = body[item.end():]
                source_match = SOURCE_RE.search(source_tail)
                source = source_match.group(1).strip() if source_match else f"Part {part}"
                cursor += 1
                questions.append(
                    {
                        "no": cursor,
                        "id": f"4:{part}:{chapter}:{question_type}:{number}",
                        "part": part,
                        "chapter": chapter,
                        "group": f"Part {part} · Chapter {chapter}",
                        "stem": stem,
                        "source": source,
                        "choices": [],
                        "answer": None,
                    }
                )
    if len(questions) != 1244:
        raise ValueError(f"4과목 문항 수 오류: {len(questions)} != 1244")
    ids = [question["id"] for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("4과목 stable id 중복")
    return questions


def load_written_questions_legacy() -> list[dict]:
    """구형 섹션 표기가 섞여도 1,244문항을 안정적으로 읽는다."""
    text = PRACTICAL_BANK.read_text(encoding="utf-8")
    questions: list[dict] = []
    part_matches = list(re.finditer(r"(?m)^## Part (\d+) 문제집\s*$", text))
    for part_index, part_match in enumerate(part_matches):
        part = int(part_match.group(1))
        end = part_matches[part_index + 1].start() if part_index + 1 < len(part_matches) else len(text)
        block = text[part_match.end():end]
        headings = list(re.finditer(r"(?m)^### (.*?)\s*$", block))
        section_number = 0
        for heading_index, heading in enumerate(headings):
            heading_text = heading.group(1).strip()
            chapter_match = re.match(r"CHAPTER\s+(\d+)\s+(.*?)\s+—\s+(.*)", heading_text)
            if not chapter_match:
                continue
            section_number += 1
            chapter = int(chapter_match.group(1))
            section_title = chapter_match.group(3).strip()
            question_type = TYPE_SLUG.get(section_title, "custom")
            section_end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(block)
            body = block[heading.end():section_end]
            starts = list(re.finditer(r"(?m)^(\d+)\.\s+", body))
            for item_index, start in enumerate(starts):
                item_end = starts[item_index + 1].start() if item_index + 1 < len(starts) else len(body)
                raw = body[start.end():item_end]
                source_match = SOURCE_RE.search(raw)
                stem = SOURCE_RE.sub("", raw)
                stem = re.sub(r"\s+", " ", stem).strip()
                number = int(start.group(1))
                questions.append(
                    {
                        "no": len(questions) + 1,
                        "id": f"4:{part}:{section_number}:{number}",
                        "part": part,
                        "chapter": chapter,
                        "section": section_number,
                        "kind": question_type,
                        "group": f"Part {part} · Chapter {chapter}",
                        "stem": stem,
                        "source": source_match.group(1).strip() if source_match else f"Part {part}",
                        "choices": [],
                        "answer": None,
                    }
                )
    if len(questions) != 1244:
        raise ValueError(f"4과목 문항 수 오류: {len(questions)} != 1244")
    ids = [question["id"] for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("4과목 stable id 중복")
    return questions


def _section_type(title: str) -> str:
    if "서술형" in title:
        return "essay"
    if "핵심 최종점검" in title:
        return "final"
    if "Check Q&A" in title:
        return "cqa"
    if "바로 Check" in title:
        return "check"
    raise ValueError(f"알 수 없는 4과목 문항 유형: {title}")


def _numbered_entries(text: str, expected: int) -> list[str]:
    """줄바꿈 없이 이어진 정답 번호도 순서대로 분리한다."""
    starts: list[tuple[int, int]] = []
    cursor = 0
    for number in range(1, expected + 1):
        match = re.search(rf"(?<!\d){number}\.\s+", text[cursor:])
        if not match:
            raise ValueError(f"4과목 정답 {number}번 누락")
        starts.append((cursor + match.start(), cursor + match.end()))
        cursor += match.end()
    answers: list[str] = []
    for index, (_, content_start) in enumerate(starts):
        content_end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        answer = re.sub(r"\s+", " ", text[content_start:content_end]).strip()
        if not answer:
            raise ValueError(f"4과목 빈 정답: {index + 1}")
        answers.append(answer)
    return answers


def load_written_answers(questions: list[dict]) -> dict[str, str]:
    answer_map: dict[str, str] = {}
    counts: dict[tuple[int, int], int] = {}
    for question in questions:
        key = (question["part"], question["section"])
        counts[key] = counts.get(key, 0) + 1

    for part in range(1, 9):
        text = (PRACTICAL_EXTRACT / f"part{part}.md").read_text(encoding="utf-8")
        marker = re.search(rf"(?m)^## Part {part} 정답 및 해설\s*$", text)
        if not marker:
            raise ValueError(f"4과목 Part {part} 정답 섹션 누락")
        answer_text = text[marker.end():]
        headings = list(re.finditer(r"(?m)^#{2,3}\s+CHAPTER\s+(\d+)\s+(.*?)\s*$", answer_text))
        for index, heading in enumerate(headings):
            section_number = index + 1
            _section_type(heading.group(2))
            key = (part, section_number)
            expected = counts.get(key, 0)
            if not expected:
                raise ValueError(f"4과목 정답에 대응하는 문제 없음: {key}")
            end = headings[index + 1].start() if index + 1 < len(headings) else len(answer_text)
            for number, answer in enumerate(
                _numbered_entries(answer_text[heading.end():end], expected), 1
            ):
                answer_map[f"4:{part}:{section_number}:{number}"] = answer

    missing = [question["id"] for question in questions if question["id"] not in answer_map]
    if missing:
        raise ValueError(f"4과목 모범답안 누락: {len(missing)}개 (예: {missing[0]})")
    return answer_map


def load_objective_questions(subject: int) -> list[dict]:
    pages: list[tuple[int, Path]] = []
    for path in STUDY.glob(f"{subject}과목-part*-exam/index.html"):
        match = PART_RE.fullmatch(path.parent.name)
        if match:
            pages.append((int(match.group(2)), path))
    pages.sort()
    expected_parts = SUBJECTS[subject][1]
    if [part for part, _ in pages] != list(range(1, expected_parts + 1)):
        raise ValueError(f"{subject}과목 Part 공개본 누락")

    combined: list[dict] = []
    for part, path in pages:
        text = path.read_text(encoding="utf-8")
        question_match = QUESTION_RE.search(text)
        answer_match = ANSWER_RE.search(text)
        if not question_match or not answer_match:
            raise ValueError(f"문제 또는 정답키 누락: {path}")
        questions = json.loads(question_match.group(1))
        answers = json.loads(answer_match.group(1))
        if len(questions) != len(answers):
            raise ValueError(f"문제·정답 수 불일치: {path}")
        for question, symbol in zip(questions, answers):
            item = dict(question)
            item["no"] = len(combined) + 1
            item["part"] = part
            item["group"] = item.get("subjectName", f"Part {part}")
            item["answer"] = SYMBOL_TO_KEY[symbol]
            combined.append(item)
    return combined


def page_html(subject: int, mode: str, count: int) -> str:
    title = SUBJECTS[subject][0]
    is_wrong = mode == "wrong"
    heading = f"{subject}과목 오답 CBT" if is_wrong else f"{subject}과목 전체 CBT"
    if subject == 4:
        note = (
            "모범답안을 확인해 직접 정답 판정하면 오답 목록에서 제거됩니다."
            if is_wrong
            else "답안 입력 후 모범답안을 확인하고 직접 정답·오답을 판정합니다."
        )
    else:
        note = (
            "정답을 맞히면 오답 목록에서 즉시 제거됩니다."
            if is_wrong
            else "답안을 클릭하면 즉시 채점되며 오답은 과목별로 누적됩니다."
        )
    asset = "../../assets" if is_wrong else "../assets"
    mode_label = "오답 재풀이" if is_wrong else f"전체 {count:,}문항"
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="공공조달관리사 {heading}"><title>{heading} · 공공조달관리사</title>
<link rel="stylesheet" href="{asset}/cumulative-cbt.css"></head><body>
<header class="topbar"><div><small>{mode_label}</small><h1>{heading}</h1><p>{title} · {note}</p></div></header>
<main id="cbt-app" class="cbt-shell" aria-live="polite"><p class="loading">문제은행을 불러오는 중입니다.</p></main>
<script>window.CBT_CONFIG={_json({"subject": subject, "mode": mode, "title": title})};</script>
<script src="{asset}/subject{subject}-bank.js"></script><script src="{asset}/{'cumulative-cbt.js' if subject == 4 else 'objective-cumulative-cbt.js'}"></script>
</body></html>
"""


def build(destination: Path) -> dict[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    assets = destination / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    counts: dict[int, int] = {}
    for subject in (1, 2, 3):
        questions = load_objective_questions(subject)
        counts[subject] = len(questions)
        (assets / f"subject{subject}-bank.js").write_text(
            "window.CBT_BANK=" + _json(questions) + ";\n", encoding="utf-8"
        )
    questions = load_written_questions_legacy()
    written_answers = load_written_answers(questions)
    for question in questions:
        question["answer"] = written_answers[question["id"]]
    counts[4] = len(questions)
    (assets / "subject4-bank.js").write_text(
        "window.CBT_BANK=" + _json(questions) + ";\n", encoding="utf-8"
    )
    for name in ("cumulative-cbt.js", "objective-cumulative-cbt.js", "cumulative-cbt.css"):
        shutil.copy2(ASSETS / name, assets / name)
    for subject, count in counts.items():
        subject_dir = destination / f"{subject}과목"
        wrong_dir = destination / "오답" / f"{subject}과목"
        subject_dir.mkdir(parents=True, exist_ok=True)
        wrong_dir.mkdir(parents=True, exist_ok=True)
        (subject_dir / "index.html").write_text(page_html(subject, "all", count), encoding="utf-8")
        (wrong_dir / "index.html").write_text(page_html(subject, "wrong", count), encoding="utf-8")
    return counts


def sync_to_docs(generated: Path) -> None:
    for relative in (Path("assets"), Path("오답")):
        target = DOCS / relative
        if target.exists() and relative.name == "오답":
            shutil.rmtree(target)
        if relative.name == "assets":
            for path in (generated / relative).iterdir():
                shutil.copy2(path, target / path.name)
        else:
            shutil.copytree(generated / relative, target)
    for subject in ACTIVE_SUBJECTS:
        shutil.copy2(generated / f"{subject}과목" / "index.html", DOCS / f"{subject}과목" / "index.html")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cumulative-cbt-") as temp:
        generated = Path(temp) / "docs"
        counts = build(generated)
        if args.check:
            paths = [
                *(Path(f"{subject}과목/index.html") for subject in ACTIVE_SUBJECTS),
                *(Path(f"오답/{subject}과목/index.html") for subject in ACTIVE_SUBJECTS),
                *(Path(f"assets/subject{subject}-bank.js") for subject in ACTIVE_SUBJECTS),
                Path("assets/cumulative-cbt.js"),
                Path("assets/objective-cumulative-cbt.js"),
                Path("assets/cumulative-cbt.css"),
            ]
            errors = [path for path in paths if not (DOCS / path).is_file() or (DOCS / path).read_bytes() != (generated / path).read_bytes()]
            if errors:
                for path in errors:
                    print(f"생성 결과 불일치: {path}")
                return 1
            print("누적 오답 CBT 검증 완료: " + ", ".join(f"{subject}과목 {count:,}문항" for subject, count in counts.items()))
            return 0
        sync_to_docs(generated)
        print("누적 오답 CBT 생성 완료: " + ", ".join(f"{subject}과목 {count:,}문항" for subject, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

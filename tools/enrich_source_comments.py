"""블록 단위 출처 주석을 문항 단위로 전파한다."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import SUBJECT_CATALOG, subject_extract_dir  # noqa: E402

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답", re.MULTILINE)
QUESTION_START_RE = re.compile(r"^\s*\d+\.\s+\S")
SOURCE_RE = re.compile(r"^<!--\s*source:\s*.+?\s*-->\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s+")


def split_body_answer(text: str) -> tuple[str, str]:
    match = ANSWER_HEADING_RE.search(text)
    if not match:
        return text, ""
    return text[: match.start()], text[match.start() :]


def is_question_start(line: str) -> bool:
    return bool(QUESTION_START_RE.match(line))


def process_segment(segment: list[str]) -> tuple[list[str], int]:
    if not segment:
        return [], 0

    sources = [line for line in segment if SOURCE_RE.match(line)]
    if not sources:
        return segment, 0

    default_source = sources[-1]
    out: list[str] = []
    added = 0
    i = 0

    while i < len(segment):
        line = segment[i]
        if is_question_start(line):
            block = [line]
            i += 1
            while i < len(segment) and not is_question_start(segment[i]):
                block.append(segment[i])
                i += 1
            if not any(SOURCE_RE.match(x) for x in block):
                block.append(default_source)
                added += 1
            out.extend(block)
            continue
        out.append(line)
        i += 1

    return out, added


def enrich_body(body: str) -> tuple[str, int]:
    lines = body.splitlines()
    result: list[str] = []
    segment: list[str] = []
    added = 0

    for line in lines:
        if line.strip() == "---" or HEADING_RE.match(line):
            enriched, n = process_segment(segment)
            result.extend(enriched)
            segment = []
            added += n
            result.append(line)
            continue
        segment.append(line)

    enriched, n = process_segment(segment)
    result.extend(enriched)
    added += n
    return "\n".join(result).rstrip() + "\n", added


def enrich_part(path: Path, dry_run: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    body, answer = split_body_answer(text)
    enriched, added = enrich_body(body)
    if added and not dry_run:
        path.write_text(enriched + answer, encoding="utf-8")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(
        description="블록 단위 출처 주석을 개별 문항에 전파합니다.",
    )
    parser.add_argument("--subject", default="all", help="1~4 or all")
    parser.add_argument("--part", type=int, default=0, help="특정 Part만 (0=전체)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    subjects = list(SUBJECT_CATALOG) if args.subject == "all" else [args.subject]
    total = 0
    for subject_no in subjects:
        extract_dir = subject_extract_dir(subject_no)
        files = sorted(extract_dir.glob("part*.md"))
        if args.part:
            files = [extract_dir / f"part{args.part}.md"]
        for path in files:
            if not path.is_file():
                continue
            added = enrich_part(path, dry_run=args.dry_run)
            total += added
            if added:
                print(f"{path.name}: +{added} 출처 주석")
    print(f"완료: {total}건 추가")


if __name__ == "__main__":
    main()

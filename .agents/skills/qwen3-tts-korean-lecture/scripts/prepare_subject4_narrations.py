#!/usr/bin/env python3
"""Prepare speech-ready plain-text narrations for Subject 4 chapter lectures."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE_ROOT = ROOT / "output" / "chapter_lectures" / "4과목"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "qwen3_tts_audio"
SOURCE_END_HEADING = "근거와 기준일"
MANUAL_LESSON_IDS = {"PPM4-P01-L01"}
NUMBER_WORDS = {
    1: "첫째",
    2: "둘째",
    3: "셋째",
    4: "넷째",
    5: "다섯째",
    6: "여섯째",
    7: "일곱째",
    8: "여덟째",
    9: "아홉째",
    10: "열째",
}
CIRCLED_NUMBERS = {
    "①": "1번",
    "②": "2번",
    "③": "3번",
    "④": "4번",
    "⑤": "5번",
    "⑥": "6번",
    "⑦": "7번",
    "⑧": "8번",
    "⑨": "9번",
    "⑩": "10번",
}


@dataclass(frozen=True)
class Chapter:
    source: Path
    part: int
    part_title: str
    chapter: int
    title: str
    lesson_id: str
    legal_cutoff: str

    @property
    def stem(self) -> str:
        safe_title = re.sub(r"[\\/:*?\"<>|]", "_", self.title).strip().replace(" ", "_")
        return f"4과목_Part{self.part:02d}_Chapter{self.chapter:02d}_{safe_title}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Subject 4 Qwen3-TTS narration files.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--only", action="append", default=[], metavar="PXX-CXX")
    parser.add_argument("--force", action="store_true", help="Replace existing generated narrations, never a manual one.")
    parser.add_argument("--check", action="store_true", help="Validate expected narrations without writing.")
    return parser.parse_args()


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"Missing YAML front matter: {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"Unclosed YAML front matter: {path}") from exc
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Malformed front matter line in {path}: {line}")
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, "\n".join(lines[end + 1 :]).strip()


def load_chapters(source_root: Path) -> list[Chapter]:
    chapters: list[Chapter] = []
    for source in sorted(source_root.glob("part[0-9][0-9]/chapter[0-9][0-9].md")):
        metadata, _ = parse_front_matter(source)
        required = ("part", "part_title", "chapter", "title", "lesson_id", "legal_cutoff")
        missing = [key for key in required if not metadata.get(key)]
        if missing:
            raise ValueError(f"Missing metadata in {source}: {', '.join(missing)}")
        chapters.append(
            Chapter(
                source=source.resolve(),
                part=int(metadata["part"]),
                part_title=metadata["part_title"],
                chapter=int(metadata["chapter"]),
                title=metadata["title"],
                lesson_id=metadata["lesson_id"],
                legal_cutoff=metadata["legal_cutoff"],
            )
        )
    if not chapters:
        raise ValueError(f"No Subject 4 chapter lectures found under {source_root}")
    keys = [(chapter.part, chapter.chapter) for chapter in chapters]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate Part/Chapter identifiers found.")
    return chapters


def parse_selector(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"P(\d{2})-C(\d{2})", value, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid --only selector {value!r}; expected PXX-CXX.")
    return int(match.group(1)), int(match.group(2))


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[^>]+>", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("~~", "")
    for symbol, replacement in CIRCLED_NUMBERS.items():
        text = text.replace(symbol, replacement)
    text = re.sub(r"\bO\s*/\s*X\b", "진위형", text, flags=re.IGNORECASE)
    if "≠" in text:
        compared = [part.strip() for part in text.split("≠") if part.strip()]
        text = ", ".join(compared) + ". 이 항목들은 서로 다릅니다"
    text = text.replace("→", ", ")
    text = text.replace("⇒", ", 따라서 ")
    text = text.replace("≤", " 이하 ").replace("≥", " 이상 ")
    text = text.replace("<", " 미만 ").replace(">", " 초과 ")
    text = re.sub(r"(?<=[가-힣A-Za-z])/(?=[가-힣A-Za-z])", "과 ", text)
    text = text.replace("·", ", ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text


def finish_sentence(text: str) -> str:
    text = text.strip(" ;")
    if not text:
        return ""
    if text.endswith((".", "?", "!", "다.", "요.", "임.", "함.")):
        return text
    return text + "."


def topic_phrase(label: str) -> str:
    if not label:
        return ""
    last = label[-1]
    if "가" <= last <= "힣":
        has_final_consonant = (ord(last) - ord("가")) % 28 != 0
        return label + ("은" if has_final_consonant else "는")
    return label + "은"


def speak_heading(line: str, chapter_title: str) -> str:
    hashes, raw = line.split(" ", 1)
    title = strip_inline_markdown(raw.strip())
    if len(hashes) == 1 and title == chapter_title:
        return ""
    title = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", title).strip()
    if not title:
        return ""
    if title in {"문제", "정답과 해설", "정답과 채점", "정답과 채점 기준"}:
        return finish_sentence(title + "입니다")
    if title.endswith("할 수 있는가"):
        return finish_sentence(title[:-1] + "지 살펴봅니다")
    if title.endswith("인가"):
        return finish_sentence(title[:-2] + "인지 살펴봅니다")
    if title.endswith("한다"):
        return finish_sentence(title[:-2] + "하는 방법입니다")
    if title.endswith("된다"):
        return finish_sentence(title[:-2] + "되는 과정입니다")
    suffixes = {
        "않는다": "않는 원칙입니다",
        "가른다": "가르는 방법입니다",
        "고른다": "고르는 방법입니다",
        "넣는다": "넣는 방법입니다",
        "바꾼다": "바꾸는 방법입니다",
        "되찾아 준다": "되찾아 주는 방법입니다",
        "찾는다": "찾는 방법입니다",
        "읽는다": "읽는 방법입니다",
        "나눈다": "나누는 방법입니다",
        "만든다": "만드는 방법입니다",
        "세운다": "세우는 방법입니다",
        "쓴다": "쓰는 방법입니다",
        "본다": "살펴봅니다",
        "그린다": "그리는 방법입니다",
        "올린다": "올리는 방법입니다",
        "따른다": "따르는 방법입니다",
        "두 갈래다": "두 갈래입니다",
        "더 길다": "더 깁니다",
        "기록이다": "기록입니다",
        "할 수 있다": "할 수 있습니다",
        "될 수 있다": "될 수 있습니다",
        "시작될 수 있다": "시작될 수 있습니다",
    }
    for suffix, replacement in suffixes.items():
        if title.endswith(suffix):
            return finish_sentence(title[: -len(suffix)] + replacement)
    if title.endswith(("입니다", "합니다", "습니다")):
        return finish_sentence(title)
    return finish_sentence(title + "입니다")


def split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [strip_inline_markdown(cell.strip()) for cell in re.split(r"(?<!\\)\|", stripped)]


def is_table_delimiter(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def speak_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    spoken: list[str] = []
    for row in rows:
        cells = row + [""] * max(0, len(headers) - len(row))
        pairs = [(header, cell) for header, cell in zip(headers, cells) if cell.strip()]
        if not pairs:
            continue
        clauses: list[str] = []
        for header, value in pairs:
            value = value.strip().rstrip(".")
            if not header or header in {"항목", "구분", "번호"}:
                clauses.append(value)
            else:
                clauses.append(f"{topic_phrase(header)} {value}")
        sentences = [clause if clause.endswith(("?", "!")) else clause + "." for clause in clauses]
        spoken.append(" ".join(sentences))
    return spoken


def normalize_answer_language(line: str) -> str:
    line = re.sub(r"^정답\s*,?\s*해설\s*:\s*X\.\s*", "정답과 해설. 틀립니다. ", line, flags=re.IGNORECASE)
    line = re.sub(r"^정답\s*,?\s*해설\s*:\s*O\.\s*", "정답과 해설. 맞습니다. ", line, flags=re.IGNORECASE)
    line = re.sub(r"^정답[과·]해설\s*:\s*X\.\s*", "정답과 해설. 틀립니다. ", line, flags=re.IGNORECASE)
    line = re.sub(r"^정답[과·]해설\s*:\s*O\.\s*", "정답과 해설. 맞습니다. ", line, flags=re.IGNORECASE)
    line = re.sub(r"^정답\s*,?\s*해설\s*:\s*", "정답과 해설. ", line)
    line = re.sub(r"^정답[·과]해설\s*:\s*", "정답과 해설. ", line)
    line = re.sub(r"^정답\s*,?\s*채점(?:\s*기준)?\s*:\s*", "정답과 채점 기준. ", line)
    line = re.sub(r"^정답[·과]채점(?:\s*기준)?\s*:\s*", "정답과 채점 기준. ", line)
    return line


def body_to_spoken(body: str, chapter_title: str) -> str:
    lines = body.splitlines()
    spoken: list[str] = []
    index = 0
    in_fence = False
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        if re.fullmatch(r"#{2,6}\s+" + re.escape(SOURCE_END_HEADING), stripped):
            break
        if not stripped or re.fullmatch(r"[-*_]{3,}", stripped):
            if spoken and spoken[-1] != "":
                spoken.append("")
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and is_table_delimiter(lines[index + 1]):
            headers = split_table_row(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1
            spoken.extend(speak_table(headers, rows))
            spoken.append("")
            continue
        if re.match(r"^#{1,6}\s+", stripped):
            heading = speak_heading(stripped, chapter_title)
            if heading:
                spoken.append(heading)
                spoken.append("")
            index += 1
            continue
        line = re.sub(r"^>\s?", "", stripped)
        line = re.sub(r"^[-*+]\s+\[[ xX]\]\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        numbered = re.match(r"^(\d+)\.\s+(.*)$", line)
        if numbered:
            number = int(numbered.group(1))
            prefix = NUMBER_WORDS.get(number, f"{number}번째")
            line = f"{prefix}, {numbered.group(2)}"
        line = strip_inline_markdown(line)
        line = normalize_answer_language(line)
        if re.fullmatch(r"\[?\s*\]?", line):
            index += 1
            continue
        if line:
            spoken.append(finish_sentence(line))
        index += 1

    compact: list[str] = []
    for line in spoken:
        if line == "" and (not compact or compact[-1] == ""):
            continue
        compact.append(line)
    while compact and compact[-1] == "":
        compact.pop()
    return "\n".join(compact)


def render_narration(chapter: Chapter) -> str:
    _, body = parse_front_matter(chapter.source)
    spoken_body = body_to_spoken(body, chapter.title)
    year, month, day = (int(part) for part in chapter.legal_cutoff.split("-"))
    intro = (
        "공공조달관리사, 제4과목 공공조달 관리실무.\n"
        f"파트 {chapter.part}, {chapter.part_title}.\n"
        f"챕터 {chapter.chapter}, {chapter.title}입니다.\n\n"
        f"이 강의는 {year}년 {month}월 {day}일을 기준으로, "
        "공식 출제기준과 조달청 표준교재, 현행 공식 원문을 대조해 작성된 강의를 음성용으로 구성했습니다. "
        "실제 업무에서는 개별 공고의 기준일과 최신 법령, 고시를 다시 확인해야 합니다.\n\n"
    )
    outro = (
        "\n\n"
        f"이상으로 제4과목 공공조달 관리실무, 파트 {chapter.part}, "
        f"챕터 {chapter.chapter}, {chapter.title}를 마칩니다.\n"
    )
    return intro + spoken_body + outro


def narration_path(chapter: Chapter, output_dir: Path) -> Path:
    return output_dir / f"{chapter.stem}_대본.txt"


def validate_narration(chapter: Chapter, narration: str) -> list[str]:
    errors: list[str] = []
    forbidden = {
        "YAML metadata": r"(?m)^subject:\s*4$",
        "Markdown heading": r"(?m)^#{1,6}\s",
        "Markdown table pipe": r"(?m)^\s*\|",
        "Markdown link": r"\[[^]]+\]\([^)]+\)",
        "URL": r"https?://",
        "source appendix": r"(?m)^근거와 기준일",
        "unnatural heading ending": r"다입니다\.",
        "unnatural comparison token": r"와 같지 않음",
        "screen-style answer label": r"(?m)^정답\s*,?\s*(?:해설|채점)\s*:",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, narration):
            errors.append(f"contains {label}")
    if f"파트 {chapter.part}" not in narration or f"챕터 {chapter.chapter}" not in narration:
        errors.append("missing spoken Part/Chapter identity")
    if chapter.title not in narration:
        errors.append("missing chapter title")
    year, month, day = (int(part) for part in chapter.legal_cutoff.split("-"))
    if f"{year}년 {month}월 {day}일" not in narration:
        errors.append("missing legal cutoff date")
    if not narration.rstrip().endswith(f"{chapter.title}를 마칩니다."):
        errors.append("missing closing sentence")
    if len(narration) < 1000:
        errors.append("narration unexpectedly short")
    return errors


def body_before_sources(chapter: Chapter) -> str:
    _, body = parse_front_matter(chapter.source)
    return re.split(rf"(?m)^##\s+{re.escape(SOURCE_END_HEADING)}\s*$", body, maxsplit=1)[0]


def high_risk_numeric_tokens(text: str) -> Counter[str]:
    pattern = re.compile(
        r"\d[\d,]*(?:\.\d+)?\s*(?:퍼센트|%|억원|만원|원|개월|년|월|일|시간|분|초|자리|쪽|회|건|명|인월)"
    )
    lines = text.splitlines()
    retained: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.search(r"권장\s*통과선|총점\s*:", line):
            index += 1
            continue
        if re.match(r"^\s*#{1,6}\s+", line):
            index += 1
            continue
        if line.strip().startswith("|") and index + 1 < len(lines) and is_table_delimiter(lines[index + 1]):
            table = [line, lines[index + 1]]
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table.append(lines[index])
                rows.append(split_table_row(lines[index]))
                index += 1
            if any(any(cell.strip() for cell in row) for row in rows):
                retained.extend(table)
            continue
        retained.append(re.sub(r"^\s*\d+\.\s+", "", line))
        index += 1
    without_headings = "\n".join(retained)
    normalized = strip_inline_markdown(without_headings)
    normalized = re.sub(r"문제\s*\d+\.\s*", "", normalized)
    spoken_counters = {
        "한": "1",
        "두": "2",
        "세": "3",
        "네": "4",
        "다섯": "5",
        "여섯": "6",
        "일곱": "7",
        "여덟": "8",
        "아홉": "9",
        "열": "10",
    }
    counter_units = r"명|자리|회|건|개월|년|시간|분|초|인월"
    for word, number in spoken_counters.items():
        normalized = re.sub(
            rf"(?<![가-힣]){word}\s*(?=(?:{counter_units}))",
            number,
            normalized,
        )
    normalized = normalized.replace(" ", "")
    return Counter(
        match.group(0).replace(" ", "").replace("%", "퍼센트")
        for match in pattern.finditer(normalized)
    )


def missing_numeric_tokens(chapter: Chapter, narration: str) -> list[str]:
    source_tokens = high_risk_numeric_tokens(body_before_sources(chapter))
    narration_tokens = high_risk_numeric_tokens(narration)
    missing: list[str] = []
    for token, count in source_tokens.items():
        deficit = count - narration_tokens[token]
        if deficit > 0:
            missing.extend([token] * deficit)
    return missing


def main() -> int:
    args = parse_args()
    try:
        source_root = args.source_root.expanduser().resolve()
        output_dir = args.output_dir.expanduser().resolve()
        chapters = load_chapters(source_root)
        selected = {parse_selector(value) for value in args.only}
        if selected:
            known = {(chapter.part, chapter.chapter) for chapter in chapters}
            unknown = selected - known
            if unknown:
                raise ValueError("Unknown --only selector(s): " + ", ".join(f"P{p:02d}-C{c:02d}" for p, c in sorted(unknown)))
            chapters = [chapter for chapter in chapters if (chapter.part, chapter.chapter) in selected]
        failures: list[str] = []
        created = skipped = checked = 0
        for chapter in chapters:
            path = narration_path(chapter, output_dir)
            expected = render_narration(chapter)
            expected_errors = validate_narration(chapter, expected)
            missing_numbers = missing_numeric_tokens(chapter, expected)
            if missing_numbers:
                expected_errors.append("lost numeric tokens: " + ", ".join(missing_numbers[:12]))
            if expected_errors:
                failures.append(f"{chapter.lesson_id} generated invalid: {', '.join(expected_errors)}")
                continue
            if args.check:
                if not path.is_file():
                    failures.append(f"{chapter.lesson_id} missing: {path}")
                    continue
                actual = path.read_text(encoding="utf-8")
                actual_errors = validate_narration(chapter, actual)
                actual_missing_numbers = missing_numeric_tokens(chapter, actual)
                if actual_missing_numbers:
                    actual_errors.append(
                        "lost numeric tokens: " + ", ".join(actual_missing_numbers[:12])
                    )
                if actual_errors:
                    failures.append(f"{chapter.lesson_id} invalid: {', '.join(actual_errors)}")
                checked += 1
                continue
            if path.exists():
                is_manual = chapter.lesson_id in MANUAL_LESSON_IDS
                if is_manual or not args.force:
                    skipped += 1
                    print(f"skip {chapter.lesson_id}: {path}")
                    continue
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
            created += 1
            print(path)
        if failures:
            for failure in failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1
        if args.check:
            print(f"Validated {checked} Subject 4 narration files.")
        else:
            print(f"Created {created}; skipped {skipped} existing narration files.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

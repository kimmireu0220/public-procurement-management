#!/usr/bin/env python3
"""Build spoken-study scripts from the chapter-level fourth-subject question bank."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = (
    ROOT
    / "output"
    / "problem_book_final"
    / "4과목_공공조달 관리실무"
    / "문제정답_챕터별"
)
OUTPUT_DIR = ROOT / "output" / "podcast_scripts" / "4과목"


def natural_answer(answer: str) -> str:
    text = re.sub(r"\s*[—–-]\s*※.*$", "", answer.strip()).rstrip(".")
    if text.endswith(("다", "요", "음", "함", "불가", "가능")):
        return f"{text}."
    return f"{text}입니다."


def compact_answer(answer: str, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", answer.strip())
    text = re.sub(r"\s*[—–-]\s*※.*$", "", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def quote_particle(text: str) -> str:
    """Return Korean '이라고/라고' for the final Hangul syllable in text."""
    for char in reversed(text):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return "이라고" if (code - 0xAC00) % 28 else "라고"
    return "라고"


def restatement(question: str, answer: str) -> str | None:
    """Turn a short quiz question into a spoken declarative answer when possible."""
    key = compact_answer(answer)
    text = question.strip()
    replacements = (
        (r"무엇이라 하는가\?$", f"‘{key}’{quote_particle(key)} 합니다."),
        (r"무엇이라 하는가\.$", f"‘{key}’{quote_particle(key)} 합니다."),
        (r"무엇을 판단하기 위한 지표인가\?$", f"‘{key}’를 판단하는 지표입니다."),
        (r"무엇을 파악하기 위한 것인가\?$", f"‘{key}’를 파악하기 위한 겁니다."),
        (r"목적은 무엇인가\?$", f"목적은 ‘{key}’입니다."),
        (r"어디에서 확인할 수 있는가\?$", f"‘{key}’에서 확인할 수 있습니다."),
        (r"어디에서 확인하는가\?$", f"‘{key}’에서 확인합니다."),
        (r"무엇인가\?$", f"바로 ‘{key}’입니다."),
        (r"무엇인가\.$", f"바로 ‘{key}’입니다."),
        (r"어떻게 되는가\?$", f"‘{key}’가 됩니다."),
        (r"처리 결과는 어떠한가\?$", f"처리 결과는 ‘{key}’입니다."),
        (r"가능 여부는\?$", f"가능 여부의 결론은 ‘{key}’입니다."),
        (r"할 수 있는가\?$", f"결론은 ‘{key}’입니다."),
    )
    for pattern, replacement in replacements:
        if re.search(pattern, text):
            return re.sub(pattern, replacement, text)
    return None


def explanation(question: str, answer: str, index: int) -> str:
    key = compact_answer(answer)
    statement = restatement(question, answer)
    variants = (
        "기억할 때는",
        "헷갈리지 않으려면",
        "여기서는",
        "한 줄로 정리하면",
    )
    lead = variants[(index - 1) % len(variants)]

    if re.search(r"법률|법령|법적 근거|근거 법", question):
        first = statement or f"이 제도에 적용되는 법은 ‘{key}’입니다."
        return f"{first} {lead} 법령 이름과 줄임말을 한 세트로 묶어 두세요."
    if re.search(
        r"언제|얼마|며칠|몇\s*(?:일|년|개월|퍼센트|%)|"
        r"(?:최대|최소)\s*기간|기한은|기간은",
        question,
    ):
        first = statement or f"여기서 답이 되는 숫자나 기준 시점은 ‘{key}’입니다."
        return f"{first} {lead} 질문의 조건과 이 숫자를 붙여서 외우면 됩니다."
    if re.search(r"어디|시스템|플랫폼", question):
        first = statement or f"이 정보를 확인할 시스템은 ‘{key}’입니다."
        return f"{first} {lead} 찾으려는 정보와 시스템 이름을 짝지어 두세요."
    if "목적" in question:
        first = statement or f"이 절차의 목적은 ‘{key}’입니다."
        return f"{first} {lead} 세부 절차보다 먼저 ‘왜 하는가’를 잡으면 됩니다."
    if re.search(r"지표|판단하기 위한|파악하기 위한", question):
        first = statement or f"이 지표로 읽어내는 대상은 ‘{key}’입니다."
        return f"{first} {lead} 지표 이름과 해석 대상을 짝지어 두세요."
    if re.search(r"가능|불가능|여부|할 수 있는가", question):
        first = statement or f"결론부터 말하면 ‘{key}’입니다."
        return f"{first} {lead} 가능과 불가능을 가르는 조건까지 함께 보세요."
    if re.search(r"계산|산식|공식", question):
        first = statement or f"계산에서 잡아야 할 답은 ‘{key}’입니다."
        return f"{first} {lead} 결과만 외우지 말고 어떤 값을 비교하는지도 살펴보세요."
    if re.search(r"세 가지|3가지|두 가지|2가지|쓰시오", question):
        first = statement or f"묶어서 기억할 답은 ‘{key}’입니다."
        return f"{first} {lead} 항목을 순서대로 한 번 더 떠올려 보세요."
    if "기준" in question:
        first = statement or f"이때 판단 기준은 ‘{key}’입니다."
        return f"{first} {lead} 기준과 적용되는 상황을 함께 묶어 두세요."
    if re.search(r"효과|결과|처리", question):
        first = statement or f"그 상황에서 생기는 결과는 ‘{key}’입니다."
        return f"{first} {lead} 원인과 결과를 한 문장으로 이어 보세요."
    if re.search(r"주체|누가|담당", question):
        first = statement or f"이 역할을 맡는 주체는 ‘{key}’입니다."
        return f"{first} {lead} 역할과 담당 주체를 바꿔 놓는 함정을 조심하세요."
    if re.search(r"의미|뜻", question):
        first = statement or f"쉽게 말하면 ‘{key}’라는 뜻입니다."
        return f"{first} {lead} 용어와 실제 의미를 같이 잡아 두세요."
    if re.search(r"무엇이라 하는가|무엇인가|어떤 것", question):
        first = statement or f"이 질문의 핵심 용어는 ‘{key}’입니다."
        return f"{first} {lead} 문제 속 표현과 이 용어를 한 문장으로 묶어 보세요."
    first = statement or f"이 문제에서 잡아야 할 답은 ‘{key}’입니다."
    return f"{first} {lead} 질문의 조건과 답을 한 문장으로 연결하면 잘 남습니다."


def parse_chapter(path: Path) -> tuple[int, int, str, list[tuple[str, str]]]:
    text = path.read_text(encoding="utf-8")
    header = re.search(
        r"^# Part\s+(\d+)\s*·\s*CHAPTER\s+(\d+)\s+(.+)$",
        text,
        flags=re.MULTILINE,
    )
    if not header:
        raise ValueError(f"Could not parse chapter header: {path}")

    core_match = re.search(
        r"^## 핵심 최종점검\s*$\n(.*?)(?=^## 서술형 출제예상문제\s*$|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not core_match:
        raise ValueError(f"Could not find core questions: {path}")

    items = re.findall(
        r"^\*\*(\d+)\.\*\*\s*(.*?)\n+\s*→\s*(.*?)(?=\n+\*\*\d+\.\*\*|\Z)",
        core_match.group(1).strip(),
        flags=re.MULTILINE | re.DOTALL,
    )
    questions = [
        (re.sub(r"\s+", " ", question).strip(), re.sub(r"\s+", " ", answer).strip())
        for _, question, answer in items
    ]
    return int(header.group(1)), int(header.group(2)), header.group(3).strip(), questions


def safe_filename(part: int, chapter: int, title: str) -> str:
    title = re.sub(r"[^\w가-힣]+", "_", title, flags=re.UNICODE).strip("_")
    return f"Part{part}_Chapter{chapter:02d}_{title}.md"


def render(part: int, chapter: int, title: str, items: list[tuple[str, str]]) -> str:
    lines = [f"# [Part {part} Chapter {chapter} 팟캐스트 대본 — {title}]", ""]
    for index, (question, answer) in enumerate(items, start=1):
        lines.extend(
            [
                f"문제 {index}.",
                question,
                "",
                "잠깐 생각해 보세요.",
                "",
                "정답.",
                natural_answer(answer),
                "",
                "해설.",
                explanation(question, answer, index),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chapters = []
    for source in sorted(SOURCE_DIR.glob("Part*_CH*.md")):
        chapter = parse_chapter(source)
        chapters.append(chapter)
        part, number, title, items = chapter
        output = OUTPUT_DIR / safe_filename(part, number, title)
        output.write_text(render(part, number, title, items), encoding="utf-8")

    combined = ["# 공공조달 관리실무 팟캐스트 대본 합본", ""]
    for part, number, title, items in chapters:
        combined.append(render(part, number, title, items).rstrip())
        combined.extend(["", "---", ""])
    (OUTPUT_DIR / "전체_합본.md").write_text(
        "\n".join(combined).rstrip("-\n ") + "\n",
        encoding="utf-8",
    )

    total = sum(len(items) for _, _, _, items in chapters)
    index_lines = [
        "# 4과목 공공조달 관리실무 팟캐스트 대본",
        "",
        f"총 {len(chapters)}개 챕터, {total}문항. 서술형 출제예상문제와 Check/Q&A는 제외.",
        "",
        "| 순서 | 챕터 | 문항 수 | 파일 |",
        "|---:|---|---:|---|",
    ]
    for order, (part, number, title, items) in enumerate(chapters, start=1):
        filename = safe_filename(part, number, title)
        index_lines.append(
            f"| {order} | Part {part} Chapter {number} {title} | "
            f"{len(items)} | [{filename}]({filename}) |"
        )
    index_lines.extend(["", "[전체 합본](전체_합본.md)", ""])
    (OUTPUT_DIR / "README.md").write_text(
        "\n".join(index_lines),
        encoding="utf-8",
    )

    print(f"Built {len(chapters)} chapters and {total} questions in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

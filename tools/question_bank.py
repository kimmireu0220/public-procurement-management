"""과목별 문제은행 Markdown의 선택형 문항 인덱스 공통 파서."""

from __future__ import annotations

import re
from dataclasses import dataclass


CHOICE_RE = re.compile(r"^\s*([①②③④])\s+(.+)$")
Q_LINE = re.compile(r"^(\d+)\.\s+(.+)$")
SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")
EXPECTED_CHOICE_LABELS = ["①", "②", "③", "④"]


@dataclass(frozen=True)
class QuestionBankParserConfig:
    subject: int
    chapter_header: re.Pattern[str]
    check_type: str
    share_trailing_source: bool = False


@dataclass(frozen=True)
class QuestionBankParseIssue:
    line: int
    stable_id: str
    message: str

    def __str__(self) -> str:
        return f"line {self.line} · {self.stable_id}: {self.message}"


class QuestionBankParseError(ValueError):
    """문제은행 후보 문항을 안전하게 인덱싱할 수 없을 때의 누적 오류."""

    def __init__(self, issues: list[QuestionBankParseIssue]) -> None:
        self.issues = tuple(issues)
        details = " | ".join(str(issue) for issue in issues)
        super().__init__(f"문제은행 후보 문항 파싱 오류 {len(issues)}건: {details}")


@dataclass
class _PendingQuestion:
    stable_id: str
    line: int
    item: dict


def _section_type(line: str, check_type: str, current: str, *, allow_ox: bool) -> str:
    if "Check Q&A" in line:
        return check_type
    if "단원별 출제예상" in line:
        return "exam"
    if allow_ox and re.search(r"최종점검\s*OX|OX\s*퀴즈", line, re.I):
        return "ox"
    return current


def _is_binary_ox(choices: list[tuple[str, str]]) -> bool:
    if [label for label, _ in choices] != ["①", "②"]:
        return False
    values = [text.strip().upper() for _, text in choices]
    return values == ["O", "X"]


def parse_question_index(text: str, config: QuestionBankParserConfig) -> dict[str, dict]:
    """선택형 후보를 인덱싱하고 누락·중복 후보를 한 번에 보고한다."""

    lines = text.splitlines()
    part = 0
    chapter = 0
    question_type = "exam"
    out: dict[str, dict] = {}
    issues: list[QuestionBankParseIssue] = []
    seen: dict[str, int] = {}
    pending: list[_PendingQuestion] = []
    i = 0

    def add_issue(line: int, stable_id: str, message: str) -> None:
        issues.append(QuestionBankParseIssue(line, stable_id, message))

    def insert(candidate: _PendingQuestion, source: str) -> None:
        item = candidate.item
        item["source"] = source
        if candidate.stable_id in out:
            # seen 검사로 먼저 차단하지만, 사전의 조용한 overwrite를 마지막으로도 방어한다.
            add_issue(
                candidate.line,
                candidate.stable_id,
                "duplicate stable_id로 기존 후보를 덮어쓸 수 없음",
            )
            return
        out[candidate.stable_id] = item

    def flush_pending(source: str = "") -> None:
        nonlocal pending
        for candidate in pending:
            if source:
                insert(candidate, source)
            else:
                add_issue(candidate.line, candidate.stable_id, "source 주석 누락")
        pending = []

    while i < len(lines):
        line = lines[i]
        if line.startswith("## Part"):
            flush_pending()
            part_match = re.search(r"Part (\d+)", line)
            if part_match is not None:
                part = int(part_match.group(1))
            else:
                add_issue(
                    i + 1,
                    f"{config.subject}:?:?:?:?",
                    "Part 번호를 파싱할 수 없음",
                )
            chapter = 0
            i += 1
            continue
        if line.startswith("###"):
            flush_pending()
        chapter_match = config.chapter_header.match(line)
        if chapter_match:
            chapter = int(chapter_match.group(1))
            question_type = _section_type(
                line,
                config.check_type,
                question_type,
                allow_ox=True,
            )
            i += 1
            continue
        next_type = _section_type(
            line,
            config.check_type,
            question_type,
            allow_ox=line.startswith("#"),
        )
        if next_type != question_type:
            question_type = next_type
            i += 1
            continue

        source_match = SOURCE_RE.search(line)
        if source_match and pending:
            flush_pending(source_match.group(1).strip())
            i += 1
            continue

        question_match = Q_LINE.match(line.strip())
        if question_match and "(O/X)" in line:
            i += 1
            continue
        if not question_match or question_type == "ox":
            i += 1
            continue

        number = int(question_match.group(1))
        stem = question_match.group(2).strip()
        if re.match(r"^[①②③④]", stem):
            i += 1
            continue

        choices: list[tuple[str, str]] = []
        source = ""
        j = i + 1
        while j < len(lines):
            candidate_line = lines[j]
            if (
                Q_LINE.match(candidate_line.strip())
                or candidate_line.startswith("###")
                or candidate_line.startswith("##")
            ):
                break
            if candidate_line.strip() == "---":
                break
            source_match = SOURCE_RE.search(candidate_line)
            if source_match:
                source = source_match.group(1).strip()
            choice_match = CHOICE_RE.match(candidate_line)
            if choice_match:
                choices.append((choice_match.group(1), choice_match.group(2).strip()))
            j += 1

        # 단답형과 ① O/② X 문항은 필기 선택형 후보가 아니므로 기존처럼 제외한다.
        if not choices or _is_binary_ox(choices):
            i = j
            continue

        stable_id = f"{config.subject}:{part}:{chapter}:{question_type}:{number}"
        line_number = i + 1
        if part < 1 or chapter < 1:
            add_issue(line_number, stable_id, "Part 또는 Chapter 문맥 누락")
            i = j
            continue
        duplicate = stable_id in seen
        if duplicate:
            add_issue(
                line_number,
                stable_id,
                f"duplicate stable_id (최초 line {seen[stable_id]})",
            )
        else:
            seen[stable_id] = line_number

        labels = [label for label, _ in choices]
        valid_choices = labels == EXPECTED_CHOICE_LABELS
        if not valid_choices:
            rendered_labels = "".join(labels) if labels else "없음"
            add_issue(
                line_number,
                stable_id,
                f"후보 문항 선지는 ①②③④ 각 1개여야 함 (감지: {rendered_labels})",
            )

        if source and config.share_trailing_source:
            flush_pending(source)

        if duplicate or not valid_choices:
            i = j
            continue

        candidate = _PendingQuestion(
            stable_id=stable_id,
            line=line_number,
            item={"stem": stem, "choices": choices, "source": source},
        )
        if source:
            insert(candidate, source)
        elif config.share_trailing_source:
            pending.append(candidate)
        else:
            add_issue(line_number, stable_id, "source 주석 누락")
        i = j

    flush_pending()
    if issues:
        raise QuestionBankParseError(issues)
    return out

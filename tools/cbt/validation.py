"""모의고사 산출물 무결성 검증."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from cbt.parser import parse_questions

ANSWER_RE = re.compile(r"^(\d+)\.\s*([①②③④])\s*—", re.MULTILINE)
SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]*)-->")
STABLE_ID_RE = re.compile(r"^[1-4]:\d+:\d+:(?:exam|check|cqa):\d+$")
PRACTICAL_ID_RE = re.compile(r"^4:\d+:\d+:(?:essay|final):\d+$")
PRACTICAL_QUESTION_RE = re.compile(r"^###\s+(\d+)\.\s+", re.MULTILINE)
PRACTICAL_ANSWER_RE = re.compile(r"^###\s+(\d+)\.\s*$", re.MULTILINE)
VALID_ANSWERS = {"①", "②", "③", "④"}


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_round(manifest_path: Path) -> list[ValidationIssue]:
    """manifest가 있는 필기 회차 하나를 검증한다."""

    issues: list[ValidationIssue] = []
    round_dir = manifest_path.parent
    problem_path = round_dir / "필기_모의_문제.md"
    answer_path = round_dir / "필기_모의_정답.md"

    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [ValidationIssue(manifest_path, f"manifest를 읽을 수 없음: {exc}")]

    items = manifest.get("items")
    if not isinstance(items, list):
        return [ValidationIssue(manifest_path, "items가 배열이 아님")]

    total = manifest.get("total")
    if total != len(items):
        issues.append(
            ValidationIssue(manifest_path, f"total={total}, items={len(items)} 불일치")
        )

    expected_numbers = list(range(1, len(items) + 1))
    exam_numbers = [item.get("exam_no") for item in items]
    if exam_numbers != expected_numbers:
        issues.append(ValidationIssue(manifest_path, "exam_no가 1부터 연속되지 않음"))

    stable_ids = [item.get("stable_id") for item in items]
    if any(not isinstance(sid, str) or not STABLE_ID_RE.fullmatch(sid) for sid in stable_ids):
        issues.append(ValidationIssue(manifest_path, "stable_id 형식 오류 또는 누락"))
    if len(stable_ids) != len(set(stable_ids)):
        issues.append(ValidationIssue(manifest_path, "회차 내부 stable_id 중복"))

    if any(item.get("answer") not in VALID_ANSWERS for item in items):
        issues.append(ValidationIssue(manifest_path, "정답이 ①~④ 범위를 벗어남"))

    if not problem_path.is_file():
        issues.append(ValidationIssue(problem_path, "문제지 누락"))
    else:
        problem_text = problem_path.read_text(encoding="utf-8")
        questions = parse_questions(problem_text)
        if len(questions) != len(items):
            issues.append(
                ValidationIssue(
                    problem_path,
                    f"파싱 문항={len(questions)}, manifest={len(items)} 불일치",
                )
            )
        if [q["no"] for q in questions] != expected_numbers:
            issues.append(ValidationIssue(problem_path, "문제 번호가 1부터 연속되지 않음"))
        if any(len(q["choices"]) != 4 for q in questions):
            issues.append(ValidationIssue(problem_path, "선지가 정확히 4개가 아닌 문항 존재"))
        if [q["id"] for q in questions] != stable_ids:
            issues.append(ValidationIssue(problem_path, "문제지 id와 manifest stable_id 불일치"))
        sources = [source.strip() for source in SOURCE_RE.findall(problem_text)]
        if len(sources) != len(items) or any(not source for source in sources):
            issues.append(ValidationIssue(problem_path, "source 주석 누락 또는 빈 값"))
        if re.search(r"\(O/X\)", problem_text, re.IGNORECASE):
            issues.append(ValidationIssue(problem_path, "실제 필기에 없는 O/X 문항 포함"))

    if not answer_path.is_file():
        issues.append(ValidationIssue(answer_path, "정답지 누락"))
    else:
        answers = {
            int(number): answer
            for number, answer in ANSWER_RE.findall(answer_path.read_text(encoding="utf-8"))
        }
        if len(answers) != len(items):
            issues.append(
                ValidationIssue(
                    answer_path,
                    f"정답 수={len(answers)}, manifest={len(items)} 불일치",
                )
            )
        elif any(answers.get(item["exam_no"]) != item["answer"] for item in items):
            issues.append(ValidationIssue(answer_path, "정답지와 manifest 정답 불일치"))

    for required in ("index.html", "필기_응시.html", "필기_모의_응시.html", "교차검수.md"):
        path = round_dir / required
        if not path.is_file():
            issues.append(ValidationIssue(path, "필수 산출물 누락"))

    by_subject: dict[str, list[str]] = {}
    for sid in stable_ids:
        if isinstance(sid, str) and STABLE_ID_RE.fullmatch(sid):
            by_subject.setdefault(sid.split(":", 1)[0], []).append(sid)
    for subject, subject_ids in by_subject.items():
        check_count = sum(sid.split(":")[3] in {"check", "cqa"} for sid in subject_ids)
        if check_count / len(subject_ids) > 0.20:
            issues.append(
                ValidationIssue(
                    manifest_path,
                    f"{subject}과목 Check Q&A {check_count}/{len(subject_ids)}로 20% 초과",
                )
            )

    return issues


def validate_published_docs(root: Path) -> list[ValidationIssue]:
    """docs CBT가 cbt-meta.json의 원본과 동일한지 검증한다."""

    issues: list[ValidationIssue] = []
    meta_paths = [
        root / "docs" / "cbt-meta.json",
        root / "docs" / "1과목" / "cbt-meta.json",
        root / "docs" / "2과목" / "cbt-meta.json",
        root / "docs" / "3과목" / "cbt-meta.json",
    ]
    for meta_path in meta_paths:
        if not meta_path.is_file():
            issues.append(ValidationIssue(meta_path, "배포 메타 누락"))
            continue
        try:
            meta = _read_json(meta_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(ValidationIssue(meta_path, f"배포 메타를 읽을 수 없음: {exc}"))
            continue
        source = root / str(meta.get("source", ""))
        published = meta_path.parent / "index.html"
        if not source.is_file():
            issues.append(ValidationIssue(source, "배포 원본 누락"))
        if not published.is_file():
            issues.append(ValidationIssue(published, "배포 index.html 누락"))
        if source.is_file() and published.is_file() and source.read_bytes() != published.read_bytes():
            issues.append(ValidationIssue(published, f"배포본이 원본 {source}와 다름"))
    return issues


def validate_practical_round(round_dir: Path) -> list[ValidationIssue]:
    """실기 모의 회차의 문제·정답 번호와 추적 주석을 검증한다."""

    issues: list[ValidationIssue] = []
    problem_path = round_dir / "실기_모의_문제.md"
    answer_path = round_dir / "실기_모의_정답.md"
    if not problem_path.is_file():
        return [ValidationIssue(problem_path, "실기 문제지 누락")]
    if not answer_path.is_file():
        return [ValidationIssue(answer_path, "실기 정답지 누락")]

    problem_text = problem_path.read_text(encoding="utf-8")
    answer_text = answer_path.read_text(encoding="utf-8")
    question_numbers = [int(number) for number in PRACTICAL_QUESTION_RE.findall(problem_text)]
    expected_numbers = list(range(1, len(question_numbers) + 1))
    if question_numbers != expected_numbers:
        issues.append(ValidationIssue(problem_path, "실기 문제 번호가 1부터 연속되지 않음"))
    if not 15 <= len(question_numbers) <= 25:
        issues.append(
            ValidationIssue(problem_path, f"실기 문항 수 {len(question_numbers)}개가 20문항 내외 범위를 벗어남")
        )

    sources = [source.strip() for source in SOURCE_RE.findall(problem_text)]
    ids = [value.strip() for value in re.findall(r"<!--\s*id:\s*([^>]*)-->", problem_text)]
    if len(sources) != len(question_numbers) or any(not source for source in sources):
        issues.append(ValidationIssue(problem_path, "실기 source 주석 누락 또는 빈 값"))
    if len(ids) != len(question_numbers) or any(not PRACTICAL_ID_RE.fullmatch(value) for value in ids):
        issues.append(ValidationIssue(problem_path, "실기 id 주석 누락 또는 형식 오류"))
    if len(ids) != len(set(ids)):
        issues.append(ValidationIssue(problem_path, "실기 회차 내부 id 중복"))

    answer_numbers = [int(number) for number in PRACTICAL_ANSWER_RE.findall(answer_text)]
    if answer_numbers != expected_numbers:
        issues.append(ValidationIssue(answer_path, "실기 정답 번호가 문제 번호와 일치하지 않음"))
    return issues


def validate_all(root: Path) -> tuple[int, int, int, list[ValidationIssue]]:
    manifests = sorted((root / "output" / "mock_exam" / "필기").glob("**/manifest.json"))
    issues: list[ValidationIssue] = []
    item_count = 0
    for manifest_path in manifests:
        try:
            item_count += len(_read_json(manifest_path).get("items", []))
        except (OSError, json.JSONDecodeError):
            pass
        issues.extend(validate_round(manifest_path))
    practical_rounds = sorted(
        path.parent
        for path in (root / "output" / "mock_exam" / "실기").glob("*회차/실기_모의_문제.md")
    )
    for round_dir in practical_rounds:
        issues.extend(validate_practical_round(round_dir))
    issues.extend(validate_published_docs(root))
    return len(manifests), item_count, len(practical_rounds), issues

"""모의고사 산출물 무결성 검증."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from cbt.builder import OUTPUT_HTML_NAMES, render_html
from cbt.parser import parse_questions
from cbt.profiles import CbtProfile, FULL_MOCK, SUBJECT1, SUBJECT2, SUBJECT3

ANSWER_RE = re.compile(r"^(\d+)\.\s*([①②③④])\s*—", re.MULTILINE)
SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]*)-->")
STABLE_ID_RE = re.compile(r"^[1-3]:\d+:\d+:(?:exam|check|cqa):\d+$")
PRACTICAL_ID_RE = re.compile(r"^4:\d+:\d+:(?:essay|final):\d+$")
PRACTICAL_QUESTION_RE = re.compile(r"^###\s+(\d+)\.\s+", re.MULTILINE)
PRACTICAL_ANSWER_RE = re.compile(r"^###\s+(\d+)\.\s*$", re.MULTILINE)
VALID_ANSWERS = {"①", "②", "③", "④"}
ROUND_DIR_RE = re.compile(r"^(\d+)회차$")
PROFILE_BY_PARENT: dict[str, CbtProfile] = {
    "통합": FULL_MOCK,
    "1과목": SUBJECT1,
    "2과목": SUBJECT2,
    "3과목": SUBJECT3,
}
PROFILE_SUBJECTS = {
    "full": [1] * 30 + [2] * 20 + [3] * 30,
    "subject1": [1] * 30,
    "subject2": [2] * 20,
    "subject3": [3] * 30,
}
SUBJECT_SLUGS = {
    "1": "1과목_공공조달의 이해",
    "2": "2과목_공공조달 계획분석",
    "3": "3과목_공공계약관리",
    "4": "4과목_공공조달 관리실무",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _profile_for_round_dir(round_dir: Path) -> CbtProfile | None:
    return PROFILE_BY_PARENT.get(round_dir.parent.name)


def _validate_manifest_profile(
    manifest_path: Path,
    manifest: dict,
    items: list[dict],
    profile: CbtProfile | None,
) -> tuple[int | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    round_match = ROUND_DIR_RE.fullmatch(manifest_path.parent.name)
    directory_round = int(round_match.group(1)) if round_match else None
    if round_match is None:
        issues.append(ValidationIssue(manifest_path, "회차 디렉터리 이름 형식 오류"))
    elif manifest.get("round") != directory_round:
        issues.append(
            ValidationIssue(
                manifest_path,
                f"manifest round={manifest.get('round')}, 디렉터리 회차={directory_round} 불일치",
            )
        )

    if profile is None:
        issues.append(
            ValidationIssue(
                manifest_path,
                f"지원하지 않는 필기 프로필 경로: {manifest_path.parent.parent.name}",
            )
        )
        return directory_round, issues

    if manifest.get("total") != profile.question_count or len(items) != profile.question_count:
        issues.append(
            ValidationIssue(
                manifest_path,
                f"{profile.id} 프로필은 {profile.question_count}문항이어야 함",
            )
        )

    expected_subjects = PROFILE_SUBJECTS[profile.id]
    actual_subjects = [
        int(stable_id.split(":", 1)[0])
        if isinstance(stable_id, str) and STABLE_ID_RE.fullmatch(stable_id)
        else None
        for stable_id in (item.get("stable_id") for item in items)
    ]
    if actual_subjects != expected_subjects:
        issues.append(ValidationIssue(manifest_path, f"{profile.id} 프로필 과목 구성·순서 불일치"))

    expected_subject = None if profile.id == "full" else int(profile.id.removeprefix("subject"))
    if expected_subject is None:
        if "subject" in manifest:
            issues.append(ValidationIssue(manifest_path, "통합 manifest에는 subject 필드를 두지 않음"))
    elif manifest.get("subject") != expected_subject:
        issues.append(
            ValidationIssue(
                manifest_path,
                f"manifest subject={manifest.get('subject')}, 프로필 subject={expected_subject} 불일치",
            )
        )
    return directory_round, issues


def _validate_source_parts(
    problem_path: Path,
    sources: list[str],
    stable_ids: list[object],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for source, stable_id in zip(sources, stable_ids):
        if not isinstance(stable_id, str):
            continue
        id_parts = stable_id.split(":")
        part_match = re.search(r"Part\s+(\d+)/", source)
        if len(id_parts) >= 2 and part_match and id_parts[1] != part_match.group(1):
            issues.append(
                ValidationIssue(
                    problem_path,
                    f"{stable_id}: stable_id Part와 source Part 불일치 ({source})",
                )
            )
    return issues


def _validate_source_images(
    problem_path: Path,
    sources: list[str],
    stable_ids: list[object],
    root: Path,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for source, stable_id in zip(sources, stable_ids):
        if not isinstance(stable_id, str):
            issues.append(ValidationIssue(problem_path, "stable_id 형식 오류로 source 검증 불가"))
            continue
        subject = stable_id.split(":", 1)[0]
        part_match = re.search(r"Part\s+(\d+)/", source)
        if subject not in SUBJECT_SLUGS or not part_match:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: source Part 형식 오류"))
            continue
        part = int(part_match.group(1))
        range_match = re.search(r"page_(\d+)\.jpg\s*~\s*page_(\d+)\.jpg", source)
        if range_match:
            pages = list(range(int(range_match.group(1)), int(range_match.group(2)) + 1))
        else:
            pages = [int(value) for value in re.findall(r"page_(\d+)\.jpg", source)]
        if not pages:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: source 페이지 형식 오류"))
            continue
        for page in pages:
            image_path = (
                root
                / "sources"
                / "민간_박문각_수험서_jpg"
                / SUBJECT_SLUGS[subject]
                / f"Part {part}"
                / f"page_{page:04d}.jpg"
            )
            if not image_path.is_file():
                issues.append(ValidationIssue(problem_path, f"{stable_id}: 원본 이미지 누락 {image_path}"))
    return issues


def _validate_round_html(
    round_dir: Path,
    questions: list[dict],
    round_no: int | None,
    profile: CbtProfile | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    html_paths = [round_dir / name for name in OUTPUT_HTML_NAMES]
    existing = [path for path in html_paths if path.is_file()]
    for path in html_paths:
        if not path.is_file():
            issues.append(ValidationIssue(path, "필수 산출물 누락"))

    if len(existing) > 1:
        first = existing[0].read_bytes()
        if any(path.read_bytes() != first for path in existing[1:]):
            issues.append(ValidationIssue(round_dir, "CBT HTML 3종의 내용이 서로 다름"))

    if profile is None or round_no is None or not questions:
        return issues

    expected_html = render_html(questions, round_no, profile)
    for path in existing:
        if path.read_text(encoding="utf-8") != expected_html:
            issues.append(
                ValidationIssue(path, "CBT HTML이 문제지 또는 현재 빌드 자산과 불일치")
            )
    return issues


def _validate_written_bank(
    problem_path: Path,
    items: list[dict],
    questions: list[dict],
) -> list[ValidationIssue]:
    from subject1.bank import fetch_question as fetch_subject1
    from subject2.bank import fetch_question as fetch_subject2
    from subject3.bank import fetch_question as fetch_subject3

    fetchers = {"1": fetch_subject1, "2": fetch_subject2, "3": fetch_subject3}
    issues: list[ValidationIssue] = []
    for item, question in zip(items, questions):
        stable_id = item.get("stable_id")
        if not isinstance(stable_id, str) or not STABLE_ID_RE.fullmatch(stable_id):
            continue
        try:
            bank_question, bank_answer = fetchers[stable_id[0]](stable_id)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 문제은행 조회 실패: {exc}"))
            continue
        choices = [(choice["label"], _normalize(choice["text"])) for choice in question["choices"]]
        bank_choices = [(label, _normalize(text)) for label, text in bank_question["choices"]]
        if _normalize(question["stem"]) != _normalize(bank_question["stem"]):
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 문제은행 지문 불일치"))
        if choices != bank_choices:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 문제은행 선지 불일치"))
        if item.get("answer") != bank_answer:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: agent_extract 정답 불일치"))
    return issues


def validate_written_bank_inventory(root: Path) -> list[ValidationIssue]:
    """필기 문제은행의 모든 선택형 문항이 정답 인덱스로 조회되는지 검증한다."""

    from subject1.bank import fetch_question as fetch_subject1
    from subject1.bank import load_questions_index as load_subject1
    from subject2.bank import fetch_question as fetch_subject2
    from subject2.bank import load_questions_index as load_subject2
    from subject3.bank import fetch_question as fetch_subject3
    from subject3.bank import load_questions_index as load_subject3

    banks = {
        "1": (load_subject1, fetch_subject1),
        "2": (load_subject2, fetch_subject2),
        "3": (load_subject3, fetch_subject3),
    }
    issues: list[ValidationIssue] = []
    for subject, (load_index, fetch_question) in banks.items():
        problem_path = (
            root
            / "output"
            / "problem_book_final"
            / SUBJECT_SLUGS[subject]
            / f"{subject}과목_문제집.md"
        )
        try:
            stable_ids = load_index()
        except (OSError, ValueError) as exc:
            issues.append(ValidationIssue(problem_path, f"문제은행 인덱스 생성 실패: {exc}"))
            continue
        for stable_id in stable_ids:
            try:
                fetch_question(stable_id)
            except (FileNotFoundError, KeyError, ValueError) as exc:
                issues.append(
                    ValidationIssue(problem_path, f"{stable_id}: 문제은행 전수 조회 실패: {exc}")
                )
    return issues


def _validate_practical_bank(problem_path: Path, stable_ids: list[str], root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    blocks = re.split(r"(?m)^###\s+", problem_path.read_text(encoding="utf-8"))[1:]
    bank_path = (
        root
        / "output"
        / "problem_book_final"
        / SUBJECT_SLUGS["4"]
        / "4과목_문제집.md"
    )
    if not bank_path.is_file():
        return [ValidationIssue(problem_path, "4과목 실기 문제은행 누락")]
    bank_text = bank_path.read_text(encoding="utf-8")
    for block, stable_id in zip(blocks, stable_ids):
        first, *rest = block.splitlines()
        _, stem = first.split(".", 1)
        mock_stem = " ".join(
            line.strip()
            for line in [stem, *rest]
            if line.strip() and not line.strip().startswith("<!--")
        )
        _, part, chapter, question_type, question_number = stable_id.split(":")
        section = "핵심 최종점검" if question_type == "final" else "서술형 출제예상문제"
        part_match = re.search(
            rf"(?ms)^## Part {part} 문제집\s*$.*?(?=^## Part \d+ 문제집\s*$|\Z)",
            bank_text,
        )
        if not part_match:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 실기 문제은행 Part 누락"))
            continue
        section_match = re.search(
            rf"(?ms)^### CHAPTER {int(chapter):02d} .*? — {section}\s*$\n(.*?)(?=^### |\Z)",
            part_match.group(0),
        )
        if not section_match:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 실기 문제은행 섹션 누락"))
            continue
        match = re.search(
            rf"(?ms)^{question_number}[.]\s+(.*?)(?=^<!--\s*source:)",
            section_match.group(1),
        )
        if not match:
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 실기 문제은행 문항 조회 실패"))
        elif _normalize(mock_stem) != _normalize(match.group(1)):
            issues.append(ValidationIssue(problem_path, f"{stable_id}: 실기 문제은행 지문 불일치"))
    return issues


def validate_round(manifest_path: Path, root: Path | None = None) -> list[ValidationIssue]:
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
    if any(not isinstance(item, dict) for item in items):
        return [ValidationIssue(manifest_path, "items 원소가 객체가 아님")]

    profile = _profile_for_round_dir(round_dir)
    directory_round, profile_issues = _validate_manifest_profile(
        manifest_path, manifest, items, profile
    )
    issues.extend(profile_issues)

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
    string_ids = [stable_id for stable_id in stable_ids if isinstance(stable_id, str)]
    if len(string_ids) != len(set(string_ids)):
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
        if len(sources) == len(stable_ids):
            issues.extend(_validate_source_parts(problem_path, sources, stable_ids))
        if re.search(r"\(O/X\)", problem_text, re.IGNORECASE):
            issues.append(ValidationIssue(problem_path, "실제 필기에 없는 O/X 문항 포함"))
        if root is not None and len(questions) == len(items):
            issues.extend(_validate_written_bank(problem_path, items, questions))
        if root is not None and len(sources) == len(stable_ids):
            issues.extend(_validate_source_images(problem_path, sources, stable_ids, root))

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
        elif any(answers.get(item.get("exam_no")) != item.get("answer") for item in items):
            issues.append(ValidationIssue(answer_path, "정답지와 manifest 정답 불일치"))

    if problem_path.is_file():
        issues.extend(_validate_round_html(round_dir, questions, directory_round, profile))
    else:
        issues.extend(_validate_round_html(round_dir, [], directory_round, profile))
    review_path = round_dir / "교차검수.md"
    if not review_path.is_file():
        issues.append(ValidationIssue(review_path, "필수 산출물 누락"))

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


def validate_practical_round(round_dir: Path, root: Path | None = None) -> list[ValidationIssue]:
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
    if len(sources) == len(ids):
        issues.extend(_validate_source_parts(problem_path, sources, ids))
    if root is not None and len(sources) == len(ids):
        issues.extend(_validate_source_images(problem_path, sources, ids, root))
        issues.extend(_validate_practical_bank(problem_path, ids, root))

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
        issues.extend(validate_round(manifest_path, root))
    practical_rounds = sorted(
        path.parent
        for path in (root / "output" / "mock_exam" / "실기").glob("*회차/실기_모의_문제.md")
    )
    for round_dir in practical_rounds:
        issues.extend(validate_practical_round(round_dir, root))
    issues.extend(validate_written_bank_inventory(root))
    issues.extend(validate_published_docs(root))
    return len(manifests), item_count, len(practical_rounds), issues

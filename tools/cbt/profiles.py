"""CBT 빌드·배포 프로필 (통합 필기 80문항 vs 과목 전용 등)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cbt.paths import MOCK_ROOT, full_round_dir, subject_round_dir

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@dataclass(frozen=True)
class CbtProfile:
    """한 종류의 모의 CBT 설정."""

    id: str
    question_count: int
    duration_sec: int
    shell_html: str
    inject_duration: bool
    storage_key_template: str

    def round_dir(self, round_no: int) -> Path:
        raise NotImplementedError

    def problem_md(self, round_no: int) -> Path:
        return self.round_dir(round_no) / "필기_모의_문제.md"

    def storage_key(self, round_no: int) -> str:
        return self.storage_key_template.format(round=round_no)

    def docs_index(self) -> Path:
        raise NotImplementedError

    def docs_meta(self) -> Path:
        return self.docs_index().parent / "cbt-meta.json"

    def publish_meta(self, round_no: int) -> dict:
        raise NotImplementedError

    def source_label(self, round_no: int) -> str:
        rel = self.round_dir(round_no).relative_to(MOCK_ROOT.parent)
        return f"{rel}/index.html"


@dataclass(frozen=True)
class FullMockProfile(CbtProfile):
    def round_dir(self, round_no: int) -> Path:
        return full_round_dir(round_no)

    def docs_index(self) -> Path:
        return DOCS / "index.html"

    def publish_meta(self, round_no: int) -> dict:
        return {
            "round": round_no,
            "source": f"output/{self.source_label(round_no)}",
            "note": "GitHub Pages 루트 — 최신 회차 필기 통합 모의 CBT (정답 미포함)",
        }


@dataclass(frozen=True)
class Subject3Profile(CbtProfile):
    def round_dir(self, round_no: int) -> Path:
        return subject_round_dir(3, round_no)

    def docs_index(self) -> Path:
        return DOCS / "3과목" / "index.html"

    def publish_meta(self, round_no: int) -> dict:
        return {
            "round": round_no,
            "subject": 3,
            "total": self.question_count,
            "source": f"output/{self.source_label(round_no)}",
            "note": "GitHub Pages — 3과목 전용 필기 모의 CBT (정답 미포함)",
        }


FULL_MOCK = FullMockProfile(
    id="full",
    question_count=80,
    duration_sec=120 * 60,
    shell_html="shell.html",
    inject_duration=False,
    storage_key_template="mock_exam_{round}_answers",
)

SUBJECT3 = Subject3Profile(
    id="subject3",
    question_count=30,
    duration_sec=45 * 60,
    shell_html="subject3_shell.html",
    inject_duration=True,
    storage_key_template="mock_exam_3s{round}_answers",
)

PROFILES: dict[str, CbtProfile] = {
    FULL_MOCK.id: FULL_MOCK,
    SUBJECT3.id: SUBJECT3,
}

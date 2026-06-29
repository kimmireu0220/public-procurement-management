# tools — 모의고사·CBT 도구

## 구조

```
tools/
├── merge_mock_draft.py            # 통합 필기 80문항 — _draft 병합
├── build_cbt_viewer.py            # CBT HTML 빌드 (--profile full | subject1 | subject2 | subject3)
├── publish_cbt_pages.py           # GitHub Pages 배포
├── build_subject{1,2,3}_draft.py  # → subjectN/ 래퍼
├── merge_mock_draft_subject{1,2,3}.py
├── cbt/                           # 공통 CBT 엔진
│   ├── paths.py                   # output/mock_exam 레이아웃 · WRONG_NOTE · subject_wrong_note()
│   ├── draft_merge.py
│   ├── profiles.py                # CbtProfile (full / subject1 / subject2 / subject3)
│   ├── parser.py
│   ├── builder.py
│   └── assets/
├── subject1/                      # 1과목 전용 30문항
├── subject2/                      # 2과목 전용 20문항
└── subject3/                      # 3과목 전용 30문항
```

## 통합 필기 (80문항)

```bash
python3 tools/merge_mock_draft.py K
python3 tools/build_cbt_viewer.py --round K
python3 tools/publish_cbt_pages.py --round K
```

오답 누적: `output/mock_exam/필기/통합/오답노트.md`

## 과목 단독 (1·2·3과목)

```bash
# 예: 2과목
python3 tools/build_subject2_draft.py K      # (선택)
python3 tools/merge_mock_draft_subject2.py K
python3 tools/build_cbt_viewer.py --profile subject2 --round K --pages
```

| profile | 문항 | Pages | 오답노트 |
|---------|-----:|-------|----------|
| `subject1` | 30 | `docs/1과목/` | `필기/1과목/오답노트.md` |
| `subject2` | 20 | `docs/2과목/` | `필기/2과목/오답노트.md` |
| `subject3` | 30 | `docs/3과목/` | `필기/3과목/오답노트.md` |

## 확장

다른 과목 단독 모의가 필요하면 `cbt/profiles.py`에 프로필을 추가하고,
`tools/subjectN/` 패키지를 `subject3/`와 같은 형태로 두면 된다.
선별(문항 고르기)은 에이전트 수동 — 코드는 병합·CBT·배포만 담당한다.

## 산출 경로 (`cbt/paths.py`)

| 구분 | 경로 |
|------|------|
| 필기 통합 80문항 | `output/mock_exam/필기/통합/{K}회차/` · 오답 `필기/통합/오답노트.md` |
| 필기 과목 단독 | `output/mock_exam/필기/{N}과목/{K}회차/` · Pages `docs/{N}과목/` — [`선별.md`](../docs/시험모의/선별.md) §A-6 |
| 실기 | `output/mock_exam/실기/{K}회차/` |

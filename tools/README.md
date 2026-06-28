# tools — 모의고사·CBT 도구

## 구조

```
tools/
├── merge_mock_draft.py          # 통합 필기 80문항 — _draft 병합
├── build_cbt_viewer.py          # CBT HTML 빌드 (--profile full | subject3)
├── publish_cbt_pages.py         # GitHub Pages 배포
├── build_subject3_draft.py      # → subject3/ 래퍼
├── merge_mock_draft_subject3.py # → subject3/ 래퍼
├── cbt/                         # 공통 CBT 엔진
│   ├── paths.py                 # output/mock_exam 레이아웃
│   ├── draft_merge.py           # _draft 파싱·병합 공통
│   ├── profiles.py              # CbtProfile (full / subject3)
│   ├── parser.py                # 문제지 md → JSON
│   ├── builder.py               # HTML 조립
│   └── assets/
└── subject3/                    # 3과목 전용 30문항 파이프라인
    ├── bank.py                  # 문제은행·정답 추출
    ├── selection.py             # 회차별 stable_id 목록
    ├── build_draft.py
    ├── merge.py
    └── publish.py
```

## 통합 필기 (80문항)

```bash
python3 tools/merge_mock_draft.py K
python3 tools/build_cbt_viewer.py --round K
python3 tools/publish_cbt_pages.py --round K
```

## 3과목 전용 (30문항)

```bash
python3 tools/build_subject3_draft.py K
python3 tools/merge_mock_draft_subject3.py K
python3 tools/build_cbt_viewer.py --profile subject3 --round K --pages
# 또는 --subject3 (호환)
```

## 확장

다른 과목 단독 모의가 필요하면 `cbt/profiles.py`에 프로필을 추가하고,
`tools/subjectN/` 패키지를 `subject3/`와 같은 형태로 두면 된다.
선별(문항 고르기)은 에이전트 수동 — 코드는 병합·CBT·배포만 담당한다.

## 산출 경로 (`cbt/paths.py`)

| 구분 | 경로 |
|------|------|
| 필기 통합 80문항 | `output/mock_exam/필기/통합/{K}회차/` |
| 필기 3과목 단독 | `output/mock_exam/필기/3과목/{K}회차/` |
| 실기 | `output/mock_exam/실기/{K}회차/` |

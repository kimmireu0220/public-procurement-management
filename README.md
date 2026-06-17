# public-procurement-management

공공조달관리사 교재 스캔 기반 문제집 추출·학습 파이프라인.

## 현재 상태 (2026-06)

| 과목 | agent_extract | problem_book (MD/HTML) | OCR | 문항 수 (검증) |
|---|---|---|---|---:|
| 1과목 필기 | ✅ ch1~7 | ✅ | ✅ | 1,050 |
| 2과목 필기 | ✅ ch1~4 | ✅ | — | 434 |
| 3과목 필기 | ✅ ch1~4 | ✅ | ✅ | 700 |
| 4과목 실기 | ✅ ch1~8 | ✅ | — | 1,141 |

**합계 3,325문항** — `validate_extract.py` 기준 문항=정답 전 과목 ✅

## 교재 원본 (Git 포함)

교재 JPG·표준 PDF는 저장소에 포함됨. 대용량으로 과목별 4회 배치 커밋·푸시 완료.

| 과목 | JPG | PDF |
|---|---|---|
| 1과목 | `교재/1과목_공공조달의 이해/` | `표준 교재/1과목_.../교재.pdf` |
| 2과목 | `교재/2과목_공공조달 계획분석/` | 동일 |
| 3과목 | `교재/3과목_공공계약관리/` | 동일 |
| 4과목 | `교재/4과목_공공조달 관리실무/` | 동일 |

## 주요 경로

| 경로 | 내용 |
|---|---|
| `교재/` · `표준 교재/` | 스캔 JPG · 원본 PDF |
| `output/ocr/` | 1·3과목 OCR 텍스트 |
| `output/agent_extract/` | 챕터별 추출본 (문제+정답, 검수 반영) |
| `output/problem_book_final/` | 최종 문제집 (문제만, MD+HTML) |
| `output/학습_프롬프트/` | 과목별 강의(설명) 프롬프트 |
| `output/extraction_guide.md` | 추출 규칙 |
| `output/문제집_제작_프롬프트.md` | 재추출·재검수 playbook |
| `tools/` | 빌드 · 검증 · 감사 · 출처 보강 스크립트 |

## 품질 검증

```bash
python3 tools/validate_extract.py --subject all    # 문항·정답 일치
python3 tools/audit_problem_book.py --subject all  # OCR·출처 대조
python3 tools/build_problem_book.py --subject 1    # 문제집 재빌드
python3 tools/enrich_source_comments.py --subject 1  # 블록 출처 → 문항별 전파
```

## 참고 (잔여·오탐)

- **1과목:** `build_problem_book` 집계(1,062)와 `validate_extract`(1,050) 차이 12 — 집계 방식 차이, 누락 아님
- **3과목 ch4:** OCR 미사용 4페이지 — 부록·표·해설 **오탐** (`누락_후보_대조.md` 분류표 참고)
- **2·3과목 ch2/3:** `본문 답안 흔적` 표식은 감점 보기(`① -10점`) 등 **검증 오탐**

## 제거된 산출물

핵심요약집, 요약노트, 모의고사, `output/_crops/` — 삭제됨.

## 설정

```bash
cp .env.example .env   # PROJECT_ROOT 등 수정
```

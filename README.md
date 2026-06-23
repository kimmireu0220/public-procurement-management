# public-procurement-management

공공조달관리사 **박문각 수험서 스캔** 기반 문제집 추출·학습 파이프라인.

## 학습 자료 (`sources/`)

외부 원본 자료는 출처별로 분리한다. 상세는 [`sources/README.md`](sources/README.md).

| 경로 | 출처 | 용도 |
|------|------|------|
| `sources/민간_박문각_수험서_jpg/` | ㈜박문각 민간 수험서 | OCR · 문제집 추출 **주 입력** |
| `sources/공식_조달청_표준교재_pdf/` | 조달청 · 공공조달역량개발원 | 공식 표준교재 PDF (대조·참고) |
| `sources/공식_qnet_예제문제/` | 한국산업인력공단 Q-Net | 필기 예제 6문항 (기출 아님) |
| `sources/공식_qnet_시행공고/` | Q-Net 수시검정 시행공고 | **일정·CBT/필답** (문항 수는 [`docs/시험_안내.md`](docs/시험_안내.md)) |

박문각 수험서는 조달청 표준교재가 **아닙니다.**

## 용어 기준

파일 경로·출처는 박문각 수험서 스캔의 `Part N` 구조를 따른다. 수험서 안의 `CHAPTER 01`, `CHAPTER 02` 등은 해당 Part 안의 소단원이다.

- 경로·출처 표기: `sources/민간_박문각_수험서_jpg/<slug>/Part N/page_XXXX.jpg`
- 1과목 출제기준·목차 폴더: `Intro`
- 학습·검수 설명: `Part N` 기준

## 현재 상태 (2026-06)

| 과목 | agent_extract | problem_book (MD/HTML) | OCR | 문항 수 (검증) |
|---|---|---|---|---:|
| 1과목 필기 | ✅ part1~7 | ✅ | ✅ | 1,050 |
| 2과목 필기 | ✅ part1~4 | ✅ | ✅ | 434 |
| 3과목 필기 | ✅ part1~4 | ✅ | ✅ | 700 |
| 4과목 실기 | ✅ part1~8 | ✅ | ✅ | 1,141 |

**합계 3,325문항** — `validate_extract.py` 기준 문항=정답 전 과목 ✅

### 문항 수 기준

| 도구 | 집계 방식 | 용도 |
|---|---|---|
| `validate_extract.py` | 정답 섹션 번호 기준 | **공식 문항 수** (README·`docs/문제집_프롬프트/`) |
| `build_problem_book.py` | 문제 본문 `N.` 줄 패턴 | 빌드·`검토_요약.md` |
| `audit_problem_book.py` | `parts_clean` Part 파일 줄 패턴 | `누락_후보_대조.md` |

1과목은 validate 1,050 vs build/audit 1,062 — **누락이 아니라 집계·빌드 패치 차이** (`build_problem_book.py`의 `augment_sources()`가 1과목 `parts_clean` 일부를 하드코딩 보정).

### 데이터 원본 구분

| 용도 | 기준 파일 |
|------|-----------|
| 정답·문항 수 검증 | `output/agent_extract/<slug>/partN.md` |
| 학습용 문제집 (HTML/MD) | `output/problem_book_final/<slug>/` — 1과목은 빌드 시 패치 반영 |

## sources 과목별 경로 (Git 포함)

| 과목 | 박문각 스캔 (JPG) | 조달청 표준교재 (PDF) |
|---|---|---|
| 1과목 | `sources/민간_박문각_수험서_jpg/1과목_공공조달의 이해/` | `sources/공식_조달청_표준교재_pdf/1과목_공공조달의 이해/교재.pdf` |
| 2과목 | `…/2과목_공공조달 계획분석/` | 동일 |
| 3과목 | `…/3과목_공공계약관리/` | 동일 |
| 4과목 | `…/4과목_공공조달 관리실무/` | 동일 |

## 주요 경로

| 경로 | 내용 |
|---|---|
| [`sources/`](sources/README.md) | 외부 학습 자료 (민간 스캔 · 공식 PDF · Q-Net 예제) |
| `output/ocr/` | 1~4과목 OCR 텍스트 (Vision, macOS) |
| `output/agent_extract/` | Part별 추출본 (`partN.md`, 문제+정답, 검수 반영) |
| `output/problem_book_final/` | 최종 문제집 (문제만, MD+HTML) — [`README`](output/problem_book_final/README.md) |
| `docs/` | 학습·문제집 프롬프트 · 추출 규칙 · [**시험 안내**](docs/시험_안내.md) — [`README`](docs/README.md) |
| `tools/` | 빌드 · 검증 · 감사 · 출처 보강 — [`README`](tools/README.md) |

## 품질 검증

```bash
python3 tools/validate_extract.py --subject all    # 문항·정답 일치
python3 tools/audit_problem_book.py --subject all  # OCR·출처 대조
python3 tools/build_problem_book.py --subject all  # 1~4 일괄 재빌드
python3 tools/build_problem_book.py --subject 1    # 단일 과목 재빌드
python3 tools/annotate_source_ranges.py --part6  # 1과목 Part 06 출처 범위 보강
```

## 참고 (잔여·오탐)

- **1과목 Part 06:** 단원별·OX 구간 `(문항 N~M)` 범위 source — `annotate_source_ranges.py --part6` (페이지 범위는 인접 섹션 추정)
- **1과목 빌드:** `augment_sources()` 패치로 `parts_clean`이 `agent_extract`와 일부 상이 — 상세는 `docs/extraction_guide.md`
- **3과목 Part 04:** OCR 미사용 4페이지 — 부록·표·해설 **오탐** (`누락_후보_대조.md` 분류표)
- **2·4과목:** OCR 미사용 후보 다수 — 대부분 해설·표 **오탐** (`누락_후보_대조.md`)
- **2·3과목 일부 Part:** `본문 답안 흔적` 표식은 감점 보기(`① -10점`) 등 **검증 오탐**

## 제거된 산출물

핵심요약집, 요약노트, 모의고사, `output/_crops/` — 삭제됨.

## 설정

```bash
cp .env.example .env   # PROJECT_ROOT만 기기 경로에 맞게 수정
```

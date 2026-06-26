# tools

문제집 파이프라인 스크립트. 저장소 루트에서 실행한다.

경로의 큰 단원은 `Part N`으로 정리되어 있다. 수험서 내부 `CHAPTER 01`, `CHAPTER 02` 등은 해당 Part 안의 소단원이다.

## 스크립트

| 스크립트 | 용도 | 출력 |
|---|---|---|
| `build_problem_book.py` | Part 단위 추출본에서 정답 제거·합본 MD/HTML 생성 | `problem_book_final/{slug}/` |
| `validate_extract.py` | 문항=정답 검증 (**공식 문항 수**) | `추출_검증.md` |
| `audit_problem_book.py` | OCR 표식 vs 출처 주석 대조 | `누락_후보_대조.md` |
| `quality_common.py` | 답안 흔적·OCR 후보 공통 필터 (validate/audit 공유) | — |
| `enrich_source_comments.py` | 블록 `<!-- source: -->` → 문항별 전파 | `agent_extract` 수정 (2과목 등) |
| `annotate_source_ranges.py` | 출처 주석에 `(문항 N~M)` 범위 보강 (1과목 Part 6) | `agent_extract` 수정 |
| `fix_choice_lines.py` | 문항 줄의 `①②③④`를 각각 한 줄로 분리 | `agent_extract` 수정 |
| `enrich_answer_kw.py` | compact 정답표 전개·`정답 키 기준.` placeholder 교체 | `agent_extract` 정답 섹션 |
| `enrich_kw_quality.py` | 2차: `kw==선지` → 해설형 문장 교체 | `agent_extract` 정답 섹션 |
| `audit_kw_coverage.py` | kw 커버리지·`--quality` 품질 리포트 | stdout 또는 `output/kw_*.md` |
| `run_ocr_pages.sh` | 박문각 수험서 JPG 일괄 OCR (macOS Vision) | `output/ocr/` |

## 모의고사 (필기 80문항)

**기본 경로 = 에이전트 출제.** 스크립트는 준비·검증·초안용.

| 스크립트 | 용도 |
|---|---|
| `prepare_mock_round.py` | K회차 브리핑·`_candidates/` shortlist 생성 |
| `merge_mock_draft.py` | `_draft/` → 최종 MD · `manifest.json` · **HTML + 브라우저 자동 열기** |
| `validate_mock_exam.py` | 형식·중복·상한 검증 (**생성 없음**) |
| `build_mock_exam_player.py` | `필기_응시.html` 생성 · **기본 브라우저 자동 열기** (`--no-open` 생략) |
| `select_mock_exam.py` | 자동 초안만 (에이전트 검수 권장) |
| `mock_exam_common.py` | 공통 모듈 (stable ID, `TOPIC_MAX`, 클러스터 상한) |

```bash
# 1. 준비 (에이전트용 후보·브리핑)
python3 tools/prepare_mock_round.py 1

# 2. 에이전트: _candidates/ 에서 선별 → _draft/manifest.json 또는 {N}과목_선별.md
#    (프롬프트: docs/문제집_프롬프트/시험모의_선별.md)

# 3. 병합·검증·HTML
python3 tools/merge_mock_draft.py 1
python3 tools/validate_mock_exam.py 1

# 급할 때 초안만 (HTML 자동 열기 포함)
python3 tools/select_mock_exam.py 1 --importance
```

이전 회차 manifest 소급: `prepare_mock_round.py K --backfill-prior`

## 일반 실행 순서

```bash
# 1. 추출본 수정 후 문제집 재빌드
python3 tools/build_problem_book.py --subject all   # 또는 --subject 1

# 2. 문항·정답 검증 (README 문항 수 기준)
python3 tools/validate_extract.py --subject all

# 3. OCR 누락 후보 감사
python3 tools/audit_problem_book.py --subject all

# 4. (선택) 출처 주석 보강
python3 tools/enrich_source_comments.py --subject 1 --dry-run
python3 tools/annotate_source_ranges.py --part6

# 5. (선택) 형식 보정
python3 tools/fix_choice_lines.py --subject N --dry-run
```

## OCR 생성 (macOS)

Swift + Vision 프레임워크 사용. Linux/Windows에서는 OCR 스크립트를 실행할 수 없다.

```bash
TEXTBOOK_IMAGES_DIR="sources/민간_박문각_수험서_jpg/2과목_공공조달 계획분석" \
OCR_DIR="output/ocr/2과목_공공조달_계획분석" \
tools/run_ocr_pages.sh
```

slug의 공백은 OCR 폴더명에서 `_`로 치환한다 (`2과목_공공조달_계획분석`).

## 환경 변수

OCR 등 셸 스크립트용. 기본값은 `tools/env.sh` 참고.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PROJECT_ROOT` | 저장소 루트 (자동) | `tools/env.sh` 기준 상위 디렉터리 |
| `PARKMUNGak_SCAN_DIR` | `sources/민간_박문각_수험서_jpg` | 박문각 스캔 루트 (`TEXTBOOK_DIR` 구명 호환) |
| `TEXTBOOK_IMAGES_DIR` | `…/1과목_공공조달의 이해` | OCR 대상 JPG 과목 폴더 |
| `STANDARD_TEXTBOOK_DIR` | `sources/공식_조달청_표준교재_pdf` | 조달청 표준교재 PDF |
| `QNET_SAMPLE_DIR` | `sources/공식_qnet_예제문제` | Q-Net 예제문제 |
| `QNET_EXAM_NOTICE_DIR` | `sources/공식_qnet_시행공고` | Q-Net 시행공고 PDF |
| `OCR_DIR` | `output/ocr/1과목_...` | OCR 출력 루트 |

## 의존성

- Python 3.9+
- OCR: macOS, Swift (`ocr_pages.swift`)
- 재추출 시: ImageMagick `convert` (크롭·확대, 선택)

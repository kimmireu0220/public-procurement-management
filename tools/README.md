# tools

문제집 파이프라인 스크립트. 저장소 루트에서 실행한다.

경로의 큰 단원은 `Part N`으로 정리되어 있다. 수험서 내부 `CHAPTER 01`, `CHAPTER 02` 등은 해당 Part 안의 소단원이다.

## 스크립트

| 스크립트 | 용도 | 출력 |
|---|---|---|
| `build_problem_book.py` | Part 단위 추출본에서 정답 제거·합본 MD/HTML 생성 | `problem_book_final/{slug}/` |
| `validate_extract.py` | 문항=정답 검증 (**공식 문항 수**) | `추출_검증.md` |
| `audit_problem_book.py` | OCR 표식 vs 출처 주석 대조 | `누락_후보_대조.md` |
| `enrich_source_comments.py` | 블록 `<!-- source: -->` → 문항별 전파 | `agent_extract` 수정 |
| `annotate_source_ranges.py` | 출처 주석에 `(문항 N~M)` 범위 보강 (1과목 Part 6) | `agent_extract` 수정 |
| `fix_choice_lines.py` | 문항 줄의 `①②③④`를 각각 한 줄로 분리 | `agent_extract` 수정 |
| `add_memo_tips.py` | 4과목 문항에 키워드 기반 암기팁 추가 | `agent_extract` 수정 |
| `run_ocr_pages.sh` | 박문각 수험서 JPG 일괄 OCR (macOS Vision) | `output/ocr/` |

## 일반 실행 순서

```bash
# 1. 추출본 수정 후 문제집 재빌드
python3 tools/build_problem_book.py --subject 1

# 2. 문항·정답 검증 (README 문항 수 기준)
python3 tools/validate_extract.py --subject all

# 3. OCR 누락 후보 감사
python3 tools/audit_problem_book.py --subject all

# 4. (선택) 출처 주석 보강
python3 tools/enrich_source_comments.py --subject 1 --dry-run
python3 tools/annotate_source_ranges.py --part6

# 5. (선택) 형식·암기팁 일괄 보정
python3 tools/fix_choice_lines.py --subject N --dry-run
python3 tools/add_memo_tips.py --dry-run   # 4과목 전용
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

`.env` 또는 셸에서 설정. 기본값은 `tools/env.sh` 참고.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PROJECT_ROOT` | 저장소 루트 | 절대 경로 (다른 기기 클론 시) |
| `PARKMUNGak_SCAN_DIR` | `sources/민간_박문각_수험서_jpg` | 박문각 스캔 루트 (`TEXTBOOK_DIR` 구명 호환) |
| `TEXTBOOK_IMAGES_DIR` | `…/1과목_공공조달의 이해` | OCR 대상 JPG 과목 폴더 |
| `STANDARD_TEXTBOOK_DIR` | `sources/공식_조달청_표준교재_pdf` | 조달청 표준교재 PDF |
| `QNET_SAMPLE_DIR` | `sources/공식_qnet_예제문제` | Q-Net 예제문제 |
| `OCR_DIR` | `output/ocr/1과목_...` | OCR 출력 루트 |

## 의존성

- Python 3.9+
- `python-dotenv` (선택, 없으면 `.env` 수동 파싱)
- OCR: macOS, Swift (`ocr_pages.swift`)
- 재추출 시: ImageMagick `convert` (크롭·확대, 선택)

# public-procurement-management

공공조달관리사 교재 스캔 기반 문제집 추출·학습 파이프라인.

## 현재 상태 (2026-06)

| 과목 | agent_extract | problem_book (MD/HTML) | OCR | 문항 수 |
|---|---|---|---|---:|
| 1과목 필기 | ✅ ch1~7 | ✅ | ✅ | 1,062 |
| 2과목 필기 | ✅ ch1~4 | ✅ | — | 434 |
| 3과목 필기 | ✅ ch1~4 | ✅ | ✅ | 693 |
| 4과목 실기 | ✅ ch1~8 | ✅ | — | 1,141 |

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
| `output/extraction_guide.md` | 추출 규칙 |
| `output/문제집_제작_프롬프트.md` | 재추출·재검수 playbook |
| `tools/` | OCR · 빌드 · 감사 스크립트 |

## 알려진 품질 이슈 (구조 문제 아님)

- **1과목 ch5:** 출처 주석 밀도 낮음 (167문항 / 출처 17)
- **3과목 ch4:** OCR 후보 10페이지 미사용 — `누락_후보_대조.md` 참고
- **4과목:** 출처 주석 비율 전반적으로 낮음

## 제거된 산출물

핵심요약집, 요약노트, 모의고사, `output/_crops/` — 삭제됨.

## 설정

```bash
cp .env.example .env   # PROJECT_ROOT 등 수정
python3 tools/build_problem_book.py --subject 1   # 문제집 재빌드 예시
python3 tools/validate_extract.py --subject 1   # 추출 검증
```

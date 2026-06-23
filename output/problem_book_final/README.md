# problem_book_final

전 과목(1~4) 최종 **문제만** 모은 학습용 산출물.

- **정답·해설:** `output/agent_extract/<slug>/partN.md` 정답 섹션
- **1과목 주의:** 빌드 시 `augment_sources()` 패치가 들어가 `parts_clean`이 `agent_extract`와 **일부 다름** — [`extraction_guide.md`](../docs/extraction_guide.md)

## 용어

파일명·출처는 `partN` / `Part N`을 사용한다. 수험서 내부 `CHAPTER 01`, `CHAPTER 02` 등은 Part 안의 소단원이다.

## 과목별 파일

| 파일 | 용도 |
|---|---|
| `{N}과목_문제집.html` | **학습 권장** — 브라우저·인쇄용 |
| `{N}과목_문제집.md` | 전체 합본 (검색·diff용) |
| `parts_clean/partN.md` | Part 단위 분할 |
| `추출_검증.md` | 문항=정답 자동 검증 (`validate_extract.py`) |
| `검토_요약.md` | 빌드 집계 (줄 패턴 기준, 검증과 수치가 다를 수 있음) |
| `누락_후보_대조.md` | OCR 누락 후보 (`audit_problem_book.py`) |
| `독립검수_리포트.md` | 1~4과목 수동 검수 기록 |

## 문항 수 기준

**공식 합계는 `validate_extract.py` 결과**이다 (README 표와 동일).

`검토_요약.md`·`누락_후보_대조.md`의 문항 수는 빌드/audit 줄 패턴 집계로, 1과목 등에서 소폭 차이날 수 있다.

## 학습 방법

1. 강의·이론: `docs/학습_프롬프트/` (문제 출제 없음)
2. 문제 풀이: 본 폴더 `{N}과목_문제집.html`
3. 정답 확인: `output/agent_extract/{slug}/partN.md` 정답 섹션

## 재생성

```bash
python3 tools/build_problem_book.py --subject N
python3 tools/validate_extract.py --subject N
python3 tools/audit_problem_book.py --subject N
```

규칙·에이전트 프롬프트: `docs/extraction_guide.md`, `docs/문제집_프롬프트/`

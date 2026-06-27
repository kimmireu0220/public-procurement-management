# problem_book_final

전 과목(1~4) 최종 **문제만** 모은 학습용 산출물.

- **정답·해설:** `output/agent_extract/<slug>/partN.md` 정답 섹션
- **본문:** `agent_extract`에서 정답만 제거한 것과 동일 (`parts_clean/`)

## 용어

파일명·출처는 `partN` / `Part N`을 사용한다. 수험서 내부 `CHAPTER 01`, `CHAPTER 02` 등은 Part 안의 소단원이다.

## 과목별 파일

| 파일 | 용도 |
|---|---|
| `{N}과목_문제집.html` | **학습 권장** — 브라우저·인쇄용 |
| `{N}과목_문제집.md` | 전체 합본 (검색·diff용) |
| `parts_clean/partN.md` | Part 단위 분할 |
| `추출_검증.md` | 문항=정답 자동 검증 (`validate_extract.py`) |

정답·해설 품질 전수조사 요약: [`output/전수조사/종합보고.md`](../전수조사/종합보고.md)

## 문항 수 기준

**공식 합계는 `validate_extract.py` 결과**이다.

## 학습 방법

1. 강의·이론: `docs/학습_프롬프트/` (문제 출제 없음)
2. 문제 풀이: 본 폴더 `{N}과목_문제집.html`
3. 정답 확인: `output/agent_extract/{slug}/partN.md` 정답 섹션

## 재생성

```bash
python3 tools/build_problem_book.py --subject all
python3 tools/validate_extract.py --subject all
```

규칙·에이전트 프롬프트: `docs/extraction_guide.md`, `docs/문제집_프롬프트/`

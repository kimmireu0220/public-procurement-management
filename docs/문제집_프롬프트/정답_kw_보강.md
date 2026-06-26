# 정답·kw(해설) 보강 프롬프트

`agent_extract` 정답 섹션의 `kw`(— 뒤 해설 문장)를 보강할 때 사용한다.  
모의고사 `필기_모의_정답.md`·`필기_응시.html` 해설은 이 `kw`에서 파생된다.

## 현황 점검

```bash
python3 tools/audit_kw_coverage.py
# → output/kw_커버리지.md
```

| 항목 | 목표 |
|------|------|
| kw 없음 | 0 |
| 정답 없음 | 0 |
| `정답 키 기준.` placeholder | 0 |
| kw == 지문 | 0 |

**2차(품질):** 선지 복사·짧은 kw → 해설형 문장 — [`정답_kw_품질_2차.md`](정답_kw_품질_2차.md)  
**3차(교재 해설):** 템플릿 328건 — [`정답_kw_품질_3차.md`](정답_kw_품질_3차.md)

## 자동 보강 (권장)

```bash
# compact 정답표 전개 + placeholder 교체
python3 tools/enrich_answer_kw.py

# 미리보기
python3 tools/enrich_answer_kw.py --dry-run

# 과목 지정
python3 tools/enrich_answer_kw.py --subject 3
```

보강 후 모의고사 산출물 갱신:

```bash
python3 tools/merge_mock_draft.py --round K   # 또는 write_round_files 경로
python3 tools/build_mock_exam_player.py --round K --no-open
```

---

## Phase 0 — 파서 수정 (코드)

**목표:** `agent_extract`에 있는 정답·해설을 `load_subject_pool()`이 읽지 못하는 문제 해소.

**증상:** 풀에 `ans`·`kw` 둘 다 비어 있으나 `partN.md` 정답 섹션에는 데이터 존재.

**원인 예:**
- `# Part 4 정답` (`#` 1개 헤더)
- `### Chapter 01` + `#### Check Q&A` 중첩 헤더
- `### [Chapter 01] 단원별 출제예상문제` 대괄호 형식

**수정 위치:** `tools/mock_exam_common.py` — `parse_answers_from_extract`, `parse_section_header`, `parse_questions_from_clean`

**완료 검증:**

```bash
python3 -c "
import sys; sys.path.insert(0,'tools')
from mock_exam_common import load_all_pools
p=load_all_pools()
na=sum(1 for pool in p.values() for q in pool.values() if not q.ans)
print('no_ans', na)
"
```

---

## Phase 1 — compact 정답표 전개

**대상:** `21. ④  22. ③ … 30. ③` 형식 (한 줄 다문항)

**주요 파일:**
- `1과목_공공조달의 이해/part1.md`
- `3과목_공공계약관리/part2.md`

### 에이전트 프롬프트 (수동·OCR 보강 시)

```
너는 `output/agent_extract/〈slug〉/part〈N〉.md` **정답 섹션만** 보강하는 편집자다.
문항 본문(문제·선지)은 바꾸지 않는다.

## 작업
1. 정답 섹션에서 compact 줄을 찾는다:
   `21. ④  22. ④  23. ③ …` (한 줄에 2문항 이상)
2. 각 문항을 아래 형식으로 **한 줄씩** 분리한다:
   `번호. ① — 해설 한 줄 (근거 요약)`
3. 해설 우선순위:
   - 수험서 JPG `<!-- source: Part N/page_*.jpg -->` 정답·해설 페이지
   - `output/ocr/〈slug_underscore〉/` 동일 페이지 OCR
   - 없으면 **정답 선지 본문** (객관식 ①~④ 중 정답 줄)
4. OX는 `번호. O — 판단 근거 한 줄` (지문 요약 가능)

## 금지
- compact 줄 유지
- `정답 키 기준.` placeholder
- 문제 본문·번호 변경

## 완료 후
python3 tools/enrich_answer_kw.py --subject 〈N〉
python3 tools/audit_kw_coverage.py
python3 tools/validate_extract.py --subject 〈N〉
```

---

## Phase 2 — placeholder 교체

**대상:** `N. ② — 정답 키 기준.`

**주요 파일:** `3과목_공공계약관리/part4.md` (단원별 출제예상문제)

### 에이전트 프롬프트

```
너는 `output/agent_extract/3과목_공공계약관리/part4.md` 정답 섹션의
`— 정답 키 기준.` placeholder를 실제 해설로 교체한다.

## 참고 (채팅 첨부)
- `@output/agent_extract/3과목_공공계약관리/part4.md`
- `@sources/민간_박문각_수험서_jpg/3과목_공공계약관리/Part 4/`
- `@output/ocr/3과목_공공계약관리/Part 4/`

## 규칙
- 형식: `번호. ① — 해설 (1~2문장)`
- 해설은 해당 문항 `<!-- source: -->` 페이지·교재 범위 안에서 작성
- 정답 번호(①~④)는 기존과 동일하게 유지
- Check Q&A는 이미 full 형식이면 수정하지 않음

## 자동 대체 (선지만 있을 때)
python3 tools/enrich_answer_kw.py --subject 3
```

---

## Phase 3 — 파이프라인 반영

```
## 모의고사 〈K〉회차 정답·HTML 재생성

1. `python3 tools/audit_kw_coverage.py` — kw 없음 0 확인
2. manifest 기준 정답지 재생성 (merge_mock_draft 또는 write_round_files)
3. `python3 tools/build_mock_exam_player.py --round 〈K〉 --no-open`
4. (이미 채점된 회차) `필기_풀이.md` 해설 줄을 `필기_모의_정답.md`와 동기화
```

---

## Phase 4 — 품질 게이트

```bash
python3 tools/audit_kw_coverage.py
python3 tools/validate_extract.py --subject all
```

| 검사 | 조치 |
|------|------|
| kw 12자 미만 多 | 선지 복사만 된 항목 — OCR·수동 보강 후보 |
| kw == 지문 | enrich 재실행 또는 수동 수정 |
| 모의 출제 kw 없음 > 0 | 해당 id `agent_extract` 역추적 |

---

## 정답 형식 규칙 (신규 추출·재추출 시)

- 정답 헤더: `## Part 〈N〉 정답 및 해설` (**`##` 권장**)
- 섹션: `## CHAPTER 01 … — Check Q&A` / `단원별 출제예상문제`
- 각 줄: `번호. ① — 해설 문장` (**compact 다중 정답 줄 금지**)
- placeholder `정답 키 기준.` **금지**
- OX: `번호. O — 판단 근거`

상세: [`extraction_guide.md`](../extraction_guide.md) 정답 형식 절

## 관련 도구

| 스크립트 | 용도 |
|----------|------|
| `enrich_answer_kw.py` | compact 전개·placeholder·선지 fallback |
| `audit_kw_coverage.py` | 풀·모의 kw 커버리지 리포트 |
| `mock_exam_common.py` | 풀 파싱·`keyword_line()` |
| `validate_extract.py` | 문항 수 = 정답 수 검증 |

# 정답·kw 3차 품질 보강 계획 (템플릿 328건 → 교재 해설)

> **전제:** [2차 보강](정답_kw_품질_2차.md) 완료 — kw 없음·선지 복사·placeholder **0건**, 모의 80문항 **실해설**.  
> **상태:** ✅ **3차 완료** (2026-06-27) — 템플릿 328건 → `tools/replace_template_kw.py` 문항별 해설 교체.

## 1. 잔여 현황

### 식별 패턴

정답 섹션 `—` 뒤에 아래 문구가 포함되면 **미보강 템플릿**:

```text
오답 선지는 요건·효과·주체를 혼동하거나 반대로 서술했다.
```

```bash
rg "오답 선지는 요건·효과·주체를 혼동" output/agent_extract/
# → 328건 (2026-06-27)
```

### 파일·Part 분포

| 배치 | 파일 | 문항 수 | OCR·JPG |
|------|------|--------:|---------|
| **T1** | `3과목_공공계약관리/part4.md` | 115 | `output/ocr/3과목_공공계약관리/Part 4/` (105p) |
| **T2** | `1과목_공공조달의 이해/part1.md` | 110 | `output/ocr/1과목_공공조달의_이해/Part 1/` |
| **T3** | `3과목_공공계약관리/part2.md` | 101 | `output/ocr/3과목_공공계약관리/Part 2/` |
| **T4** | `1과목_공공조달의 이해/part6.md` | 2 | Part 6 OCR |

2과목·모의 미출제 구간은 **대상 없음**.

### 구간별 (Chapter)

| Ch | 문항 | 비고 |
|----|-----:|------|
| 3과목 P4 Ch01~03 exam | 115 | 단원별 출제예상 |
| 1과목 P1 Ch01~04 exam | 110 | 단원별 출제예상 |
| 3과목 P2 Ch01~02 exam+check | 101 | check 15건 포함 |

---

## 2. 완료 정의 (DoD)

| 검사 | 목표 |
|------|------|
| 템플릿 패턴 포함 kw | **0** |
| `kw == 정답 선지` | **0** (유지) |
| 해설 길이 | **20자 이상**, 선지 전문과 **문자열 동일 금지** |
| 형식 | `번호. ① — 해설 1~2문장` |
| 근거 | 문항 `source` 페이지·OCR·교재 범위 |
| `enrich_kw_quality.py` | 템플릿 재생성 **방지** (아래 T0) |

**품질 예**

```markdown
# Before (템플릿)
30. ③ — 「설계·시공 일괄입찰(Turn-Key)…」 문항에서 정답 ③는 … 오답 선지는 요건·효과·주체를 혼동…

# After (교재형)
30. ③ — Turn-Key 계약은 설계·시공을 일괄 도급하므로 설계변경 리스크가 수급인에게 있고,
         계약금액 증액은 정부 책임·천재지변 등 예외적 사유에 한정된다.
```

---

## 3. 단계별 실행

### Phase T0 — 감사·재오염 방지 (0.5일)

**1) 템플릿 감지 추가**

`audit_kw_coverage.py`에 `--template` 또는 `--quality` 확장:

```bash
python3 tools/audit_kw_coverage.py --quality
# kw==선지 | 템플릿 | 짧은 kw | 모의
```

**2) `enrich_kw_quality.py` 수정 (필수)**

- `craft_kw()`가 **이미 실해설인 줄**은 건너뛰기 (템플릿 패턴만 대상)
- 또는 `MANUAL_KW`·`kw_db.json`에 있는 id는 **절대 덮어쓰지 않음**
- **3차 보강 후 `enrich_kw_quality.py` 일괄 재실행 금지** (문서·주석에 명시)

**3) 체크리스트 산출**

```bash
python3 tools/enrich_kw_quality.py --export-template output/kw_템플릿_대상.json
# (T0에서 스크립트에 --export-template 옵션 추가 권장)
```

---

### Phase T1 — 3과목 P4 (115문항, 4~5일)

**파일:** `output/agent_extract/3과목_공공계약관리/part4.md`  
**구간:** `#### 단원별 출제예상문제` (CH01~03)

**작업 순서 (Chapter당)**

1. 해당 Chapter **문항 본문** + `<!-- source: -->` 목록 추출
2. 정답·해설 **JPG** (`sources/…/Part 4/page_*.jpg`) 또는 **OCR** 대조
3. 정답 섹션만 `N. ② — (해설)` 교체
4. Chapter 완료 후 `rg`로 템플릿 잔여 0 확인

**에이전트 프롬프트:**

```
너는 `output/agent_extract/3과목_공공계약관리/part4.md` **정답 섹션** 3차 보강 편집자다.

## 이번 배치
- ### Chapter 〈NN〉 … `#### 단원별 출제예상문제` 구간만
- 템플릿 패턴(`오답 선지는 요건·효과·주체를 혼동`) 포함 줄 전부 교체

## 참고 첨부
- `@output/agent_extract/3과목_공공계약관리/part4.md`
- `@sources/민간_박문각_수험서_jpg/3과목_공공계약관리/Part 4/`
- `@output/ocr/3과목_공공계약관리/Part 4/`

## 규칙
1. 정답 번호(①~④) 유지 · 문제 본문·선지 수정 금지
2. `—` 뒤 1~2문장: **왜 정답인지** + (가능하면) 대표 오답 함정 1가지
3. 선지 문장 **전문 복붙 금지** · 템플릿 문장 재사용 금지
4. OCR·교재에 해설 없으면: 지문·선지·법령 범위에서 **시험형 해설** 작성

## 완료 검증
rg "오답 선지는 요건·효과·주체를 혼동" output/agent_extract/3과목_공공계약관리/part4.md
# → 0건 (해당 Chapter 구간)
```

---

### Phase T2 — 1과목 P1 (110문항, 4일)

**파일:** `output/agent_extract/1과목_공공조달의 이해/part1.md`  
**구간:** `## Chapter 0N 단원별 출제예상문제` 정답 섹션

동일 규칙 · CH01 → CH04 순

---

### Phase T3 — 3과목 P2 (101문항, 4일)

**파일:** `output/agent_extract/3과목_공공계약관리/part2.md`  
**구간:** CH01·CH02 `단원별 출제예상문제` + `Check Q&A` 중 템플릿 15건

설계변경·물가변동·Turn-Key 등 **시험 고빈도** → 해설 품질 특히 엄격히 검수

---

### Phase T4 — 1과목 P6 (2문항, 0.5일)

소량 — T2와 동시 또는 마지막에 처리

---

### Phase T5 — 검증·동기화 (0.5일)

```bash
rg "오답 선지는 요건·효과·주체를 혼동" output/agent_extract/   # → 0
python3 tools/audit_kw_coverage.py --quality
python3 tools/validate_extract.py --subject 1
python3 tools/validate_extract.py --subject 3
# 2회차 출제 전 problem pool 자동 반영 (별도 HTML 재빌드는 1회차 템플릿 0이라 선택)
```

**산출물 Git:** `agent_extract` 4파일만 (리포트 `output/kw_*.md`는 커밋 제외)

---

## 4. 일정 (제안)

| 주 | 작업 |
|----|------|
| 1 | T0 (도구) + T1 CH01 |
| 2 | T1 CH02~03 |
| 3 | T2 (1과목 P1) |
| 4 | T3 (3과목 P2) + T4 + T5 |

**총 3~4주** (에이전트 배치 + 사람 검수 10% 샘플)

---

## 5. 검수 샘플링

Chapter 완료마다 **10% 무작위** 또는 **시험 빈출 키워드 전수**:

- 설계변경 · 물가변동 · Turn-Key · MAS · 보증금 · 수의계약 · 전략적 조달

틀리면 해당 Chapter 전량 재검토.

---

## 6. `MANUAL_KW` / 데이터베이스 전략 (선택)

대량 보강 시 `tools/kw_db.json` 도입 권장:

```json
{
  "3:2:2:exam:30": "Turn-Key 계약은 설계·시공 리스크가…"
}
```

`enrich_kw_quality.py`가 `MANUAL_KW` → `kw_db.json` 순으로 조회, **템플릿이 아닌 해설은 skip**.

---

## 7. 하지 않을 것

- `parts_clean`·문항 본문 수정
- `enrich_kw_quality.py`로 328건 **재템플릿화**
- 4과목 실기 (필기 합격 후)
- `output/kw_*.md` Git 추적

---

## 8. 3차 완료 후

| 영역 | 상태 |
|------|------|
| kw 파이프라인 | **종료** (신규 추출 시 [1차 형식 규칙](정답_kw_보강.md) 준수만) |
| 학습 | 2회차 모의 · 오답 복기 · 과목별 학습 |
| 선택 | 4과목 · 실기 모의 |

---

## 다음 액션

1. **T0:** `audit_kw_coverage.py` 템플릿 카운트 + `enrich_kw_quality.py` 재오염 방지
2. **T1 CH01:** 3과목 P4 파일럿 ~15문항 → 품질 합의 후 115건 전량
3. 완료마다 `rg` 템플릿 0 확인

관련: [1차 보강](정답_kw_보강.md) · [2차 보강](정답_kw_품질_2차.md) · [extraction_guide.md](../extraction_guide.md)

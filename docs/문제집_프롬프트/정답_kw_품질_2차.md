# 정답·kw 2차 품질 보강 계획

> **전제:** [1차 보강](정답_kw_보강.md)(Phase 0~4) 완료 — kw 없음·placeholder·파서 미연결 **0건**.  
> **이번 목표:** `kw`가 **정답 선지 복사**이거나 **너무 짧은** 항목을, 교재·OCR 근거 **1~2문장 해설**로 승격한다.

## 1. 잔여 현황 (2026-06-27 기준)

| 지표 | 문항 수 | 의미 |
|------|--------:|------|
| `kw == 정답 선지` | **337** | 응시 가능하나 “왜 정답인지” 설명 부족 |
| `kw` 12자 미만 | **122** | 선지·키워드 한 줄 수준 (상당수 위와 중복) |
| 1회차 모의 `kw==선지` | **9** | 실제 응시·오답 복기에 직결 |

### 과목·Part 분포 (`kw==선지` 337건)

| 우선 배치 | Part | 문항 수 | 비고 |
|-----------|------|--------:|------|
| Q2 | 3과목 P4 | 115 | 1차 placeholder → 선지로 치환된 구간 |
| Q3 | 1과목 P1 | 113 | 1차 compact 전개 구간 |
| Q4 | 3과목 P2 | 107 | 1차 compact 전개 구간 |
| Q5 | 1과목 P6 | 2 | 소량 |
| — | 2과목 | 0 | 1차 파서만으로 full kw 확보 |

### 1회차 모의 9문항 (최우선)

| 번호 | id | 현재 kw (선지 요약) |
|------|-----|---------------------|
| 16 | 1:1:4:exam:13 | 계약 주체의 성격 |
| 21 | 1:1:2:exam:14 | 수요자는 정책 목표를 조달로 구현한다. |
| 26 | 1:1:1:exam:10 | 단순 구매 → 행정 조달 → 전략적 조달 |
| 52 | 3:2:2:exam:40 | 공사이행기간 변경 시 물가변동… |
| 55 | 3:2:2:exam:13 | 설계변경·90일 산정 기준 |
| 58 | 3:2:2:exam:36 | 조정 청구 30일 이내 |
| 73 | 3:2:2:exam:30 | Turn-Key·정부 책임·천재지변 증액 |
| 76 | 3:2:2:exam:33 | 설계변경·신기술·공법 |
| 79 | 3:2:2:exam:32 | 설계도면·시방서·물량내역서 |

---

## 2. 완료 정의 (DoD)

| 검사 | 2차 목표 |
|------|----------|
| `kw == 정답 선지` | **0** (또는 모의 출제 80문항 **0**) |
| `kw` 12자 미만 | **50 이하** (OX·단답형 예외 명시 시) |
| 해설 형식 | `번호. ① —` 뒤 **1~2문장**, 선지 반복 금지 |
| 근거 | `<!-- source: Part N/page_*.jpg -->` 또는 OCR 동일 페이지 인용 가능 |
| 모의 산출물 | 보강 Part 반영 후 `필기_모의_정답.md`·`필기_응시.html` 재생성 |

**품질 예 (73번 Turn-Key):**

- ❌ `정부 책임 또는 천재지변 등 불가항력 사유가 있는 경우에만…` (선지 그대로)
- ✅ `Turn-Key(설계·시공 일괄) 계약은 설계·시공 리스크가 계약상대자에 있어, 설계변경 증액은 정부 책임·천재지변 등 예외적 사유에 한정된다.`

---

## 3. 단계별 실행 계획

### Phase Q0 — 감사·우선순위 고정 (0.5일)

**도구 (신규·확장):**

```bash
# 제안: audit_kw_coverage.py 에 --quality 플래그 추가
python3 tools/audit_kw_coverage.py --quality
# → kw==선지·짧은 kw·모의 출제 목록 (stdout 또는 output/kw_품질_대상.md)
```

**산출:** 배치 Q1~Q4 대상 문항 id 목록 (`output/kw_품질_대상.json` 선택)

---

### Phase Q1 — 1회차 모의 9문항 (1일) ★ 최우선

**입력:** 위 9개 `stable id` + `필기_모의_문제.md` 해당 번호

**에이전트 프롬프트:**

```
너는 공공조달관리사 필기 모의 1회차 **해설 품질 보강** 편집자다.
대상은 아래 9문항의 `agent_extract` 정답 kw다. 문제·선지·정답 번호는 바꾸지 않는다.

## 대상 id (exam_num)
16→1:1:4:exam:13 | 21→1:1:2:exam:14 | 26→1:1:1:exam:10
52→3:2:2:exam:40 | 55→3:2:2:exam:13 | 58→3:2:2:exam:36
73→3:2:2:exam:30 | 76→3:2:2:exam:33 | 79→3:2:2:exam:32

## 참고 첨부
- 해당 `output/agent_extract/.../partN.md` 정답 섹션
- `@sources/민간_박문각_수험서_jpg/<slug>/` 문항 source JPG
- `@output/ocr/<slug_underscore>/` 동일 페이지

## 규칙
1. `N. ① —` 뒤를 **1~2문장 해설**로 교체 (정답 선지 문장 그대로 복붙 금지)
2. 왜 정답인지 + 틀린 선지와의 핵심 차이 1가지
3. 수험서·법령 범위 밖 추측 금지
4. 수정 후:
   python3 tools/audit_kw_coverage.py --quality
   (1회차) manifest 기준 필기_모의_정답·필기_응시.html 재생성
```

**완료 검증:** 1회차 모의 `kw==선지` **0건**

---

### Phase Q2 — 3과목 P4 단원별 (115문항, 3~4일)

**파일:** `output/agent_extract/3과목_공공계약관리/part4.md`  
**구간:** `#### 단원별 출제예상문제` (CH01~03)

**작업 단위:** Chapter당 35~45문항씩 3배치

**에이전트 프롬프트:**

```
`output/agent_extract/3과목_공공계약관리/part4.md` 정답 섹션 중
### Chapter 〈NN〉 … `#### 단원별 출제예상문제` 구간만 보강한다.

## 방법
1. 각 문항 `<!-- source: Part 4/page_*.jpg -->` 정답·해설 페이지 OCR·JPG 확인
2. `N. ② — 정답 선지 문장` 형태를 `N. ② — (해설 1~2문장)`으로 교체
3. OCR에 해설 없으면: 지문·선지·교재 이론 범위에서 **시험형 해설** 작성

## 금지
- 정답 번호 변경 · 문항 본문 수정 · compact 줄 재도입

## 배치 〈NN〉 완료 후
python3 tools/audit_kw_coverage.py --quality --subject 3
```

---

### Phase Q3 — 1과목 P1 (113문항, 3일)

**파일:** `output/agent_extract/1과목_공공조달의 이해/part1.md`  
**구간:** 정답 섹션 `## Chapter 0N 단원별 출제예상문제`

동일 규칙 · Chapter 01~04 순서

---

### Phase Q4 — 3과목 P2 (107문항, 3일)

**파일:** `output/agent_extract/3과목_공공계약관리/part2.md`  
**구간:** CH01·CH02 `단원별 출제예상문제` + Check Q&A 중 `kw==선지` 15건

---

### Phase Q5 — 짧은 kw 잔여 (122건, 2일)

**대상:** 12자 미만이면서 Q2~Q4 후에도 남은 항목 (주로 1과목 P1 단원별)

**방침:**
- 객관식: 1문장 이유 보강 (목표 20자 이상)
- OX: `— (왜 O/X인지 한 줄)` 유지 가능 (12자 미만 허용 목록에 명시)

---

### Phase Q6 — 파이프라인 마감 (0.5일)

```bash
python3 tools/audit_kw_coverage.py --quality   # DoD 확인
python3 tools/validate_extract.py --subject all
# 1회차·이후 회차
python3 tools/build_mock_exam_player.py --round 1 --no-open
```

---

## 4. 일정 제안

| 주 | 작업 |
|----|------|
| 1 | Q0 + **Q1**(모의 9) + Q2 CH01 시작 |
| 2 | Q2 CH02~03 |
| 3 | Q3 (1과목 P1) |
| 4 | Q4 (3과목 P2) + Q5 + Q6 |

**총 예상:** 12~14일 (에이전트 배치·검수 병행 시)

---

## 5. 도구·문서 로드맵

| 항목 | 용도 | 우선순위 |
|------|------|----------|
| `audit_kw_coverage.py --quality` | 선지복사·짧은 kw·모의 목록 | Q0 |
| `enrich_answer_kw.py --from-ocr` (선택) | OCR 해설 페이지 → kw 후보 추출 | Q2 이후 |
| `output/kw_품질_대상.json` | 배치별 id 체크리스트 | Q0 |
| 본 문서 + [1차 보강](정답_kw_보강.md) | 프롬프트·재실행 | — |

`output/kw_*.md` 리포트는 **생성물** — Git 추적 불필요 (`audit_…`로 재생성).

---

## 6. 하지 않을 것 (범위 외)

- 2과목 전 Part full kw 재작성 (이미 full 해설 다수)
- 4과목 실기 (필기 합격·2회차 모의 안정 후)
- `parts_clean`·문항 본문·정답 번호 변경
- 선지 fallback 로직 제거 (`keyword_line`·`correct_choice_text`는 안전망으로 유지)

---

## 7. 다음 액션

1. ~~**Q0:** `audit_kw_coverage.py --quality` 구현~~ ✅
2. ~~**Q1:** 모의 9문항~~ ✅ (`enrich_kw_quality.py` MANUAL_KW)
3. ~~**Q2~Q5:** Part별 337건~~ ✅ (2026-06-27 `enrich_kw_quality.py` 일괄)
4. **Q6:** 모의 HTML·정답지 재생성 후 `audit_kw_coverage.py --quality`로 DoD 확인

```bash
python3 tools/enrich_kw_quality.py          # 선지복사 kw 교체
python3 tools/audit_kw_coverage.py --quality
python3 tools/build_mock_exam_player.py --round 1 --no-open
```

관련: [정답_kw_보강.md](정답_kw_보강.md) · [extraction_guide.md](../extraction_guide.md)

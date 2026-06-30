# 3과목 전용 필기 모의

3과목(공공계약관리) **30문항만** 응시하는 CBT 모의고사입니다. 통합 80문항(`필기/통합/`)과 별도로 운영합니다.

**경로:** `output/mock_exam/필기/3과목/〈K〉회차/`  
**오답 누적:** [`오답노트.md`](오답노트.md)  
**출제·배포:** [`docs/시험모의/선별.md`](../../../docs/시험모의/선별.md) §A-6 · **채점:** [`풀이.md`](../../../docs/시험모의/풀이.md) §C

## 회차

| 회차 | 경로 | CBT |
|------|------|-----|
| 1 | [1회차/](1회차/) | (로컬 `index.html`) |
| 2~7 | [2회차/](2회차/) … [7회차/](7회차/) | (로컬) |
| 8 | [8회차/](8회차/) | [온라인 CBT](../../../docs/3과목/index.html) |

## 워크플로

```bash
# 1. 선별 draft 생성 (stable_id 목록은 tools/build_subject3_draft.py)
python3 tools/build_subject3_draft.py 1

# 2. 병합
python3 tools/merge_mock_draft_subject3.py 1

# 3. 교차검수 후 CBT + Pages
python3 tools/build_cbt_viewer.py --profile subject3 --round 1 --pages
# (--subject3 도 동일)
```

- 선별: `problem_book_final` + `agent_extract` 대조 (자동 추첨 없음)
- 통합·이전 3과목 단독 manifest의 `3:*` stable_id **1차 lap 재사용 금지** · 1차 소진 후 §A-0b **2차 lap**
- 제한시간 **45분** · localStorage `mock_exam_3sK_answers` (K=회차)

## 답안 제출

CBT 종료 화면 문자열을 채팅에 붙여넣기: `1③ 2④ … 30②`

# 3과목 전용 필기 모의

3과목(공공계약관리) **30문항만** 응시하는 CBT 모의고사입니다. 통합 80문항 모의(`1회차`~`N회차`)와 별도로 운영합니다.

## 회차

| 회차 | 경로 | CBT |
|------|------|-----|
| 1 | [1회차/](1회차/) | [온라인 CBT](../../docs/3과목/index.html) |

## 워크플로

```bash
# 1. 선별 draft 생성 (stable_id 목록은 tools/build_subject3_draft.py)
python3 tools/build_subject3_draft.py 1

# 2. 병합
python3 tools/merge_mock_draft_subject3.py 1

# 3. 교차검수 후 CBT + Pages
python3 tools/build_cbt_viewer.py --subject3 --round 1 --pages
```

- 선별: `problem_book_final` + `agent_extract` 대조 (자동 추첨 없음)
- 통합 모의 manifest의 `3:*` stable_id **재사용 금지**
- 제한시간 **45분** · localStorage `mock_exam_3s1_answers`

## 답안 제출

CBT 종료 화면 문자열을 채팅에 붙여넣기: `1③ 2④ … 30②`

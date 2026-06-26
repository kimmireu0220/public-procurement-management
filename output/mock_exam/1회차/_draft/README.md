# 1회차 초안 폴더

에이전트가 과목별 선별 결과를 여기에 둔다.

## 방식 A (권장): manifest.json

```json
{
  "round": 1,
  "subjects": {
    "1": ["1:1:1:exam:3", "..."],
    "2": ["2:1:2:check:5", "..."],
    "3": ["3:2:1:exam:1", "..."]
  }
}
```

## 방식 B: 과목별 MD

- `1과목_선별.md` (30문항)
- `2과목_선별.md` (20문항)
- `3과목_선별.md` (30문항)

각 문항에 `<!-- id: 과목:part:chapter:stype:qn -->` 필수.

## 다음 단계

```bash
python3 tools/merge_mock_draft.py 1   # HTML + 브라우저 자동 열기
python3 tools/validate_mock_exam.py 1
```

# mock_exam — 필기 모의시험

회차별 **80문항**(1과목 30 · 2과목 20 · 3과목 30). 실기는 동일 폴더에 별도 MD.

## 출제 방식

| 경로 | 설명 |
|------|------|
| **에이전트 출제 (기본)** | `prepare` → 에이전트 선별·검수 → `merge` → `validate` |
| 스크립트 초안 | `select_mock_exam.py` — 에이전트 검수 권장 |

프롬프트: [`docs/문제집_프롬프트/시험모의_선별.md`](../../docs/문제집_프롬프트/시험모의_선별.md)

## K회차 새로 만들기

```bash
python3 tools/prepare_mock_round.py K
# 에이전트: _candidates/ → _draft/
python3 tools/merge_mock_draft.py K    # HTML 생성 + 브라우저 자동 열기
python3 tools/validate_mock_exam.py K
```

## 회차별 파일

| 파일 | 용도 |
|------|------|
| `manifest.json` | 문항 stable ID (`1:part:ch:stype:qn`) — 회차 간 중복 추적 |
| `필기_모의_문제.md` | 80문항 (1~80) |
| `필기_모의_정답.md` | 정답·키워드 |
| `필기_응시.html` | 1문항씩 응시 UI |
| `필기_풀이.md` | 응시 후 채점·해설 |
| `_briefing.md` / `_candidates/` | 에이전트 출제 준비물 |

## 현재 상태

- **1회차** — 출제 완료 (`필기_모의_문제.md`, `필기_모의_정답.md`, `필기_응시.html`, `manifest.json`)

## 오답노트

[`오답노트.md`](오답노트.md) — 틀린 문항 회차별 누적. 풀이 프롬프트: [`시험모의_풀이.md`](../../docs/문제집_프롬프트/시험모의_풀이.md)

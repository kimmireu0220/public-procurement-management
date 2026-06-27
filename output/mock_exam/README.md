# mock_exam — 필기 모의시험

회차별 **80문항**(1과목 30 · 2과목 20 · 3과목 30).

## 파일

| 파일 | 용도 |
|------|------|
| `필기_모의_문제.md` | 80문항 |
| `필기_모의_정답.md` | 정답·해설 |
| `index.html` | CBT 응시 UI |
| `필기_응시.html` | `index.html`과 동일 |
| `필기_모의_응시.html` | `index.html`과 동일 |
| `필기_풀이.md` | 채점·해설 (미응시 시 템플릿) |
| `교차검수.md` | 3단계 교차 검수 기록 |
| `manifest.json` | 문항 ID (중복 방지) |
| [`오답노트.md`](오답노트.md) | 틀린 문항 누적 |

## 출제·풀이

- 선별: [`docs/시험모의_선별.md`](../../docs/시험모의_선별.md)
- 채점·해설: [`docs/시험모의_풀이.md`](../../docs/시험모의_풀이.md)

회차 폴더 `〈K〉회차/`는 출제 시 생성한다.

### 출제 병합 · CBT 로컬 실행

```bash
python3 tools/merge_mock_draft.py K          # _draft/3과목 선별본 → 문제·정답·manifest
python3 tools/build_cbt_viewer.py --round K   # 필기_모의_문제.md → HTML 3종
cd output/mock_exam/〈K〉회차 && python3 -m http.server 8765
open http://localhost:8765/
```

- `merge_mock_draft.py` — 과목별 `_draft/*_선별.md`를 1~80 연번으로 합침 (선별은 에이전트, 병합만 기계)
- `build_cbt_viewer.py` — CBT UI (키보드·과목별 문항판·답안 초기화 등은 스크립트 내 템플릿)

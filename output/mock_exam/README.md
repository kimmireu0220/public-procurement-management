# mock_exam — 모의시험 산출

필기(통합·과목별)와 실기 모의를 구분해 둡니다.

## 디렉터리

```
output/mock_exam/
├── 필기/
│   ├── 통합/            # 80문항 (1·2·3과목 합본) — 〈K〉회차/
│   │   └── 오답노트.md  # 통합 필기 오답 누적
│   ├── 1과목/           # 과목 단독 30문항 · 오답노트.md
│   ├── 2과목/           # 과목 단독 20문항 · 오답노트.md
│   └── 3과목/           # 과목 단독 30문항 · 오답노트.md
└── 실기/                # 실기 모의 (20문항 내외)
```

## 필기 통합 (80문항)

| 항목 | 경로 |
|------|------|
| 회차 산출 | `필기/통합/〈K〉회차/` |
| 온라인 CBT | [GitHub Pages](https://kimmireu0220.github.io/public-procurement-management/) |
| 출제·풀이 | [`docs/시험모의/`](../../docs/시험모의/) |

```bash
python3 tools/merge_mock_draft.py K
python3 tools/build_cbt_viewer.py --round K --pages
```

## 필기 3과목 단독 (30문항)

| 항목 | 경로 |
|------|------|
| 회차 산출 | `필기/3과목/〈K〉회차/` |
| 온라인 CBT | [GitHub Pages `/3과목/`](https://kimmireu0220.github.io/public-procurement-management/3%EA%B3%BC%EB%AA%A9/) |
| 출제·풀이 | [`선별.md` §A-6](../../docs/시험모의/선별.md) · [`풀이.md` §C](../../docs/시험모의/풀이.md) |

```bash
python3 tools/merge_mock_draft_subject3.py K
python3 tools/build_cbt_viewer.py --profile subject3 --round K --pages
```

상세: [`필기/3과목/README.md`](필기/3과목/README.md)

## 실기

[`실기/README.md`](실기/README.md) — 회차별 `실기_모의_문제.md` · `실기_모의_정답.md`.

## 공통 회차 파일 (필기)

| 파일 | 용도 |
|------|------|
| `필기_모의_문제.md` | 문제지 |
| `필기_모의_정답.md` | 정답 (채점 전 비공개) |
| `index.html` | CBT |
| `manifest.json` | stable_id (중복 방지) |
| `교차검수.md` | 출제 검수 |
| `필기_풀이.md` | 채점·해설 |

출제 완료 시 `docs/` 갱신 후 `main` push — 통합 [`선별.md`](../../docs/시험모의/선별.md) §A-5 · 3과목 단독 §A-6.

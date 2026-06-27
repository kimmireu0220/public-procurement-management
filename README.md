# 공공조달관리사 학습 저장소

박문각 수험서·조달청 표준교재·Q-Net 자료 기반 **학습·모의시험**용.

## 시험 안내

[`docs/시험_안내.md`](docs/시험_안내.md) — 2026 제1회 일정·문항 수·합격 기준  
문서 목록: [`docs/README.md`](docs/README.md)

## 학습 경로

| 단계 | 경로 | 설명 |
|------|------|------|
| 1. 이론 | [`docs/학습_프롬프트/`](docs/학습_프롬프트/) | 과목별 Cursor 강의 프롬프트 |
| 2. 문제 풀이 | `output/problem_book_final/<과목>/〈N〉과목_문제집.html` | 사람 학습용 (정답 없음) |
| 2b. 출제·선별 | `…/〈N〉과목_문제집.md` | 에이전트·모의 출제용 (html과 동일 내용) |
| 3. 정답·해설 | `output/agent_extract/<과목>/partN.md` | 정답 섹션 |
| 4. 모의시험 | [`docs/시험모의/`](docs/시험모의/) · [`output/mock_exam/`](output/mock_exam/README.md) | 출제·채점 프롬프트 · 필기 80문항 · 풀이 · 오답노트 |

## 원본 자료 (`sources/`)

| 경로 | 용도 |
|------|------|
| `민간_박문각_수험서_jpg/` | 수험서 스캔 (주 교재) |
| `공식_조달청_표준교재_pdf/` | 조달청 표준교재 |
| `공식_qnet_예제문제/` | Q-Net 예제 |
| `공식_qnet_시행공고/` | 시행공고 |

## 문항 수 (3,325)

| 과목 | 문항 |
|------|-----:|
| 1과목 필기 | 1,050 |
| 2과목 필기 | 434 |
| 3과목 필기 | 700 |
| 4과목 실기 | 1,141 |

## 모의고사

- 프롬프트: [`docs/시험모의/`](docs/시험모의/) — [`선별.md`](docs/시험모의/선별.md) · [`풀이.md`](docs/시험모의/풀이.md)
- **온라인 CBT:** [GitHub Pages](https://kimmireu0220.github.io/public-procurement-management/) — 출제 후 `build_cbt_viewer.py --round K --pages` → **`main` 커밋·푸시** 필수 ([`선별.md` §A-5](docs/시험모의/선별.md))

에이전트 역할: [`AGENTS.md`](AGENTS.md)

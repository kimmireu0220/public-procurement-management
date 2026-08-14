# 공공조달관리사 — 에이전트 지침

박문각 수험서, 조달청 표준교재, Q-Net 자료를 근거로 공공조달관리사 시험 학습을 지원한다.

## 기준과 자료

- 시험 고정값은 `docs/시험_안내.md`와 `sources/공식_qnet_시행공고/`를 따른다.
- 이론 범위와 주제는 `output/standard_textbook/<과목>/INDEX.md` 및 장별 Markdown을 우선한다.
- 숫자·기한·비율은 `docs/학습_숫자암기/`를 확인한다.
- 필기 지문은 `output/problem_book_final/<과목>/`의 Markdown에서만 선별한다.
- 필기 정답은 `output/agent_extract/<과목>/partN.md`와 반드시 대조한다.
- 실기 지문은 4과목 문제은행, 범위는 4과목 표준교재를 사용한다.

## 필기 모의고사

| 구분 | 문항 | 시간 |
|---|---:|---:|
| 통합 | 80문항(1과목 30, 2과목 20, 3과목 30) | 120분 |
| 1과목 | 30문항 | 45분 |
| 2과목 | 20문항 | 30분 |
| 3과목 | 30문항 | 45분 |

- 문항은 에이전트가 직접 선별하며 코드로 자동 추첨하지 않는다.
- O/X와 최종점검 퀴즈는 필기에서 제외한다.
- `Check Q&A`는 과목당 20% 이하이며 필요한 경우에만 사용한다.
- Part와 Chapter를 분산하고 동일·유사 지문 및 동일 클러스터 과밀을 피한다.
- 1차 lap에서는 기존 manifest의 `stable_id`를 재사용하지 않는다.
- 문항에는 `source`와 `id` HTML 주석을 유지한다.
- 상세 선별·채점 규칙은 `docs/시험모의/선별.md`, `docs/시험모의/풀이.md`를 따른다.

필기 산출 경로:

- 통합: `output/mock_exam/필기/통합/<K>회차/`
- 과목별: `output/mock_exam/필기/<N>과목/<K>회차/`

회차 기본 파일은 `manifest.json`, `필기_모의_문제.md`, `필기_모의_정답.md`, `index.html`이다.
응시 후에는 `필기_풀이.md`, `출제_피드백.md`, `풀이/`를 필요한 경우에만 추가한다.

## 실기 모의고사

- 약 20문항으로 구성하되 유형과 Part 비중은 학습 상황에 맞춰 판단한다.
- 산출: `output/mock_exam/실기/<K>회차/실기_모의_문제.md`, `실기_모의_정답.md`.

## CBT와 검증

```bash
python3 tools/build_cbt_viewer.py --round K --pages
python3 tools/build_cbt_viewer.py --profile subjectN --round K --pages
python3 tools/validate_mock_exam.py
python3 -m unittest discover -s tests -v
```

- 회차에는 `index.html` 하나만 생성한다.
- GitHub Pages 공개본은 `docs/`에 둔다.
- 답안 문자열을 받으면 즉시 채점하고 틀린 문항만 해설·오답노트에 반영한다.
- 답안 제출만으로 커밋하거나 푸시하지 않는다. 사용자가 Git 반영을 요청한 경우에만 수행한다.

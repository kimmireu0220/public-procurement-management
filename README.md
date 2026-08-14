# 공공조달관리사 학습 저장소

공공조달관리사 필기 1~3과목과 실기 4과목 학습 자료, 문제은행, 모의고사 및 CBT를 관리한다.

## 바로가기

- [통합 필기 CBT](https://kimmireu0220.github.io/public-procurement-management/)
- [1과목 CBT](https://kimmireu0220.github.io/public-procurement-management/1%EA%B3%BC%EB%AA%A9/)
- [2과목 CBT](https://kimmireu0220.github.io/public-procurement-management/2%EA%B3%BC%EB%AA%A9/)
- [3과목 CBT](https://kimmireu0220.github.io/public-procurement-management/3%EA%B3%BC%EB%AA%A9/)
- [단원별 학습 CBT](https://kimmireu0220.github.io/public-procurement-management/study/)

## 구조

| 경로 | 내용 |
|---|---|
| `docs/시험_안내.md` | 시험 형식·일정·합격 기준 |
| `docs/학습_프롬프트/` | 과목별 이론 학습 자료 |
| `docs/학습_숫자암기/` | 금액·기한·비율 암기 자료 |
| `docs/시험모의/` | 모의고사 선별·채점 규칙 |
| `output/standard_textbook/` | 조달청 표준교재 핵심 정리 |
| `output/problem_book_final/` | 박문각 문제은행 Markdown |
| `output/agent_extract/` | 문제은행 정답·해설 |
| `output/mock_exam/` | 필기·실기 1회차 모의고사 |
| `output/part_lectures/` | 4과목 강의 대본 |
| `output/gpt_sovits_audio/` | 4과목 최종 강의 MP3 |
| `docs/` | GitHub Pages 공개본 |
| `sources/` | 공식·민간 원본 자료 |

## CBT 관리

문항은 에이전트가 직접 선별한다. 코드는 확정된 문제지의 HTML 빌드·배포·검증에만 사용한다.

```bash
python3 tools/build_cbt_viewer.py --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject1 --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject2 --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject3 --round 1 --pages
python3 tools/validate_mock_exam.py
python3 -m unittest discover -s tests -v
```

통합 모의고사를 `--pages`로 배포하면 빌드된 모든 회차가 `docs/mock/<K>회차/`에
누적되고, `docs/index.html`에는 응시할 회차를 고르는 목록이 생성된다.

각 필기 회차는 문제·정답·manifest·`index.html`만 기본 산출물로 유지한다.

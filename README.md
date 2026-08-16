# 공공조달관리사 학습 저장소

공공조달관리사 필기 1~3과목과 실기 4과목 학습 자료, 문제은행, 모의고사 및 CBT를 관리한다.

## 바로가기

### 이론 강의 (104개 Chapter)

- [강의 홈](https://kimmireu0220.github.io/public-procurement-management/lecture/)
- [1과목 공공조달과 법제도 이해](https://kimmireu0220.github.io/public-procurement-management/lecture/1/) — 29 Chapter
- [2과목 공공조달계획 수립 및 분석](https://kimmireu0220.github.io/public-procurement-management/lecture/2/) — 28 Chapter
- [3과목 공공계약관리](https://kimmireu0220.github.io/public-procurement-management/lecture/3/) — 22 Chapter
- [4과목 공공조달 관리실무](https://kimmireu0220.github.io/public-procurement-management/lecture/4/) — 25 Chapter

### 문제풀이 CBT

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
| `docs/자료_공개_및_저장_정책.md` | 공개 범위·저작권·대용량 파일 정책 |
| `output/standard_textbook/` | 조달청 표준교재 핵심 정리 |
| `output/problem_book_final/` | 박문각 문제은행 Markdown |
| `output/agent_extract/` | 문제은행 정답·해설 |
| `output/mock_exam/` | 필기·실기 1회차 모의고사 |
| `output/chapter_lectures/` | Chapter 강의 원본 (공개본: `docs/lecture/`) |
| `output/part_lectures/` | 4과목 강의 대본 |
| `output/gpt_sovits_audio/` | 4과목 최종 강의 MP3 |
| `docs/` | GitHub Pages 공개본 |
| `sources/` | 공식 근거 자료와 로컬 민간 원본의 보관 위치 |

시험 학습의 기준은 조달청 표준교재다. 현행 규정은
`sources/현행_법령_근거/manifest.json`에 공식 URL·시행일·수집일·SHA-256과 함께
보관하고 `현행(시행일)`로 구분한다. 민간 교재 스캔은 로컬 전용이며 Git에 올리지
않는다. 자세한 범위는 `docs/자료_공개_및_저장_정책.md`를 따른다.

개발·검증 환경은 Python 3.12 이상을 지원하고 CI는 Python 3.13을 사용한다.

```bash
python3 -m pip install -r requirements-dev.txt
```

## 강의 관리

강의 원본은 `output/chapter_lectures/<과목>/partNN/chapterNN.md`에 두고, 공개본은
빌드로 생성한다. `docs/lecture/`는 산출물이므로 직접 고치지 않는다.

```bash
python3 tools/build_lecture_pages.py
```

각 Chapter는 `학습목표 → ① 한눈에 보기 → ② 차근차근 설명 → ③ 시험 포인트 →
④ 암기 체크리스트 → ⑤ 다음 Chapter` 순서를 지킨다. 과목마다 `overview.md`와
`total-review.md`를 두고, 문제·퀴즈는 넣지 않는다. 이 구조는
`tests/test_lecture_pages.py`가 검사한다.

## CBT 관리

문항은 에이전트가 직접 선별한다. 코드는 확정된 문제지의 HTML 빌드·배포·검증에만 사용한다.

```bash
python3 tools/build_cbt_viewer.py --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject1 --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject2 --round 1 --pages
python3 tools/build_cbt_viewer.py --profile subject3 --round 1 --pages
python3 tools/build_study_cbt.py
python3 tools/build_study_cbt.py --check
python3 tools/build_lecture_pages.py --check
python3 tools/private_source_inventory.py
python3 tools/verify_legal_sources.py
python3 tools/validate_mock_exam.py
python3 -m unittest discover -s tests -v
```

통합 모의고사를 `--pages`로 배포하면 빌드된 모든 회차가 `docs/mock/<K>회차/`에
누적되고, `docs/index.html`에는 응시할 회차를 고르는 목록이 생성된다.

각 필기 회차는 문제·정답·manifest·`index.html`만 기본 산출물로 유지한다.

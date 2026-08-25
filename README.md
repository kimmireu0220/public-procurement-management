# 공공조달관리사 학습 저장소

공공조달관리사 필기 1~3과목과 실기 4과목의 공식 자료 기반 학습 강의를 관리한다.

## 바로가기

### 이론 강의

- [강의 홈](https://kimmireu0220.github.io/public-procurement-management/lecture/)
- [1과목 공공조달과 법제도 이해](https://kimmireu0220.github.io/public-procurement-management/lecture/1/)
- [2과목 공공조달계획 수립 및 분석](https://kimmireu0220.github.io/public-procurement-management/lecture/2/)
- [3과목 공공계약관리](https://kimmireu0220.github.io/public-procurement-management/lecture/3/)
- [4과목 공공조달 관리실무](https://kimmireu0220.github.io/public-procurement-management/lecture/4/)

### 연습문제

- 각 Chapter의 객관식·O/X·회상·사례 문제 바로 아래에 정답과 해설을 둔다.
- [강의별 자체 연습문제 안내](https://kimmireu0220.github.io/public-procurement-management/study/)

## 구조

| 경로 | 내용 |
|---|---|
| `docs/시험_안내.md` | 시험 형식·일정·합격 기준 |
| `docs/학습_프롬프트/` | 과목별 이론 학습 자료 |
| `docs/학습_숫자암기/` | 금액·기한·비율 암기 자료 |
| `docs/시험모의/` | 모의고사 선별·채점 규칙 |
| `docs/자료_공개_및_저장_정책.md` | 공개 범위·저작권·대용량 파일 정책 |
| `output/standard_textbook/` | 조달청 표준교재 핵심 정리 |
| `output/problem_book_final/` | 민간 문제은행 Markdown(로컬 전용) |
| `output/agent_extract/` | 민간 문제은행 정답·해설(로컬 전용) |
| `output/mock_exam/` | 로컬 모의고사 작업물; 공개 전 권리·출처 확인 필수 |
| `output/chapter_lectures/` | Chapter 강의 원본 (공개본: `docs/lecture/`) |
| `docs/` | GitHub Pages 공개본 |
| `sources/` | 공식 근거 자료와 로컬 민간 원본의 보관 위치 |

시험 학습의 기준은 조달청 표준교재다. 현행 규정은 시험 기준과 혼동되지 않게
시행일과 근거를 함께 밝힌다. 민간 교재 스캔과 공개 허가가 없는 제3자 원문·문항·해설은
로컬 전용이며 Git이나 Pages에 올리지 않는다. 자세한 범위는
`docs/자료_공개_및_저장_정책.md`를 따른다.

개발·검증 환경은 Python 3.12 이상을 지원하고 CI는 Python 3.13을 사용한다.

```bash
python3 -m pip install -r requirements-dev.txt
```

## 강의 관리

강의 원본은 `output/chapter_lectures/<과목>/partNN/chapterNN.md`에 두고, 공개본은
빌드로 생성할 수 있다. 공개본을 직접 수정했다면 다음 빌드에 사라지지 않도록 원본에도
반영한다.

```bash
python3 tools/build_lecture_pages.py
```

Chapter의 목차, 길이와 설명 방식은 자유다. 필요에 따라 사례, 비교표, 비유, 질문,
O/X, 회상 연습, 문제풀이와 요약을 사용할 수 있다. `overview.md`와
`total-review.md`도 필요할 때만 둔다. 빌더를 사용할 문서에는 페이지 경로를 만들기 위한
front matter만 필요하다.

## CBT 관리

문항은 직접 작성·선별·변형하거나 도구로 보조할 수 있다. 실제 시험 재현용 프로필은 공식
문항 수와 시간을 따르고, 그 밖의 연습자료는 목적에 맞게 문항 수와 유형을 정한다. 기존
CBT 빌더를 사용할 때는 문제·정답·식별자와 출처가 서로 대응해야 한다.

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

산출물의 수와 형식은 작업 목적에 맞게 정한다. 기존 CBT 빌더의 표준 입력은 문제지,
정답지와 `manifest.json`이며 출력은 `index.html`이다.

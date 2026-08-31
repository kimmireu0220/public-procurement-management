# 공공조달관리사 학습 저장소

공공조달관리사 필기 1~3과목과 실기 4과목의 공식 자료 기반 강의와 문제은행을 관리한다.

## 바로가기

- [학습센터](https://kimmireu0220.github.io/public-procurement-management/)
- [이론 강의](https://kimmireu0220.github.io/public-procurement-management/lecture/)
- [과목별 문제은행](https://kimmireu0220.github.io/public-procurement-management/study/)

## 구조

| 경로 | 내용 |
|---|---|
| `docs/시험_안내.md` | 공식 시험 일정·형식·합격 기준 |
| `docs/lecture/` | 생성된 공개 강의 |
| `docs/{1,2,3,4}과목/`, `docs/오답/` | 전체·누적 오답 CBT |
| `docs/study/` | 과목별 문제은행 원본 페이지와 안내 |
| `docs/학습_숫자암기/` | 금액·기한·비율 확인 자료 |
| `output/standard_textbook/` | 조달청 표준교재 정리 |
| `output/chapter_lectures/` | 강의 Markdown 원본 |
| `output/problem_book_final/`, `output/agent_extract/` | 4과목 문제·정답 원본 |
| `sources/` | 공식 근거와 문제 출처 자료 |

시험 내용은 조달청 표준교재를 주 기준으로 삼고, 현행 규정은 시행일과 근거를 표시해
시험 기준과 구별한다. Git이 추적하는 파일은 공개 자료로 취급하며 자세한 원칙은
`docs/자료_공개_및_저장_정책.md`에 둔다.

## 생성과 검증

개발 환경은 Python 3.12 이상을 지원하고 CI는 Python 3.13을 사용한다.

```bash
python3 -m pip install -r requirements-dev.txt
python3 tools/build_lecture_pages.py
python3 tools/build_cumulative_cbt.py
python3 tools/build_study_cbt.py
```

- 강의는 `output/chapter_lectures/`에서 `docs/lecture/`로 생성된다.
- 전체·오답 CBT는 기존 필기 문제은행 페이지와 4과목 문제·정답 원본을 결합해 생성된다.
- `docs/`의 생성 결과를 직접 수정했다면 다음 빌드에 사라지지 않도록 원본이나 빌더에도
  반영한다.

변경별 검사 명령은 각 빌더의 `--check`와 전체 단위 테스트를 사용한다. CI의 전체 기준은
`.github/workflows/deploy-pages.yml`에 있다.

```bash
python3 tools/build_study_cbt.py --check
python3 tools/build_cumulative_cbt.py --check
python3 tools/build_lecture_pages.py --check
python3 -m unittest discover -s tests -v
```

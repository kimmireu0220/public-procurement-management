# 공공조달관리사 Chapter 강의

채팅에서 진행한 강의를 과목·Part·Chapter 단위로 보존하는 원본 디렉터리다.

- 원본: `output/chapter_lectures/<과목>/partNN/chapterNN.md`
- 공개본: `docs/lecture/`
- 생성: `python3 tools/build_lecture_pages.py`
- 문제·퀴즈는 포함하지 않고 이론 강의만 둔다.
- 숫자·기한·비율은 `docs/학습_숫자암기/`와 대조한다.
- 과목 개요는 `overview.md`에 두고 `kind: overview`를 지정한다.
- 진행 중인 과목은 `catalog.json`의 상태를 `in_progress`로 두어 완료된 Chapter까지 순차 공개한다.

각 Chapter 문서는 `한눈에 보기 → 차근차근 설명 → 시험 포인트 → 암기 체크리스트` 순서를 따른다.

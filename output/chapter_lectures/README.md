# 공공조달관리사 Chapter 강의

채팅에서 진행한 강의를 과목·Part·Chapter 단위로 보존하는 원본 디렉터리다.

- 원본: `output/chapter_lectures/<과목>/partNN/chapterNN.md`
- 공개본: `docs/lecture/`
- 생성: `python3 tools/build_lecture_pages.py`
- 숫자·기한·비율처럼 오류 영향이 큰 내용은 `docs/학습_숫자암기/`와 원문을 대조한다.
- 고정된 강의 목차나 분량은 없다. 설명, 사례, 질문, 퀴즈와 문제풀이를 자유롭게 섞는다.
- 과목 개요가 필요하면 `overview.md`에 `kind: overview`, 총정리가 필요하면
  `total-review.md`에 `kind: review`를 지정할 수 있다. 둘 다 선택 사항이다.
- `catalog.json`의 `published`와 `in_progress`는 공개 화면에 표시할 상태를 정한다.

빌더를 사용할 Chapter 문서에는 URL과 내비게이션을 위한 front matter가 필요하다. 그 밖의
본문 구조와 공개 순서는 작업 목적에 맞게 정한다.

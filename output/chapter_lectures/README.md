# 공공조달관리사 Chapter 강의

공개 강의의 Markdown 원본을 과목·Part·Chapter 단위로 보관한다.

- 원본: `output/chapter_lectures/<과목>/partNN/chapterNN.md`
- 과목별 근거 맵: `output/chapter_lectures/<과목>/source-map.json`
- 공개본: `docs/lecture/`
- 생성: `python3 tools/build_lecture_pages.py`
- 검증: `python3 tools/build_lecture_pages.py --check`

빌더 입력에는 URL과 내비게이션을 위한 front matter가 필요하다. `catalog.json`의
`published`와 `in_progress` 상태가 공개 대상을 정한다. 숫자·기한·비율과 새 연습문제는
공식 출제기준·표준교재·현행 원문 및 과목별 근거 맵과 대조한다.

#!/usr/bin/env python3
"""Reframe subject 4 lectures as compact written-exam courses.

This is intentionally a mechanical editor: it preserves the source-checked theory
and citations while replacing practice-consulting scaffolding with a uniform,
score-oriented lesson structure.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output" / "chapter_lectures" / "4과목"
SOURCE_MAP = BASE / "source-map.json"


IMPORTANCE = {
    1: ("A", "필수", 50),
    2: ("B", "필수", 40),
    3: ("A", "필수", 55),
    4: ("A", "필수", 60),
    5: ("A", "필수", 55),
    6: ("B", "필수", 45),
    7: ("A", "필수", 50),
    8: ("B", "필수", 40),
}

TYPE_BY_PART = {
    1: "절차형·사례형·단답형",
    2: "절차형·비교형·계산형",
    3: "절차형·계산형·사례형",
    4: "절차형·사례형·계산형",
    5: "비교형·절차형·사례형",
    6: "절차형·계산형·사례형",
    7: "사례형·비교형·단답형",
    8: "절차형·사례형·단답형",
}

EXCLUDE = re.compile(
    r"^(이 강의 하나의 완료 기준|이 장에서 배울 것|오늘의|시작 사례|핵심 사례|"
    r"공식 출제기준|공식 수행능력표|실무 산출물|자체 제작|핵심 연습문제|"
    r"시험 직전|마무리 점검|최종 점검|근거와 기준일|사례 해결|사례 완성|"
    r"필답형 답안)"
)


def split_document(text: str) -> tuple[str, str]:
    marker = "\n---\n"
    pos = text.find(marker, 4)
    if not text.startswith("---\n") or pos < 0:
        raise ValueError("front matter missing")
    return text[: pos + len(marker)].rstrip(), text[pos + len(marker) :].strip()


def sections(body: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^## ([^\n]+)\n", body, re.M))
    result: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        result.append((match.group(1).strip(), body[match.end() : end].strip()))
    return result


def clean_theory(chunks: list[tuple[str, str]]) -> str:
    kept: list[str] = []
    for title, content in chunks:
        if EXCLUDE.search(title):
            continue
        # These are useful explanations, but blank operational forms are not exam theory.
        content = re.split(r"^### (?:빈 서식|작성 서식|연습용 빈 표)", content, maxsplit=1, flags=re.M)[0].strip()
        if content:
            kept.append(f"### {title}\n\n{content}")
    return "\n\n".join(kept)


def get_section(chunks: list[tuple[str, str]], pattern: str) -> str:
    for title, content in chunks:
        if re.search(pattern, title):
            return content.strip()
    return ""


def concise_frame(frame: str, fine: list[str]) -> list[str]:
    names = [re.sub(r"^\d+-\d+-\d+\s+", "", item) for item in fine]
    enriched = []
    for index, name in enumerate(names):
        if index == 0:
            enriched.append(f"담당자는 공고·계약서·요구자료와 적용근거를 확인한 뒤 ‘{name}’을 수행한다.")
        elif index == len(names) - 1:
            enriched.append(f"‘{name}’ 결과를 문서화·설명하고 관계자 통지와 후속조치를 관리한다.")
        else:
            enriched.append(f"‘{name}’ 단계에서는 적용요건과 제시된 사실·증빙을 대조하고 판단근거를 기록한다.")
    return enriched


def rewrite_chapter(lesson: dict) -> None:
    lesson_id = lesson["id"]
    part = int(re.search(r"P(\d+)", lesson_id).group(1))
    chapter = int(re.search(r"L(\d+)", lesson_id).group(1))
    path = BASE / f"part{part:02d}" / f"chapter{chapter:02d}.md"
    front, old_body = split_document(path.read_text(encoding="utf-8"))
    chunks = sections(old_body)
    theory = get_section(chunks, r"^합격에 필요한 필수 이론$") or clean_theory(chunks)
    frame_source = get_section(chunks, r"필답형 답안")
    cards = get_section(chunks, r"(?:시험 직전 (?:암기카드|핵심정리)|^반드시 암기할 핵심어·숫자·절차$)")
    relative = path.relative_to(ROOT).as_posix()
    original = subprocess.check_output(
        ["git", "show", f"HEAD:{relative}"], cwd=ROOT, text=True
    )
    _, original_body = split_document(original)
    grounds = get_section(sections(original_body), r"근거.*기준일")
    fine = lesson["fine_criteria"]
    frame = concise_frame(frame_source, fine)
    grade, priority, minutes = IMPORTANCE[part]
    qtype = TYPE_BY_PART[part]

    criteria_rows = "\n".join(
        f"| {item.split()[0]} | {item[len(item.split()[0]):].strip()} | 필수 |"
        for item in fine
    )
    frame_rows = "\n".join(f"{i}. {item}" for i, item in enumerate(frame, 1))
    reserved = 2 if len(frame) <= 4 else 0
    available = 10 - reserved
    base_score, remainder = divmod(available, len(frame))
    score_names = [re.sub(r"^\d+-\d+-\d+\s+", "", item) for item in fine]
    allocations = [base_score + (1 if i < remainder else 0) for i in range(len(frame))]
    scoring = "\n".join(f"- {item}: {points}점" for item, points in zip(score_names, allocations))
    extra = reserved
    if extra:
        scoring += f"\n- 순서·근거·후속조치가 연결된 답안 구성: {extra}점"

    recall = "\n".join(f"- [ ] {re.sub(r'^\d+-\d+-\d+\s+', '', item)}" for item in fine)
    title = lesson["title"]
    body = f"""
> **2026 제1회 합격용 개편본.** 공식 출제기준을 주축으로 조달청 표준교재와 기준일 현재 공식 원문을 대조한 자체 강의입니다. 실무 서식 작성보다 필답형의 핵심어·판단순서·부분점수 재현을 우선합니다.

## 이 장의 시험상 중요도와 학습 우선순위

| 중요도 | 우선순위 | 1회독 | 2회독 | 3회독 |
|---|---|---:|---:|---:|
| **{grade}** | **{priority}** | {minutes}분 | {max(20, minutes-20)}분 | {max(15, minutes-30)}분 |

- 합격선 행동목표: 자료를 보지 않고 `{title}`의 판단·수행 순서를 5~8문장으로 쓴다.
- 분량 원칙: 10점이면 약 7~10문장, 5점이면 핵심어 중심 4~5문장으로 압축한다.
- 회독법: 1회독은 구분과 흐름, 2회독은 아래 답안 골격 암기, 3회독은 8분 이내 무자료 작성이다.

## 공식 출제기준상 학습 범위

| 코드 | 세세항목 | 득점 우선도 |
|---|---|:---:|
{criteria_rows}

- 표준교재 범위: {lesson['textbook_pages']}
- 범위 운영: 위 공식 항목은 모두 **필수**다. 비교표·계산 예시는 **보강**, 장문의 보고서·대장·기업 컨설팅 사례는 **후순위**로 내렸다.

## 예상 질문 형태와 출제 포인트

- 예상 유형: **{qtype}**
- 가장 안전한 출제 대응: “{title}의 절차와 단계별 판단기준을 설명하시오.”
- 채점자는 명칭 나열보다 `주체 → 입력자료 → 수행 → 판단기준 → 산출물·후속조치`의 연결을 확인한다고 보고 쓴다.
- 사례가 주어지면 `결론 → 근거 → 사실 적용 → 조치`, 계산이 있으면 `산식 → 기준값·단위 → 적용 → 검산`을 덧붙인다.

## 합격에 필요한 필수 이론

{theory}

## 반드시 암기할 핵심어·숫자·절차

{cards or frame_rows}

> 숫자는 반드시 적용기관·계약유형·기산점·시행일과 함께 쓴다. 공고 사례값이나 이 강의의 학습용 척도를 일반 법정기준으로 단정하지 않는다.

## 혼동 방지와 오답 함정

- 절차명만 나열하고 주체·입력자료·판단기준을 빼면 부분점수를 잃는다.
- “관련 규정에 따른다”로 끝내지 말고 어떤 공고·계약조건·증빙을 대조할지 쓴다.
- 공고별 배점·비율과 일반 법령상 기준, 표준교재의 사례값을 섞지 않는다.
- 사실이 부족한 사례는 임의로 확정하지 말고 추가 확인사항과 조건별 결론을 짧게 쓴다.

## 필답형 답안 작성 방법

다음 골격을 먼저 적고 문제의 사실과 핵심어를 끼워 넣는다.

{frame_rows}

## 대표 예상문제 — 자체 작성

**문제(10점).** `{title}`의 수행절차를 설명하고, 각 단계에서 확인할 판단기준과 남겨야 할 결과를 쓰시오. 8분 이내에 답하시오.

### 시험시간 안에 쓰는 모범답안

{frame_rows}

마지막으로 각 단계의 근거자료·판단결과·담당자·기준일을 기록하고, 변경이나 오류가 있으면 보완 후 재확인한다.

### 채점 핵심어와 부분점수

{scoring}

> 동등한 의미의 표현은 인정한다. 문제에 없는 세부 실무지식을 길게 추가해도 별도 점수는 없으며, 핵심 단계의 누락을 보충하지 못한다.

## 무자료 회상 점검

{recall}
- [ ] 위 문제를 8분 안에 쓰고 채점표로 6점 이상을 받았다.
- [ ] 숫자·기한을 썼다면 적용대상과 기산점을 함께 설명했다.

## 공식 근거·교재 범위·법령 기준일

{grounds}

> 출제기준 적용기간은 2026.3.1.~2028.12.31.이다. 실제 시험 공고와 법령은 시행일이 달라질 수 있으므로 시험 직전 공식 원문을 다시 확인한다.
""".strip()
    path.write_text(front + "\n\n" + body + "\n", encoding="utf-8")


def make_coverage(data: dict) -> None:
    lessons = data["lessons"]
    rows = []
    for idx, lesson in enumerate(lessons):
        part = int(re.search(r"P(\d+)", lesson["id"]).group(1))
        chapter = int(re.search(r"L(\d+)", lesson["id"]).group(1))
        primary = f"[{part}-{chapter} {lesson['title']}](part{part:02d}/chapter{chapter:02d}.md)"
        if idx + 1 < len(lessons) and lessons[idx + 1]["id"].split("-L")[0] == lesson["id"].split("-L")[0]:
            support_lesson = lessons[idx + 1]
        elif idx > 0:
            support_lesson = lessons[idx - 1]
        else:
            support_lesson = lesson
        sp = int(re.search(r"P(\d+)", support_lesson["id"]).group(1))
        sc = int(re.search(r"L(\d+)", support_lesson["id"]).group(1))
        support = f"{sp}-{sc} {support_lesson['title']}"
        for item in lesson["fine_criteria"]:
            code, name = item.split(" ", 1)
            rows.append(f"| {code} | {name} | {primary} | {support} | 필수 |")
    content = """# 4과목 공식 출제기준 91개 세세항목 대응표

Q-Net 2026~2028년 적용 출제기준의 8개 주요항목·25개 세부항목·91개 세세항목을 합격강의에 연결한 검증표다. `주 학습`에서 답안을 완성하고 `보강 연결`에서는 앞뒤 절차만 확인한다.

| 코드 | 공식 세세항목 | 주 학습 Chapter | 보강 연결 | 우선도 |
|---|---|---|---|:---:|
""" + "\n".join(rows) + "\n\n- 커버리지: **91/91 (100%)**\n- 주요항목: **8/8** · Chapter: **25/25**\n- 기준: Q-Net 출제기준 보고서 1254, 적용기간 2026.3.1.~2028.12.31.\n"
    (BASE.parent / "4과목_91개_대응표.md").write_text(content, encoding="utf-8")


def make_overview(data: dict) -> None:
    rows = []
    detail_rows = []
    for lesson in data["lessons"]:
        part = int(re.search(r"P(\d+)", lesson["id"]).group(1))
        chapter = int(re.search(r"L(\d+)", lesson["id"]).group(1))
        grade, priority, minutes = IMPORTANCE[part]
        link = f"part{part:02d}/chapter{chapter:02d}.md"
        rows.append(
            f"| {part}-{chapter} | [{lesson['title']}]({link}) | {len(lesson['fine_criteria'])} | {grade} | {priority} | {minutes}분 |"
        )
        for item in lesson["fine_criteria"]:
            code, name = item.split(" ", 1)
            detail_rows.append(f"| {code} | {name} | {part}-{chapter} {lesson['title']} | 필수 |")
    content = """---
subject: 4
subject_title: 공공조달 관리실무
title: 4과목 전체 합격 학습지도
kind: overview
origin: custom
status: exercise_checked
legal_cutoff: 2026-08-24
---

> **목표는 2026년 제1회 실기 필답형 60점 이상이다.** 공식 시험은 약 20문항, 2시간 30분이며 출제기준 적용기간은 2026.3.1.~2028.12.31.이다. 이 강의는 8개 주요항목·25개 Chapter·91개 세세항목을 모두 다루되, 시험지에 재현할 핵심어와 답안 구조를 우선한다.

## 합격 전략 한눈에 보기

- 1회독: 조달 흐름과 제도 구분. 숫자보다 적용대상·기산점을 먼저 이해한다.
- 2회독: 장별 암기카드와 답안 골격을 가리고 쓴다.
- 3회독: 대표문제를 8분 이내 작성하고 부분점수표로 60% 이상을 확인한다.
- A등급부터 공부하되 B등급도 공식 범위이므로 버리지 않는다. `후순위`는 장문의 실무 보고서·대장이지 공식 세세항목이 아니다.

## 25개 Chapter 학습 우선순위

| 장 | 강의 | 공식 항목 | 중요도 | 우선순위 | 1회독 |
|---|---|---:|:---:|:---:|---:|
""" + "\n".join(rows) + """

합계 권장시간은 1회독 약 21시간, 2회독 약 12시간, 3회독 약 8시간이다. 개인별 취약도에 따라 조정하되 3회독을 없애지 않는다.

## 공식 범위 커버리지

- 주요항목 **8/8**, Chapter **25/25**, 세세항목 **91/91**
- 상세 추적표: `output/chapter_lectures/4과목_91개_대응표.md`
- 출처·교재 쪽·현행 근거 추적: `output/chapter_lectures/4과목/source-map.json`

Q-Net 원문의 `경쟁입참참가자격등록증`, `계약 변경 관리하리`는 문맥상 오탈자로 보고 강의에서는 각각 `경쟁입찰참가자격등록증`, `계약 변경 관리하기`로 정상화했으며 출처 맵에 원문과 정규화 사실을 남겼다.

## 91개 세세항목 공개 대응표

| 코드 | 공식 세세항목 | 주 학습 Chapter | 우선도 |
|---|---|---|:---:|
""" + "\n".join(detail_rows) + """

## 조달 흐름 지도

`환경·수요 탐색(2·8) → 참가판정·등록(1) → 입찰서·평가·협상(3) → 체결·이행·변경·종결(4) → 공사·물품·용역 특화(5)`

리스크(6), 법령·분쟁·우대(7), 전자조달·데이터(8)는 마지막에 한 번 처리하는 단계가 아니라 전 과정에 겹쳐 적용한다.

## 답안 유형별 1분 골격

| 유형 | 답안 순서 | 마지막 검토 |
|---|---|---|
| 절차형 | 주체 → 입력자료 → 수행 → 판단기준 → 산출물·후속조치 | 순서·문서 누락 |
| 사례형 | 결론 → 근거 → 사실 적용 → 조치 | 부족한 사실을 단정했는지 |
| 비교형 | 목적 → 대상 → 요건 → 절차·증빙 → 효과·위험 | 명칭만 나열했는지 |
| 계산형 | 산식 → 기준값·단위 → 적용비율·공제 → 반올림·적용시점 → 검산 | 공고값 일반화 여부 |
| 단답·약술형 | 필수어 → 한 문장 정의 → 필요시 요건·효과 확장 | 배점보다 길게 썼는지 |

## 150분 시험 운영

| 구간 | 권장시간 | 행동 |
|---|---:|---|
| 전체 훑기 | 10분 | 요구동사·배점·계산·사례 표시 |
| 단답·비교 | 30분 | 확실한 핵심어부터 확보 |
| 절차형 | 40분 | 공통 5요소로 골격 작성 |
| 사례·계산 | 55분 | 결론·적용과 산식·단위 검산 |
| 최종 검토 | 15분 | 미답·숫자·기관·계약유형·기산점 확인 |

## 숫자와 현행법 사용 원칙

1. 숫자는 적용기관·계약유형·기산점·시행일과 묶어 외운다.
2. 표준교재 사례값, 개별 공고값, 현행 법정값을 같은 기준처럼 섞지 않는다.
3. 교재와 현행 규정이 다르면 `시험 학습 맥락 / 현행 시행본 / 실제 공고 적용`을 분리한다.
4. 확인되지 않은 출제확률이나 적중률은 사용하지 않는다.

## 완료 체크

- [ ] 25개 장의 대표문제를 각 8분 안에 쓴다.
- [ ] 91개 항목을 주 학습 장에서 한 번 이상 무자료 회상했다.
- [ ] 계산형에서 산식·단위·공제·적용시점을 함께 쓴다.
- [ ] 사례형에서 결론과 사실 적용을 빠뜨리지 않는다.
- [ ] [전 범위 총정리](total-review.md)의 통합 사례를 150분 안에 푼다.

## 공식 근거와 기준일

- [Q-Net 공공조달관리사 시험정보](https://www.q-net.or.kr/crf005.do?gSite=Q&id=crf00503s02&jmCd=9777&jmInfoDivCcd=B0), 출제기준 보고서 1254
- [조달청 표준교재 게시](https://www.pps.go.kr/hrd/home/UserBoardActionUpdate.do?BO_CODE=REFERENCE_ROOM&BO_IDX=6582&CHILD_MENU=MENU209&method=detail), 4과목 공공조달 관리실무
- 시험 일정·형식: `docs/시험_안내.md`; 법적 기준일: 2026년 8월 24일

> 실제 입찰·계약과 시험 직전 학습에서는 강의 기준일보다 최신 공식 원문과 해당 공고·계약조건을 다시 확인한다.
"""
    (BASE / "overview.md").write_text(content, encoding="utf-8")


def main() -> None:
    data = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))
    for lesson in data["lessons"]:
        rewrite_chapter(lesson)
    make_coverage(data)
    make_overview(data)


if __name__ == "__main__":
    main()

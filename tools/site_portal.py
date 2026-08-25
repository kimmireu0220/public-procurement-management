"""GitHub Pages 통합 학습 홈을 생성한다."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from build_lecture_pages import load_lectures
from cbt.profiles import FULL_MOCK

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

@dataclass(frozen=True)
class LectureLink:
    subject: int
    subject_title: str
    part: int
    part_title: str
    chapter: int
    title: str
    is_review: bool
    is_overview: bool
    url: str


def lecture_links() -> list[LectureLink]:
    return [
        LectureLink(
            subject=item.subject,
            subject_title=item.subject_title,
            part=item.part,
            part_title=item.part_title,
            chapter=item.chapter,
            title=item.title,
            is_review=item.is_review,
            is_overview=item.is_overview,
            url=f"lecture/{item.relative_url}",
        )
        for item in load_lectures()
    ]


def published_rounds() -> list[int]:
    meta_path = DOCS / "cbt-meta.json"
    if not meta_path.is_file():
        return []
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rounds = meta.get("rounds", [])
    return sorted(int(item["round"]) for item in rounds if isinstance(item, dict) and "round" in item)


def _round_cards(rounds: list[int]) -> str:
    latest = max(rounds)
    minutes = FULL_MOCK.duration_sec // 60
    return "".join(
        f'<a class="choice-card featured" href="mock/{round_no}회차/">'
        f'<span class="card-kicker">통합 모의고사</span><strong>{round_no}회차</strong>'
        f'<span>{FULL_MOCK.question_count}문항 · {minutes}분</span>'
        f'{"<em>최신</em>" if round_no == latest else ""}</a>'
        for round_no in rounds
    )


def _subject_cbt_cards() -> str:
    subjects = (
        (1, "공공조달과 법제도 이해", 670, "필기 CBT", "즉시 채점"),
        (2, "공공조달계획 수립 및 분석", 335, "필기 CBT", "즉시 채점"),
        (3, "공공계약관리", 390, "필기 CBT", "즉시 채점"),
        (4, "공공조달 관리실무", 1244, "서술형 CBT", "자가판정"),
    )
    return "".join(
        f'<a class="choice-card featured" href="{subject}과목/">'
        f'<span class="card-kicker">{kind}</span><strong>{subject}과목</strong>'
        f'<span class="card-description">{html.escape(title)}</span>'
        f'<span class="card-meta">{count:,}문항 · {grading}</span></a>'
        for subject, title, count, kind, grading in subjects
    )


def _wrong_cbt_cards() -> str:
    subjects = (
        (1, "공공조달과 법제도 이해"),
        (2, "공공조달계획 수립 및 분석"),
        (3, "공공계약관리"),
        (4, "공공조달 관리실무"),
    )
    return "".join(
        f'<a class="choice-card wrong-card" href="오답/{subject}과목/" data-wrong-subject="{subject}">'
        f'<span class="card-kicker">누적 오답 CBT</span><strong>{subject}과목 오답</strong>'
        f'<span class="card-description">{html.escape(title)}</span>'
        f'<span class="card-meta"><b class="wrong-count" aria-live="polite">0</b>문항 저장됨</span></a>'
        for subject, title in subjects
    )


def _lecture_groups(links: list[LectureLink]) -> str:
    by_subject: dict[int, list[LectureLink]] = defaultdict(list)
    for link in links:
        by_subject[link.subject].append(link)

    subject_groups: list[str] = []
    for subject, items in sorted(by_subject.items()):
        chapters = [item for item in items if not item.is_review and not item.is_overview]
        review = next((item for item in items if item.is_review), None)
        overview = next((item for item in items if item.is_overview), None)
        by_part: dict[int, list[LectureLink]] = defaultdict(list)
        for item in chapters:
            by_part[item.part].append(item)

        part_groups: list[str] = []
        if overview:
            part_groups.append(
                f'<a class="review-link overview-link" href="{html.escape(overview.url)}">'
                f'<span>전체 학습 지도</span><strong>{subject}과목 개요 →</strong></a>'
            )
        for part, part_items in sorted(by_part.items()):
            chapter_links = "".join(
                f'<a href="{html.escape(item.url)}"><span>Chapter {item.chapter}</span>'
                f'<strong>{html.escape(item.title)}</strong></a>'
                for item in part_items
            )
            part_groups.append(
                f'<div class="lecture-part"><h3>Part {part} · {html.escape(part_items[0].part_title)}</h3>'
                f'<div class="chapter-grid">{chapter_links}</div></div>'
            )
        if review:
            part_groups.append(
                f'<a class="review-link" href="{html.escape(review.url)}">'
                f'<span>최종 복습</span><strong>{subject}과목 총정리 →</strong></a>'
            )
        subject_groups.append(
            f'<details class="subject-group lecture-group"><summary>'
            f'<span class="subject-summary-title"><b>{subject}과목</b> · {html.escape(items[0].subject_title)}</span>'
            f'<small>{len(chapters)}개 Chapter</small></summary><div class="lecture-body">'
            f'{"".join(part_groups)}</div></details>'
        )
    return "".join(subject_groups)


PORTAL_STYLE = """
:root {
  --navy: #123b66;
  --navy-deep: #0b2b4b;
  --blue: #1769aa;
  --blue-strong: #0f5b98;
  --sky: #eaf4fc;
  --bg: #f4f7fb;
  --paper: #fff;
  --line: #d5e0eb;
  --text: #172535;
  --muted: #5d6e81;
  --wrong: #a63d36;
  --accent: #f3a712;
  --focus: #ffbf47;
  --shadow: 0 8px 28px rgba(16, 47, 80, .08);
  --gutter: clamp(1rem, 3vw, 2.5rem);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 1rem; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", sans-serif;
  font-size: 16px;
  line-height: 1.65;
  word-break: keep-all;
  overflow-wrap: break-word;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
.skip-link {
  position: fixed;
  top: .75rem;
  left: .75rem;
  z-index: 100;
  padding: .7rem 1rem;
  border-radius: .65rem;
  background: #fff;
  color: var(--navy-deep);
  font-weight: 800;
  text-decoration: none;
  transform: translateY(-160%);
  box-shadow: var(--shadow);
}
.skip-link:focus { transform: translateY(0); }
:where(a, summary):focus-visible {
  outline: 3px solid var(--focus);
  outline-offset: 3px;
}
.hero {
  position: relative;
  overflow: hidden;
  padding: clamp(2.75rem, 6vw, 4.25rem) var(--gutter) clamp(2.4rem, 5vw, 3.5rem);
  background: linear-gradient(128deg, var(--navy-deep) 0%, var(--navy) 48%, #1f70b2 100%);
  color: #fff;
}
.hero::after {
  content: "";
  position: absolute;
  right: -8rem;
  bottom: -14rem;
  width: 31rem;
  height: 31rem;
  border: 1px solid rgba(255, 255, 255, .14);
  border-radius: 50%;
  box-shadow: 0 0 0 5rem rgba(255, 255, 255, .035), 0 0 0 10rem rgba(255, 255, 255, .025);
  pointer-events: none;
}
.hero-inner, .page { width: min(100%, 1280px); margin: 0 auto; }
.hero-inner { position: relative; z-index: 1; }
.eyebrow {
  display: block;
  margin-bottom: .55rem;
  color: #c9e3fb;
  font-size: .78rem;
  font-weight: 850;
  letter-spacing: .13em;
}
h1 { margin: 0; font-size: clamp(2.15rem, 5vw, 3.35rem); line-height: 1.15; letter-spacing: -.035em; }
.hero p { max-width: 720px; margin: .9rem 0 0; color: #e5f1fb; font-size: clamp(1rem, 2vw, 1.12rem); }
.quick-nav { display: flex; flex-wrap: wrap; gap: .6rem; margin-top: 1.55rem; }
.quick-nav a {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  padding: .58rem .95rem;
  border: 1px solid rgba(255, 255, 255, .4);
  border-radius: 999px;
  color: #fff;
  font-size: .92rem;
  font-weight: 750;
  text-decoration: none;
  transition: background-color .16s ease, color .16s ease, transform .16s ease;
}
.quick-nav a:hover { background: #fff; color: var(--navy-deep); transform: translateY(-1px); }
.page { padding: 1rem var(--gutter) 4.5rem; }
.section { scroll-margin-top: 1rem; padding: clamp(2.25rem, 5vw, 3.5rem) 0; border-bottom: 1px solid var(--line); }
.section:last-child { border-bottom: 0; }
.section-head { display: flex; justify-content: space-between; align-items: end; gap: 1rem; margin-bottom: 1.25rem; }
.section h2 { margin: 0; color: var(--navy-deep); font-size: clamp(1.45rem, 2.5vw, 1.85rem); line-height: 1.3; letter-spacing: -.025em; }
.section-head p { margin: .15rem 0 0; color: var(--muted); font-size: .95rem; }
.choice-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
.four-card-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.choice-card {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 154px;
  flex-direction: column;
  padding: 1.2rem 1.2rem 1.1rem;
  border: 1px solid var(--line);
  border-top: 4px solid var(--blue);
  border-radius: 15px;
  background: var(--paper);
  text-decoration: none;
  box-shadow: 0 5px 18px rgba(16, 47, 80, .055);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}
.choice-card::after {
  content: "→";
  position: absolute;
  right: 1.1rem;
  bottom: .9rem;
  color: var(--blue);
  font-size: 1.05rem;
  font-weight: 900;
}
.choice-card:hover, .choice-card:focus-visible {
  transform: translateY(-3px);
  border-color: #83add0;
  box-shadow: var(--shadow);
}
.choice-card.wrong-card { border-top-color: var(--wrong); }
.choice-card.wrong-card::after { color: var(--wrong); }
.card-kicker { color: var(--muted); font-size: .78rem; font-weight: 800; letter-spacing: .02em; }
.choice-card strong { margin: .35rem 0 .18rem; color: var(--navy-deep); font-size: 1.38rem; line-height: 1.3; }
.card-description { color: var(--muted); font-size: .9rem; line-height: 1.45; }
.card-meta { margin-top: auto; padding-top: .55rem; padding-right: 1.35rem; color: #405367; font-size: .82rem; font-weight: 750; }
.choice-card em { position: absolute; right: .9rem; top: .8rem; padding: .18rem .5rem; border-radius: 999px; background: #fff2ca; color: #765000; font-size: .72rem; font-style: normal; font-weight: 850; }
.wrong-count { color: var(--wrong); font-variant-numeric: tabular-nums; }
.subject-group { margin: .8rem 0; border: 1px solid var(--line); border-radius: 15px; background: var(--paper); overflow: clip; box-shadow: 0 3px 12px rgba(16, 47, 80, .035); }
.subject-group summary {
  display: flex;
  min-height: 58px;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.2rem;
  color: var(--navy-deep);
  cursor: pointer;
  list-style: none;
  font-size: 1rem;
}
.subject-group summary::-webkit-details-marker { display: none; }
.subject-group summary::after { content: "+"; flex: none; width: 1.7rem; color: var(--blue); font-size: 1.35rem; font-weight: 500; text-align: center; }
.subject-group[open] summary::after { content: "−"; }
.subject-group summary:hover { background: #f7fbfe; }
.subject-group summary > span { flex: 1; }
.subject-group summary small { color: var(--muted); white-space: nowrap; }
.lecture-body { padding: 0 1.2rem 1.2rem; }
.lecture-part { padding: 1rem 0; border-top: 1px solid var(--line); }
.lecture-part h3 { margin: 0 0 .65rem; color: var(--navy-deep); font-size: 1.02rem; }
.chapter-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .6rem; }
.chapter-grid a {
  display: flex;
  min-height: 68px;
  flex-direction: column;
  justify-content: center;
  padding: .75rem .85rem;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #f5f8fb;
  text-decoration: none;
}
.chapter-grid a:hover { border-color: #b9d3e9; background: var(--sky); }
.chapter-grid span { color: var(--blue-strong); font-size: .76rem; font-weight: 850; }
.chapter-grid strong { color: var(--text); font-size: .91rem; line-height: 1.45; }
.review-link { display: flex; justify-content: space-between; gap: 1rem; margin-top: .8rem; padding: .95rem 1.05rem; border-radius: 10px; background: #fff6dc; color: #684700; text-decoration: none; }
.review-link.overview-link { margin: 0 0 .8rem; background: var(--sky); color: var(--navy-deep); }
.review-link span { font-size: .84rem; font-weight: 750; }
.footer { padding: 1.6rem var(--gutter) 2.25rem; color: var(--muted); font-size: .84rem; text-align: center; }
@media (max-width: 1099px) {
  .four-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chapter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 639px) {
  body { line-height: 1.6; }
  .hero { padding-top: 2.5rem; }
  h1 { font-size: clamp(2rem, 11vw, 2.55rem); }
  .quick-nav { gap: .45rem; }
  .quick-nav a { flex: 1 1 calc(50% - .45rem); justify-content: center; padding-inline: .7rem; }
  .page { padding-inline: 1rem; }
  .section-head { display: block; }
  .section-head p { margin-top: .4rem; }
  .choice-grid, .four-card-grid, .chapter-grid { grid-template-columns: 1fr; }
  .choice-card { min-height: 132px; }
  .subject-group summary { align-items: flex-start; padding: .95rem 1rem; }
  .subject-group summary small { font-size: .8rem; }
  .lecture-body { padding-inline: .9rem; }
  .review-link { align-items: flex-start; flex-direction: column; gap: .2rem; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
""".strip()


def render_portal(rounds: list[int], lectures: list[LectureLink] | None = None) -> str:
    lecture_items = lecture_links() if lectures is None else lectures
    mock_nav = '<a href="#full-mock">통합 모의고사</a>' if rounds else ""
    mock_section = (
        f'<section class="section" id="full-mock"><div class="section-head"><h2>통합 필기 모의고사</h2>'
        f'<p>실전과 같은 {FULL_MOCK.question_count}문항 · {FULL_MOCK.duration_sec // 60}분</p></div>'
        f'<div class="choice-grid">{_round_cards(rounds)}</div></section>'
        if rounds
        else ""
    )
    subject_cbt_section = (
        '<section class="section" id="subject-cbt"><div class="section-head">'
        '<h2>과목별 문제은행</h2><p>1·2·3과목 즉시 채점 CBT · 4과목 실기 답안 연습</p></div>'
        f'<div class="choice-grid four-card-grid">{_subject_cbt_cards()}</div></section>'
    )
    wrong_cbt_section = (
        '<section class="section" id="wrong-cbt"><div class="section-head">'
        '<div><h2>누적 오답 CBT</h2><p>틀린 문제만 모아 다시 풀고, 정답을 맞히면 자동 제거 · 현재 브라우저에 저장</p></div></div>'
        f'<div class="choice-grid four-card-grid">{_wrong_cbt_cards()}</div></section>'
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="공공조달관리사 모의고사와 공식 자료 기반 자체 강의를 한곳에서 학습하세요.">
<meta name="theme-color" content="#123b66">
<title>공공조달관리사 학습센터</title>
<style>{PORTAL_STYLE}</style>
</head>
<body>
<a class="skip-link" href="#main-content">본문으로 바로가기</a>
<header class="hero"><div class="hero-inner"><span class="eyebrow">PUBLIC PROCUREMENT MANAGER</span><h1>공공조달관리사 학습센터</h1><p>공식 자료 기반 자체 강의와 검증된 연습문제를 한곳에서 선택하세요.</p><nav class="quick-nav" aria-label="학습 메뉴"><a href="#subject-cbt">과목별 문제은행</a><a href="#wrong-cbt">누적 오답 CBT</a>{mock_nav}<a href="#lectures">이론 강의</a></nav></div></header>
<main class="page" id="main-content">
{subject_cbt_section}
{wrong_cbt_section}
{mock_section}
<section class="section" id="lectures"><div class="section-head"><h2>과목별 이론 강의</h2><p>출제기준 · 실무 판단 · 답안 훈련</p></div>{_lecture_groups(lecture_items)}</section>
</main>
<footer class="footer">공식 출제기준 · 조달청 표준교재 · 현행 규정 기반 자체 제작 학습자료</footer>
<script>
(function(){{
  function updateWrongCounts(){{
    document.querySelectorAll('[data-wrong-subject]').forEach(function(card){{
      var subject = card.dataset.wrongSubject;
      var count = 0;
      try {{ var items = JSON.parse(localStorage.getItem('ppm_cbt_wrong_subject_' + subject + '_v1') || '[]'); count = Array.isArray(items) ? items.length : 0; }} catch (error) {{}}
      card.querySelector('.wrong-count').textContent = count.toLocaleString('ko-KR');
    }});
  }}
  updateWrongCounts();
  window.addEventListener('pageshow', updateWrongCounts);
  window.addEventListener('storage', updateWrongCounts);
  document.addEventListener('visibilitychange', function(){{ if (!document.hidden) updateWrongCounts(); }});
}})();
</script>
</body>
</html>
"""


def write_portal(rounds: list[int] | None = None) -> Path:
    selected_rounds = published_rounds() if rounds is None else rounds
    destination = DOCS / "index.html"
    destination.write_text(render_portal(selected_rounds), encoding="utf-8")
    return destination

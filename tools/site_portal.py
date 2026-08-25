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
        (1, "공공조달과 법제도 이해", 670, "필기 CBT"),
        (2, "공공조달계획 수립 및 분석", 335, "필기 CBT"),
        (3, "공공계약관리", 390, "필기 CBT"),
        (4, "공공조달 관리실무", 1244, "서술형 자가판정 CBT"),
    )
    return "".join(
        f'<a class="choice-card featured" href="{subject}과목/">'
        f'<span class="card-kicker">{kind}</span><strong>{subject}과목</strong>'
        f'<span>{html.escape(title)} · 전체 {count:,}문항</span></a>'
        for subject, title, count, kind in subjects
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
        f'<span>{html.escape(title)} · <b class="wrong-count">0</b>문항</span></a>'
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
            f'<span><b>{subject}과목</b> · {html.escape(items[0].subject_title)}</span>'
            f'<small>{len(chapters)}개 Chapter</small></summary><div class="lecture-body">'
            f'{"".join(part_groups)}</div></details>'
        )
    return "".join(subject_groups)


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
        f'<div class="choice-grid">{_subject_cbt_cards()}</div></section>'
    )
    wrong_cbt_section = (
        '<section class="section" id="wrong-cbt"><div class="section-head">'
        '<div><h2>누적 오답 CBT</h2><p>틀린 문제만 모아 다시 풀고, 정답을 맞히면 자동 제거</p></div>'
        '<button type="button" class="reset-wrong" id="reset-wrong-all">오답 전체 초기화</button></div>'
        f'<div class="choice-grid">{_wrong_cbt_cards()}</div></section>'
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="공공조달관리사 모의고사와 공식 자료 기반 자체 강의를 한곳에서 학습하세요.">
<title>공공조달관리사 학습센터</title>
<style>
:root{{--navy:#102f50;--blue:#1763a6;--sky:#eaf3fb;--bg:#f5f7fa;--paper:#fff;--line:#dbe4ee;--text:#172331;--muted:#647386;--accent:#f3a712;--gutter:clamp(.75rem,3vw,3.5rem)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--text);font-family:"Apple SD Gothic Neo","Pretendard","Malgun Gothic","Segoe UI",sans-serif;line-height:1.6}}
a{{color:inherit}}.hero{{background:linear-gradient(135deg,#102f50,#1763a6);color:#fff;padding:3.4rem var(--gutter) 2.8rem}}.hero-inner,.page{{margin:0 auto}}
.eyebrow{{display:block;margin-bottom:.55rem;color:#bcdafa;font-size:.78rem;font-weight:800;letter-spacing:.12em}}h1{{margin:0;font-size:clamp(2rem,5vw,3rem);line-height:1.2}}.hero p{{max-width:680px;margin:.85rem 0 0;color:#e3effa;font-size:1.05rem}}
.quick-nav{{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1.5rem}}.quick-nav a{{padding:.55rem .85rem;border:1px solid rgba(255,255,255,.35);border-radius:999px;text-decoration:none;font-size:.9rem;font-weight:700}}.quick-nav a:hover{{background:#fff;color:var(--navy)}}
.page{{padding:1.2rem var(--gutter) 4rem}}.section{{padding:2.25rem 0;border-bottom:1px solid var(--line)}}.section:last-child{{border-bottom:0}}.section-head{{display:flex;justify-content:space-between;gap:1rem;align-items:end;margin-bottom:1.15rem}}.section h2{{margin:0;color:var(--navy);font-size:1.45rem}}.section-head p{{margin:0;color:var(--muted);font-size:.94rem}}
.choice-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.85rem}}.choice-card{{position:relative;display:flex;min-height:132px;flex-direction:column;padding:1.05rem;border:1px solid var(--line);border-radius:13px;background:var(--paper);text-decoration:none;box-shadow:0 4px 14px rgba(16,47,80,.05);transition:.15s ease}}.choice-card:hover,.choice-card:focus-visible{{transform:translateY(-2px);border-color:#8eb6d9;box-shadow:0 8px 20px rgba(16,47,80,.11);outline:none}}.choice-card.featured{{border-top:4px solid var(--blue)}}.choice-card.wrong-card{{border-top:4px solid #b7463e}}.card-kicker{{color:var(--muted);font-size:.78rem;font-weight:700}}.choice-card strong{{margin:.3rem 0 .12rem;color:var(--navy);font-size:1.3rem}}.choice-card>span:last-of-type{{color:var(--muted);font-size:.9rem}}.choice-card em{{position:absolute;right:.8rem;top:.75rem;padding:.18rem .48rem;border-radius:999px;background:#fff2ca;color:#805500;font-size:.72rem;font-style:normal;font-weight:800}}.wrong-count{{color:#a52a24}}.reset-wrong{{padding:.6rem .9rem;border:1px solid #dda7a3;border-radius:8px;background:#fff7f6;color:#a52a24;font-weight:700;cursor:pointer}}
.subject-group{{margin:.7rem 0;border:1px solid var(--line);border-radius:13px;background:var(--paper);overflow:hidden}}.subject-group summary{{display:flex;justify-content:space-between;gap:1rem;align-items:center;padding:1rem 1.1rem;cursor:pointer;color:var(--navy);list-style-position:inside}}.subject-group summary:hover{{background:#f8fbfe}}.subject-group summary small{{color:var(--muted);white-space:nowrap}}.mini-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:.65rem;padding:0 1rem 1rem}}.mini-card{{display:flex;justify-content:space-between;align-items:center;gap:.5rem;padding:.75rem .85rem;border-radius:9px;background:var(--sky);text-decoration:none}}.mini-card:hover{{background:#dbeeff}}.mini-card strong{{color:var(--navy)}}.mini-card span{{color:var(--muted);font-size:.82rem}}
.lecture-body{{padding:0 1rem 1rem}}.lecture-part{{padding:.85rem 0;border-top:1px solid var(--line)}}.lecture-part h3{{margin:0 0 .6rem;color:var(--navy);font-size:1rem}}.chapter-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.5rem}}.chapter-grid a{{display:flex;flex-direction:column;padding:.7rem .8rem;border-radius:8px;background:#f6f9fc;text-decoration:none}}.chapter-grid a:hover{{background:var(--sky)}}.chapter-grid span{{color:var(--blue);font-size:.76rem;font-weight:800}}.chapter-grid strong{{font-size:.9rem}}.review-link{{display:flex;justify-content:space-between;gap:1rem;margin-top:.8rem;padding:.9rem 1rem;border-radius:9px;background:#fff6dc;text-decoration:none;color:#684700}}.review-link.overview-link{{margin:0 0 .8rem;background:var(--sky);color:var(--navy)}}.review-link span{{font-size:.82rem;font-weight:700}}
.footer{{padding:1.4rem;text-align:center;color:var(--muted);font-size:.82rem}}@media(max-width:620px){{.hero{{padding-top:2.5rem}}.section-head{{display:block}}.section-head p{{margin-top:.35rem}}.choice-grid{{grid-template-columns:1fr 1fr}}.choice-card{{min-height:120px}}.subject-group summary{{align-items:flex-start}}.chapter-grid{{grid-template-columns:1fr}}}}@media(max-width:380px){{.choice-grid{{grid-template-columns:1fr}}}}@media(min-width:1024px){{.page{{padding:1.6rem var(--gutter) 5rem}}.hero{{padding:4rem var(--gutter) 3.2rem}}.hero p{{max-width:760px;font-size:1.12rem}}.quick-nav a{{padding:.6rem 1rem .55rem}}.section-head{{margin-bottom:1.35rem}}.section h2{{font-size:1.65rem}}.section-head p{{font-size:1rem}}.choice-grid{{grid-template-columns:repeat(auto-fill,minmax(clamp(210px,15vw,300px),1fr))}}.choice-card{{min-height:150px}}.choice-card strong{{font-size:1.4rem}}.choice-card span{{font-size:1rem}}.subject-group{{margin:.9rem 0}}.subject-group summary{{padding:1.15rem 1.2rem;font-size:1rem}}.subject-group summary small{{font-size:.9rem}}.mini-grid{{grid-template-columns:repeat(auto-fill,minmax(clamp(210px,14vw,260px),1fr));gap:.85rem;padding:0 1.2rem 1.2rem}}.lecture-body{{padding:0 1.2rem 1.2rem}}.chapter-grid{{grid-template-columns:repeat(auto-fill,minmax(clamp(210px,14vw,280px),1fr));gap:.65rem}}.chapter-grid strong{{font-size:.96rem}}.review-link{{padding:.95rem 1.2rem}}.review-link span{{font-size:.9rem}}}}
</style>
</head>
<body>
<header class="hero"><div class="hero-inner"><span class="eyebrow">PUBLIC PROCUREMENT MANAGER</span><h1>공공조달관리사 학습센터</h1><p>공식 자료 기반 자체 강의와 검증된 연습문제를 한곳에서 선택하세요.</p><nav class="quick-nav" aria-label="학습 메뉴"><a href="#subject-cbt">과목별 문제은행</a><a href="#wrong-cbt">누적 오답 CBT</a>{mock_nav}<a href="#lectures">이론 강의</a></nav></div></header>
<main class="page">
{subject_cbt_section}
{wrong_cbt_section}
{mock_section}
<section class="section" id="lectures"><div class="section-head"><h2>Chapter 이론 강의</h2><p>출제기준 · 실무 판단 · 답안 훈련</p></div>{_lecture_groups(lecture_items)}</section>
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
  document.getElementById('reset-wrong-all').addEventListener('click', function(){{
    if (!confirm('1·2·3·4과목의 누적 오답을 모두 삭제할까요?')) return;
    [1,2,3,4].forEach(function(subject){{ localStorage.removeItem('ppm_cbt_wrong_subject_' + subject + '_v1'); }});
    updateWrongCounts();
  }});
  updateWrongCounts();
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

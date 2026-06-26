#!/usr/bin/env python3
"""Build one-question-at-a-time HTML player from mock exam markdown."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
import sys

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import ROOT  # noqa: E402
from mock_exam_common import open_mock_exam_html  # noqa: E402

CHOICE_RE = re.compile(r"^\s*([①②③④⑤])\s*(.+)$")
SECTION_RE = re.compile(r"^##\s+(\d)과목")
QUESTION_START = re.compile(r"^(\d+)\.\s+(.+)")
ANSWER_LINE_RE = re.compile(r"^(\d+)\.\s*([①②③④⑤])(?:\s*—\s*(.+))?$")
SOURCE_RE = re.compile(r"<!--\s*source:\s*(.+?)\s*-->")


def parse_questions(md_path: Path) -> tuple[str, list[dict]]:
    text = md_path.read_text(encoding="utf-8")
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else md_path.parent.name

    questions: list[dict] = []
    current_subject = ""
    block_lines: list[str] = []
    block_num = 0

    def flush_block() -> None:
        nonlocal block_lines, block_num
        if not block_lines:
            return
        first = block_lines[0]
        qm = QUESTION_START.match(first)
        if not qm:
            block_lines = []
            return
        num = int(qm.group(1))
        stem_parts = [qm.group(2).strip()]
        choices: list[dict] = []
        source = ""
        for line in block_lines[1:]:
            sm = SOURCE_RE.search(line)
            if sm:
                source = sm.group(1).strip()
                continue
            cm = CHOICE_RE.match(line)
            if cm:
                choices.append({"label": cm.group(1), "text": cm.group(2).strip()})
            elif line.strip() and not line.strip().startswith("<!--"):
                stem_parts.append(line.strip())
        if len(choices) >= 4:
            questions.append(
                {
                    "num": num,
                    "subject": current_subject,
                    "stem": "\n".join(stem_parts),
                    "choices": choices[:4],
                    "source": source,
                }
            )
        block_lines = []

    for line in text.splitlines():
        sm = SECTION_RE.match(line.strip())
        if sm:
            flush_block()
            current_subject = sm.group(1)
            continue
        qm = QUESTION_START.match(line)
        if qm:
            flush_block()
            block_num = int(qm.group(1))
            block_lines = [line]
            continue
        if block_lines:
            block_lines.append(line)
    flush_block()
    questions.sort(key=lambda q: q["num"])
    return title, questions


def clean_explain(text: str) -> str:
    idx = text.rfind("(Part")
    if idx >= 0:
        return text[:idx].rstrip()
    return text.strip()


def parse_answers(ans_path: Path) -> dict[int, dict[str, str]]:
    answers: dict[int, dict[str, str]] = {}
    for line in ans_path.read_text(encoding="utf-8").splitlines():
        m = ANSWER_LINE_RE.match(line.strip())
        if not m:
            continue
        answers[int(m.group(1))] = {
            "answer": m.group(2),
            "explain": clean_explain(m.group(3) or ""),
        }
    return answers


def attach_answers(questions: list[dict], answer_map: dict[int, dict[str, str]]) -> None:
    for q in questions:
        info = answer_map.get(q["num"], {})
        q["answer"] = info.get("answer", "")
        q["explain"] = info.get("explain", "")


def build_html(title: str, questions: list[dict], round_dir: Path) -> str:
    data = json.dumps(questions, ensure_ascii=False)
    storage_key = f"mock_exam_{round_dir.name}"
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — 응시</title>
<style>
:root {{
  --bg: #f4f6f9;
  --card: #fff;
  --text: #1a1d21;
  --muted: #5c6570;
  --accent: #1f6feb;
  --accent-soft: #e8f1ff;
  --border: #d8dee6;
  --ok: #1a7f37;
  --ok-soft: #e6f4ea;
  --bad: #cf222e;
  --bad-soft: #ffebe9;
  --warn: #9a6700;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-size: 18px;
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}}
.wrap {{
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 20px 0 100px;
}}
header {{
  margin-bottom: 16px;
}}
h1 {{
  font-size: 1.35rem;
  margin: 0 0 8px;
}}
.meta {{
  color: var(--muted);
  font-size: 1rem;
}}
.progress-bar {{
  height: 8px;
  background: var(--border);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 12px;
}}
.progress-fill {{
  height: 100%;
  background: var(--accent);
  width: 0%;
  transition: width 0.2s;
}}
.card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}}
.q-num {{
  font-size: 0.95rem;
  color: var(--accent);
  font-weight: 700;
  margin-bottom: 8px;
}}
.stem {{
  font-size: 1.2rem;
  font-weight: 600;
  white-space: pre-wrap;
  margin-bottom: 18px;
}}
.choices {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}
.choice {{
  display: flex;
  gap: 10px;
  align-items: flex-start;
  width: 100%;
  text-align: left;
  padding: 14px 16px;
  border: 2px solid var(--border);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
}}
.choice:hover {{ border-color: #a8c4f0; background: #fafcff; }}
.choice.selected {{
  border-color: var(--accent);
  background: var(--accent-soft);
}}
.choice:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}}
.choice .label {{
  font-weight: 700;
  min-width: 1.6em;
}}
.choice .text {{ flex: 1; line-height: 1.45; }}
.toolbar {{
  position: fixed;
  left: 0; right: 0; bottom: 0;
  background: rgba(255,255,255,0.96);
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  justify-content: center;
}}
.toolbar-inner {{
  width: min(1120px, calc(100vw - 32px));
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}}
.toolbar-nav {{
  display: flex;
  gap: 10px;
}}
.btn {{
  padding: 13px 22px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: #fff;
  font: inherit;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}}
.btn:hover:not(:disabled) {{ background: #f6f8fa; border-color: #b8c4d0; }}
.btn:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}}
.btn:disabled {{ opacity: 0.45; cursor: not-allowed; }}
.btn-secondary {{
  background: #fff;
  color: var(--text);
  border-color: #c5ced8;
}}
.btn-secondary:hover:not(:disabled) {{
  background: #eef2f6;
  border-color: #9aa8b8;
}}
.btn-primary {{
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  min-width: 140px;
}}
.btn-primary:hover:not(:disabled) {{
  background: #1858a8;
  border-color: #1858a8;
}}
.btn-reset {{
  background: var(--bad);
  color: #fff;
  border-color: var(--bad);
}}
.btn-reset:hover:not(:disabled) {{
  background: #9a1c12;
  border-color: #9a1c12;
  color: #fff;
}}
.btn-reset:focus-visible {{
  outline-color: var(--bad);
}}
#result {{
  display: none;
}}
#result.show {{ display: block; }}
.result-box {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}}
.result-box h2 {{ margin: 0 0 16px; font-size: 1.4rem; }}
.score-hero {{
  text-align: center;
  padding: 20px 16px;
  border-radius: 12px;
  background: #f6f8fa;
  margin-bottom: 16px;
}}
.score-hero .big {{
  font-size: 2.6rem;
  font-weight: 800;
  line-height: 1.1;
}}
.score-hero .sub {{ color: var(--muted); margin-top: 6px; font-size: 1.05rem; }}
.pass-badge {{
  display: inline-block;
  margin-top: 10px;
  padding: 6px 14px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 1rem;
}}
.pass-badge.pass {{ background: var(--ok-soft); color: var(--ok); }}
.pass-badge.fail {{ background: var(--bad-soft); color: var(--bad); }}
.subject-grid {{
  display: grid;
  gap: 10px;
  margin-bottom: 20px;
}}
.subject-card {{
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}}
.subject-card .name {{ font-weight: 700; font-size: 1.05rem; }}
.subject-card .detail {{ color: var(--muted); font-size: 0.98rem; }}
.subject-card .pct {{ font-weight: 800; font-size: 1.2rem; }}
.subject-card.fail-subj {{ border-color: #f5c2c7; background: #fff8f8; }}
.result-section h3 {{
  margin: 0 0 10px;
  font-size: 1.1rem;
}}
.review-item {{
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 10px;
  overflow: hidden;
}}
.review-item summary {{
  list-style: none;
  cursor: pointer;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-weight: 600;
}}
.review-item summary::-webkit-details-marker {{ display: none; }}
.review-item summary::before {{
  content: "▸";
  color: var(--muted);
  flex-shrink: 0;
  margin-top: 1px;
}}
.review-item[open] summary::before {{ content: "▾"; }}
.review-body {{ padding: 0 14px 14px; border-top: 1px solid var(--border); }}
.review-stem {{
  white-space: pre-wrap;
  font-weight: 600;
  margin: 12px 0;
  font-size: 1.05rem;
}}
.review-choices {{ display: flex; flex-direction: column; gap: 8px; }}
.review-choice {{
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 1rem;
}}
.review-choice.correct {{ border-color: var(--ok); background: var(--ok-soft); }}
.review-choice.wrong {{ border-color: var(--bad); background: var(--bad-soft); }}
.review-choice .label {{ font-weight: 700; min-width: 1.6em; }}
.review-explain {{
  margin-top: 12px;
  padding: 10px 12px;
  background: #f6f8fa;
  border-radius: 8px;
  font-size: 1rem;
  color: var(--muted);
}}
.tag {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}}
.tag.ok {{ background: var(--ok-soft); color: var(--ok); }}
.tag.bad {{ background: var(--bad-soft); color: var(--bad); }}
.tag.skip {{ background: #f0f0f0; color: var(--muted); }}
.result-actions {{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}}
.all-list {{ margin-top: 16px; }}
.all-row {{
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 1rem;
}}
.all-row:last-child {{ border-bottom: none; }}
.hint {{ color: var(--muted); font-size: 0.98rem; }}
@media (max-width: 480px) {{
  body {{ font-size: 17px; }}
  .stem {{ font-size: 1.12rem; }}
  .choice {{ padding: 12px 14px; }}
}}
</style>
</head>
<body>
<div class="wrap" id="exam-view">
  <header>
    <h1>{safe_title}</h1>
    <div class="meta" id="status">1 / {len(questions)} · 미응답 0</div>
    <div class="progress-bar"><div class="progress-fill" id="progress"></div></div>
  </header>
  <div class="card" id="question-card"></div>
</div>

<div class="wrap" id="result">
  <div class="result-box">
    <h2>채점 결과</h2>
    <div id="score-panel"></div>
    <div id="subject-panel"></div>
    <div class="result-section" id="wrong-section">
      <h3>오답 · 미응답 <span id="wrong-count"></span></h3>
      <div id="wrong-list"></div>
      <p class="hint" id="wrong-empty" style="display:none">모든 문항을 맞혔습니다.</p>
    </div>
    <div class="result-actions">
      <button class="btn btn-secondary" type="button" id="toggle-all-btn">전체 문항 보기</button>
      <button class="btn btn-reset restart-btn" type="button">처음부터</button>
    </div>
    <div class="all-list" id="all-list" style="display:none"></div>
    <p class="hint" style="margin-top:12px">합격 기준: 과목당 40점 이상 · 전과목 평균 60점 이상</p>
  </div>
</div>

<div class="toolbar" id="toolbar">
  <div class="toolbar-inner">
    <button class="btn btn-reset restart-btn" type="button">처음부터</button>
    <div class="toolbar-nav">
      <button class="btn btn-secondary" type="button" id="prev-btn">이전</button>
      <button class="btn btn-primary" type="button" id="next-btn">다음 문제</button>
    </div>
  </div>
</div>

<script>
const QUESTIONS = {data};
const STORAGE_KEY = {json.dumps(storage_key)};
const LABEL_TO_NUM = {{"①":1,"②":2,"③":3,"④":4}};
const NUM_TO_LABEL = {{"1":"①","2":"②","3":"③","4":"④"}};

let index = 0;
let answers = {{}};

function clearStateIfRequested() {{
  if (!new URLSearchParams(location.search).has("reset")) return;
  localStorage.removeItem(STORAGE_KEY);
  history.replaceState(null, "", location.pathname);
}}

function loadState() {{
  try {{
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved.answers) answers = saved.answers;
    if (typeof saved.index === "number") index = saved.index;
  }} catch (e) {{}}
}}

function saveState() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify({{ index, answers }}));
}}

function answeredCount() {{
  return Object.keys(answers).length;
}}

function selectChoice(label) {{
  const q = QUESTIONS[index];
  answers[q.num] = label;
  saveState();
  render();
  document.querySelectorAll("#question-card .choice").forEach(btn => {{
    if (btn.dataset.label === label) btn.focus();
  }});
}}

function moveChoice(delta) {{
  const q = QUESTIONS[index];
  const labels = q.choices.map(c => c.label);
  let cur = labels.indexOf(answers[q.num]);
  if (cur < 0) cur = delta > 0 ? -1 : labels.length;
  const next = (cur + delta + labels.length) % labels.length;
  selectChoice(labels[next]);
}}

function render() {{
  const q = QUESTIONS[index];
  const card = document.getElementById("question-card");
  const selected = answers[q.num];
  const choicesHtml = q.choices.map(c => `
    <button type="button" class="choice${{selected === c.label ? " selected" : ""}}" data-label="${{c.label}}">
      <span class="label">${{c.label}}</span>
      <span class="text">${{escapeHtml(c.text)}}</span>
    </button>`).join("");

  card.innerHTML = `
    <div class="q-num">${{q.subject ? q.subject + "과목 · " : ""}}${{q.num}}번</div>
    <div class="stem">${{escapeHtml(q.stem)}}</div>
    <div class="choices">${{choicesHtml}}</div>`;

  card.querySelectorAll(".choice").forEach(btn => {{
    btn.addEventListener("click", () => selectChoice(btn.dataset.label));
  }});

  const total = QUESTIONS.length;
  const unanswered = total - answeredCount();
  document.getElementById("status").textContent =
    `${{index + 1}} / ${{total}} · 응답 ${{answeredCount()}} · 미응답 ${{unanswered}}`;
  document.getElementById("progress").style.width = `${{((index + 1) / total) * 100}}%`;
  document.getElementById("prev-btn").disabled = index === 0;
  document.getElementById("next-btn").textContent =
    index === total - 1 ? "제출하기" : "다음 문제";
}}

function escapeHtml(s) {{
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}

const SUBJECT_META = {{
  "1": {{ name: "1과목", range: "1~30", total: 30 }},
  "2": {{ name: "2과목", range: "31~50", total: 20 }},
  "3": {{ name: "3과목", range: "51~80", total: 30 }},
}};

function gradeAll() {{
  return QUESTIONS.map(q => {{
    const user = answers[q.num] || "";
    const correct = q.answer || "";
    const ok = !!user && user === correct;
    return {{ ...q, user, correct, ok }};
  }});
}}

function subjectStats(graded) {{
  return Object.entries(SUBJECT_META).map(([id, meta]) => {{
    const items = graded.filter(q => q.subject === id);
    const correct = items.filter(q => q.ok).length;
    const pct = items.length ? Math.round((correct / items.length) * 1000) / 10 : 0;
    return {{ id, ...meta, correct, count: items.length, pct, pass: pct >= 40 }};
  }});
}}

function renderReviewChoices(item) {{
  return item.choices.map(c => {{
    let cls = "review-choice";
    if (c.label === item.correct) cls += " correct";
    else if (c.label === item.user && item.user !== item.correct) cls += " wrong";
    return `<div class="${{cls}}"><span class="label">${{c.label}}</span><span>${{escapeHtml(c.text)}}</span></div>`;
  }}).join("");
}}

function renderReviewItem(item, open) {{
  const userText = item.user || "미응답";
  const tag = item.ok
    ? `<span class="tag ok">정답</span>`
    : (item.user
      ? `<span class="tag bad">오답</span>`
      : `<span class="tag skip">미응답</span>`);
  const summary = `${{tag}} <span>${{item.subject ? item.subject + "과목 · " : ""}}${{item.num}}번</span>`;
  const explain = item.explain
    ? `<div class="review-explain"><strong>해설</strong> — ${{escapeHtml(item.explain)}}</div>`
    : "";
  const detail = item.user && !item.ok
    ? `<div class="hint" style="margin-top:8px">내 답 ${{item.user}} · 정답 ${{item.correct}}</div>`
    : (!item.user ? `<div class="hint" style="margin-top:8px">정답 ${{item.correct}}</div>` : "");
  return `
    <details class="review-item"${{open ? " open" : ""}}>
      <summary>${{summary}}</summary>
      <div class="review-body">
        <div class="review-stem">${{escapeHtml(item.stem)}}</div>
        <div class="review-choices">${{renderReviewChoices(item)}}</div>
        ${{detail}}${{explain}}
      </div>
    </details>`;
}}

function renderResult(graded) {{
  const totalCorrect = graded.filter(q => q.ok).length;
  const total = graded.length;
  const avgPct = total ? Math.round((totalCorrect / total) * 1000) / 10 : 0;
  const subjects = subjectStats(graded);
  const allSubjectsPass = subjects.every(s => s.pass);
  const overallPass = allSubjectsPass && avgPct >= 60;
  const wrong = graded.filter(q => !q.ok);

  document.getElementById("score-panel").innerHTML = `
    <div class="score-hero">
      <div class="big">${{totalCorrect}} / ${{total}}</div>
      <div class="sub">환산 평균 ${{avgPct}}점</div>
      <div class="pass-badge ${{overallPass ? "pass" : "fail"}}">${{overallPass ? "합격" : "불합격"}}</div>
    </div>`;

  document.getElementById("subject-panel").innerHTML = `
    <div class="subject-grid">
      ${{subjects.map(s => `
        <div class="subject-card${{s.pass ? "" : " fail-subj"}}">
          <div>
            <div class="name">${{s.name}} (${{s.range}})</div>
            <div class="detail">${{s.correct}} / ${{s.count}}문항 · ${{s.pass ? "과목 합격" : "과목 미달"}}</div>
          </div>
          <div class="pct">${{s.pct}}점</div>
        </div>`).join("")}}
    </div>`;

  document.getElementById("wrong-count").textContent = wrong.length ? `(${{wrong.length}})` : "";
  document.getElementById("wrong-empty").style.display = wrong.length ? "none" : "block";
  document.getElementById("wrong-list").innerHTML = wrong.map(q => renderReviewItem(q, false)).join("");

  document.getElementById("all-list").innerHTML = graded.map(q => {{
    const tag = q.ok
      ? `<span class="tag ok">O</span>`
      : (q.user ? `<span class="tag bad">X</span>` : `<span class="tag skip">-</span>`);
    return `<div class="all-row">${{tag}} <span>${{q.num}}번</span> <span class="hint">${{q.user || "—"}} → ${{q.correct}}</span></div>`;
  }}).join("");
}}

function showResult() {{
  const graded = gradeAll();
  document.getElementById("exam-view").style.display = "none";
  document.getElementById("toolbar").style.display = "none";
  document.getElementById("result").classList.add("show");
  renderResult(graded);
  saveState();
  window.scrollTo(0, 0);
}}

function goNext() {{
  if (index < QUESTIONS.length - 1) {{
    index++;
    saveState();
    render();
  }} else {{
    showResult();
  }}
}}

function goPrev() {{
  if (index > 0) {{ index--; saveState(); render(); }}
}}

document.getElementById("prev-btn").addEventListener("click", goPrev);

document.getElementById("next-btn").addEventListener("click", goNext);

document.addEventListener("keydown", (e) => {{
  if (document.getElementById("result").classList.contains("show")) return;
  const ae = document.activeElement;
  if (ae && (ae.tagName === "TEXTAREA" || ae.tagName === "INPUT")) return;

  if (e.key === "ArrowDown") {{
    e.preventDefault();
    moveChoice(1);
    return;
  }}
  if (e.key === "ArrowUp") {{
    e.preventDefault();
    moveChoice(-1);
    return;
  }}
  if (e.key === "ArrowLeft") {{
    e.preventDefault();
    goPrev();
    return;
  }}
  if (e.key === "ArrowRight") {{
    e.preventDefault();
    goNext();
    return;
  }}
  const numLabel = NUM_TO_LABEL[e.key];
  if (numLabel) {{
    const q = QUESTIONS[index];
    if (q.choices.some(c => c.label === numLabel)) {{
      e.preventDefault();
      selectChoice(numLabel);
    }}
    return;
  }}
  if (e.key !== "Enter") return;
  e.preventDefault();
  goNext();
}});

document.getElementById("toggle-all-btn").addEventListener("click", () => {{
  const list = document.getElementById("all-list");
  const btn = document.getElementById("toggle-all-btn");
  const show = list.style.display === "none";
  list.style.display = show ? "block" : "none";
  btn.textContent = show ? "전체 문항 숨기기" : "전체 문항 보기";
}});

function restartExam() {{
  if (!confirm("저장된 답안을 모두 지우고 처음부터 시작할까요?")) return;
  localStorage.removeItem(STORAGE_KEY);
  index = 0;
  answers = {{}};
  document.getElementById("exam-view").style.display = "";
  document.getElementById("toolbar").style.display = "";
  document.getElementById("result").classList.remove("show");
  render();
  window.scrollTo(0, 0);
}}

document.querySelectorAll(".restart-btn").forEach(btn => {{
  btn.addEventListener("click", restartExam);
}});

clearStateIfRequested();
loadState();
render();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build interactive mock exam HTML player")
    parser.add_argument(
        "round_dir",
        type=Path,
        nargs="?",
        help="Mock round directory (e.g. output/mock_exam/1회차)",
    )
    parser.add_argument(
        "--mock-root",
        type=Path,
        default=ROOT / "output/mock_exam",
        help="Mock exam root (used with --round)",
    )
    parser.add_argument("--round", type=int, help="Round number (with --mock-root)")
    parser.add_argument(
        "--open",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="생성 후 기본 브라우저에서 필기_응시.html 열기 (기본: 열기)",
    )
    args = parser.parse_args()

    if args.round_dir:
        round_dir = args.round_dir if args.round_dir.is_absolute() else ROOT / args.round_dir
    elif args.round:
        round_dir = args.mock_root / f"{args.round}회차"
    else:
        parser.error("round_dir or --round required")

    prob = round_dir / "필기_모의_문제.md"
    if not prob.is_file():
        raise SystemExit(f"Not found: {prob}")

    ans_path = round_dir / "필기_모의_정답.md"
    if not ans_path.is_file():
        raise SystemExit(f"Not found: {ans_path}")

    title, questions = parse_questions(prob)
    answer_map = parse_answers(ans_path)
    attach_answers(questions, answer_map)
    missing = [q["num"] for q in questions if not q.get("answer")]
    if missing:
        print(f"Warning: no answer for questions: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if len(questions) != 80:
        print(f"Warning: parsed {len(questions)} questions (expected 80)")

    out = round_dir / "필기_응시.html"
    out.write_text(build_html(title, questions, round_dir), encoding="utf-8")
    print(f"Wrote {out} ({len(questions)} questions)")
    if args.open:
        if open_mock_exam_html(out):
            print(f"Opened {out} in default browser")
        else:
            print(f"Could not open {out}")


if __name__ == "__main__":
    main()

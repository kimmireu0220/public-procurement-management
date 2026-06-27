#!/usr/bin/env python3
"""필기_모의_문제.md → CBT 응시 HTML 생성."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "output/mock_exam/1회차/필기_모의_문제.md"
OUT_DIR = ROOT / "output/mock_exam/1회차"

Q_START = re.compile(r"^(\d+)\.\s+(.+)$")
CHOICE = re.compile(r"^\s*([①②③④])\s+(.+)$")
SUBJECT = re.compile(r"^##\s+(\d)과목\s+(.+?)\s+\(")
ID_TAG = re.compile(r"<!--\s*id:\s*([^>]+)\s*-->")


def parse_questions(text: str) -> list[dict]:
    lines = text.splitlines()
    subject_no = 1
    subject_name = ""
    questions: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        sm = SUBJECT.match(line)
        if sm:
            subject_no = int(sm.group(1))
            subject_name = sm.group(2).strip()
            i += 1
            continue
        qm = Q_START.match(line)
        if qm:
            no = int(qm.group(1))
            stem_parts = [qm.group(2).strip()]
            choices: list[dict] = []
            qid = ""
            i += 1
            while i < len(lines):
                ln = lines[i]
                if Q_START.match(ln) or SUBJECT.match(ln) or ln.startswith("## "):
                    break
                if ln.strip() in ("---", ""):
                    i += 1
                    continue
                im = ID_TAG.search(ln)
                if im:
                    qid = im.group(1).strip()
                    i += 1
                    continue
                if ln.strip().startswith("<!--"):
                    i += 1
                    continue
                cm = CHOICE.match(ln)
                if cm:
                    label = cm.group(1)
                    key = {"①": "1", "②": "2", "③": "3", "④": "4"}[label]
                    choices.append({"key": key, "label": label, "text": cm.group(2).strip()})
                    i += 1
                    continue
                if ln.strip():
                    stem_parts.append(ln.strip())
                i += 1
            if len(choices) >= 2:
                questions.append(
                    {
                        "no": no,
                        "subject": subject_no,
                        "subjectName": subject_name,
                        "stem": " ".join(stem_parts),
                        "choices": choices,
                        "id": qid,
                    }
                )
            continue
        i += 1
    return questions


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>공공조달관리사 필기 모의 1회차 — CBT</title>
<style>
:root {
  --bg: #e8ecf1;
  --panel: #fff;
  --primary: #1a4d8f;
  --primary-dark: #0f3460;
  --accent: #2e7dd1;
  --border: #c5d0de;
  --text: #1a1a1a;
  --muted: #5c6b7a;
  --answered: #2e7dd1;
  --current: #1a4d8f;
  --unanswered: #d0d7e2;
  --warn: #c0392b;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

/* 시작 화면 */
#screen-start { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 1.5rem; }
.start-card { background: var(--panel); max-width: 520px; width: 100%; border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,.12); padding: 2.5rem 2rem; text-align: center; border-top: 4px solid var(--primary); }
.start-card h1 { font-size: 1.65rem; color: var(--primary-dark); margin-bottom: .5rem; }
.start-card .sub { color: var(--muted); font-size: 1.05rem; margin-bottom: 1.5rem; }
.start-card ul { text-align: left; margin: 0 auto 1.75rem; max-width: 340px; font-size: .92rem; line-height: 1.8; color: #333; }
.start-card .btn-start { background: var(--primary); color: #fff; border: none; padding: .85rem 2.5rem; font-size: 1.05rem; border-radius: 4px; cursor: pointer; font-weight: 600; }
.start-card .btn-start:hover { background: var(--primary-dark); }

/* 시험 화면 */
#screen-exam { display: none; flex-direction: column; height: 100vh; }
.topbar { background: var(--primary-dark); color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.5rem; font-size: 1.1rem; flex-shrink: 0; min-height: 3.75rem; }
.topbar .exam-title { font-weight: 700; font-size: 1.3rem; }
.topbar .timer { font-size: 1.65rem; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: .05em; }
.topbar .timer.warn { color: #ffcc00; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: .7; } }
.subbar { background: var(--primary); color: #fff; padding: .9rem 1.5rem; font-size: 1.1rem; display: flex; justify-content: space-between; align-items: center; min-height: 3.25rem; }
.subbar #subject-label { font-size: 1.15rem; font-weight: 600; }
.subbar #progress-label { font-size: 1.1rem; font-weight: 600; }

.main { display: flex; flex: 1; overflow: hidden; }
.question-panel { flex: 1; overflow-y: auto; padding: 1.5rem 2rem 2rem; background: var(--panel); }
.q-header { display: flex; align-items: center; gap: .75rem; margin-bottom: 1.25rem; }
.q-badge { background: var(--primary); color: #fff; font-weight: 700; font-size: 1.35rem; min-width: 3.25rem; text-align: center; padding: .45rem .7rem; border-radius: 4px; }
.q-subject { color: var(--muted); font-size: 1rem; font-weight: 600; }
.q-stem { font-size: 1.2rem; line-height: 1.75; margin-bottom: 1.5rem; font-weight: 600; }
.q-stem strong { color: var(--primary-dark); }

.choices { display: flex; flex-direction: column; gap: .65rem; }
.choice { display: flex; align-items: flex-start; gap: .75rem; padding: .85rem 1rem; border: 2px solid var(--border); border-radius: 6px; cursor: pointer; transition: border-color .15s, background .15s; background: #fafbfc; }
.choice:hover { border-color: var(--accent); background: #f0f6fc; }
.choice.selected { border-color: var(--primary); background: #e8f0fa; box-shadow: 0 0 0 1px var(--primary); }
.choice.focused { outline: 2px solid var(--accent); outline-offset: 2px; }
.choice .num { font-weight: 700; color: var(--primary); min-width: 1.75rem; font-size: 1.15rem; }
.choice .text { flex: 1; line-height: 1.6; font-size: 1.12rem; }
.choice input { display: none; }

.nav-panel { width: 280px; background: #f4f6f9; border-left: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
.nav-title { padding: .85rem 1rem; font-size: 1rem; font-weight: 700; color: var(--primary-dark); border-bottom: 1px solid var(--border); }
.nav-scroll { overflow-y: auto; flex: 1; padding: .75rem; }
.nav-section { margin-bottom: .9rem; }
.nav-section:last-child { margin-bottom: 0; }
.nav-section-title { font-size: .95rem; font-weight: 700; color: var(--primary-dark); margin-bottom: .45rem; padding-bottom: .3rem; border-bottom: 1px solid var(--border); line-height: 1.4; }
.nav-section-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.nav-btn { min-height: 2.35rem; border: 1px solid var(--border); background: var(--unanswered); border-radius: 4px; font-size: .85rem; font-weight: 600; cursor: pointer; color: #444; }
.nav-btn.answered { background: #b8d4f0; border-color: var(--answered); color: var(--primary-dark); }
.nav-btn.current { background: var(--current); color: #fff; border-color: var(--current); }
.nav-btn:hover { filter: brightness(.95); }
.nav-legend { padding: .5rem .75rem; font-size: .72rem; color: var(--muted); border-top: 1px solid var(--border); display: flex; gap: .75rem; flex-wrap: wrap; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 2px; vertical-align: middle; }

.bottombar { background: var(--panel); border-top: 1px solid var(--border); padding: .65rem 1.25rem; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; gap: .75rem; }
.bottombar-left, .bottombar-right { display: flex; align-items: center; gap: .5rem; }
.bottombar button { padding: .55rem 1.4rem; font-size: .92rem; border-radius: 4px; cursor: pointer; border: 1px solid var(--border); background: #fff; }
.bottombar button.reset { color: var(--warn); border-color: #e8c4c0; background: #fff8f7; }
.bottombar button.reset:hover { background: #fdecea; }
.bottombar button.primary { background: var(--primary); color: #fff; border-color: var(--primary); font-weight: 600; }
.bottombar button:disabled { opacity: .4; cursor: not-allowed; }
.progress-text { font-size: 1rem; font-weight: 600; color: var(--text); }

/* 종료 화면 */
#screen-end { display: none; min-height: 100vh; padding: 2rem; }
.end-card { max-width: 640px; margin: 0 auto; background: var(--panel); border-radius: 8px; padding: 2rem; box-shadow: 0 4px 20px rgba(0,0,0,.1); }
.end-card h2 { color: var(--primary-dark); margin-bottom: 1rem; font-size: 1.55rem; }
.end-card textarea { width: 100%; height: 160px; font-family: monospace; font-size: .85rem; padding: .75rem; border: 1px solid var(--border); border-radius: 4px; margin: 1rem 0; }
.end-card .hint { font-size: .88rem; color: var(--muted); line-height: 1.6; }
.end-card button { margin-right: .5rem; margin-top: .5rem; padding: .55rem 1.2rem; border-radius: 4px; cursor: pointer; border: 1px solid var(--border); background: #fff; }
.end-card button.primary { background: var(--primary); color: #fff; border-color: var(--primary); }

@media (max-width: 768px) {
  .main { flex-direction: column; }
  .nav-panel { width: 100%; border-left: none; border-top: 1px solid var(--border); max-height: 200px; }
  .nav-section-grid { grid-template-columns: repeat(8, 1fr); }
  .question-panel { padding: 1rem; }
}
</style>
</head>
<body>

<div id="screen-start">
  <div class="start-card">
    <h1>공공조달관리사 필기 모의 1회차</h1>
    <p class="sub">Computer Based Test (CBT) 모의 응시</p>
    <ul>
      <li>총 <strong>80문항</strong> · 제한시간 <strong>120분</strong></li>
      <li>1과목 30문항 · 2과목 20문항 · 3과목 30문항</li>
      <li>4지 선다형 — 문항당 하나만 선택</li>
      <li>답안은 자동 저장됩니다 (브라우저)</li>
    </ul>
    <button class="btn-start" id="btn-start">시험 시작</button>
  </div>
</div>

<div id="screen-exam">
  <div class="topbar">
    <span class="exam-title">공공조달관리사 1회 필기 모의 1회차</span>
    <span class="timer" id="timer">02:00:00</span>
  </div>
  <div class="subbar">
    <span id="subject-label">1과목 공공조달과 법제도 이해</span>
    <span>
      <span id="progress-label">1 / 80</span>
    </span>
  </div>
  <div class="main">
    <div class="question-panel" id="question-panel"></div>
    <aside class="nav-panel">
      <div class="nav-title">문항 이동</div>
      <div class="nav-scroll" id="nav-scroll"></div>
      <div class="nav-legend">
        <span><span class="legend-dot" style="background:var(--unanswered)"></span>미답</span>
        <span><span class="legend-dot" style="background:#b8d4f0"></span>답변</span>
        <span><span class="legend-dot" style="background:var(--current)"></span>현재</span>
      </div>
    </aside>
  </div>
  <div class="bottombar">
    <div class="bottombar-left">
      <button id="btn-prev">◀ 이전</button>
      <button class="reset" id="btn-reset" type="button">처음부터</button>
    </div>
    <span class="progress-text" id="answered-count">답변 0 / 80</span>
    <div class="bottombar-right">
      <button id="btn-next">다음 ▶</button>
      <button class="primary" id="btn-submit">시험 종료</button>
    </div>
  </div>
</div>

<div id="screen-end">
  <div class="end-card">
    <h2>시험 종료</h2>
    <p class="hint">아래 답안 문자열을 복사해 채팅에 붙여넣으면 채점합니다.<br>형식: <code>1③ 2④ 3④ …</code> 또는 <code>1-3,2-4,…</code></p>
    <textarea id="answer-export" readonly></textarea>
    <button class="primary" id="btn-copy">답안 복사</button>
    <button id="btn-restart">다시 응시</button>
    <p class="hint" style="margin-top:1rem">※ 정답·해설은 채점 후 제공됩니다.</p>
  </div>
</div>

<script>
const QUESTIONS = __QUESTIONS_JSON__;
const STORAGE_KEY = 'mock_exam_1_answers';
const DURATION_SEC = 120 * 60;

let current = 0;
let answers = {};
let timerSec = DURATION_SEC;
let timerId = null;
let choiceFocus = 0;
let examActive = false;

function loadAnswers() {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s) answers = JSON.parse(s);
  } catch (e) {}
}
function saveAnswers() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(answers));
}

function subjectLabel(q) {
  return q.subject + '과목 ' + q.subjectName;
}

function formatTime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':').replace(/^00:/, '');
}

function startTimer() {
  const el = document.getElementById('timer');
  timerId = setInterval(() => {
    timerSec--;
    el.textContent = formatTime(timerSec);
    if (timerSec <= 600) el.classList.add('warn');
    if (timerSec <= 0) { clearInterval(timerId); finishExam(true); }
  }, 1000);
}

function renderQuestion() {
  const q = QUESTIONS[current];
  const panel = document.getElementById('question-panel');
  const selected = answers[q.no];

  const selIdx = selected ? q.choices.findIndex(c => c.key === selected) : -1;
  choiceFocus = selIdx >= 0 ? selIdx : 0;

  let html = '<div class="q-header"><span class="q-badge">' + q.no + '</span><span class="q-subject">' + subjectLabel(q) + '</span></div>';
  html += '<div class="q-stem">' + q.stem.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') + '</div>';
  html += '<div class="choices" id="choices">';
  q.choices.forEach((c, i) => {
    const sel = selected === c.key ? ' selected' : '';
    const foc = i === choiceFocus ? ' focused' : '';
    html += '<label class="choice' + sel + foc + '" data-key="' + c.key + '" data-idx="' + i + '"><span class="num">' + c.label + '</span><span class="text">' + escapeHtml(c.text) + '</span><input type="radio" name="q" value="' + c.key + '"' + (sel ? ' checked' : '') + '></label>';
  });
  html += '</div>';
  panel.innerHTML = html;

  panel.querySelectorAll('.choice').forEach(el => {
    el.addEventListener('click', () => selectAnswer(q.no, el.dataset.key));
  });

  document.getElementById('subject-label').textContent = subjectLabel(q);
  document.getElementById('progress-label').textContent = (current + 1) + ' / ' + QUESTIONS.length;
  document.getElementById('btn-prev').disabled = current === 0;
  document.getElementById('btn-next').disabled = current === QUESTIONS.length - 1;
  updateNav();
  updateCount();
  updateChoiceFocus();
}

function updateChoiceFocus() {
  const panel = document.getElementById('question-panel');
  if (!panel) return;
  panel.querySelectorAll('.choice').forEach((el, i) => {
    el.classList.toggle('focused', i === choiceFocus);
  });
  const focused = panel.querySelector('.choice.focused');
  if (focused) focused.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function selectAnswer(no, key) {
  answers[no] = key;
  saveAnswers();
  const q = QUESTIONS[current];
  const idx = q.choices.findIndex(c => c.key === key);
  if (idx >= 0) choiceFocus = idx;

  if (current < QUESTIONS.length - 1) {
    current++;
    renderQuestion();
  } else {
    updateNav();
    updateCount();
    renderQuestion();
  }
}

function goPrev() {
  if (current > 0) { current--; renderQuestion(); }
}

function goNext() {
  if (current < QUESTIONS.length - 1) { current++; renderQuestion(); }
}

function handleExamKeydown(e) {
  if (!examActive) return;
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

  const q = QUESTIONS[current];
  const n = q.choices.length;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    choiceFocus = (choiceFocus + 1) % n;
    updateChoiceFocus();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    choiceFocus = (choiceFocus - 1 + n) % n;
    updateChoiceFocus();
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    goPrev();
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    goNext();
  } else if (e.key >= '1' && e.key <= '4') {
    const idx = parseInt(e.key, 10) - 1;
    if (idx < n) {
      e.preventDefault();
      selectAnswer(q.no, q.choices[idx].key);
    }
  } else if (e.key === 'Enter') {
    e.preventDefault();
    goNext();
  }
}

function buildNav() {
  renderNavGrid();
}

function renderNavGrid() {
  const container = document.getElementById('nav-scroll');
  container.innerHTML = '';
  let lastSubject = null;
  let sectionGrid = null;

  QUESTIONS.forEach((q, i) => {
    if (q.subject !== lastSubject) {
      lastSubject = q.subject;
      const section = document.createElement('div');
      section.className = 'nav-section';
      const title = document.createElement('div');
      title.className = 'nav-section-title';
      title.textContent = q.subject + '과목 ' + q.subjectName;
      sectionGrid = document.createElement('div');
      sectionGrid.className = 'nav-section-grid';
      section.appendChild(title);
      section.appendChild(sectionGrid);
      container.appendChild(section);
    }
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'nav-btn';
    btn.dataset.index = String(i);
    btn.textContent = q.no;
    btn.title = subjectLabel(q);
    btn.addEventListener('click', () => { current = i; renderQuestion(); });
    sectionGrid.appendChild(btn);
  });
}

function updateNav() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    const i = parseInt(btn.dataset.index, 10);
    const q = QUESTIONS[i];
    btn.classList.remove('current', 'answered');
    if (i === current) {
      btn.classList.add('current');
      btn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else if (answers[q.no]) {
      btn.classList.add('answered');
    }
  });
}

function updateCount() {
  const n = Object.keys(answers).length;
  document.getElementById('answered-count').textContent = '답변 ' + n + ' / ' + QUESTIONS.length;
}

function resetAnswers() {
  const n = Object.keys(answers).length;
  const msg = n > 0
    ? '선택한 답안 ' + n + '개를 모두 지우고 1번 문항부터 다시 시작합니다.'
    : '1번 문항부터 다시 시작합니다.';
  if (!confirm(msg)) return;
  answers = {};
  localStorage.removeItem(STORAGE_KEY);
  current = 0;
  choiceFocus = 0;
  renderNavGrid();
  renderQuestion();
}

function exportAnswers() {
  return QUESTIONS.map(q => {
    const a = answers[q.no];
    const sym = {1:'①',2:'②',3:'③',4:'④'}[a] || '?';
    return q.no + sym;
  }).join(' ');
}

function finishExam(auto) {
  if (!auto) {
    const n = Object.keys(answers).length;
    const left = QUESTIONS.length - n;
    if (left > 0 && !confirm('미답 ' + left + '문항이 있습니다. 시험을 종료하시겠습니까?')) return;
  }
  examActive = false;
  clearInterval(timerId);
  document.getElementById('screen-exam').style.display = 'none';
  document.getElementById('screen-end').style.display = 'block';
  document.getElementById('answer-export').value = exportAnswers();
}

document.getElementById('btn-start').addEventListener('click', () => {
  loadAnswers();
  document.getElementById('screen-start').style.display = 'none';
  document.getElementById('screen-exam').style.display = 'flex';
  examActive = true;
  buildNav();
  renderQuestion();
  startTimer();
});

document.addEventListener('keydown', handleExamKeydown);

document.getElementById('btn-prev').addEventListener('click', goPrev);
document.getElementById('btn-reset').addEventListener('click', resetAnswers);
document.getElementById('btn-next').addEventListener('click', goNext);
document.getElementById('btn-submit').addEventListener('click', () => finishExam(false));

document.getElementById('btn-copy').addEventListener('click', () => {
  const ta = document.getElementById('answer-export');
  ta.select();
  navigator.clipboard.writeText(ta.value).catch(() => {});
});

document.getElementById('btn-restart').addEventListener('click', () => {
  if (confirm('저장된 답안을 지우고 처음부터 다시 시작합니다.')) {
    localStorage.removeItem(STORAGE_KEY);
    location.reload();
  }
});
</script>
</body>
</html>
"""


def main() -> None:
    text = MD.read_text(encoding="utf-8")
    questions = parse_questions(text)
    if len(questions) != 80:
        raise SystemExit(f"expected 80 questions, got {len(questions)}")
    html = HTML_TEMPLATE.replace("__QUESTIONS_JSON__", json.dumps(questions, ensure_ascii=False))
    for name in ("index.html", "필기_응시.html", "필기_모의_응시.html"):
        (OUT_DIR / name).write_text(html, encoding="utf-8")
    print(f"CBT viewer: {len(questions)} questions → {OUT_DIR}")


if __name__ == "__main__":
    main()

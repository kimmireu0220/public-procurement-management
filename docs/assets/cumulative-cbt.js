(function () {
  'use strict';
  const config = window.CBT_CONFIG;
  const bank = Array.isArray(window.CBT_BANK) ? window.CBT_BANK : [];
  const app = document.getElementById('cbt-app');
  const wrongKey = `ppm_cbt_wrong_subject_${config.subject}_v1`;
  const progressKey = `ppm_cbt_progress_subject_${config.subject}_${config.mode}_v1`;
  const symbols = {1:'①',2:'②',3:'③',4:'④'};
  let index = Number(localStorage.getItem(progressKey) || 0);
  let locked = false;

  function readWrong() {
    try { return new Set(JSON.parse(localStorage.getItem(wrongKey) || '[]')); }
    catch (_) { return new Set(); }
  }
  function writeWrong(set) { localStorage.setItem(wrongKey, JSON.stringify([...set])); }
  function questions() {
    if (config.mode !== 'wrong') return bank;
    const wrong = readWrong();
    return bank.filter(q => wrong.has(q.id));
  }
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function saveIndex(total) {
    if (total) index = Math.max(0, Math.min(index, total - 1)); else index = 0;
    localStorage.setItem(progressKey, String(index));
  }
  function mark(question, isCorrect) {
    const wrong = readWrong();
    if (isCorrect) {
      if (config.mode === 'wrong') wrong.delete(question.id);
    } else wrong.add(question.id);
    writeWrong(wrong);
  }
  function move(delta) {
    const total = questions().length;
    index = Math.max(0, Math.min(index + delta, Math.max(0, total - 1)));
    saveIndex(total); render();
  }
  function finishQuestion(wasCorrect) {
    const total = questions().length;
    if (config.mode === 'wrong') {
      if (!total) index = 0;
      else if (wasCorrect) index = index >= total ? 0 : index;
      else index = (index + 1) % total;
    } else if (index < total - 1) index += 1;
    saveIndex(total); render();
  }
  function toolbar(list) {
    return `<div class="toolbar"><strong>${index + 1} / ${list.length} · 누적 오답 ${readWrong().size}개</strong>`+
      `<button type="button" data-action="prev">이전</button><label>문항 <input class="jump" type="number" min="1" max="${list.length}" value="${index + 1}" aria-label="이동할 문항"></label>`+
      `<button type="button" data-action="next">다음</button>`+
      (config.mode === 'wrong' ? `<button type="button" class="danger" data-action="reset">오답 초기화</button>` : '') + `</div>`;
  }
  function objective(question, list) {
    return toolbar(list) + `<article class="question-card"><div class="meta"><span>${escapeHtml(question.group)}</span><span>${question.no}번</span></div>`+
      `<h2 class="stem">${escapeHtml(question.stem)}</h2><div class="choices">${question.choices.map(choice =>
        `<button type="button" class="choice" data-choice="${choice.key}"><span class="symbol">${escapeHtml(choice.label || symbols[choice.key])}</span><span>${escapeHtml(choice.text)}</span></button>`
      ).join('')}</div><div id="feedback"></div></article>`;
  }
  function written(question, list) {
    return toolbar(list) + `<article class="question-card"><div class="meta"><span>${escapeHtml(question.group)}</span><span>${question.no}번</span></div>`+
      `<h2 class="stem">${escapeHtml(question.stem)}</h2><div class="answer-form"><label for="written-answer"><strong>내 답안</strong></label>`+
      `<textarea id="written-answer" placeholder="답안을 입력하세요."></textarea><div class="answer-actions"><button type="button" class="primary" data-action="reveal">답안 확인</button></div></div>`+
      `<section id="model-answer" class="model-answer hidden"><h3>모범답안</h3><p>${escapeHtml(question.answer)}</p>`+
      `<div class="judge-actions"><button type="button" data-judge="correct">정답</button><button type="button" data-judge="wrong">오답</button></div></section></article>`;
  }
  function bind(question) {
    app.querySelector('[data-action="prev"]')?.addEventListener('click', () => move(-1));
    app.querySelector('[data-action="next"]')?.addEventListener('click', () => move(1));
    app.querySelector('.jump')?.addEventListener('change', event => {
      index = Number(event.target.value) - 1; saveIndex(questions().length); render();
    });
    app.querySelector('[data-action="reset"]')?.addEventListener('click', () => {
      if (!confirm(`${config.subject}과목 오답을 모두 삭제할까요?`)) return;
      localStorage.removeItem(wrongKey); index = 0; render();
    });
    app.querySelector('[data-action="reveal"]')?.addEventListener('click', () => {
      const answer = app.querySelector('#written-answer');
      if (!answer.value.trim()) { answer.focus(); return; }
      app.querySelector('#model-answer').classList.remove('hidden');
      answer.readOnly = true;
    });
    app.querySelectorAll('[data-judge]').forEach(button => button.addEventListener('click', () => {
      if (locked || app.querySelector('#model-answer').classList.contains('hidden')) return;
      const isCorrect = button.dataset.judge === 'correct';
      locked = true; mark(question, isCorrect); finishQuestion(isCorrect);
    }));
    app.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => {
      if (locked) return; locked = true;
      const selected = String(button.dataset.choice); const correct = String(question.answer);
      const isCorrect = selected === correct; mark(question, isCorrect);
      app.querySelectorAll('[data-choice]').forEach(choice => {
        choice.disabled = true;
        if (choice.dataset.choice === correct) choice.classList.add('correct');
      });
      if (!isCorrect) button.classList.add('wrong');
      app.querySelector('#feedback').innerHTML = `<p class="feedback ${isCorrect ? 'ok' : 'bad'}">${isCorrect ? '정답입니다.' : `오답입니다. 정답은 ${symbols[correct]}입니다.`}</p>`+
        `<div class="nav-actions"><button type="button" class="primary" data-action="continue">다음 문제</button></div>`;
      app.querySelector('[data-action="continue"]').addEventListener('click', () => finishQuestion(isCorrect));
    }));
  }
  function render() {
    locked = false; const list = questions(); saveIndex(list.length);
    if (!list.length) {
      app.innerHTML = `<section class="empty-card"><h2>누적된 오답이 없습니다.</h2><p>전체 CBT에서 틀린 문항이 여기에 자동으로 모입니다.</p><a href="../../${config.subject}과목/">${config.subject}과목 전체 CBT로 이동</a></section>`;
      return;
    }
    const question = list[index];
    app.innerHTML = config.subject === 4 ? written(question, list) : objective(question, list);
    bind(question);
  }
  render();
})();

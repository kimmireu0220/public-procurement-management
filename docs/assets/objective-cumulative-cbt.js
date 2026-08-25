(function () {
  'use strict';
  const config = window.CBT_CONFIG;
  const bank = Array.isArray(window.CBT_BANK) ? window.CBT_BANK : [];
  const app = document.getElementById('cbt-app');
  const wrongKey = `ppm_cbt_wrong_subject_${config.subject}_v1`;
  const progressKey = `ppm_cbt_progress_subject_${config.subject}_${config.mode}_v1`;
  const symbols = {1:'①',2:'②',3:'③',4:'④'};
  let index = readIndex();
  let locked = false;

  function safeGet(key, fallback) {
    try { return localStorage.getItem(key) ?? fallback; }
    catch (_) { return fallback; }
  }
  function safeSet(key, value) {
    try { localStorage.setItem(key, value); }
    catch (_) {}
  }
  function safeRemove(key) {
    try { localStorage.removeItem(key); }
    catch (_) {}
  }
  function readIndex() {
    const value = Number.parseInt(safeGet(progressKey, '0'), 10);
    return Number.isFinite(value) && value >= 0 ? value : 0;
  }
  function readWrong() {
    try {
      const parsed = JSON.parse(safeGet(wrongKey, '[]'));
      return new Set(Array.isArray(parsed) ? parsed.filter(item => typeof item === 'string') : []);
    } catch (_) {
      return new Set();
    }
  }
  function writeWrong(set) { safeSet(wrongKey, JSON.stringify([...set])); }
  function questions() {
    if (config.mode !== 'wrong') return bank;
    const wrong = readWrong();
    return bank.filter(question => wrong.has(question.id));
  }
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  }
  function displayGroup(value) {
    return String(value || '').replace(/^Part\s*(\d+)\s*Ch(?:apter)?\s*(\d+)$/i, 'Part $1 · Chapter $2');
  }
  function saveIndex(total) {
    index = total ? Math.max(0, Math.min(Math.trunc(index), total - 1)) : 0;
    safeSet(progressKey, String(index));
  }
  function updateWrongCount() {
    const count = app.querySelector('[data-wrong-count]');
    if (count) count.textContent = readWrong().size.toLocaleString('ko-KR');
  }
  function mark(question, isCorrect) {
    const wrong = readWrong();
    if (isCorrect) {
      if (config.mode === 'wrong') wrong.delete(question.id);
    } else {
      wrong.add(question.id);
    }
    writeWrong(wrong);
    updateWrongCount();
  }
  function focusQuestion() {
    const stem = app.querySelector('.stem');
    if (stem) stem.focus({preventScroll:true});
  }
  function move(delta) {
    const total = questions().length;
    index += delta;
    saveIndex(total);
    render();
    focusQuestion();
  }
  function finishQuestion(wasCorrect) {
    const total = questions().length;
    if (config.mode === 'wrong') {
      if (!total) index = 0;
      else if (wasCorrect) index = index >= total ? 0 : index;
      else index = (index + 1) % total;
    } else if (index < total - 1) {
      index += 1;
    }
    saveIndex(total);
    render();
    focusQuestion();
  }
  function toolbar(list) {
    const current = index + 1;
    const wrong = readWrong().size.toLocaleString('ko-KR');
    const reset = config.mode === 'wrong'
      ? `<button type="button" class="danger" data-action="reset">${config.subject}과목 오답 초기화</button>`
      : '';
    return `<nav class="toolbar" aria-label="문항 이동"><div class="progress-block"><div class="progress-copy">`+
      `<strong>${current.toLocaleString('ko-KR')} / ${list.length.toLocaleString('ko-KR')}</strong>`+
      `<span class="wrong-summary">누적 오답 <b data-wrong-count>${wrong}</b>개</span></div>`+
      `<progress class="question-progress" value="${current}" max="${list.length}" aria-label="전체 문항 진행률"></progress></div>`+
      `<div class="toolbar-controls"><button type="button" data-action="prev" ${index === 0 ? 'disabled' : ''}>← 이전</button>`+
      `<label class="jump-label"><span>문항</span><input class="jump" type="number" inputmode="numeric" min="1" max="${list.length}" value="${current}" aria-label="이동할 문항"></label>`+
      `<button type="button" data-action="next" ${index >= list.length - 1 ? 'disabled' : ''}>다음 →</button>${reset}</div></nav>`;
  }
  function questionHtml(question, list) {
    return toolbar(list) + `<article class="question-card"><div class="meta"><span>${escapeHtml(displayGroup(question.group))}</span><span>${question.no}번</span></div>`+
      `<h2 class="stem" id="question-stem" tabindex="-1">${escapeHtml(question.stem)}</h2><div class="choices" aria-labelledby="question-stem">${question.choices.map(choice =>
        `<button type="button" class="choice" data-choice="${choice.key}"><span class="symbol">${escapeHtml(choice.label || symbols[choice.key])}</span><span>${escapeHtml(choice.text)}</span></button>`
      ).join('')}</div><div id="feedback" role="status" aria-live="polite" aria-atomic="true" tabindex="-1"></div>`+
      `<p class="keyboard-hint">숫자 키 1–4로 답안 선택 · ← → 문항 이동</p></article>`;
  }
  function bind(question) {
    app.querySelector('[data-action="prev"]')?.addEventListener('click', () => move(-1));
    app.querySelector('[data-action="next"]')?.addEventListener('click', () => move(1));
    app.querySelector('.jump')?.addEventListener('change', event => {
      const value = Number.parseInt(event.target.value, 10);
      index = Number.isFinite(value) ? value - 1 : index;
      saveIndex(questions().length);
      render();
      focusQuestion();
    });
    app.querySelector('[data-action="reset"]')?.addEventListener('click', () => {
      if (!confirm(`${config.subject}과목 오답을 모두 삭제할까요?`)) return;
      safeRemove(wrongKey);
      index = 0;
      render();
    });
    app.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => {
      if (locked) return;
      locked = true;
      const selected = String(button.dataset.choice);
      const correct = String(question.answer);
      const isCorrect = selected === correct;
      mark(question, isCorrect);
      app.querySelectorAll('[data-choice]').forEach(choice => {
        choice.disabled = true;
        if (choice.dataset.choice === correct) choice.classList.add('correct');
      });
      if (!isCorrect) button.classList.add('wrong');
      const removed = isCorrect && config.mode === 'wrong';
      const message = removed
        ? '정답입니다. 오답 목록에서 제거했습니다.'
        : isCorrect ? '정답입니다.' : `오답입니다. 정답은 ${symbols[correct]}입니다.`;
      const feedback = app.querySelector('#feedback');
      feedback.innerHTML = `<p class="feedback ${isCorrect ? 'ok' : 'bad'}">${message}</p>`+
        `<div class="nav-actions"><button type="button" class="primary" data-action="continue">다음 문제 →</button></div>`;
      feedback.focus({preventScroll:true});
      feedback.querySelector('[data-action="continue"]').addEventListener('click', () => finishQuestion(isCorrect));
    }));
  }
  function render() {
    locked = false;
    const list = questions();
    saveIndex(list.length);
    if (!list.length) {
      app.innerHTML = config.mode === 'wrong'
        ? `<section class="empty-card" role="status"><h2>누적된 오답이 없습니다.</h2><p>전체 CBT에서 틀린 문항이 여기에 자동으로 모입니다.</p><a href="../../${config.subject}과목/">${config.subject}과목 전체 CBT로 이동</a></section>`
        : `<section class="empty-card" role="alert"><h2>문제은행을 불러오지 못했습니다.</h2><p>페이지를 새로고침한 뒤 다시 시도해 주세요.</p></section>`;
      return;
    }
    const question = list[index];
    app.innerHTML = questionHtml(question, list);
    bind(question);
  }
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target.matches('input, textarea')) return;
    if (!locked && /^[1-4]$/.test(event.key)) {
      const choice = app.querySelector(`[data-choice="${event.key}"]`);
      if (choice) { event.preventDefault(); choice.click(); }
    } else if (!locked && event.key === 'ArrowLeft') {
      const previous = app.querySelector('[data-action="prev"]:not(:disabled)');
      if (previous) { event.preventDefault(); previous.click(); }
    } else if (!locked && event.key === 'ArrowRight') {
      const next = app.querySelector('[data-action="next"]:not(:disabled)');
      if (next) { event.preventDefault(); next.click(); }
    }
  });
  render();
})();

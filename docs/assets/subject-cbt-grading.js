(function () {
  const SYMBOL_TO_KEY = { '①': '1', '②': '2', '③': '3', '④': '4' };
  const KEY_TO_SYMBOL = { '1': '①', '2': '②', '3': '③', '4': '④' };

  function renderResult() {
    const endScreen = document.getElementById('screen-end');
    if (!endScreen || endScreen.style.display === 'none' || document.getElementById('grading-result')) return;

    let answers = {};
    try {
      answers = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (error) {}

    const answerKey = (window.CBT_ANSWER_KEY || []).map(symbol => SYMBOL_TO_KEY[symbol]);
    const correctCount = QUESTIONS.reduce((total, question, index) => (
      total + (String(answers[question.no] || '') === answerKey[index] ? 1 : 0)
    ), 0);
    const answeredCount = Object.keys(answers).length;

    const result = document.createElement('section');
    result.id = 'grading-result';
    result.innerHTML = '<h3>채점 결과</h3>' +
      '<p class="grading-score"><strong>' + correctCount + ' / ' + QUESTIONS.length + '</strong>문항 정답</p>' +
      '<p class="grading-summary">응답 ' + answeredCount + '문항 · 미답 ' + (QUESTIONS.length - answeredCount) + '문항</p>' +
      '<div class="grading-grid">' + QUESTIONS.map(function (question, index) {
        const selected = String(answers[question.no] || '');
        const correct = answerKey[index];
        const isCorrect = selected === correct;
        return '<div class="grading-item ' + (isCorrect ? 'correct' : 'wrong') + '">' +
          '<strong>' + question.no + '번 ' + (isCorrect ? '정답' : '오답') + '</strong>' +
          '<span>선택 ' + (KEY_TO_SYMBOL[selected] || '미답') + ' · 정답 ' + KEY_TO_SYMBOL[correct] + '</span></div>';
      }).join('') + '</div>';

    const card = endScreen.querySelector('.end-card');
    card.insertBefore(result, card.querySelector('.hint'));
  }

  const style = document.createElement('style');
  style.textContent = '#grading-result{margin:1rem 0 1.4rem;padding:1.1rem;border:1px solid var(--border);border-radius:8px;background:#f8fbff}' +
    '#grading-result h3{margin:0 0 .35rem;color:var(--primary-dark)}.grading-score{margin:.2rem 0;font-size:1.05rem}.grading-score strong{margin-right:.35rem;color:var(--primary);font-size:1.5rem}' +
    '.grading-summary{margin:0 0 .85rem;color:var(--muted);font-size:.88rem}.grading-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:.45rem}' +
    '.grading-item{display:flex;flex-direction:column;padding:.55rem .65rem;border-radius:6px;font-size:.82rem}.grading-item.correct{background:#e7f6ec;color:#176235}.grading-item.wrong{background:#fff0ef;color:#9d2922}.grading-item span{margin-top:.15rem}';
  document.head.appendChild(style);

  const endScreen = document.getElementById('screen-end');
  if (endScreen) {
    new MutationObserver(renderResult).observe(endScreen, { attributes: true, attributeFilter: ['style'] });
  }
  document.getElementById('btn-submit')?.addEventListener('click', function () { setTimeout(renderResult, 0); });
})();

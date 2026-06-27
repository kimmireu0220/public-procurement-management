/* CBT 응시 — DOM 렌더링·이벤트 (UI 로직) */
(function (global) {
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function init(session) {
    const screenStart = document.getElementById('screen-start');
    const screenExam = document.getElementById('screen-exam');
    const screenEnd = document.getElementById('screen-end');
    const questionPanel = document.getElementById('question-panel');
    const navScroll = document.getElementById('nav-scroll');
    const timerEl = document.getElementById('timer');
    const subjectLabelEl = document.getElementById('subject-label');
    const progressLabelEl = document.getElementById('progress-label');
    const answeredCountEl = document.getElementById('answered-count');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const answerExportEl = document.getElementById('answer-export');

    function updateChoiceFocus() {
      if (!questionPanel) return;
      questionPanel.querySelectorAll('.choice').forEach((el, i) => {
        el.classList.toggle('focused', i === session.getChoiceFocus());
      });
      const focused = questionPanel.querySelector('.choice.focused');
      if (focused) focused.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function updateNav() {
      const questions = session.getQuestions();
      const current = session.getCurrentIndex();
      document.querySelectorAll('.nav-btn').forEach(btn => {
        const i = parseInt(btn.dataset.index, 10);
        const q = questions[i];
        btn.classList.remove('current', 'answered');
        if (i === current) {
          btn.classList.add('current');
          btn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else if (session.getAnswer(q.no)) {
          btn.classList.add('answered');
        }
      });
    }

    function updateCount() {
      const total = session.getQuestions().length;
      answeredCountEl.textContent = '답변 ' + session.getAnsweredCount() + ' / ' + total;
    }

    function renderNavGrid() {
      const questions = session.getQuestions();
      navScroll.innerHTML = '';
      let lastSubject = null;
      let sectionGrid = null;

      questions.forEach((q, i) => {
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
          navScroll.appendChild(section);
        }
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'nav-btn';
        btn.dataset.index = String(i);
        btn.textContent = q.no;
        btn.title = session.subjectLabel(q);
        btn.addEventListener('click', () => {
          session.goToIndex(i);
          renderQuestion();
        });
        sectionGrid.appendChild(btn);
      });
    }

    function renderQuestion() {
      const q = session.getCurrentQuestion();
      const selected = session.getAnswer(q.no);
      session.syncChoiceFocusFromAnswer();

      let html = '<div class="q-header"><span class="q-badge">' + q.no + '</span><span class="q-subject">' + session.subjectLabel(q) + '</span></div>';
      html += '<div class="q-stem">' + q.stem.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') + '</div>';
      html += '<div class="choices" id="choices">';
      q.choices.forEach((c, i) => {
        const sel = selected === c.key ? ' selected' : '';
        const foc = i === session.getChoiceFocus() ? ' focused' : '';
        html += '<label class="choice' + sel + foc + '" data-key="' + c.key + '" data-idx="' + i + '"><span class="num">' + c.label + '</span><span class="text">' + escapeHtml(c.text) + '</span><input type="radio" name="q" value="' + c.key + '"' + (sel ? ' checked' : '') + '></label>';
      });
      html += '</div>';
      questionPanel.innerHTML = html;

      questionPanel.querySelectorAll('.choice').forEach(el => {
        el.addEventListener('click', () => {
          session.selectAnswer(el.dataset.key);
          renderQuestion();
        });
      });

      subjectLabelEl.textContent = session.subjectLabel(q);
      progressLabelEl.textContent = (session.getCurrentIndex() + 1) + ' / ' + session.getQuestions().length;
      btnPrev.disabled = !session.canGoPrev();
      btnNext.disabled = !session.canGoNext();
      updateNav();
      updateCount();
      updateChoiceFocus();
    }

    function startTimer() {
      timerEl.textContent = session.formatTime(session.getTimerSec());
      session.startTimer((sec, timedOut) => {
        timerEl.textContent = session.formatTime(sec);
        if (sec <= 600) timerEl.classList.add('warn');
        if (timedOut) finishExam(true);
      });
    }

    function finishExam(auto) {
      if (!auto) {
        const left = session.getUnansweredCount();
        if (left > 0 && !confirm(session.finishConfirmMessage())) return;
      }
      session.stopExam();
      screenExam.style.display = 'none';
      screenEnd.style.display = 'block';
      answerExportEl.value = session.exportAnswers();
    }

    function handleExamKeydown(e) {
      if (!session.isExamActive()) return;
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

      const q = session.getCurrentQuestion();
      const n = q.choices.length;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        session.moveChoiceFocus(1);
        updateChoiceFocus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        session.moveChoiceFocus(-1);
        updateChoiceFocus();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (session.goPrev()) renderQuestion();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (session.goNext()) renderQuestion();
      } else if (e.key >= '1' && e.key <= '4') {
        const idx = parseInt(e.key, 10) - 1;
        if (idx < n) {
          e.preventDefault();
          session.selectAnswerByIndex(idx);
          renderQuestion();
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (session.goNext()) renderQuestion();
      }
    }

    document.getElementById('btn-start').addEventListener('click', () => {
      session.loadAnswers();
      screenStart.style.display = 'none';
      screenExam.style.display = 'flex';
      session.startExam();
      renderNavGrid();
      renderQuestion();
      startTimer();
    });

    document.addEventListener('keydown', handleExamKeydown);

    btnPrev.addEventListener('click', () => {
      if (session.goPrev()) renderQuestion();
    });

    document.getElementById('btn-reset').addEventListener('click', () => {
      if (!confirm(session.resetConfirmMessage())) return;
      session.resetSession();
      renderNavGrid();
      renderQuestion();
    });

    btnNext.addEventListener('click', () => {
      if (session.goNext()) renderQuestion();
    });

    document.getElementById('btn-submit').addEventListener('click', () => finishExam(false));

    document.getElementById('btn-copy').addEventListener('click', () => {
      answerExportEl.select();
      navigator.clipboard.writeText(answerExportEl.value).catch(() => {});
    });

    document.getElementById('btn-restart').addEventListener('click', () => {
      if (confirm('저장된 답안을 지우고 처음부터 다시 시작합니다.')) {
        session.clearStoredAnswers();
        location.reload();
      }
    });
  }

  global.CBTUI = { init };
})(window);

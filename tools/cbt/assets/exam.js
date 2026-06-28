/* CBT 응시 — 시험 상태·답안·타이머 (비즈니스 로직) */
(function (global) {
  const CHOICE_SYM = { 1: '①', 2: '②', 3: '③', 4: '④' };
  const DURATION_SEC = 120 * 60;

  function subjectLabel(q) {
    return q.subject + '과목 ' + q.subjectName;
  }

  function formatTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return [h, m, s].map(v => String(v).padStart(2, '0')).join(':').replace(/^00:/, '');
  }

  function createSession(questions, storageKey, durationSec) {
    const duration = durationSec || DURATION_SEC;
    let current = 0;
    let answers = {};
    let timerSec = duration;
    let timerId = null;
    let choiceFocus = 0;
    let examActive = false;

    function loadAnswers() {
      try {
        const s = localStorage.getItem(storageKey);
        if (s) answers = JSON.parse(s);
      } catch (e) {}
    }

    function saveAnswers() {
      localStorage.setItem(storageKey, JSON.stringify(answers));
    }

    function clearStoredAnswers() {
      localStorage.removeItem(storageKey);
    }

    function getQuestions() {
      return questions;
    }

    function getCurrentIndex() {
      return current;
    }

    function getCurrentQuestion() {
      return questions[current];
    }

    function getChoiceFocus() {
      return choiceFocus;
    }

    function setChoiceFocus(idx) {
      choiceFocus = idx;
    }

    function moveChoiceFocus(delta) {
      const n = getCurrentQuestion().choices.length;
      choiceFocus = (choiceFocus + delta + n) % n;
    }

    function syncChoiceFocusFromAnswer() {
      const q = getCurrentQuestion();
      const selected = answers[q.no];
      const selIdx = selected ? q.choices.findIndex(c => c.key === selected) : -1;
      choiceFocus = selIdx >= 0 ? selIdx : 0;
    }

    function getAnswer(no) {
      return answers[no];
    }

    function getAnsweredCount() {
      return Object.keys(answers).length;
    }

    function getUnansweredCount() {
      return questions.length - getAnsweredCount();
    }

    function canGoPrev() {
      return current > 0;
    }

    function canGoNext() {
      return current < questions.length - 1;
    }

    function goPrev() {
      if (!canGoPrev()) return false;
      current--;
      return true;
    }

    function goNext() {
      if (!canGoNext()) return false;
      current++;
      return true;
    }

    function goToIndex(index) {
      if (index < 0 || index >= questions.length) return false;
      current = index;
      return true;
    }

    function selectAnswer(key) {
      const q = getCurrentQuestion();
      answers[q.no] = key;
      saveAnswers();
      const idx = q.choices.findIndex(c => c.key === key);
      if (idx >= 0) choiceFocus = idx;

      const advanced = current < questions.length - 1;
      if (advanced) current++;
      return { advanced };
    }

    function selectAnswerByIndex(choiceIndex) {
      const q = getCurrentQuestion();
      if (choiceIndex < 0 || choiceIndex >= q.choices.length) return null;
      return selectAnswer(q.choices[choiceIndex].key);
    }

    function exportAnswers() {
      return questions.map(q => {
        const a = answers[q.no];
        const sym = CHOICE_SYM[a] || '?';
        return q.no + sym;
      }).join(' ');
    }

    function resetSession() {
      answers = {};
      clearStoredAnswers();
      current = 0;
      choiceFocus = 0;
    }

    function resetConfirmMessage() {
      const n = getAnsweredCount();
      return n > 0
        ? '선택한 답안 ' + n + '개를 모두 지우고 1번 문항부터 다시 시작합니다.'
        : '1번 문항부터 다시 시작합니다.';
    }

    function finishConfirmMessage() {
      const left = getUnansweredCount();
      return '미답 ' + left + '문항이 있습니다. 시험을 종료하시겠습니까?';
    }

    function startExam() {
      examActive = true;
    }

    function stopExam() {
      examActive = false;
      if (timerId !== null) {
        clearInterval(timerId);
        timerId = null;
      }
    }

    function isExamActive() {
      return examActive;
    }

    function getTimerSec() {
      return timerSec;
    }

    function startTimer(onTick) {
      timerId = setInterval(() => {
        timerSec--;
        onTick(timerSec);
        if (timerSec <= 0) {
          stopExam();
          onTick(0, true);
        }
      }, 1000);
    }

    return {
      CHOICE_SYM,
      DURATION_SEC: duration,
      subjectLabel,
      formatTime,
      loadAnswers,
      saveAnswers,
      clearStoredAnswers,
      getQuestions,
      getCurrentIndex,
      getCurrentQuestion,
      getChoiceFocus,
      setChoiceFocus,
      moveChoiceFocus,
      syncChoiceFocusFromAnswer,
      getAnswer,
      getAnsweredCount,
      getUnansweredCount,
      canGoPrev,
      canGoNext,
      goPrev,
      goNext,
      goToIndex,
      selectAnswer,
      selectAnswerByIndex,
      exportAnswers,
      resetSession,
      resetConfirmMessage,
      finishConfirmMessage,
      startExam,
      stopExam,
      isExamActive,
      getTimerSec,
      startTimer,
    };
  }

  global.CBTExam = { createSession, DURATION_SEC, formatTime };
})(window);

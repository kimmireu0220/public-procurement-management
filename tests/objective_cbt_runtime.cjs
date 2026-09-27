const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor() {
    this.children = new Map();
    this.listeners = {};
    this.classes = new Set();
    this.classList = {
      add: name => this.classes.add(name),
      toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name),
    };
  }
  set innerHTML(value) {
    this.html = value;
    this.children = new Map();
    for (const match of value.matchAll(/data-action="([^"]+)"/g)) {
      this.children.set(`[data-action="${match[1]}"]`, new Element());
    }
    for (const match of value.matchAll(/data-choice="([^"]+)"/g)) {
      const child = new Element();
      child.dataset = {choice: match[1]};
      this.children.set(`[data-choice="${match[1]}"]`, child);
    }
    for (const selector of ['#feedback', '.progress-jump', '.stem', '[data-wrong-count]']) {
      if (value.includes(selector === '#feedback' ? 'id="feedback"' : selector.slice(1))) {
        this.children.set(selector, new Element());
      }
    }
  }
  get innerHTML() { return this.html; }
  querySelector(selector) { return this.children.get(selector) || null; }
  querySelectorAll() { return [...this.children.entries()].filter(([key]) => key.startsWith('[data-choice=')).map(([, value]) => value); }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  setAttribute(name, value) { this[name] = value; }
  click() { this.listeners.click(); }
  focus() {}
}

const storage = new Map([['ppm_cbt_wrong_subject_1_v1', '["legacy"]']]);
const question = {id: 'photo:one', no: 1, group: '단원', stem: '문제는?', answer: null,
  choices: ['1', '2', '3', '4'].map(key => ({key, text: key}))};
function run(mode, bank, namespace = 'new-bank') {
  const app = new Element();
  vm.runInNewContext(fs.readFileSync('docs/assets/objective-cumulative-cbt.js', 'utf8'), {
    window: {CBT_CONFIG: {subject: 1, mode, storageNamespace: namespace}, CBT_BANK: bank, location: {search: ''}},
    document: {getElementById: () => app, addEventListener() {}},
    localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    URLSearchParams, confirm: () => true,
  });
  return app;
}
const key = 'ppm_cbt_new-bank_wrong_subject_1_v1';
let app = run('all', [question]);
app.querySelector('[data-choice="2"]').click();
assert.equal(storage.get(key), undefined, 'Unknown answer must not be graded as wrong');
assert.equal(app.querySelector('[data-choice="2"]').classes.has('selected'), true);
app.querySelector('#feedback').querySelector('[data-action="review"]').click();
assert.deepEqual(JSON.parse(storage.get(key)), [question.id]);
app = run('wrong', [question]);
app.querySelector('#feedback').querySelector('[data-action="review"]').click();
assert.deepEqual(JSON.parse(storage.get(key)), []);
assert.match(app.innerHTML, /누적된 오답이 없습니다/);
assert.equal(storage.get('ppm_cbt_wrong_subject_1_v1'), '["legacy"]');
app = run('all', [{...question, answer: '1'}], 'graded');
app.querySelector('[data-choice="2"]').click();
assert.deepEqual(JSON.parse(storage.get('ppm_cbt_graded_wrong_subject_1_v1')), [question.id]);
assert.equal(app.querySelector('[data-choice="1"]').classes.has('correct'), true);
app = run('wrong', [{...question, answer: '1'}], 'graded');
app.querySelector('[data-choice="1"]').click();
assert.deepEqual(JSON.parse(storage.get('ppm_cbt_graded_wrong_subject_1_v1')), []);
assert.match(app.innerHTML, /누적된 오답이 없습니다/);
console.log('Unknown-answer selection, manual wrong bank, storage isolation and grading: OK');

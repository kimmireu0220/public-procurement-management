"""필기_모의_문제.md 파싱 (CBT용 문항 데이터)."""

from __future__ import annotations

import re

Q_START = re.compile(r"^(\d+)\.\s+(.+)$")
CHOICE = re.compile(r"^\s*([①②③④])\s+(.+)$")
SUBJECT = re.compile(r"^##\s+(\d)과목\s+(.+?)\s+\(")
ID_TAG = re.compile(r"<!--\s*id:\s*([^>]+)\s*-->")

CHOICE_KEYS = {"①": "1", "②": "2", "③": "3", "④": "4"}

EXPECTED_QUESTION_COUNT = 80


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
                    choices.append(
                        {
                            "key": CHOICE_KEYS[label],
                            "label": label,
                            "text": cm.group(2).strip(),
                        }
                    )
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

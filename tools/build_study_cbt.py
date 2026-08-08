#!/usr/bin/env python3
"""문제은행 Part exam 풀 → 학습용 CBT HTML (GitHub Pages 배포 가능)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from cbt.builder import inline_json, load_asset  # noqa: E402
from cbt.profiles import DOCS, ROOT  # noqa: E402

BANK = {
    1: ("subject1.bank", "공공조달과 법제도 이해"),
    2: ("subject2.bank", "공공조달계획 수립 및 분석"),
    3: ("subject3.bank", "공공계약관리"),
}

CHOICE_KEYS = {"①": "1", "②": "2", "③": "3", "④": "4"}


def _import_bank(subject: int):
    mod_name, subject_name = BANK[subject]
    mod = __import__(mod_name, fromlist=["load_questions_index", "fetch_question"])
    return mod.load_questions_index, mod.fetch_question, subject_name


def slug(subject: int, part: int, stype: str) -> str:
    return f"{subject}과목-part{part}-{stype}"


def study_dir(subject: int, part: int, stype: str) -> Path:
    return ROOT / "output" / "study" / "cbt" / slug(subject, part, stype)


def docs_dir(subject: int, part: int, stype: str) -> Path:
    return DOCS / "study" / slug(subject, part, stype)


def collect_questions(subject: int, part: int, stype: str) -> list[dict]:
    load_index, fetch, subject_name = _import_bank(subject)
    idx = load_index()
    grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for sid in idx:
        s, p, ch, t, qn = sid.split(":")
        if int(s) != subject or p != str(part) or t != stype:
            continue
        grouped[int(ch)].append((int(qn), sid))

    questions: list[dict] = []
    no = 0
    for ch in sorted(grouped):
        for qn, sid in sorted(grouped[ch]):
            no += 1
            q, _ans = fetch(sid)
            questions.append(
                {
                    "no": no,
                    "subject": subject,
                    "subjectName": f"Part{part} Ch{ch}",
                    "stem": q["stem"],
                    "choices": [
                        {"key": CHOICE_KEYS[label], "label": label, "text": text}
                        for label, text in q["choices"]
                    ],
                    "id": sid,
                }
            )
    if not questions:
        raise SystemExit(f"no questions: subject={subject} part={part} stype={stype}")
    return questions


def render_study_html(questions: list[dict], title: str, subtitle: str, storage_key: str) -> str:
    shell = load_asset("study_shell.html")
    css = load_asset("styles.css")
    exam_js = load_asset("exam.js")
    ui_js = load_asset("ui.js")
    count = len(questions)
    html = shell
    html = html.replace("__TITLE__", title)
    html = html.replace("__SUBTITLE__", subtitle)
    html = html.replace("__QUESTION_COUNT__", str(count))
    html = html.replace("__STORAGE_KEY__", storage_key)
    html = html.replace("__QUESTIONS_JSON__", inline_json(questions))
    html = html.replace("__STYLES__", css)
    html = html.replace("__EXAM_JS__", exam_js)
    html = html.replace("__UI_JS__", ui_js)
    return html


def build_manifest(questions: list[dict], subject: int, part: int, stype: str) -> dict:
    _, fetch, _ = _import_bank(subject)
    items = []
    for q in questions:
        _, ans = fetch(q["id"])
        items.append({"exam_no": q["no"], "stable_id": q["id"], "answer": ans})
    return {
        "kind": "study",
        "subject": subject,
        "part": part,
        "stype": stype,
        "total": len(questions),
        "items": items,
    }


def build(subject: int, part: int, stype: str = "exam") -> Path:
    _, _, subject_name = _import_bank(subject)
    questions = collect_questions(subject, part, stype)
    out = study_dir(subject, part, stype)
    out.mkdir(parents=True, exist_ok=True)

    title = f"{subject}과목 Part{part} {stype.upper()} 학습"
    subtitle = f"{subject_name} · 문제은행 {stype} 전체"
    key = f"study_{subject}_p{part}_{stype}_answers"

    html = render_study_html(questions, title, subtitle, key)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(build_manifest(questions, subject, part, stype), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return out


def publish(subject: int, part: int, stype: str = "exam") -> Path:
    src = build(subject, part, stype)
    dest = docs_dir(subject, part, stype)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "index.html", dest / "index.html")
    (DOCS / ".nojekyll").touch()
    meta = {
        "kind": "study",
        "subject": subject,
        "part": part,
        "stype": stype,
        "source": str(src.relative_to(ROOT)),
        "note": "GitHub Pages — 문제은행 학습 CBT (정답 미포함)",
    }
    (dest / "study-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="문제은행 Part → 학습 CBT")
    parser.add_argument("--subject", "-s", type=int, default=1)
    parser.add_argument("--part", "-p", type=int, default=1)
    parser.add_argument("--stype", default="exam", choices=("exam",))
    parser.add_argument("--pages", action="store_true", help="docs/study/ 에 배포")
    args = parser.parse_args()

    if args.pages:
        dest = publish(args.subject, args.part, args.stype)
        print(f"GitHub Pages: {dest.relative_to(ROOT)}/index.html")
    else:
        out = build(args.subject, args.part, args.stype)
        n = json.loads((out / "manifest.json").read_text())["total"]
        print(f"study CBT: {n} questions → {out}")


if __name__ == "__main__":
    main()

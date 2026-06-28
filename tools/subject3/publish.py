"""3과목 전용 CBT → docs/3과목/ (GitHub Pages)."""

from __future__ import annotations

import json
import re
import shutil

from cbt.paths import SUBJECT_ROOTS
from cbt.profiles import SUBJECT3

ROUND_DIR = re.compile(r"^(\d+)회차$")


def find_latest_round() -> int:
    base = SUBJECT_ROOTS[3]
    rounds: list[int] = []
    if not base.is_dir():
        raise SystemExit(f"no 3과목 mock dir: {base}")
    for p in base.iterdir():
        if not p.is_dir():
            continue
        m = ROUND_DIR.match(p.name)
        if m and (p / "index.html").is_file() and (p / "필기_모의_문제.md").is_file():
            rounds.append(int(m.group(1)))
    if not rounds:
        raise SystemExit(f"no 3과목 mock round with CBT under {base}")
    return max(rounds)


def publish(round_no: int | None = None) -> int:
    k = round_no if round_no is not None else find_latest_round()
    src = SUBJECT3.round_dir(k) / "index.html"
    if not src.is_file():
        raise SystemExit(
            f"not found: {src} (run build_cbt_viewer.py --profile subject3 --round {k} first)"
        )

    dest = SUBJECT3.docs_index()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    (SUBJECT3.docs_index().parents[1] / ".nojekyll").touch()

    SUBJECT3.docs_meta().write_text(
        json.dumps(SUBJECT3.publish_meta(k), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return k

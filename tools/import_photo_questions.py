"""사진 OCR 검토 자료에서 네 선택지가 인식된 문항을 가져온다."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHOICE = re.compile(r"(?m)^([①②③④])\s*")


def extract_questions(drafts: list[dict], bank_id: str, subject: int) -> tuple[list[dict], list[dict]]:
    questions: list[dict] = []
    rejected = []
    seen = set()
    for draft in drafts:
        raw = draft["raw_question_text"].strip()
        choices = list(CHOICE.finditer(raw))
        if len(choices) != 4 or {match.group(1) for match in choices} != set("①②③④"):
            rejected.append({"photo": draft["photo"], "column": draft["column"], "reason": "네 선택지 미인식 또는 문항 경계 불확실"})
            continue
        stem = raw[:choices[0].start()].strip()
        if not stem or "?" not in stem or raw.count("?") != 1:
            rejected.append({"photo": draft["photo"], "column": draft["column"], "reason": "문제 문장 경계 불확실"})
            continue
        texts = [raw[match.end():choices[i + 1].start() if i < 3 else len(raw)].strip() for i, match in enumerate(choices)]
        if any(not text or "다음 중" in text or "다음 사례" in text for text in texts):
            rejected.append({"photo": draft["photo"], "column": draft["column"], "reason": "선택지 경계 불확실"})
            continue
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        def normalize(text: str) -> str:
            return re.sub(r"\s+", " ", re.sub(r"\s+[xX✓✔]\s*$", "", text)).strip()
        questions.append({
            "no": len(questions) + 1, "id": f"{bank_id}:{fingerprint}",
            "group": draft["group"], "stem": normalize(stem),
            "choices": sorted([
                {"key": str("①②③④".index(match.group(1)) + 1), "label": match.group(1), "text": normalize(text)}
                for match, text in zip(choices, texts)
            ], key=lambda choice: choice["key"]),
            "answer": None,
            "source": {"photo": draft["photo"], "column": draft["column"], "printedNumberOcr": draft["printed_no_ocr"], "subject": subject, "collectedAt": "2026-09-27", "permission": "사용자가 공개 재게시 허락이 있음을 확인", "transcription": "사진 OCR; 정답 미확인"},
        })
    return questions, rejected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bank-id", required=True)
    parser.add_argument("--subject", type=int, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    args = parser.parse_args()
    questions, rejected = extract_questions(json.loads(args.input.read_text(encoding="utf-8")), args.bank_id, args.subject)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.review_output.write_text(json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.bank_id}: 등록 {len(questions)}문항, 보류 {len(rejected)}건")


if __name__ == "__main__":
    main()

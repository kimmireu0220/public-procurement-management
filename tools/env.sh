#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$TOOLS_DIR/.." && pwd)"

if [[ -f "$DEFAULT_ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$DEFAULT_ROOT/.env"
  set +a
fi

export PROJECT_ROOT="${PROJECT_ROOT:-$DEFAULT_ROOT}"
export TEXTBOOK_IMAGES_DIR="${TEXTBOOK_IMAGES_DIR:-교재/1과목_공공조달의 이해}"
export OCR_DIR="${OCR_DIR:-output/ocr/1과목_공공조달의_이해}"
export AGENT_EXTRACT_DIR="${AGENT_EXTRACT_DIR:-output/agent_extract}"
export PROBLEM_BOOK_FINAL_DIR="${PROBLEM_BOOK_FINAL_DIR:-output/problem_book_final}"

resolve_path() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$PROJECT_ROOT/$value"
  fi
}

TEXTBOOK_IMAGES_PATH="$(resolve_path "$TEXTBOOK_IMAGES_DIR")"
OCR_OUTPUT_PATH="$(resolve_path "$OCR_DIR")"
AGENT_EXTRACT_PATH="$(resolve_path "$AGENT_EXTRACT_DIR")"
PROBLEM_BOOK_FINAL_PATH="$(resolve_path "$PROBLEM_BOOK_FINAL_DIR")"

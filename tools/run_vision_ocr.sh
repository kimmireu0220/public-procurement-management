#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

if [[ $# -lt 1 ]]; then
  echo "usage: run_vision_ocr.sh IMAGE_PATH" >&2
  exit 2
fi

IMAGE_PATH="$1"
if [[ "$IMAGE_PATH" != /* ]]; then
  IMAGE_PATH="$PROJECT_ROOT/$IMAGE_PATH"
fi

swift "$TOOLS_DIR/vision_ocr.swift" "$IMAGE_PATH"

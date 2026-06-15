#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

swift "$TOOLS_DIR/ocr_layout.swift" "$TEXTBOOK_IMAGES_PATH" "$OCR_OUTPUT_PATH"

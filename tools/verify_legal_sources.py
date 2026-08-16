#!/usr/bin/env python3
"""Verify the frozen official-law source manifest and snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "sources" / "현행_법령_근거" / "manifest.json"
REQUIRED_ENTRY_FIELDS = {
    "id",
    "title",
    "effective_date",
    "version",
    "category",
    "source_url",
    "snapshot",
    "sha256",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _effective_marker(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"시행 {parsed.year}. {parsed.month}. {parsed.day}."


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"manifest를 읽을 수 없습니다: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append("manifest 최상위 값은 객체여야 합니다.")
        return None
    return payload


def verify_manifest(manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    """Return every validation error; an empty list means the bundle is valid."""

    manifest_path = manifest_path.resolve()
    errors: list[str] = []
    payload = _load_json(manifest_path, errors)
    if payload is None:
        return errors

    if payload.get("schema_version") != 1:
        errors.append("schema_version은 1이어야 합니다.")

    retrieved_at = payload.get("retrieved_at")
    try:
        if not isinstance(retrieved_at, str):
            raise ValueError
        date.fromisoformat(retrieved_at)
    except ValueError:
        errors.append("retrieved_at은 YYYY-MM-DD 형식이어야 합니다.")

    provider = payload.get("provider")
    if not isinstance(provider, dict) or provider.get("base_url") != "https://www.law.go.kr/":
        errors.append("provider.base_url은 국가법령정보센터 HTTPS 주소여야 합니다.")

    entries = payload.get("sources")
    if not isinstance(entries, list) or not entries:
        errors.append("sources는 하나 이상의 항목을 가진 배열이어야 합니다.")
        return errors

    base_dir = manifest_path.parent
    snapshot_root = (base_dir / "snapshots").resolve()
    listed_snapshots: set[Path] = set()
    seen_ids: set[str] = set()

    for index, entry in enumerate(entries, start=1):
        label = f"sources[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: 객체여야 합니다.")
            continue

        missing_fields = sorted(REQUIRED_ENTRY_FIELDS - entry.keys())
        if missing_fields:
            errors.append(f"{label}: 필수 필드 누락: {', '.join(missing_fields)}")
            continue

        entry_id = entry["id"]
        if not isinstance(entry_id, str) or not entry_id:
            errors.append(f"{label}: id는 비어 있지 않은 문자열이어야 합니다.")
        elif entry_id in seen_ids:
            errors.append(f"{label}: 중복 id: {entry_id}")
        else:
            seen_ids.add(entry_id)
            label = entry_id

        source_url = entry["source_url"]
        if not isinstance(source_url, str) or not source_url.startswith(
            "https://www.law.go.kr/"
        ):
            errors.append(f"{label}: source_url은 국가법령정보센터 HTTPS 주소여야 합니다.")

        digest = entry["sha256"]
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            errors.append(f"{label}: sha256은 소문자 64자리 16진수여야 합니다.")

        try:
            marker = _effective_marker(entry["effective_date"])
        except (TypeError, ValueError):
            errors.append(f"{label}: effective_date는 YYYY-MM-DD 형식이어야 합니다.")
            marker = ""

        relative = entry["snapshot"]
        if not isinstance(relative, str):
            errors.append(f"{label}: snapshot은 상대 경로 문자열이어야 합니다.")
            continue
        snapshot = (base_dir / relative).resolve()
        if snapshot_root not in snapshot.parents:
            errors.append(f"{label}: snapshot은 snapshots/ 아래에 있어야 합니다: {relative}")
            continue
        if snapshot in listed_snapshots:
            errors.append(f"{label}: 중복 snapshot: {relative}")
        listed_snapshots.add(snapshot)

        try:
            raw = snapshot.read_bytes()
        except OSError as exc:
            errors.append(f"{label}: snapshot을 읽을 수 없습니다: {exc}")
            continue

        actual_digest = hashlib.sha256(raw).hexdigest()
        if actual_digest != digest:
            errors.append(
                f"{label}: SHA-256 불일치 (manifest={digest}, actual={actual_digest})"
            )

        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{label}: snapshot이 UTF-8 HTML이 아닙니다.")
            continue

        for field_name, expected in (
            ("title", entry["title"]),
            ("version", entry["version"]),
            ("effective_date", marker),
        ):
            if not isinstance(expected, str) or expected not in html:
                errors.append(f"{label}: snapshot에서 {field_name} 표기를 찾을 수 없습니다.")

        if isinstance(source_url, str):
            query = parse_qs(urlparse(source_url).query)
            source_ids = [
                value
                for key in ("lsiSeq", "admRulId", "admRulSeq")
                for value in query.get(key, [])
            ]
            if not source_ids:
                errors.append(f"{label}: source_url에 원문 식별자가 없습니다.")
            for source_id in source_ids:
                if source_id not in html:
                    errors.append(
                        f"{label}: source_url 식별자 {source_id}가 snapshot과 불일치합니다."
                    )

    if snapshot_root.is_dir():
        actual_snapshots = {path.resolve() for path in snapshot_root.glob("*.html")}
        for unlisted in sorted(actual_snapshots - listed_snapshots):
            errors.append(f"manifest에 없는 snapshot: {unlisted.name}")
        for missing_snapshot in sorted(listed_snapshots - actual_snapshots):
            if missing_snapshot.exists():
                continue
            errors.append(f"snapshots/에 없는 manifest 파일: {missing_snapshot.name}")
    else:
        errors.append(f"snapshot 디렉터리가 없습니다: {snapshot_root}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="검증할 manifest.json 경로",
    )
    args = parser.parse_args()
    errors = verify_manifest(args.manifest)
    if errors:
        print("현행 법령 근거 검증 실패:")
        for error in errors:
            print(f"- {error}")
        return 1
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(
        "현행 법령 근거 검증 통과: "
        f"{len(payload['sources'])}종, 수집일 {payload['retrieved_at']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

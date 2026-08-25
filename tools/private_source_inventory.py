#!/usr/bin/env python3
"""Build and verify metadata for local-only private source images."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / "sources" / "민간_박문각_수험서_jpg"
DEFAULT_MANIFEST = DEFAULT_SOURCE_ROOT / "inventory.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class SourceImage:
    path: str
    size: int
    sha256: str


class SourceInventoryError(ValueError):
    """Raised when the committed inventory metadata is invalid."""


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_payload(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, object]:
    source_root = source_root.resolve()
    images = []
    for path in sorted(source_root.rglob("*.jpg")):
        images.append(
            {
                "path": path.relative_to(source_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _digest(path),
            }
        )
    if not images:
        raise SourceInventoryError(f"인벤토리를 만들 JPG가 없습니다: {source_root}")
    return {
        "schema_version": 1,
        "visibility": "local-only",
        "root": "sources/민간_박문각_수험서_jpg",
        "images": images,
    }


def write_inventory(
    manifest_path: Path = DEFAULT_MANIFEST,
    source_root: Path = DEFAULT_SOURCE_ROOT,
) -> int:
    payload = build_payload(source_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    images = payload["images"]
    if not isinstance(images, list):
        raise AssertionError("build_payload images 형식 오류")
    return len(images)


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceInventoryError(f"인벤토리를 읽을 수 없습니다: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceInventoryError("인벤토리 최상위 값은 객체여야 합니다.")
    return payload


def load_inventory(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, SourceImage]:
    payload = _load_payload(manifest_path)
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version은 1이어야 합니다.")
    if payload.get("root") != "sources/민간_박문각_수험서_jpg":
        errors.append("root 경로가 예상값과 다릅니다.")

    raw_images = payload.get("images")
    if not isinstance(raw_images, list) or not raw_images:
        errors.append("images는 하나 이상의 항목을 가진 배열이어야 합니다.")
        raw_images = []

    inventory: dict[str, SourceImage] = {}
    for index, raw in enumerate(raw_images, start=1):
        label = f"images[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{label}: 객체여야 합니다.")
            continue
        path_value = raw.get("path")
        size = raw.get("bytes")
        sha256 = raw.get("sha256")
        if not isinstance(path_value, str):
            errors.append(f"{label}: path는 문자열이어야 합니다.")
            continue
        pure_path = PurePosixPath(path_value)
        if pure_path.is_absolute() or ".." in pure_path.parts or pure_path.suffix != ".jpg":
            errors.append(f"{label}: 안전한 JPG 상대 경로가 아닙니다: {path_value}")
            continue
        if path_value in inventory:
            errors.append(f"{label}: 중복 경로: {path_value}")
            continue
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            errors.append(f"{label}: bytes는 양의 정수여야 합니다.")
            continue
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            errors.append(f"{label}: sha256은 소문자 64자리 16진수여야 합니다.")
            continue
        inventory[path_value] = SourceImage(path_value, size, sha256)

    if errors:
        raise SourceInventoryError(" | ".join(errors))
    return inventory


def verify_inventory(
    manifest_path: Path = DEFAULT_MANIFEST,
    source_root: Path = DEFAULT_SOURCE_ROOT,
) -> tuple[list[str], bool]:
    """Return errors and whether local JPGs were available for full verification."""

    try:
        inventory = load_inventory(manifest_path)
    except SourceInventoryError as exc:
        return [str(exc)], False

    source_root = source_root.resolve()
    local_files = {
        path.relative_to(source_root).as_posix(): path
        for path in source_root.rglob("*.jpg")
    }
    if not local_files:
        return [], False

    errors: list[str] = []
    expected = set(inventory)
    actual = set(local_files)
    for missing in sorted(expected - actual):
        errors.append(f"로컬 원본 누락: {missing}")
    for unexpected in sorted(actual - expected):
        errors.append(f"인벤토리에 없는 로컬 원본: {unexpected}")
    for relative in sorted(expected & actual):
        entry = inventory[relative]
        path = local_files[relative]
        actual_size = path.stat().st_size
        if actual_size != entry.size:
            errors.append(
                f"크기 불일치: {relative} (inventory={entry.size}, actual={actual_size})"
            )
            continue
        actual_digest = _digest(path)
        if actual_digest != entry.sha256:
            errors.append(f"SHA-256 불일치: {relative}")
    return errors, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="로컬 JPG로 inventory.json 생성")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    args = parser.parse_args()

    if args.write:
        count = write_inventory(args.manifest, args.source_root)
        print(f"민간 원본 인벤토리 생성 완료: {count}개")
        return 0

    errors, checked_local = verify_inventory(args.manifest, args.source_root)
    if errors:
        print("민간 원본 인벤토리 검증 실패:")
        for error in errors:
            print(f"- {error}")
        return 1
    count = len(load_inventory(args.manifest))
    mode = "메타데이터+로컬 원본" if checked_local else "메타데이터"
    print(f"민간 원본 인벤토리 검증 통과: {count}개 ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

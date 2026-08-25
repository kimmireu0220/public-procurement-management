#!/usr/bin/env python3
"""Strict local ASR QA for raw WAV chunks in one MLX production cache.

This verifier intentionally compares each candidate only with the narration text.
It does not need, read, or score a PyTorch reference cache.  All selected WAVs are
validated before MLX Whisper is imported, then transcribed sequentially in this
single Python process.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPT_DIR / "generate_qwen3_tts.py"
COMPARE_PATH = SCRIPT_DIR / "compare_qwen3_tts_ab_asr.py"
VERIFIER_PATH = SCRIPT_DIR / "verify_qwen3_tts_audio.py"
DEFAULT_MAX_CHARS = 160
MIN_SIMILARITY = 0.80
MIN_REFERENCE_COVERAGE = 0.75
MIN_LENGTH_RATIO = 0.80
MAX_LENGTH_RATIO = 1.20
MAX_DECODE_DURATION_DELTA_SECONDS = 0.05
SCHEMA_VERSION = 1
SUPPORTED_CACHE_SCHEMA_VERSION = 1
CHUNK_NAME_RE = re.compile(r"^chunk_(\d{4})\.wav$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GROUP_SELECTOR_RE = re.compile(r"^group_(\d{4})\.commit\.json$")
GENERATION_NAME_RE = re.compile(r"^generation_[A-Za-z0-9_-]+$")

SPOKEN_LETTERS = {
    "에이치": "H",
    "더블유": "W",
    "에프": "F",
    "에이": "A",
    "브이": "V",
    "엑스": "X",
    "와이": "Y",
    "제트": "Z",
    "아이": "I",
    "제이": "J",
    "케이": "K",
    "에스": "S",
    "비": "B",
    "씨": "C",
    "디": "D",
    "이": "E",
    "지": "G",
    "엘": "L",
    "엠": "M",
    "엔": "N",
    "오": "O",
    "피": "P",
    "큐": "Q",
    "알": "R",
    "티": "T",
    "유": "U",
}
SPOKEN_DIGITS = {
    "제로": "0",
    "영": "0",
    "공": "0",
    "일": "1",
    "이": "2",
    "삼": "3",
    "사": "4",
    "오": "5",
    "육": "6",
    "칠": "7",
    "팔": "8",
    "구": "9",
}
LETTER_TOKEN_PATTERN = "|".join(
    re.escape(value) for value in sorted(SPOKEN_LETTERS, key=len, reverse=True)
)
DIGIT_TOKEN_PATTERN = "|".join(
    re.escape(value) for value in sorted(SPOKEN_DIGITS, key=len, reverse=True)
)
LETTER_RUN_PATTERN = rf"(?:{LETTER_TOKEN_PATTERN})(?:\s*(?:{LETTER_TOKEN_PATTERN}))*"
SPOKEN_DIGIT_RUN_PATTERN = rf"(?:(?:{DIGIT_TOKEN_PATTERN})){{2,}}"
DIGIT_FIELD_PATTERN = rf"(?:[0-9]+|{SPOKEN_DIGIT_RUN_PATTERN})"
EXPLICIT_CODE_SEPARATOR_PATTERN = r"(?:\s*(?:[,./:_-]|대시|하이픈|슬래시)\s*)"
STRONG_NUMERIC_CODE_SEPARATOR_PATTERN = (
    r"(?:\s*(?:[/:_-]|대시|하이픈|슬래시)\s*)"
)
LETTER_TO_DIGIT_SEPARATOR_PATTERN = EXPLICIT_CODE_SEPARATOR_PATTERN
CODE_TERMINATOR_PATTERN = (
    r"(?=$|[\s.,!?;:)\]}]|입니다|이며|이고|이고요|인|의|을|를|은|는|이|가|에|"
    r"에서|로|으로|와|과|도|만|부터|까지)"
)
STANDALONE_TERMINATOR_PATTERN = (
    r"(?=$|[.,!?;:)\]}]|입니다|이며|이고|이고요|인|의|을|를|은|는|이|가|에|"
    r"에서|로|으로|와|과|도|만|부터|까지)"
)
SPOKEN_ALPHANUMERIC_CODE_RE = re.compile(
    rf"(?P<letters>{LETTER_RUN_PATTERN})"
    rf"(?P<separator>{LETTER_TO_DIGIT_SEPARATOR_PATTERN})"
    rf"(?P<digits>{DIGIT_FIELD_PATTERN}"
    rf"(?:{EXPLICIT_CODE_SEPARATOR_PATTERN}{DIGIT_FIELD_PATTERN})*)"
    rf"{CODE_TERMINATOR_PATTERN}"
)
SPOKEN_NUMERIC_CODE_RE = re.compile(
    rf"(?P<digits>{DIGIT_FIELD_PATTERN}"
    rf"(?:{STRONG_NUMERIC_CODE_SEPARATOR_PATTERN}{DIGIT_FIELD_PATTERN})+)"
    rf"{CODE_TERMINATOR_PATTERN}"
)
CODE_CONTEXT_VALUE_RE = re.compile(
    rf"(?P<prefix>(?:(?:사업|요구|위험|증거|연계|추적)\s*)?"
    rf"(?:등급|코드|식별자|식별번호|아이디|번호)\s*"
    rf"(?:은|는|이|가|을|를|:)?\s*)"
    rf"(?P<value>{LETTER_RUN_PATTERN}|{SPOKEN_DIGIT_RUN_PATTERN})"
    rf"{STANDALONE_TERMINATOR_PATTERN}"
)


class MlxChunkQaError(RuntimeError):
    """Raised when a cache cannot be verified safely."""


class CodeAwareVerifier:
    """Delegate structural QA while canonicalizing only code-like text for scoring."""

    def __init__(self, verifier: ModuleType) -> None:
        self.verifier = verifier

    def __getattr__(self, name: str) -> Any:
        return getattr(self.verifier, name)

    def compare_transcript(
        self,
        reference: str,
        asr_result: dict[str, Any],
        duration_seconds: float,
        *,
        min_block_coverage: float,
        min_tail_coverage: float,
    ) -> dict[str, Any]:
        return compare_transcript_code_aware(
            self.verifier,
            reference,
            asr_result,
            duration_seconds,
            min_block_coverage=min_block_coverage,
            min_tail_coverage=min_tail_coverage,
        )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def read_json_object(path: Path, description: str) -> dict[str, Any]:
    if path.is_symlink():
        raise MlxChunkQaError(f"{description} must not be a symbolic link: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MlxChunkQaError(f"Unable to read {description}: {path}") from exc
    if not isinstance(payload, dict):
        raise MlxChunkQaError(f"{description} must be a JSON object: {path}")
    return payload


def decode_spoken_letters(value: str) -> str:
    compact = re.sub(r"\s+", "", value)
    tokens = sorted(SPOKEN_LETTERS, key=len, reverse=True)
    decoded: list[str] = []
    cursor = 0
    while cursor < len(compact):
        token = next(
            (candidate for candidate in tokens if compact.startswith(candidate, cursor)),
            None,
        )
        if token is None:
            raise MlxChunkQaError(f"Unable to decode spoken Latin letters: {value}")
        decoded.append(SPOKEN_LETTERS[token])
        cursor += len(token)
    return "".join(decoded)


def decode_spoken_digits(value: str) -> str:
    compact = re.sub(
        r"대시|하이픈|슬래시|[,./:_\-\s]", "", value, flags=re.IGNORECASE
    )
    tokens = sorted(SPOKEN_DIGITS, key=len, reverse=True)
    decoded: list[str] = []
    cursor = 0
    while cursor < len(compact):
        if compact[cursor].isdigit():
            end = cursor + 1
            while end < len(compact) and compact[end].isdigit():
                end += 1
            decoded.append(compact[cursor:end])
            cursor = end
            continue
        token = next(
            (candidate for candidate in tokens if compact.startswith(candidate, cursor)),
            None,
        )
        if token is None:
            raise MlxChunkQaError(f"Unable to decode spoken digits: {value}")
        decoded.append(SPOKEN_DIGITS[token])
        cursor += len(token)
    return "".join(decoded)


def canonicalize_code_equivalents(text: str) -> tuple[str, list[dict[str, str]]]:
    """Canonicalize conservative spoken-code spans, leaving ordinary Korean intact."""
    events: list[dict[str, str]] = []

    def replace_alphanumeric(match: re.Match[str]) -> str:
        canonical = decode_spoken_letters(match.group("letters")) + decode_spoken_digits(
            match.group("digits")
        )
        original = match.group(0)
        if canonical != original:
            events.append(
                {"kind": "spoken_alphanumeric_code", "original": original, "canonical": canonical}
            )
        return canonical

    def replace_numeric(match: re.Match[str]) -> str:
        canonical = decode_spoken_digits(match.group("digits"))
        original = match.group(0)
        if canonical != original:
            events.append(
                {"kind": "spoken_numeric_code", "original": original, "canonical": canonical}
            )
        return canonical

    def replace_context_value(match: re.Match[str]) -> str:
        value = match.group("value")
        if re.fullmatch(LETTER_RUN_PATTERN, value):
            canonical = decode_spoken_letters(value)
            kind = "contextual_spoken_latin"
        else:
            canonical = decode_spoken_digits(value)
            kind = "contextual_spoken_digits"
        if canonical != value:
            events.append({"kind": kind, "original": value, "canonical": canonical})
        return match.group("prefix") + canonical

    canonical = SPOKEN_ALPHANUMERIC_CODE_RE.sub(replace_alphanumeric, text)
    canonical = SPOKEN_NUMERIC_CODE_RE.sub(replace_numeric, canonical)
    canonical = CODE_CONTEXT_VALUE_RE.sub(replace_context_value, canonical)
    return canonical, events


def compare_transcript_code_aware(
    verifier: ModuleType,
    reference: str,
    asr_result: dict[str, Any],
    duration_seconds: float,
    *,
    min_block_coverage: float,
    min_tail_coverage: float,
) -> dict[str, Any]:
    canonical_reference, reference_events = canonicalize_code_equivalents(reference)
    raw_hypothesis = str(asr_result.get("text", ""))
    canonical_hypothesis, hypothesis_events = canonicalize_code_equivalents(
        raw_hypothesis
    )
    canonical_asr = dict(asr_result)
    canonical_asr["text"] = canonical_hypothesis
    canonical_segments: list[dict[str, Any]] = []
    for segment in asr_result.get("segments", []):
        if not isinstance(segment, dict):
            continue
        canonical_segment = dict(segment)
        canonical_segment["text"] = canonicalize_code_equivalents(
            str(segment.get("text", ""))
        )[0]
        canonical_segments.append(canonical_segment)
    canonical_asr["segments"] = canonical_segments
    comparison = verifier.compare_transcript(
        canonical_reference,
        canonical_asr,
        duration_seconds,
        min_block_coverage=min_block_coverage,
        min_tail_coverage=min_tail_coverage,
    )
    comparison["method"] = (
        "Conservative Korean-spoken code canonicalization, then "
        + str(comparison.get("method", "normalized transcript comparison"))
    )
    comparison["code_equivalence_normalization"] = {
        "version": 1,
        "scope": "code-like spans and explicit code/grade contexts only",
        "reference_replacements": reference_events,
        "asr_replacements": hypothesis_events,
        "canonical_reference_sha256": sha256_text(canonical_reference),
        "canonical_asr_sha256": sha256_text(canonical_hypothesis),
    }
    return comparison


def load_script(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise MlxChunkQaError(f"Unable to import project script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_generator_module() -> ModuleType:
    return load_script(GENERATOR_PATH, "qwen3_tts_mlx_chunk_qa_generator")


def load_compare_module() -> ModuleType:
    return load_script(COMPARE_PATH, "qwen3_tts_mlx_chunk_qa_compare")


def load_verifier_module() -> ModuleType:
    return load_script(VERIFIER_PATH, "qwen3_tts_mlx_chunk_qa_verifier")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify raw WAV chunks in one MLX Qwen3-TTS production cache against "
            "their Korean narration with one local MLX Whisper process."
        )
    )
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--candidate-cache-dir", type=Path, required=True)
    parser.add_argument(
        "--asr-model",
        type=Path,
        required=True,
        help="Existing local MLX Whisper model directory; downloads are never attempted",
    )
    parser.add_argument(
        "--chunk-indices",
        type=int,
        nargs="+",
        metavar="N",
        help="One-based chunks to inspect; omit to require and inspect the full cache",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help=(
            "Print only compact run metadata and totals; --output-json still receives "
            "the complete per-chunk report"
        ),
    )
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg executable")
    parser.add_argument("--min-similarity", type=float, default=MIN_SIMILARITY)
    parser.add_argument(
        "--min-reference-coverage", type=float, default=MIN_REFERENCE_COVERAGE
    )
    parser.add_argument("--min-length-ratio", type=float, default=MIN_LENGTH_RATIO)
    parser.add_argument("--max-length-ratio", type=float, default=MAX_LENGTH_RATIO)
    return parser.parse_args(argv)


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def validate_args(args: argparse.Namespace, invocation_dir: Path) -> argparse.Namespace:
    args.narration = resolve_path(args.narration, invocation_dir)
    args.candidate_cache_dir = resolve_path(args.candidate_cache_dir, invocation_dir)
    args.asr_model = resolve_path(args.asr_model, invocation_dir)
    if args.output_json is not None:
        args.output_json = resolve_path(args.output_json, invocation_dir)
    if not args.narration.is_file():
        raise MlxChunkQaError(f"Narration file not found: {args.narration}")
    if not args.candidate_cache_dir.is_dir():
        raise MlxChunkQaError(
            f"Candidate cache directory not found: {args.candidate_cache_dir}"
        )
    if not args.asr_model.is_dir():
        raise MlxChunkQaError(
            "--asr-model must be an existing local directory; downloads are disabled: "
            f"{args.asr_model}"
        )
    if args.chunk_indices is not None:
        if not args.chunk_indices or any(index < 1 for index in args.chunk_indices):
            raise MlxChunkQaError(
                "--chunk-indices must contain one-based positive integers"
            )
        if len(args.chunk_indices) != len(set(args.chunk_indices)):
            raise MlxChunkQaError("Duplicate chunk indices are not allowed")
    for name in ("min_similarity", "min_reference_coverage"):
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            raise MlxChunkQaError(f"--{name.replace('_', '-')} must be between 0 and 1")
    if args.min_length_ratio <= 0.0:
        raise MlxChunkQaError("--min-length-ratio must be greater than zero")
    if args.max_length_ratio < args.min_length_ratio:
        raise MlxChunkQaError(
            "--max-length-ratio must be at least --min-length-ratio"
        )
    return args


def observed_chunk_indices(cache_dir: Path) -> tuple[list[int], list[str]]:
    indices: list[int] = []
    malformed: list[str] = []
    for path in sorted(cache_dir.glob("chunk_*.wav")):
        match = CHUNK_NAME_RE.fullmatch(path.name)
        if match is None or int(match.group(1)) < 1:
            malformed.append(path.name)
        else:
            indices.append(int(match.group(1)))
    return indices, malformed


def select_requested_indices(
    chunk_indices: Sequence[int] | None, total_chunks: int
) -> list[int]:
    expected = list(range(1, total_chunks + 1))
    if chunk_indices is None:
        return expected
    selected = list(chunk_indices)
    outside = [index for index in selected if index > total_chunks]
    if outside:
        raise MlxChunkQaError(
            f"Chunk index/indices {outside} are outside the extracted range "
            f"1..{total_chunks}"
        )
    return selected


def resolve_flat_cache(
    cache_dir: Path,
    *,
    total_chunks: int,
    selected: Sequence[int],
    full_inventory_required: bool,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    observed, malformed = observed_chunk_indices(cache_dir)
    if malformed:
        raise MlxChunkQaError(
            "Malformed candidate chunk filename(s): " + ", ".join(malformed)
        )
    expected = list(range(1, total_chunks + 1))
    if full_inventory_required and observed != expected:
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        raise MlxChunkQaError(
            "Full candidate cache inventory mismatch: "
            f"expected={len(expected)}, observed={len(observed)}, "
            f"missing={missing}, unexpected={unexpected}"
        )
    bindings: dict[int, dict[str, Any]] = {}
    for index in selected:
        path = cache_dir / f"chunk_{index:04d}.wav"
        if not path.is_file():
            raise MlxChunkQaError(f"Candidate WAV not found for chunk {index}: {path}")
        bindings[index] = {
            "path": path,
            "recorded_wav_sha256": None,
            "cache_binding": {
                "cache_format": "flat-calibration",
                "relative_path": path.name,
            },
        }
    return (
        {
            "path": str(cache_dir),
            "format": "flat-calibration",
            "observed_chunk_indices": observed,
            "full_inventory_required": full_inventory_required,
        },
        bindings,
    )


def validate_identity_groups(
    identity: dict[str, Any], chunks: Sequence[str]
) -> list[dict[str, Any]]:
    batch_plan = identity.get("batch_plan")
    if not isinstance(batch_plan, dict):
        raise MlxChunkQaError("Versioned cache identity batch_plan is missing")
    algorithm = batch_plan.get("algorithm")
    groups = batch_plan.get("groups")
    if not isinstance(algorithm, str) or not algorithm:
        raise MlxChunkQaError("Versioned cache batch algorithm is invalid")
    if not isinstance(groups, list) or not groups:
        raise MlxChunkQaError("Versioned cache identity groups are missing")

    normalized_groups: list[dict[str, Any]] = []
    owners: dict[int, int] = {}
    for position, raw_group in enumerate(groups):
        if not isinstance(raw_group, dict):
            raise MlxChunkQaError(f"Identity group {position} is not an object")
        stable_index = raw_group.get("stable_index")
        length_bucket = raw_group.get("length_bucket")
        chunk_indices = raw_group.get("chunk_indices")
        character_lengths = raw_group.get("character_lengths")
        text_sha256s = raw_group.get("text_sha256s")
        fingerprint = raw_group.get("fingerprint")
        if type(stable_index) is not int or stable_index != position:
            raise MlxChunkQaError(
                f"Identity group stable index is invalid at position {position}"
            )
        if type(length_bucket) is not int or length_bucket < 0:
            raise MlxChunkQaError(f"Identity group {stable_index} length bucket is invalid")
        if (
            not isinstance(chunk_indices, list)
            or not chunk_indices
            or any(type(index) is not int or index < 1 for index in chunk_indices)
            or len(set(chunk_indices)) != len(chunk_indices)
        ):
            raise MlxChunkQaError(f"Identity group {stable_index} chunk indices are invalid")
        if (
            not isinstance(character_lengths, list)
            or len(character_lengths) != len(chunk_indices)
            or any(type(length) is not int or length < 1 for length in character_lengths)
        ):
            raise MlxChunkQaError(
                f"Identity group {stable_index} character lengths are invalid"
            )
        if (
            not isinstance(text_sha256s, list)
            or len(text_sha256s) != len(chunk_indices)
            or any(not isinstance(value, str) for value in text_sha256s)
        ):
            raise MlxChunkQaError(f"Identity group {stable_index} text hashes are invalid")
        if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
            raise MlxChunkQaError(f"Identity group {stable_index} fingerprint is invalid")

        expected_lengths: list[int] = []
        expected_hashes: list[str] = []
        for chunk_index in chunk_indices:
            if chunk_index > len(chunks):
                raise MlxChunkQaError(
                    f"Identity group {stable_index} contains out-of-range chunk {chunk_index}"
                )
            if chunk_index in owners:
                raise MlxChunkQaError(
                    f"Chunk {chunk_index} belongs to multiple identity groups "
                    f"{owners[chunk_index]} and {stable_index}"
                )
            owners[chunk_index] = stable_index
            expected_lengths.append(len(chunks[chunk_index - 1]))
            expected_hashes.append(sha256_text(chunks[chunk_index - 1]))
        if character_lengths != expected_lengths or text_sha256s != expected_hashes:
            raise MlxChunkQaError(
                f"Identity group {stable_index} does not match the narration chunks"
            )
        fingerprint_payload = {
            "algorithm": algorithm,
            "stable_index": stable_index,
            "length_bucket": length_bucket,
            "chunk_indices": chunk_indices,
            "character_lengths": character_lengths,
            "text_sha256s": text_sha256s,
        }
        if json_digest(fingerprint_payload) != fingerprint:
            raise MlxChunkQaError(
                f"Identity group {stable_index} fingerprint is stale or corrupt"
            )
        normalized_groups.append(
            {
                "stable_index": stable_index,
                "fingerprint": fingerprint,
                "chunk_indices": list(chunk_indices),
            }
        )
    expected_union = set(range(1, len(chunks) + 1))
    if set(owners) != expected_union:
        missing = sorted(expected_union - set(owners))
        unexpected = sorted(set(owners) - expected_union)
        raise MlxChunkQaError(
            "Identity group chunk union is not exact: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return normalized_groups


def safe_selected_generation_dir(
    cache_dir: Path, stable_group_index: int, value: Any
) -> tuple[Path, str]:
    if not isinstance(value, str):
        raise MlxChunkQaError(
            f"Selected generation directory is missing for group {stable_group_index}"
        )
    relative = Path(value)
    expected_parent = f"group_{stable_group_index:04d}_generations"
    if (
        relative.is_absolute()
        or len(relative.parts) != 2
        or relative.parts[0] != expected_parent
        or not GENERATION_NAME_RE.fullmatch(relative.parts[1])
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise MlxChunkQaError(
            f"Unsafe selected generation directory for group {stable_group_index}: {value}"
        )
    parent = cache_dir / expected_parent
    generation_dir = cache_dir / relative
    if parent.is_symlink() or generation_dir.is_symlink():
        raise MlxChunkQaError(
            f"Unsafe symbolic-link generation directory for group {stable_group_index}: {value}"
        )
    try:
        cache_resolved = cache_dir.resolve(strict=True)
        parent_resolved = parent.resolve(strict=True)
        generation_resolved = generation_dir.resolve(strict=True)
    except OSError as exc:
        raise MlxChunkQaError(
            f"Selected generation directory is missing for group {stable_group_index}: "
            f"{generation_dir}"
        ) from exc
    if (
        not generation_resolved.is_dir()
        or parent_resolved.parent != cache_resolved
        or generation_resolved.parent != parent_resolved
    ):
        raise MlxChunkQaError(
            f"Unsafe selected generation directory for group {stable_group_index}: {value}"
        )
    return generation_resolved, relative.as_posix()


def resolve_versioned_group(
    cache_dir: Path,
    *,
    cache_schema_version: int,
    cache_identity_sha256: str,
    group: dict[str, Any],
    chunks: Sequence[str],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    stable_index = group["stable_index"]
    fingerprint = group["fingerprint"]
    group_indices = group["chunk_indices"]
    selector_path = cache_dir / f"group_{stable_index:04d}.commit.json"
    selector = read_json_object(selector_path, "group selector")
    if (
        selector.get("schema_version") != cache_schema_version
        or selector.get("cache_identity_sha256") != cache_identity_sha256
        or selector.get("group_fingerprint") != fingerprint
        or selector.get("stable_group_index") != stable_index
    ):
        raise MlxChunkQaError(
            f"Group selector {stable_index} is stale or corrupt: {selector_path}"
        )
    generation_dir, generation_relative = safe_selected_generation_dir(
        cache_dir, stable_index, selector.get("generation_dir")
    )
    manifest_path = generation_dir / "generation.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise MlxChunkQaError(
            f"Selected generation manifest is missing for group {stable_index}: "
            f"{manifest_path}"
        )
    recorded_manifest_sha256 = selector.get("generation_manifest_sha256")
    if (
        not isinstance(recorded_manifest_sha256, str)
        or not SHA256_RE.fullmatch(recorded_manifest_sha256)
        or sha256_file(manifest_path) != recorded_manifest_sha256
    ):
        raise MlxChunkQaError(
            f"Selected generation manifest SHA is stale for group {stable_index}: "
            f"{manifest_path}"
        )
    manifest = read_json_object(manifest_path, "selected generation manifest")
    if (
        manifest.get("schema_version") != cache_schema_version
        or manifest.get("cache_identity_sha256") != cache_identity_sha256
        or manifest.get("group_fingerprint") != fingerprint
        or manifest.get("stable_group_index") != stable_index
    ):
        raise MlxChunkQaError(
            f"Selected generation manifest is stale or corrupt for group {stable_index}"
        )
    records = manifest.get("chunks")
    if not isinstance(records, list):
        raise MlxChunkQaError(
            f"Selected generation chunks are missing for group {stable_index}"
        )
    by_index: dict[int, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or type(record.get("chunk_index")) is not int:
            raise MlxChunkQaError(
                f"Selected generation chunk record is invalid for group {stable_index}"
            )
        chunk_index = record["chunk_index"]
        if chunk_index in by_index:
            raise MlxChunkQaError(
                f"Selected generation repeats chunk {chunk_index} in group {stable_index}"
            )
        by_index[chunk_index] = record
    if set(by_index) != set(group_indices) or len(by_index) != len(group_indices):
        raise MlxChunkQaError(
            f"Selected generation chunk index union is not exact for group {stable_index}"
        )
    observed, malformed = observed_chunk_indices(generation_dir)
    if malformed or observed != sorted(group_indices):
        raise MlxChunkQaError(
            f"Selected generation WAV inventory is not exact for group {stable_index}: "
            f"malformed={malformed}, observed={observed}, expected={sorted(group_indices)}"
        )

    selector_relative = selector_path.relative_to(cache_dir).as_posix()
    manifest_relative = manifest_path.relative_to(cache_dir).as_posix()
    selector_sha256 = sha256_file(selector_path)
    bindings: dict[int, dict[str, Any]] = {}
    for chunk_index in group_indices:
        record = by_index[chunk_index]
        expected_text_sha256 = sha256_text(chunks[chunk_index - 1])
        if record.get("text_sha256") != expected_text_sha256:
            raise MlxChunkQaError(
                f"Selected generation text hash is stale for chunk {chunk_index}"
            )
        wav_path = generation_dir / f"chunk_{chunk_index:04d}.wav"
        if wav_path.is_symlink() or not wav_path.is_file():
            raise MlxChunkQaError(
                f"Selected generation WAV is missing or unsafe for chunk {chunk_index}: "
                f"{wav_path}"
            )
        try:
            if wav_path.resolve(strict=True).parent != generation_dir:
                raise MlxChunkQaError(
                    f"Selected generation WAV escapes its directory: {wav_path}"
                )
        except OSError as exc:
            raise MlxChunkQaError(
                f"Selected generation WAV is missing for chunk {chunk_index}: {wav_path}"
            ) from exc
        recorded_wav_sha256 = record.get("sha256")
        if recorded_wav_sha256 is not None:
            if (
                not isinstance(recorded_wav_sha256, str)
                or not SHA256_RE.fullmatch(recorded_wav_sha256)
                or sha256_file(wav_path) != recorded_wav_sha256
            ):
                raise MlxChunkQaError(
                    f"Selected generation WAV SHA is stale for chunk {chunk_index}: "
                    f"{wav_path}"
                )
        bindings[chunk_index] = {
            "path": wav_path,
            "recorded_wav_sha256": recorded_wav_sha256,
            "cache_binding": {
                "cache_format": "versioned-immutable-groups",
                "stable_group_index": stable_index,
                "group_fingerprint": fingerprint,
                "selector": selector_relative,
                "selector_sha256": selector_sha256,
                "generation_dir": generation_relative,
                "generation_manifest": manifest_relative,
                "generation_manifest_sha256": recorded_manifest_sha256,
                "recorded_wav_sha256": recorded_wav_sha256,
            },
        }
    return bindings, {
        "stable_group_index": stable_index,
        "group_fingerprint": fingerprint,
        "selector_sha256": selector_sha256,
        "generation_dir": generation_relative,
        "generation_manifest_sha256": recorded_manifest_sha256,
        "chunk_indices": list(group_indices),
    }


def resolve_versioned_cache(
    cache_dir: Path,
    *,
    source_file_sha256: str,
    cleaned_text: str,
    chunks: Sequence[str],
    selected: Sequence[int],
    full_inventory_required: bool,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    identity_path = cache_dir / "cache_identity.json"
    payload = read_json_object(identity_path, "cache identity")
    cache_identity_sha256 = payload.get("cache_identity_sha256")
    identity = payload.get("identity")
    if (
        not isinstance(cache_identity_sha256, str)
        or not SHA256_RE.fullmatch(cache_identity_sha256)
        or not isinstance(identity, dict)
        or json_digest(identity) != cache_identity_sha256
    ):
        raise MlxChunkQaError(f"Cache identity digest is stale or corrupt: {identity_path}")
    cache_schema_version = identity.get("cache_schema_version")
    if cache_schema_version != SUPPORTED_CACHE_SCHEMA_VERSION:
        raise MlxChunkQaError(
            f"Unsupported versioned cache schema: {cache_schema_version}"
        )
    narration = identity.get("narration")
    settings = identity.get("settings")
    expected_chunk_hashes = [sha256_text(text) for text in chunks]
    if not isinstance(narration, dict) or not isinstance(settings, dict):
        raise MlxChunkQaError("Versioned cache narration/settings identity is missing")
    if (
        narration.get("speech_sha256") != source_file_sha256
        or narration.get("cleaned_sha256") != sha256_text(cleaned_text)
        or narration.get("cleaned_chars") != len(cleaned_text)
        or narration.get("chunk_text_sha256s") != expected_chunk_hashes
        or settings.get("max_chars") != DEFAULT_MAX_CHARS
    ):
        raise MlxChunkQaError(
            "Versioned cache identity does not match this narration/max_chars=160 request"
        )
    groups = validate_identity_groups(identity, chunks)
    selected_set = set(selected)
    relevant_groups = [
        group for group in groups if selected_set.intersection(group["chunk_indices"])
    ]
    if not relevant_groups:
        raise MlxChunkQaError("No versioned cache group contains the selected chunks")
    bindings: dict[int, dict[str, Any]] = {}
    group_summaries: list[dict[str, Any]] = []
    for group in relevant_groups:
        group_bindings, group_summary = resolve_versioned_group(
            cache_dir,
            cache_schema_version=cache_schema_version,
            cache_identity_sha256=cache_identity_sha256,
            group=group,
            chunks=chunks,
        )
        bindings.update(group_bindings)
        group_summaries.append(group_summary)
    selected_bindings = {index: bindings[index] for index in selected}
    return (
        {
            "path": str(cache_dir),
            "format": "versioned-immutable-groups",
            "full_inventory_required": full_inventory_required,
            "cache_identity_sha256": cache_identity_sha256,
            "identity_groups": len(groups),
            "resolved_groups": len(group_summaries),
            "resolved_group_indices": [
                summary["stable_group_index"] for summary in group_summaries
            ],
            "resolved_bindings_sha256": json_digest(group_summaries),
        },
        selected_bindings,
    )


def resolve_candidate_cache(
    cache_dir: Path,
    *,
    source_file_sha256: str,
    cleaned_text: str,
    chunks: Sequence[str],
    selected: Sequence[int],
    full_inventory_required: bool,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    identity_path = cache_dir / "cache_identity.json"
    versioned_markers = list(cache_dir.glob("group_*.commit.json")) or list(
        cache_dir.glob("group_*_generations")
    )
    if identity_path.is_file():
        return resolve_versioned_cache(
            cache_dir,
            source_file_sha256=source_file_sha256,
            cleaned_text=cleaned_text,
            chunks=chunks,
            selected=selected,
            full_inventory_required=full_inventory_required,
        )
    if identity_path.exists() or versioned_markers:
        raise MlxChunkQaError(
            f"Incomplete or unsafe versioned cache metadata: {identity_path}"
        )
    return resolve_flat_cache(
        cache_dir,
        total_chunks=len(chunks),
        selected=selected,
        full_inventory_required=full_inventory_required,
    )


def build_plan(
    args: argparse.Namespace, generator: ModuleType, compare: ModuleType
) -> dict[str, Any]:
    try:
        source_bytes = args.narration.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MlxChunkQaError(
            f"Narration must be a readable UTF-8 file: {args.narration}"
        ) from exc
    cleaned = generator.clean_narration(source_text)
    chunks = generator.split_narration(cleaned, DEFAULT_MAX_CHARS)
    if not chunks:
        raise MlxChunkQaError("Narration produced no speech chunks")
    selected = select_requested_indices(args.chunk_indices, len(chunks))
    cache_report, cache_bindings = resolve_candidate_cache(
        args.candidate_cache_dir,
        source_file_sha256=sha256_bytes(source_bytes),
        cleaned_text=cleaned,
        chunks=chunks,
        selected=selected,
        full_inventory_required=args.chunk_indices is None,
    )

    candidates: list[dict[str, Any]] = []
    for index in selected:
        binding = cache_bindings[index]
        path = binding["path"]
        text = chunks[index - 1]
        candidates.append(
            {
                "index": index,
                "text": text,
                "text_sha256": compare.sha256_text(text),
                "characters": len(text),
                "candidate_path": path,
                "recorded_wav_sha256": binding["recorded_wav_sha256"],
                "cache_binding": binding["cache_binding"],
            }
        )
    return {
        "source": {
            "path": str(args.narration),
            "file_sha256": sha256_bytes(source_bytes),
            "cleaned_text_sha256": sha256_text(cleaned),
            "cleaned_characters": len(cleaned),
            "total_chunks": len(chunks),
            "max_chars": DEFAULT_MAX_CHARS,
        },
        "cache": cache_report,
        "selected_chunk_indices": selected,
        "candidates": candidates,
    }


def evaluate_candidate(
    candidate: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    comparison = candidate["comparison"]
    issues = candidate["issue_counts"]
    duration_delta = float(candidate["decode"]["probe_duration_delta_seconds"])
    tail_clipped_samples = int(candidate["decode"].get("tail_clipped_samples", 0))
    strict_issues = {
        name: int(count)
        for name, count in issues.items()
        if name != "end_clipping"
    }
    raw_end_boundary_risk = int(issues.get("end_clipping", 0)) > 0
    criteria = {
        "similarity": {
            "value": float(comparison["similarity"]),
            "minimum": float(args.min_similarity),
            "passed": float(comparison["similarity"]) >= args.min_similarity,
        },
        "reference_coverage": {
            "value": float(comparison["reference_coverage"]),
            "minimum": float(args.min_reference_coverage),
            "passed": (
                float(comparison["reference_coverage"])
                >= args.min_reference_coverage
            ),
        },
        "length_ratio": {
            "value": float(comparison["length_ratio"]),
            "minimum": float(args.min_length_ratio),
            "maximum": float(args.max_length_ratio),
            "passed": (
                args.min_length_ratio
                <= float(comparison["length_ratio"])
                <= args.max_length_ratio
            ),
        },
        "decode_duration_delta": {
            "value_seconds": duration_delta,
            "maximum_seconds": MAX_DECODE_DURATION_DELTA_SECONDS,
            "passed": duration_delta <= MAX_DECODE_DURATION_DELTA_SECONDS,
        },
        "zero_strict_detected_issues": {
            "counts": strict_issues,
            "passed": all(count == 0 for count in strict_issues.values()),
        },
        "zero_tail_full_scale_samples": {
            "count": tail_clipped_samples,
            "passed": tail_clipped_samples == 0,
        },
        "raw_terminal_boundary_advisory": {
            "risk_detected": raw_end_boundary_risk,
            "strict_failure": False,
            "reason": (
                "Production merge appends exactly 250 ms silence after this raw chunk."
            ),
        },
    }
    failures: list[str] = []
    if not criteria["similarity"]["passed"]:
        failures.append("low_normalized_similarity")
    if not criteria["reference_coverage"]["passed"]:
        failures.append("low_reference_coverage")
    if not criteria["length_ratio"]["passed"]:
        failures.append("asr_reference_length_ratio_out_of_range")
    if not criteria["decode_duration_delta"]["passed"]:
        failures.append("decoded_duration_mismatch")
    issue_labels = {
        "omissions": "likely_omission",
        "repetitions": "likely_repetition",
        "tail_missing": "narration_tail_missing",
        "long_silence_regions": "long_silence_at_least_3_seconds",
    }
    failures.extend(
        label for name, label in issue_labels.items() if int(issues.get(name, 0)) > 0
    )
    if tail_clipped_samples:
        failures.append("digital_full_scale_samples_in_tail")
    advisories = (
        ["raw_terminal_boundary_risk_before_final_250ms_pad"]
        if raw_end_boundary_risk
        else []
    )
    return {
        "passed": not failures,
        "criteria": criteria,
        "failures": failures,
        "advisories": advisories,
    }


def build_report(
    args: argparse.Namespace,
    plan: dict[str, Any],
    *,
    ffmpeg: str,
    transcribe: Callable[..., dict[str, Any]],
    asr_version: str,
    compare: ModuleType,
    verifier: ModuleType,
) -> dict[str, Any]:
    chunk_reports: list[dict[str, Any]] = []
    code_aware_verifier = CodeAwareVerifier(verifier)
    for item in plan["candidates"]:
        candidate = compare.analyze_audio(
            audio=item["candidate_path"],
            expected_text=item["text"],
            model_path=args.asr_model,
            ffmpeg=ffmpeg,
            transcribe=transcribe,
            verifier=code_aware_verifier,
        )
        evaluation = evaluate_candidate(candidate, args)
        chunk_reports.append(
            {
                "index": item["index"],
                "text": item["text"],
                "text_sha256": item["text_sha256"],
                "characters": item["characters"],
                "cache_binding": item["cache_binding"],
                "candidate": candidate,
                "evaluation": evaluation,
            }
        )
    failed_indices = [
        chunk["index"] for chunk in chunk_reports if not chunk["evaluation"]["passed"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": not failed_indices,
        "comparison_mode": "candidate-versus-source-absolute-no-reference-cache",
        "source": plan["source"],
        "cache": plan["cache"],
        "asr": {
            "engine": "mlx_whisper",
            "version": asr_version,
            "model_path": str(args.asr_model),
            "language": "ko",
            "condition_on_previous_text": False,
            "same_process": True,
            "transcriptions": len(chunk_reports),
        },
        "thresholds": {
            "normalized_similarity": args.min_similarity,
            "reference_coverage": args.min_reference_coverage,
            "length_ratio": [args.min_length_ratio, args.max_length_ratio],
            "large_omission_block_coverage": compare.MIN_BLOCK_COVERAGE,
            "tail_coverage": compare.MIN_TAIL_COVERAGE,
            "long_silence_seconds": compare.LONG_SILENCE_SECONDS,
            "silence_db": compare.SILENCE_DB,
            "maximum_decode_duration_delta_seconds": (
                MAX_DECODE_DURATION_DELTA_SECONDS
            ),
            "raw_terminal_boundary_policy": (
                "advisory-only; production merge appends exactly 250 ms silence"
            ),
        },
        "summary": {
            "selected_chunks": len(chunk_reports),
            "passed_chunks": len(chunk_reports) - len(failed_indices),
            "failed_chunks": len(failed_indices),
            "failed_chunk_indices": failed_indices,
        },
        "chunks": chunk_reports,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def compact_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return production-friendly stdout fields without per-chunk payloads."""
    return {
        key: report[key]
        for key in ("ok", "source", "cache", "asr", "thresholds", "summary")
    }


def main(argv: Sequence[str] | None = None) -> int:
    args: argparse.Namespace | None = None
    try:
        args = validate_args(parse_args(argv), Path.cwd().resolve())
        generator = load_generator_module()
        compare = load_compare_module()
        verifier = load_verifier_module()
        plan = build_plan(args, generator, compare)
        # Validate every selected WAV before importing MLX Whisper or initializing Metal.
        for item in plan["candidates"]:
            observed = compare.probe_wav(item["candidate_path"])
            recorded_sha256 = item.get("recorded_wav_sha256")
            if recorded_sha256 is not None and observed.get("sha256") != recorded_sha256:
                raise MlxChunkQaError(
                    f"Selected generation WAV changed before ASR for chunk "
                    f"{item['index']}: {item['candidate_path']}"
                )
        ffmpeg = verifier.find_program(args.ffmpeg, "ffmpeg")
        transcribe, asr_version = compare.load_transcriber()
        report = build_report(
            args,
            plan,
            ffmpeg=ffmpeg,
            transcribe=transcribe,
            asr_version=asr_version,
            compare=compare,
            verifier=verifier,
        )
        if args.output_json is not None:
            atomic_write_json(args.output_json, report)
        stdout_report = compact_stdout_report(report) if args.summary_only else report
        print(json.dumps(stdout_report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        error = {"ok": False, "error": str(exc)}
        if args is not None and args.output_json is not None:
            try:
                atomic_write_json(args.output_json, error)
            except OSError:
                pass
        print(json.dumps(error, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

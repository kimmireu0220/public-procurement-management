#!/usr/bin/env python3
"""Generate the 25 Subject 4 chapters with MLX-Audio and safe hybrid adoption.

The MLX path intentionally uses a cache namespace and manifest separate from the
existing PyTorch generator.  A production MP3 is never overwritten: an existing
file must either be adopted from the current PyTorch manifest or verified as a
current MLX artifact from this script's committed group cache.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[4]
GENERATOR_PATH = Path(__file__).with_name("generate_qwen3_tts.py")
PYTORCH_BATCH_PATH = Path(__file__).with_name("generate_qwen3_tts_batch.py")
DEFAULT_CHAPTER_ROOT = REPO_ROOT / "output" / "chapter_lectures" / "4과목"
DEFAULT_AUDIO_ROOT = REPO_ROOT / "output" / "qwen3_tts_audio"
DEFAULT_MANIFEST_NAME = "4과목_Qwen3-TTS_Sohee_hybrid_manifest.json"
DEFAULT_PYTORCH_MANIFEST_NAME = "4과목_Qwen3-TTS_Sohee_manifest.json"
DEFAULT_MODEL_REPO_CACHE = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice"
)
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_INSTRUCT = "차분하고 명료한 한국어 강의 톤으로 또박또박 말해 주세요."
DEFAULT_MAX_CHARS = 160
DEFAULT_PAUSE_MS = 250
DEFAULT_SPEED = 1.0
DEFAULT_SEED = 1234
DEFAULT_TEMPERATURE = 0.9
DEFAULT_TOP_P = 1.0
DEFAULT_TOP_K = 50
DEFAULT_REPETITION_PENALTY = 1.05
DEFAULT_MAX_TOKENS = 1024
DEFAULT_BATCH_SIZE = 3
EXPECTED_SAMPLE_RATE = 24000
EXPECTED_CHANNELS = 1
EXPECTED_SAMPLE_WIDTH = 2
EXPECTED_MP3_BIT_RATE = 128000
LENGTH_BUCKET_CHARS = 16
TOKEN_LIMIT_GUARD_RATIO = 0.95
SAMPLES_PER_AUDIO_TOKEN = 1920
TAIL_PROBE_MS = 200
TAIL_PEAK_LIMIT = 512
TAIL_RMS_LIMIT = 64.0
ENGINE = "mlx-audio-qwen3-tts-custom-voice-direct-hf-bf16"
PYTORCH_ENGINE = "pytorch-qwen3-tts-custom-voice"
CACHE_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1

EXPECTED_INVENTORY = tuple(
    [f"P01-C{chapter:02d}" for chapter in range(1, 4)]
    + [f"P02-C{chapter:02d}" for chapter in range(1, 4)]
    + [f"P03-C{chapter:02d}" for chapter in range(1, 4)]
    + [f"P04-C{chapter:02d}" for chapter in range(1, 5)]
    + [f"P05-C{chapter:02d}" for chapter in range(1, 4)]
    + [f"P06-C{chapter:02d}" for chapter in range(1, 5)]
    + [f"P07-C{chapter:02d}" for chapter in range(1, 4)]
    + [f"P08-C{chapter:02d}" for chapter in range(1, 3)]
)


class MlxBatchError(RuntimeError):
    """Raised for an invalid inventory, cache, generation, or artifact."""


@dataclass(frozen=True)
class MlxRuntime:
    load_model: Callable[[Path], Any]
    write_audio: Callable[[Path, Any, int, str | None], None]
    set_seed: Callable[[int], None]
    versions: dict[str, str]


@dataclass(frozen=True)
class GroupPlan:
    stable_index: int
    seed: int
    length_bucket: int
    chunk_indices: tuple[int, ...]
    character_lengths: tuple[int, ...]
    text_sha256s: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class ChapterPlan:
    chapter: Any
    speech_sha256: str | None
    speech_chars: int | None
    cleaned_sha256: str | None
    cleaned_chars: int | None
    chunks: tuple[str, ...]
    groups: tuple[GroupPlan, ...]
    cache_identity: dict[str, Any] | None
    cache_identity_sha256: str | None
    request_fingerprint: str | None
    cache_dir: Path | None
    error: str | None = None

    @property
    def expected_chunks(self) -> int:
        return len(self.chunks)


@dataclass(frozen=True)
class ArtifactVerification:
    ok: bool
    reason: str | None
    metadata: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None


def _load_support_module(path: Path, name: str) -> ModuleType:
    existing = sys.modules.get(name)
    if isinstance(existing, ModuleType):
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise MlxBatchError(f"Unable to import support script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# These support modules have no eager Torch/MLX import.  Reusing their narration
# splitter and inventory naming keeps the PyTorch and MLX requests aligned.
GENERATOR = _load_support_module(GENERATOR_PATH, "_qwen3_tts_mlx_batch_generator")
PYTORCH_BATCH = _load_support_module(PYTORCH_BATCH_PATH, "_qwen3_tts_mlx_batch_pytorch")


def default_model_path() -> Path:
    override = os.environ.get("QWEN3_TTS_MLX_MODEL") or os.environ.get("QWEN3_TTS_MODEL")
    if override:
        return Path(override).expanduser()
    ref = DEFAULT_MODEL_REPO_CACHE / "refs" / "main"
    try:
        revision = ref.read_text(encoding="utf-8").strip()
    except OSError:
        revision = "0c0e3051f131929182e2c023b9537f8b1c68adfe"
    return DEFAULT_MODEL_REPO_CACHE / "snapshots" / revision


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate all 25 Subject 4 Sohee chapters with direct local HF BF16 "
            "weights through MLX-Audio."
        )
    )
    parser.add_argument("--chapter-root", type=Path, default=DEFAULT_CHAPTER_ROOT)
    parser.add_argument("--speech-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--pytorch-manifest", type=Path)
    parser.add_argument("--model", default=str(default_model_path()))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--instruct", default=DEFAULT_INSTRUCT)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--pause-ms", type=int, default=DEFAULT_PAUSE_MS)
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--top-p", type=float, default=DEFAULT_TOP_P)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--repetition-penalty", type=float, default=DEFAULT_REPETITION_PENALTY
    )
    parser.add_argument(
        "--max-tokens",
        "--max-new-tokens",
        dest="max_tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--chunks-only",
        action="store_true",
        help="Generate and commit raw WAV groups without creating the production MP3.",
    )
    parser.add_argument(
        "--regenerate-group",
        action="append",
        default=[],
        metavar="PXX-CXX:G",
        help=(
            "Atomically replace one 1-based length-bucket group with an alternate "
            "seed/batch composition; requires --chunks-only and matching --only."
        ),
    )
    parser.add_argument("--regenerate-seed-offset", type=int, default=10000)
    parser.add_argument("--regenerate-batch-size", type=int, default=2)
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PXX-CXX",
        help="Process only the selected chapter; may be repeated.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def resolve_arguments(args: argparse.Namespace, invocation_dir: Path) -> argparse.Namespace:
    args.chapter_root = resolve_path(args.chapter_root, invocation_dir)
    args.speech_root = resolve_path(args.speech_root, invocation_dir)
    args.output_root = resolve_path(args.output_root, invocation_dir)
    args.manifest = (
        resolve_path(args.manifest, invocation_dir)
        if args.manifest is not None
        else args.output_root / DEFAULT_MANIFEST_NAME
    )
    args.pytorch_manifest = (
        resolve_path(args.pytorch_manifest, invocation_dir)
        if args.pytorch_manifest is not None
        else args.output_root / DEFAULT_PYTORCH_MANIFEST_NAME
    )
    model = Path(args.model).expanduser()
    args.model = str(model.resolve() if model.is_absolute() else (invocation_dir / model).resolve())
    args.regenerate_groups = parse_regeneration_selectors(args.regenerate_group)
    validate_arguments(args)
    return args


def parse_regeneration_selectors(values: Sequence[str]) -> dict[str, set[int]]:
    selected: dict[str, set[int]] = {}
    for value in values:
        match = re.fullmatch(r"(P\d{2}-C\d{2}):(\d+)", value.upper())
        if match is None or int(match.group(2)) < 1:
            raise MlxBatchError(
                f"Invalid --regenerate-group {value!r}; expected PXX-CXX:G with G >= 1."
            )
        selected.setdefault(match.group(1), set()).add(int(match.group(2)))
    return selected


def validate_arguments(args: argparse.Namespace) -> None:
    if args.batch_size < 1:
        raise MlxBatchError("--batch-size must be 1 or greater.")
    if args.max_chars < 50:
        raise MlxBatchError("--max-chars must be at least 50.")
    if args.pause_ms != DEFAULT_PAUSE_MS:
        raise MlxBatchError("This production profile requires exactly --pause-ms 250.")
    if args.speed != DEFAULT_SPEED:
        raise MlxBatchError("This production profile requires --speed 1.0.")
    if not 0.0 < args.temperature <= 2.0:
        raise MlxBatchError("--temperature must be greater than 0 and at most 2.")
    if not 0.0 < args.top_p <= 1.0:
        raise MlxBatchError("--top-p must be greater than 0 and at most 1.")
    if args.top_k < 1:
        raise MlxBatchError("--top-k must be at least 1.")
    if not 0.5 <= args.repetition_penalty <= 2.0:
        raise MlxBatchError("--repetition-penalty must be between 0.5 and 2.")
    if args.max_tokens < 128:
        raise MlxBatchError("--max-tokens must be at least 128.")
    if args.regenerate_batch_size < 1:
        raise MlxBatchError("--regenerate-batch-size must be 1 or greater.")
    if args.regenerate_seed_offset < 1:
        raise MlxBatchError("--regenerate-seed-offset must be positive.")
    if args.regenerate_groups and not args.chunks_only:
        raise MlxBatchError("--regenerate-group requires --chunks-only.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def local_runtime_profile() -> dict[str, Any]:
    """Describe the MLX runtime without importing MLX or initializing Metal."""
    return {
        "engine": ENGINE,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {
            "mlx-audio": package_version("mlx-audio"),
            "mlx": package_version("mlx"),
            "mlx-metal": package_version("mlx-metal"),
            "transformers": package_version("transformers"),
        },
        "source_weights": "original-hugging-face-bfloat16",
        "batch_script_sha256": sha256_file(Path(__file__).resolve()),
    }


def load_mlx_runtime() -> MlxRuntime:
    """Import MLX only when a non-committed group actually needs generation."""
    import mlx.core as mx
    from mlx_audio.audio_io import write as audio_write
    from mlx_audio.tts.utils import load_model

    def write_audio(path: Path, audio: Any, sample_rate: int, output_format: str | None) -> None:
        audio_write(path, audio, sample_rate, format=output_format)

    return MlxRuntime(
        load_model=load_model,
        write_audio=write_audio,
        set_seed=mx.random.seed,
        versions={
            "mlx-audio": package_version("mlx-audio"),
            "mlx": package_version("mlx"),
            "mlx-metal": package_version("mlx-metal"),
            "transformers": package_version("transformers"),
        },
    )


def safetensors_dtypes(path: Path) -> set[str]:
    try:
        with path.open("rb") as handle:
            header_size_raw = handle.read(8)
            if len(header_size_raw) != 8:
                raise MlxBatchError(f"Invalid safetensors header: {path}")
            header_size = int.from_bytes(header_size_raw, "little")
            if header_size <= 0 or header_size > 256 * 1024 * 1024:
                raise MlxBatchError(f"Invalid safetensors header size: {path}")
            header = json.loads(handle.read(header_size).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MlxBatchError(f"Unable to inspect safetensors dtype: {path}") from exc
    if not isinstance(header, dict):
        raise MlxBatchError(f"Invalid safetensors tensor map: {path}")
    dtypes = {
        str(record["dtype"])
        for name, record in header.items()
        if name != "__metadata__"
        and isinstance(record, dict)
        and isinstance(record.get("dtype"), str)
    }
    if not dtypes:
        raise MlxBatchError(f"Safetensors file contains no tensor dtype records: {path}")
    return dtypes


def inspect_model(
    model_path: Path,
    speaker: str = DEFAULT_SPEAKER,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    if not model_path.is_dir():
        raise MlxBatchError(f"Direct local model directory not found: {model_path}")
    config = model_path / "config.json"
    if not config.is_file():
        raise MlxBatchError(f"Model config.json not found: {model_path}")
    try:
        config_payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MlxBatchError(f"Invalid model config.json: {config}") from exc
    if (
        config_payload.get("model_type") != "qwen3_tts"
        or config_payload.get("tts_model_type") != "custom_voice"
    ):
        raise MlxBatchError(f"Model is not a CustomVoice checkpoint: {model_path}")
    try:
        GENERATOR.validate_model_snapshot(model_path, speaker, language)
    except (OSError, ValueError) as exc:
        raise MlxBatchError(str(exc)) from exc
    safetensors = sorted(model_path.rglob("*.safetensors"))
    if not safetensors:
        raise MlxBatchError(f"No safetensors weights found under: {model_path}")
    generation_config = model_path / "generation_config.json"
    root_weights = model_path / "model.safetensors"
    root_dtypes = safetensors_dtypes(root_weights)
    if root_dtypes != {"BF16"}:
        raise MlxBatchError(
            f"Direct original model weights must be BF16; found {sorted(root_dtypes)} in "
            f"{root_weights}"
        )
    return {
        "path": str(model_path.resolve()),
        "format": "direct-original-hugging-face",
        "config_sha256": sha256_file(config),
        "generation_config_sha256": (
            sha256_file(generation_config) if generation_config.is_file() else None
        ),
        "root_weight_dtypes": sorted(root_dtypes),
        "safetensors_sha256": {
            path.relative_to(model_path).as_posix(): sha256_file(path)
            for path in safetensors
        },
    }


def discover_inventory(args: argparse.Namespace) -> list[Any]:
    try:
        chapters = PYTORCH_BATCH.discover_chapters(
            args.chapter_root, args.speech_root, args.output_root
        )
    except PYTORCH_BATCH.BatchError as exc:
        raise MlxBatchError(str(exc)) from exc
    keys = tuple(chapter.key for chapter in chapters)
    if keys != EXPECTED_INVENTORY:
        missing = sorted(set(EXPECTED_INVENTORY) - set(keys))
        extra = sorted(set(keys) - set(EXPECTED_INVENTORY))
        raise MlxBatchError(
            "Subject 4 inventory must contain the fixed 25 chapters; "
            f"found={len(keys)}, missing={missing}, extra={extra}"
        )
    return chapters


def select_chapters(chapters: list[Any], selectors: Sequence[str]) -> list[Any]:
    try:
        return PYTORCH_BATCH.select_chapters(chapters, list(selectors))
    except PYTORCH_BATCH.BatchError as exc:
        raise MlxBatchError(str(exc)) from exc


def generation_settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "speaker": args.speaker,
        "language": args.language,
        "instruct": args.instruct,
        "max_chars": args.max_chars,
        "pause_ms": args.pause_ms,
        "pause_policy": "after-every-raw-chunk-including-final",
        "speed": args.speed,
        "seed": args.seed,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "repetition_penalty": args.repetition_penalty,
        "max_tokens": args.max_tokens,
        "batch_size": args.batch_size,
        "group_override_policy": "atomic-whole-group-seed-and-batch-v1",
        "length_bucket_chars": LENGTH_BUCKET_CHARS,
        "token_limit_guard_ratio": TOKEN_LIMIT_GUARD_RATIO,
        "sample_rate": EXPECTED_SAMPLE_RATE,
        "channels": EXPECTED_CHANNELS,
        "sample_width_bytes": EXPECTED_SAMPLE_WIDTH,
        "mp3_bit_rate": EXPECTED_MP3_BIT_RATE,
    }


def build_group_plan(
    chunks: Sequence[str], batch_size: int, base_seed: int
) -> tuple[GroupPlan, ...]:
    """Create fixed groups from deterministic 16-character length buckets."""
    buckets: dict[int, list[tuple[int, str]]] = {}
    for chunk_index, text in enumerate(chunks, 1):
        bucket = (max(1, len(text)) - 1) // LENGTH_BUCKET_CHARS
        buckets.setdefault(bucket, []).append((chunk_index, text))
    raw_groups: list[tuple[int, list[tuple[int, str]]]] = []
    for bucket in sorted(buckets, reverse=True):
        items = sorted(buckets[bucket], key=lambda item: (-len(item[1]), item[0]))
        for offset in range(0, len(items), batch_size):
            raw_groups.append((bucket, items[offset : offset + batch_size]))
    groups: list[GroupPlan] = []
    for stable_index, (bucket, items) in enumerate(raw_groups):
        chunk_indices = tuple(index for index, _text in items)
        character_lengths = tuple(len(text) for _index, text in items)
        text_sha256s = tuple(sha256_text(text) for _index, text in items)
        payload = {
            "algorithm": "fixed-character-length-bucket-v1",
            "stable_index": stable_index,
            "length_bucket": bucket,
            "chunk_indices": chunk_indices,
            "character_lengths": character_lengths,
            "text_sha256s": text_sha256s,
        }
        groups.append(
            GroupPlan(
                stable_index=stable_index,
                seed=base_seed + stable_index,
                length_bucket=bucket,
                chunk_indices=chunk_indices,
                character_lengths=character_lengths,
                text_sha256s=text_sha256s,
                fingerprint=json_digest(payload),
            )
        )
    return tuple(groups)


def batch_plan_payload(groups: Sequence[GroupPlan], batch_size: int) -> dict[str, Any]:
    return {
        "algorithm": "fixed-character-length-bucket-v1",
        "bucket_width_chars": LENGTH_BUCKET_CHARS,
        "batch_size": batch_size,
        "groups": [
            {
                "stable_index": group.stable_index,
                "seed": group.seed,
                "length_bucket": group.length_bucket,
                "chunk_indices": list(group.chunk_indices),
                "character_lengths": list(group.character_lengths),
                "text_sha256s": list(group.text_sha256s),
                "fingerprint": group.fingerprint,
            }
            for group in groups
        ],
    }


def analyze_chapter(
    chapter: Any,
    args: argparse.Namespace,
    model_identity: dict[str, Any] | None,
    profile: dict[str, Any],
) -> ChapterPlan:
    if not chapter.speech_path.is_file():
        return ChapterPlan(
            chapter, None, None, None, None, (), (), None, None, None, None,
            "speech-ready text missing",
        )
    try:
        raw = chapter.speech_path.read_text(encoding="utf-8")
        cleaned = GENERATOR.clean_narration(raw)
        chunks = tuple(GENERATOR.split_narration(cleaned, args.max_chars))
    except (OSError, UnicodeError, ValueError) as exc:
        return ChapterPlan(
            chapter, None, None, None, None, (), (), None, None, None, None, str(exc)
        )
    if not chunks:
        return ChapterPlan(
            chapter,
            sha256_file(chapter.speech_path),
            len(raw),
            sha256_text(cleaned),
            len(cleaned),
            (),
            (),
            None,
            None,
            None,
            None,
            "speech text is empty",
        )
    groups = build_group_plan(chunks, args.batch_size, args.seed)
    if model_identity is None:
        return ChapterPlan(
            chapter,
            sha256_file(chapter.speech_path),
            len(raw),
            sha256_text(cleaned),
            len(cleaned),
            chunks,
            groups,
            None,
            None,
            None,
            None,
            None,
        )
    identity = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "engine": ENGINE,
        "profile": profile,
        "model": model_identity,
        "chapter": chapter.key,
        "narration": {
            "speech_sha256": sha256_file(chapter.speech_path),
            "cleaned_sha256": sha256_text(cleaned),
            "cleaned_chars": len(cleaned),
            "chunk_text_sha256s": [sha256_text(text) for text in chunks],
        },
        "settings": generation_settings(args),
        "batch_plan": batch_plan_payload(groups, args.batch_size),
    }
    identity_sha256 = json_digest(identity)
    request = {
        "chapter": chapter.key,
        "output_path": str(chapter.output_path),
        "cache_identity_sha256": identity_sha256,
    }
    cache_dir = chapter.output_path.parent / (
        f".{chapter.output_path.stem}_qwen3tts_mlx_{identity_sha256[:12]}"
    )
    return ChapterPlan(
        chapter=chapter,
        speech_sha256=identity["narration"]["speech_sha256"],
        speech_chars=len(raw),
        cleaned_sha256=identity["narration"]["cleaned_sha256"],
        cleaned_chars=len(cleaned),
        chunks=chunks,
        groups=groups,
        cache_identity=identity,
        cache_identity_sha256=identity_sha256,
        request_fingerprint=json_digest(request),
        cache_dir=cache_dir,
    )


def probe_wav(path: Path, *, allow_silence: bool = False) -> dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size < 1024:
            raise MlxBatchError(f"WAV is missing or too small: {path}")
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise MlxBatchError(f"Invalid WAV file {path}: {exc}") from exc
    if (
        channels != EXPECTED_CHANNELS
        or sample_width != EXPECTED_SAMPLE_WIDTH
        or sample_rate != EXPECTED_SAMPLE_RATE
        or frames <= 0
    ):
        raise MlxBatchError(
            f"Unexpected WAV format for {path}: channels={channels}, width={sample_width}, "
            f"sample_rate={sample_rate}, frames={frames}"
        )
    clipping_samples = 0
    peak_pcm16 = 0
    try:
        with wave.open(str(path), "rb") as handle:
            while True:
                block = handle.readframes(256 * 1024)
                if not block:
                    break
                values = array("h")
                values.frombytes(block[: len(block) // 2 * 2])
                if sys.byteorder != "little":
                    values.byteswap()
                if values:
                    block_peak = max(abs(value) for value in values)
                    peak_pcm16 = max(peak_pcm16, block_peak)
                    clipping_samples += sum(
                        value <= -32768 or value >= 32767 for value in values
                    )
    except (OSError, EOFError, wave.Error) as exc:
        raise MlxBatchError(f"Unable to scan WAV samples for clipping: {path}") from exc
    if clipping_samples:
        raise MlxBatchError(
            f"Digital clipping detected in {path}: {clipping_samples} full-scale samples"
        )
    if peak_pcm16 == 0 and not allow_silence:
        raise MlxBatchError(f"Generated WAV is digitally silent: {path}")
    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "peak_pcm16": peak_pcm16,
        "digital_clipping_samples": clipping_samples,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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
        fsync_directory(path.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MlxBatchError(f"Unable to read {description}: {path}") from exc
    if not isinstance(payload, dict):
        raise MlxBatchError(f"{description} must be a JSON object: {path}")
    return payload


def group_commit_path(plan: ChapterPlan, group: GroupPlan) -> Path:
    assert plan.cache_dir is not None
    return plan.cache_dir / f"group_{group.stable_index:04d}.commit.json"


def group_generation_root(plan: ChapterPlan, group: GroupPlan) -> Path:
    assert plan.cache_dir is not None
    return plan.cache_dir / f"group_{group.stable_index:04d}_generations"


def group_for_chunk(plan: ChapterPlan, chunk_index: int) -> GroupPlan:
    for group in plan.groups:
        if chunk_index in group.chunk_indices:
            return group
    raise MlxBatchError(
        f"Chunk {chunk_index} is outside the batch plan for {plan.chapter.key}."
    )


def selected_generation_dir(
    plan: ChapterPlan, group: GroupPlan, selector: dict[str, Any]
) -> Path:
    if plan.cache_dir is None:
        raise MlxBatchError(f"MLX cache unavailable for {plan.chapter.key}")
    value = selector.get("generation_dir")
    if not isinstance(value, str):
        raise MlxBatchError(
            f"Selected generation directory is missing for {plan.chapter.key}."
        )
    relative = Path(value)
    expected_parent = f"group_{group.stable_index:04d}_generations"
    if (
        relative.is_absolute()
        or len(relative.parts) != 2
        or relative.parts[0] != expected_parent
        or not relative.parts[1].startswith("generation_")
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise MlxBatchError(
            f"Unsafe selected generation directory for {plan.chapter.key}: {value}"
        )
    path = plan.cache_dir / relative
    if not path.is_dir():
        raise MlxBatchError(f"Selected generation directory is missing: {path}")
    return path


def chunk_path(plan: ChapterPlan, chunk_index: int) -> Path:
    group = group_for_chunk(plan, chunk_index)
    selector = read_json(group_commit_path(plan, group), "group selector")
    return selected_generation_dir(plan, group, selector) / f"chunk_{chunk_index:04d}.wav"


def write_cache_identity(plan: ChapterPlan) -> None:
    if plan.cache_dir is None or plan.cache_identity is None:
        raise MlxBatchError(f"MLX request identity unavailable for {plan.chapter.key}")
    plan.cache_dir.mkdir(parents=True, exist_ok=True)
    path = plan.cache_dir / "cache_identity.json"
    payload = {
        "cache_identity_sha256": plan.cache_identity_sha256,
        "identity": plan.cache_identity,
    }
    if path.is_file():
        if read_json(path, "cache identity") != payload:
            raise MlxBatchError(f"Cache identity collision or corruption: {path}")
        return
    atomic_write_json(path, payload)


def validate_group_commit(plan: ChapterPlan, group: GroupPlan) -> dict[str, Any]:
    commit_path = group_commit_path(plan, group)
    if not commit_path.is_file():
        raise MlxBatchError(f"Group commit missing: {commit_path}")
    selector = read_json(commit_path, "group selector")
    if (
        selector.get("schema_version") != CACHE_SCHEMA_VERSION
        or selector.get("cache_identity_sha256") != plan.cache_identity_sha256
        or selector.get("group_fingerprint") != group.fingerprint
        or selector.get("stable_group_index") != group.stable_index
    ):
        raise MlxBatchError(f"Group commit is stale or corrupt: {commit_path}")
    generation_dir = selected_generation_dir(plan, group, selector)
    generation_manifest_path = generation_dir / "generation.json"
    if (
        not generation_manifest_path.is_file()
        or selector.get("generation_manifest_sha256")
        != sha256_file(generation_manifest_path)
    ):
        raise MlxBatchError(
            f"Selected generation manifest is missing or stale: {generation_manifest_path}"
        )
    commit = read_json(generation_manifest_path, "group generation manifest")
    if (
        commit.get("schema_version") != CACHE_SCHEMA_VERSION
        or commit.get("cache_identity_sha256") != plan.cache_identity_sha256
        or commit.get("group_fingerprint") != group.fingerprint
        or commit.get("stable_group_index") != group.stable_index
    ):
        raise MlxBatchError(
            f"Selected group generation is stale or corrupt: {generation_manifest_path}"
        )
    generation = commit.get("generation")
    if not isinstance(generation, dict):
        raise MlxBatchError(f"Group generation record is missing: {commit_path}")
    mode = generation.get("mode")
    base_seed = generation.get("base_seed")
    seed_offset = generation.get("seed_offset")
    effective_batch_size = generation.get("batch_size")
    subgroups = generation.get("subgroups")
    if (
        mode not in {"base", "override"}
        or base_seed != group.seed
        or not isinstance(seed_offset, int)
        or not isinstance(effective_batch_size, int)
        or effective_batch_size < 1
        or not isinstance(subgroups, list)
    ):
        raise MlxBatchError(f"Group generation record is invalid: {commit_path}")
    if mode == "base" and (
        seed_offset != 0 or effective_batch_size != len(group.chunk_indices)
    ):
        raise MlxBatchError(f"Base group generation record is invalid: {commit_path}")
    if mode == "override" and seed_offset == 0:
        raise MlxBatchError(f"Override group seed offset is invalid: {commit_path}")
    expected_subgroups = []
    for subgroup_index, offset in enumerate(
        range(0, len(group.chunk_indices), effective_batch_size)
    ):
        expected_subgroups.append(
            {
                "subgroup_index": subgroup_index,
                "seed": group.seed + seed_offset + subgroup_index,
                "chunk_indices": list(
                    group.chunk_indices[offset : offset + effective_batch_size]
                ),
            }
        )
    if subgroups != expected_subgroups:
        raise MlxBatchError(f"Group subgroup mapping is invalid: {commit_path}")
    records = commit.get("chunks")
    if not isinstance(records, list):
        raise MlxBatchError(f"Group commit chunks are invalid: {commit_path}")
    by_index = {
        int(record.get("chunk_index")): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("chunk_index"), int)
    }
    if set(by_index) != set(group.chunk_indices) or len(by_index) != len(records):
        raise MlxBatchError(f"Group commit chunk mapping is invalid: {commit_path}")
    expected_chunk_names = {
        f"chunk_{chunk_index:04d}.wav" for chunk_index in group.chunk_indices
    }
    observed_chunk_names = {
        path.name for path in generation_dir.glob("chunk_*.wav")
    }
    if observed_chunk_names != expected_chunk_names:
        raise MlxBatchError(
            f"Selected generation chunk inventory is invalid: {generation_dir}"
        )
    for chunk_index in group.chunk_indices:
        path = generation_dir / f"chunk_{chunk_index:04d}.wav"
        observed = probe_wav(path)
        recorded = by_index[chunk_index]
        for field in (
            "sample_rate",
            "channels",
            "sample_width_bytes",
            "frames",
            "peak_pcm16",
            "digital_clipping_samples",
            "size",
            "sha256",
        ):
            if recorded.get(field) != observed[field]:
                raise MlxBatchError(
                    f"Committed chunk metadata mismatch for {path}: {field}"
                )
    return {
        **commit,
        "generation_dir": str(generation_dir.relative_to(plan.cache_dir)),
        "generation_manifest_sha256": selector["generation_manifest_sha256"],
        "selector_sha256": sha256_file(commit_path),
        "selected_at": selector.get("selected_at"),
    }


def group_is_committed(plan: ChapterPlan, group: GroupPlan) -> bool:
    try:
        validate_group_commit(plan, group)
        return True
    except (MlxBatchError, OSError, ValueError):
        return False


def generation_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "top_k": args.top_k,
        "top_p": args.top_p,
        "repetition_penalty": args.repetition_penalty,
        "verbose": False,
        "stream": False,
    }


def map_batch_results(results: Iterable[Any], expected_count: int) -> dict[int, Any]:
    by_sequence: dict[int, Any] = {}
    for result in results:
        if not hasattr(result, "sequence_idx"):
            raise MlxBatchError("MLX batch result is missing sequence_idx.")
        try:
            sequence_index = int(result.sequence_idx)
        except (TypeError, ValueError) as exc:
            raise MlxBatchError("MLX batch result has an invalid sequence_idx.") from exc
        if sequence_index in by_sequence:
            raise MlxBatchError(f"MLX batch returned duplicate sequence_idx {sequence_index}.")
        by_sequence[sequence_index] = result
    expected = set(range(expected_count))
    if set(by_sequence) != expected:
        raise MlxBatchError(
            f"MLX batch result indices {sorted(by_sequence)} do not match expected {sorted(expected)}."
        )
    return by_sequence


def guard_generation_result(
    result: Any, args: argparse.Namespace, chunk_index: int
) -> dict[str, Any]:
    try:
        sample_rate = int(result.sample_rate)
        samples = int(result.samples)
        token_count = int(result.token_count)
    except (AttributeError, TypeError, ValueError) as exc:
        raise MlxBatchError(
            f"MLX result metadata is invalid for chunk {chunk_index}."
        ) from exc
    if sample_rate != EXPECTED_SAMPLE_RATE or samples <= 0 or token_count < 0:
        raise MlxBatchError(
            f"MLX result metadata is invalid for chunk {chunk_index}: "
            f"sample_rate={sample_rate}, samples={samples}, token_count={token_count}"
        )
    duration = samples / sample_rate
    token_threshold = math.ceil(args.max_tokens * TOKEN_LIMIT_GUARD_RATIO)
    duration_limit = args.max_tokens * SAMPLES_PER_AUDIO_TOKEN / sample_rate
    if token_count >= token_threshold or duration >= duration_limit * TOKEN_LIMIT_GUARD_RATIO:
        raise MlxBatchError(
            f"MLX chunk {chunk_index} reached the generation limit before a safe ending "
            f"(tokens={token_count}/{args.max_tokens}, duration={duration:.3f}s)."
        )
    return {
        "reported_samples": samples,
        "reported_token_count": token_count,
        "reported_processing_time_seconds": float(
            getattr(result, "processing_time_seconds", 0.0)
        ),
        "reported_peak_memory_gb": float(getattr(result, "peak_memory_usage", 0.0)),
    }


def generate_group(
    plan: ChapterPlan,
    group: GroupPlan,
    args: argparse.Namespace,
    model: Any,
    runtime: MlxRuntime,
    *,
    seed_offset: int = 0,
    override_batch_size: int | None = None,
) -> dict[str, Any]:
    if plan.cache_dir is None:
        raise MlxBatchError(f"MLX cache unavailable for {plan.chapter.key}")
    if override_batch_size is None:
        if seed_offset != 0:
            raise MlxBatchError("A non-zero group seed offset requires override batch size.")
        effective_batch_size = len(group.chunk_indices)
        mode = "base"
    else:
        if override_batch_size < 1 or seed_offset == 0:
            raise MlxBatchError(
                "A group override requires positive batch size and non-zero seed offset."
            )
        effective_batch_size = override_batch_size
        mode = "override"
    plan.cache_dir.mkdir(parents=True, exist_ok=True)
    generation_root = group_generation_root(plan, group)
    generation_root.mkdir(parents=True, exist_ok=True)
    fsync_directory(plan.cache_dir)
    temporary_dir: Path | None = Path(
        tempfile.mkdtemp(prefix=".pending.", dir=generation_root)
    )
    records: list[dict[str, Any]] = []
    subgroup_records: list[dict[str, Any]] = []
    try:
        for subgroup_index, offset in enumerate(
            range(0, len(group.chunk_indices), effective_batch_size)
        ):
            subgroup_indices = group.chunk_indices[
                offset : offset + effective_batch_size
            ]
            texts = [plan.chunks[index - 1] for index in subgroup_indices]
            subgroup_seed = group.seed + seed_offset + subgroup_index
            runtime.set_seed(subgroup_seed)
            generated = model.batch_generate(
                texts=texts,
                voices=[args.speaker] * len(texts),
                instructs=[args.instruct or None] * len(texts),
                lang_code=args.language,
                **generation_kwargs(args),
            )
            by_sequence = map_batch_results(generated, len(texts))
            subgroup_records.append(
                {
                    "subgroup_index": subgroup_index,
                    "seed": subgroup_seed,
                    "chunk_indices": list(subgroup_indices),
                }
            )
            for sequence_index, chunk_index in enumerate(subgroup_indices):
                result = by_sequence[sequence_index]
                reported = guard_generation_result(result, args, chunk_index)
                assert temporary_dir is not None
                temporary_chunk = temporary_dir / f"chunk_{chunk_index:04d}.wav"
                runtime.write_audio(
                    temporary_chunk, result.audio, int(result.sample_rate), "wav"
                )
                fsync_file(temporary_chunk)
                observed = probe_wav(temporary_chunk)
                if observed["frames"] != reported["reported_samples"]:
                    raise MlxBatchError(
                        f"MLX reported {reported['reported_samples']} samples but WAV "
                        f"contains {observed['frames']} for chunk {chunk_index}."
                    )
                records.append(
                    {
                        "chunk_index": chunk_index,
                        "text_sha256": sha256_text(plan.chunks[chunk_index - 1]),
                        **observed,
                        **reported,
                    }
                )
        # Build a complete immutable generation before changing the selected
        # generation.  A failed override therefore cannot mix old and new WAVs.
        assert temporary_dir is not None
        generation_manifest = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_identity_sha256": plan.cache_identity_sha256,
            "group_fingerprint": group.fingerprint,
            "stable_group_index": group.stable_index,
            "seed": subgroup_records[0]["seed"],
            "generation": {
                "mode": mode,
                "base_seed": group.seed,
                "seed_offset": seed_offset,
                "batch_size": effective_batch_size,
                "subgroups": subgroup_records,
            },
            "chunks": records,
            "committed_at": timestamp(),
        }
        atomic_write_json(temporary_dir / "generation.json", generation_manifest)
        fsync_directory(temporary_dir)

        unique_suffix = temporary_dir.name.removeprefix(".pending.")
        generation_dir = generation_root / f"generation_{unique_suffix}"
        os.rename(temporary_dir, generation_dir)
        temporary_dir = None
        fsync_directory(generation_root)

        selector = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_identity_sha256": plan.cache_identity_sha256,
            "group_fingerprint": group.fingerprint,
            "stable_group_index": group.stable_index,
            "generation_dir": str(generation_dir.relative_to(plan.cache_dir)),
            "generation_manifest_sha256": sha256_file(
                generation_dir / "generation.json"
            ),
            "selected_at": timestamp(),
        }
        # This single atomic selector replacement is the only operation that
        # activates the new generation.  Until it succeeds, a prior generation
        # and every one of its chunks remain selected and valid.
        atomic_write_json(group_commit_path(plan, group), selector)
        return validate_group_commit(plan, group)
    finally:
        if temporary_dir is not None:
            shutil.rmtree(temporary_dir, ignore_errors=True)


class MlxBatchRunner:
    """Lazily load one MLX runtime/model and reuse it across every chapter."""

    def __init__(
        self,
        args: argparse.Namespace,
        profile: dict[str, Any],
        runtime_loader: Callable[[], MlxRuntime] = load_mlx_runtime,
    ) -> None:
        self.args = args
        self.profile = profile
        self.runtime_loader = runtime_loader
        self.runtime: MlxRuntime | None = None
        self.model: Any | None = None

    def get_runtime(self) -> MlxRuntime:
        if self.runtime is None:
            runtime = self.runtime_loader()
            if runtime.versions != self.profile.get("packages"):
                raise MlxBatchError(
                    "Loaded MLX package versions do not match the cache identity profile."
                )
            self.runtime = runtime
        return self.runtime

    def get_model(self) -> Any:
        if self.model is None:
            self.model = self.get_runtime().load_model(Path(self.args.model))
        return self.model

    def generate_chapter(self, plan: ChapterPlan) -> None:
        if plan.cache_identity is None or plan.cache_dir is None:
            raise MlxBatchError(f"MLX request identity unavailable for {plan.chapter.key}")
        if plan.chapter.output_path.exists():
            raise MlxBatchError(
                f"Refusing to overwrite existing production output: {plan.chapter.output_path}"
            )
        write_cache_identity(plan)
        override_groups = self.args.regenerate_groups.get(plan.chapter.key, set())
        for group in plan.groups:
            group_number = group.stable_index + 1
            if group_number in override_groups:
                print(
                    f"REGENERATE {plan.chapter.key}: group {group_number}/{len(plan.groups)} "
                    f"chunks={list(group.chunk_indices)} "
                    f"seed_offset={self.args.regenerate_seed_offset} "
                    f"batch_size={self.args.regenerate_batch_size}",
                    flush=True,
                )
                generate_group(
                    plan,
                    group,
                    self.args,
                    self.get_model(),
                    self.get_runtime(),
                    seed_offset=self.args.regenerate_seed_offset,
                    override_batch_size=self.args.regenerate_batch_size,
                )
                continue
            if group_is_committed(plan, group):
                print(
                    f"RESUME {plan.chapter.key}: group {group.stable_index + 1}/{len(plan.groups)}",
                    flush=True,
                )
                continue
            print(
                f"GENERATE {plan.chapter.key}: group {group.stable_index + 1}/{len(plan.groups)} "
                f"chunks={list(group.chunk_indices)} seed={group.seed}",
                flush=True,
            )
            generate_group(
                plan, group, self.args, self.get_model(), self.get_runtime()
            )
        verify_mlx_cache(plan)
        if not self.args.chunks_only:
            merge_chapter(plan, self.args)


def verify_mlx_cache(plan: ChapterPlan) -> dict[str, Any]:
    if plan.cache_dir is None or plan.cache_identity is None:
        raise MlxBatchError(f"MLX cache identity unavailable for {plan.chapter.key}")
    identity_path = plan.cache_dir / "cache_identity.json"
    expected_identity = {
        "cache_identity_sha256": plan.cache_identity_sha256,
        "identity": plan.cache_identity,
    }
    if not identity_path.is_file() or read_json(identity_path, "cache identity") != expected_identity:
        raise MlxBatchError(f"Cache identity is missing, stale, or corrupt: {identity_path}")
    expected_commit_names = {
        f"group_{group.stable_index:04d}.commit.json" for group in plan.groups
    }
    observed_commit_names = {
        path.name for path in plan.cache_dir.glob("group_*.commit.json")
    }
    if observed_commit_names != expected_commit_names:
        raise MlxBatchError(
            f"MLX cache group commit inventory mismatch for {plan.chapter.key}."
        )
    commits = [validate_group_commit(plan, group) for group in plan.groups]
    wavs = [probe_wav(chunk_path(plan, index)) for index in range(1, plan.expected_chunks + 1)]
    raw_duration = sum(item["duration_seconds"] for item in wavs)
    return {
        "cache_dir": str(plan.cache_dir.resolve()),
        "cache_identity_sha256": plan.cache_identity_sha256,
        "observed_chunks": len(wavs),
        "observed_groups": len(commits),
        "group_generations": [commit["generation"] for commit in commits],
        "raw_chunk_duration_seconds": raw_duration,
        "raw_digital_clipping_samples": sum(
            item["digital_clipping_samples"] for item in wavs
        ),
        "raw_chunk_frames": [item["frames"] for item in wavs],
        "raw_chunk_sha256s": [item["sha256"] for item in wavs],
    }


def verify_mlx_cache_artifact(plan: ChapterPlan) -> ArtifactVerification:
    try:
        cache = verify_mlx_cache(plan)
        return ArtifactVerification(
            True,
            None,
            {
                **cache,
                "chunks_only": True,
                "verified_at": timestamp(),
            },
            plan.cache_identity.get("profile") if plan.cache_identity else None,
        )
    except (MlxBatchError, OSError, ValueError, RuntimeError) as exc:
        return ArtifactVerification(False, str(exc))


def find_program(configured: str) -> str:
    candidate = Path(configured).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if candidate.is_file():
            return str(candidate.absolute())
        raise MlxBatchError(f"Required program not found: {configured}")
    located = shutil.which(configured)
    if located:
        return located
    fallback = Path("/opt/homebrew/bin") / configured
    if fallback.is_file():
        return str(fallback)
    raise MlxBatchError(f"Required program not found: {configured}")


def probe_mp3(path: Path, ffprobe: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size < 1024:
        raise MlxBatchError(f"MP3 output is missing or too small: {path}")
    completed = subprocess.run(
        [
            find_program(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bit_rate:format=duration,size,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise MlxBatchError(f"ffprobe failed for {path}: {detail}")
    try:
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        format_payload = payload["format"]
        codec = str(stream["codec_name"])
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        bit_rate = int(stream.get("bit_rate") or format_payload["bit_rate"])
        duration = float(format_payload["duration"])
        size = int(format_payload["size"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MlxBatchError(f"Invalid ffprobe response for {path}") from exc
    if (
        codec != "mp3"
        or sample_rate != EXPECTED_SAMPLE_RATE
        or channels != EXPECTED_CHANNELS
        or abs(bit_rate - EXPECTED_MP3_BIT_RATE) > 1000
        or duration <= 0.0
        or size < 1024
    ):
        raise MlxBatchError(
            f"Unexpected MP3 format for {path}: codec={codec}, sample_rate={sample_rate}, "
            f"channels={channels}, bit_rate={bit_rate}, duration={duration}"
        )
    return {
        "codec": codec,
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_rate": bit_rate,
        "duration_seconds": duration,
        "size": size,
    }


def verify_full_decode(path: Path, ffmpeg: str) -> None:
    completed = subprocess.run(
        [
            find_program(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MlxBatchError(f"Full ffmpeg decode failed for {path}: {detail}")


def verify_tail_silence(path: Path, ffmpeg: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            find_program(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-sseof",
            f"-{TAIL_PROBE_MS / 1000:.3f}",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            str(EXPECTED_SAMPLE_RATE),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MlxBatchError(f"Tail silence decode failed for {path}: {detail}")
    values = array("h")
    values.frombytes(completed.stdout[: len(completed.stdout) // 2 * 2])
    if sys.byteorder != "little":
        values.byteswap()
    minimum_frames = round(EXPECTED_SAMPLE_RATE * TAIL_PROBE_MS / 1000 * 0.8)
    if len(values) < minimum_frames:
        raise MlxBatchError(f"Tail silence probe returned too little audio for {path}.")
    peak = max(abs(value) for value in values)
    rms = math.sqrt(sum(value * value for value in values) / len(values))
    if peak > TAIL_PEAK_LIMIT or rms > TAIL_RMS_LIMIT:
        raise MlxBatchError(
            f"Final 250 ms safety padding is not silent enough for {path}: "
            f"peak={peak}, rms={rms:.3f}"
        )
    return {
        "probe_ms": TAIL_PROBE_MS,
        "frames": len(values),
        "peak_pcm16": peak,
        "rms_pcm16": rms,
        "peak_limit": TAIL_PEAK_LIMIT,
        "rms_limit": TAIL_RMS_LIMIT,
        "end_clipping_risk": 0,
    }


def verify_boundary_silence(
    path: Path,
    ffmpeg: str,
    raw_chunk_frames: Sequence[int],
    pause_ms: int,
) -> dict[str, Any]:
    """Verify a quiet interior window in every inserted 250 ms boundary pad."""
    minimum_silence_seconds = 0.06
    noise_threshold_db = -48
    completed = subprocess.run(
        [
            find_program(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            f"silencedetect=noise={noise_threshold_db}dB:d={minimum_silence_seconds}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MlxBatchError(f"Boundary silence scan failed for {path}: {detail}")
    log = completed.stderr.decode("utf-8", errors="replace")
    starts = [
        float(value)
        for value in re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", log)
    ]
    ends = [
        float(value)
        for value in re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", log)
    ]
    if len(starts) != len(ends):
        raise MlxBatchError(
            f"Boundary silence scan returned unpaired intervals for {path}."
        )
    intervals = list(zip(starts, ends))
    pause_seconds = pause_ms / 1000
    raw_elapsed = 0.0
    expected_centers: list[float] = []
    for boundary_index, frames in enumerate(raw_chunk_frames):
        raw_elapsed += frames / EXPECTED_SAMPLE_RATE
        pad_start = raw_elapsed + boundary_index * pause_seconds
        expected_centers.append(pad_start + pause_seconds / 2)
    # Inspect a 50 ms interior window.  It stays far from both audio transitions,
    # so MP3 filterbank ringing cannot be mistaken for a missing 250 ms separator.
    half_window = 0.025
    unmatched: list[float] = []
    for center in expected_centers:
        if not any(
            start <= center - half_window and end >= center + half_window
            for start, end in intervals
        ):
            unmatched.append(center)
    if unmatched:
        preview = ", ".join(f"{value:.3f}s" for value in unmatched[:5])
        raise MlxBatchError(
            f"Final MP3 is missing safe 250 ms boundary silence at "
            f"{len(unmatched)}/{len(expected_centers)} positions ({preview})."
        )
    return {
        "expected_boundaries": len(expected_centers),
        "verified_boundaries": len(expected_centers),
        "silence_intervals": len(intervals),
        "noise_threshold_db": noise_threshold_db,
        "minimum_interval_seconds": minimum_silence_seconds,
        "interior_window_seconds": half_window * 2,
        "boundary_clipping_risk": 0,
    }


def merge_receipt_path(plan: ChapterPlan) -> Path:
    if plan.cache_dir is None:
        raise MlxBatchError(f"MLX cache unavailable for {plan.chapter.key}")
    return plan.cache_dir / "merge.commit.json"


def durable_publish_mp3(
    temporary_output: Path,
    output: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
) -> None:
    """Durably bind and publish a verified MP3 without overwriting output."""
    # Flush the MP3 inode before either durable metadata points at it.  A
    # directory fsync alone does not guarantee that the encoded bytes survived.
    fsync_file(temporary_output)
    atomic_write_json(receipt_path, receipt)
    try:
        # Same-volume hard linking is an atomic create-if-absent publication.
        os.link(temporary_output, output)
        fsync_directory(output.parent)
    except FileExistsError as exc:
        raise MlxBatchError(
            f"Production output appeared during merge; refusing overwrite: {output}"
        ) from exc


def verify_merge_receipt(
    plan: ChapterPlan,
    args: argparse.Namespace,
    cache: dict[str, Any],
    audio: dict[str, Any],
) -> dict[str, Any]:
    path = merge_receipt_path(plan)
    if not path.is_file():
        raise MlxBatchError(f"MLX merge receipt is missing: {path}")
    receipt = read_json(path, "MLX merge receipt")
    output = plan.chapter.output_path
    output_sha256 = sha256_file(output)
    output_record = receipt.get("output")
    if (
        receipt.get("schema_version") != CACHE_SCHEMA_VERSION
        or receipt.get("cache_identity_sha256") != plan.cache_identity_sha256
        or receipt.get("request_fingerprint") != plan.request_fingerprint
        or receipt.get("raw_chunk_sha256s") != cache["raw_chunk_sha256s"]
        or receipt.get("raw_chunk_frames") != cache["raw_chunk_frames"]
        or receipt.get("pause_policy") != "after-every-raw-chunk-including-final"
        or receipt.get("pause_count") != plan.expected_chunks
        or receipt.get("pause_ms") != args.pause_ms
        or not isinstance(output_record, dict)
        or output_record.get("sha256") != output_sha256
        or output_record.get("size") != output.stat().st_size
        or output_record.get("duration_seconds") != audio["duration_seconds"]
        or output_record.get("codec") != audio["codec"]
        or output_record.get("sample_rate") != audio["sample_rate"]
        or output_record.get("channels") != audio["channels"]
        or output_record.get("bit_rate") != audio["bit_rate"]
    ):
        raise MlxBatchError(
            f"MLX merge receipt does not bind the current cache and MP3: {path}"
        )
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "output_sha256": output_sha256,
        "created_at": receipt.get("created_at"),
    }


def merge_chapter(plan: ChapterPlan, args: argparse.Namespace) -> None:
    if plan.chapter.output_path.exists():
        raise MlxBatchError(
            f"Refusing to overwrite existing production output: {plan.chapter.output_path}"
        )
    cache = verify_mlx_cache(plan)
    output = plan.chapter.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_program(args.ffmpeg)
    with tempfile.TemporaryDirectory(prefix="qwen3-tts-mlx-merge-") as temp_name:
        work = Path(temp_name)
        silence = work / "silence_250ms.wav"
        GENERATOR.write_silence(silence, EXPECTED_SAMPLE_RATE, args.pause_ms)
        silence_metadata = probe_wav(silence, allow_silence=True)
        expected_silence_frames = round(EXPECTED_SAMPLE_RATE * args.pause_ms / 1000)
        if silence_metadata["frames"] != expected_silence_frames:
            raise MlxBatchError("Unable to construct exact 250 ms merge padding.")
        concat = work / "chunks.txt"
        lines: list[str] = []
        # Add one and only one 250 ms zero pad after every raw chunk, including
        # the final chunk.  This provides both separators and a safe terminal release.
        for index in range(1, plan.expected_chunks + 1):
            for path in (chunk_path(plan, index), silence):
                escaped = path.as_posix().replace("'", "'\\''")
                lines.append(f"file '{escaped}'\n")
        concat.write_text("".join(lines), encoding="utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}.mlx.", suffix=".tmp.mp3", dir=output.parent
        )
        os.close(descriptor)
        temporary_output = Path(temporary_name)
        temporary_output.unlink(missing_ok=True)
        try:
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    "-ar",
                    str(EXPECTED_SAMPLE_RATE),
                    "-ac",
                    "1",
                    str(temporary_output),
                ],
                capture_output=True,
            )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise MlxBatchError(f"MLX chapter MP3 merge failed: {detail}")
            audio = probe_mp3(temporary_output, args.ffprobe)
            verify_full_decode(temporary_output, args.ffmpeg)
            tail = verify_tail_silence(temporary_output, args.ffmpeg)
            boundaries = verify_boundary_silence(
                temporary_output,
                args.ffmpeg,
                cache["raw_chunk_frames"],
                args.pause_ms,
            )
            expected_duration = (
                cache["raw_chunk_duration_seconds"]
                + args.pause_ms / 1000 * plan.expected_chunks
            )
            tolerance = max(0.5, expected_duration * 0.001)
            if abs(audio["duration_seconds"] - expected_duration) > tolerance:
                raise MlxBatchError(
                    f"Merged duration {audio['duration_seconds']:.3f}s does not match "
                    f"raw chunks plus {plan.expected_chunks} exact trailing pads "
                    f"({expected_duration:.3f}s)."
                )
            receipt = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "cache_identity_sha256": plan.cache_identity_sha256,
                "request_fingerprint": plan.request_fingerprint,
                "raw_chunk_sha256s": cache["raw_chunk_sha256s"],
                "raw_chunk_frames": cache["raw_chunk_frames"],
                "pause_policy": "after-every-raw-chunk-including-final",
                "pause_count": plan.expected_chunks,
                "pause_ms": args.pause_ms,
                "output": {
                    **audio,
                    "sha256": sha256_file(temporary_output),
                },
                "boundary_silence": boundaries,
                "tail_silence": tail,
                "created_at": timestamp(),
            }
            # The helper fsyncs encoded bytes before the durable receipt and the
            # atomic create-if-absent production link.
            durable_publish_mp3(
                temporary_output,
                output,
                merge_receipt_path(plan),
                receipt,
            )
        finally:
            temporary_output.unlink(missing_ok=True)


def verify_mlx_artifact(plan: ChapterPlan, args: argparse.Namespace) -> ArtifactVerification:
    try:
        cache = verify_mlx_cache(plan)
        audio = probe_mp3(plan.chapter.output_path, args.ffprobe)
        verify_full_decode(plan.chapter.output_path, args.ffmpeg)
        tail = verify_tail_silence(plan.chapter.output_path, args.ffmpeg)
        boundaries = verify_boundary_silence(
            plan.chapter.output_path,
            args.ffmpeg,
            cache["raw_chunk_frames"],
            args.pause_ms,
        )
        receipt = verify_merge_receipt(plan, args, cache, audio)
        expected_duration = (
            cache["raw_chunk_duration_seconds"]
            + args.pause_ms / 1000 * plan.expected_chunks
        )
        tolerance = max(0.5, expected_duration * 0.001)
        if abs(audio["duration_seconds"] - expected_duration) > tolerance:
            raise MlxBatchError(
                f"Output duration {audio['duration_seconds']:.3f}s != expected "
                f"{expected_duration:.3f}s including final 250 ms padding."
            )
        stat = plan.chapter.output_path.stat()
        metadata = {
            **audio,
            **cache,
            "expected_output_duration_seconds": expected_duration,
            "pause_count": plan.expected_chunks,
            "pause_ms": args.pause_ms,
            "trailing_silence_ms": args.pause_ms,
            "boundary_safe": True,
            "boundary_silence": boundaries,
            "tail_silence": tail,
            "merge_receipt": receipt,
            "output_sha256": receipt["output_sha256"],
            "output_mtime_ns": stat.st_mtime_ns,
            "verified_at": timestamp(),
        }
        return ArtifactVerification(True, None, metadata, local_runtime_profile())
    except (MlxBatchError, OSError, ValueError, RuntimeError) as exc:
        return ArtifactVerification(False, str(exc))


def _same_path(recorded: object, expected: Path) -> bool:
    if not isinstance(recorded, str):
        return False
    try:
        return Path(recorded).expanduser().resolve() == expected.resolve()
    except OSError:
        return False


def load_optional_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return read_json(path, "manifest")


def pytorch_settings_are_compatible(
    settings: dict[str, Any], args: argparse.Namespace
) -> bool:
    required = {
        "speaker": args.speaker,
        "language": args.language,
        "instruct": args.instruct,
        "max_chars": args.max_chars,
        "pause_ms": args.pause_ms,
        "speed": args.speed,
        "seed": args.seed,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "repetition_penalty": args.repetition_penalty,
        "max_new_tokens": args.max_tokens,
    }
    if any(settings.get(key) != value for key, value in required.items()):
        return False
    source_model = settings.get("model")
    if source_model == "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice":
        return True
    if not isinstance(source_model, str):
        return False
    candidate = Path(source_model).expanduser()
    if not candidate.is_absolute():
        return False
    try:
        return candidate.resolve() == Path(args.model).resolve()
    except OSError:
        return False


def verify_pytorch_adoption(
    plan: ChapterPlan,
    args: argparse.Namespace,
    source_manifest: dict[str, Any] | None,
) -> ArtifactVerification:
    try:
        if source_manifest is None:
            raise MlxBatchError("PyTorch source manifest is missing.")
        if source_manifest.get("schema_version") != 1:
            raise MlxBatchError("Unsupported PyTorch source manifest schema.")
        if tuple(source_manifest.get("inventory", [])) != EXPECTED_INVENTORY:
            raise MlxBatchError("PyTorch source manifest inventory is not the fixed 25 chapters.")
        settings = source_manifest.get("settings")
        if not isinstance(settings, dict):
            raise MlxBatchError("PyTorch source manifest settings are missing.")
        if source_manifest.get("settings_fingerprint") != PYTORCH_BATCH.json_digest(settings):
            raise MlxBatchError("PyTorch source settings fingerprint is stale.")
        if not pytorch_settings_are_compatible(settings, args):
            raise MlxBatchError(
                "PyTorch source settings do not match the approved Sohee/Korean request."
            )
        generator_path = Path(str(source_manifest.get("generator", ""))).expanduser()
        if (
            not generator_path.is_file()
            or settings.get("generator_sha256") != sha256_file(generator_path)
        ):
            raise MlxBatchError("PyTorch source generator hash is not current.")
        chapters = source_manifest.get("chapters")
        entry = chapters.get(plan.chapter.key) if isinstance(chapters, dict) else None
        if not isinstance(entry, dict) or entry.get("status") != "verified":
            raise MlxBatchError("PyTorch chapter is not current verified.")
        if (
            entry.get("speech_sha256") != plan.speech_sha256
            or entry.get("expected_chunks") != plan.expected_chunks
            or not _same_path(entry.get("speech_path"), plan.chapter.speech_path)
            or not _same_path(entry.get("output_path"), plan.chapter.output_path)
        ):
            raise MlxBatchError("PyTorch chapter request inputs are stale.")
        request = {
            "chapter": plan.chapter.key,
            "speech_sha256": plan.speech_sha256,
            "output_path": str(plan.chapter.output_path),
            "settings": settings,
        }
        request_fingerprint = PYTORCH_BATCH.json_digest(request)
        if entry.get("request_fingerprint") != request_fingerprint:
            raise MlxBatchError("PyTorch chapter request fingerprint is stale.")
        recorded = entry.get("verification")
        if not isinstance(recorded, dict):
            raise MlxBatchError("PyTorch chapter verification is missing.")
        output = plan.chapter.output_path
        if not output.is_file():
            raise MlxBatchError("PyTorch output is missing.")
        audio = probe_mp3(output, args.ffprobe)
        verify_full_decode(output, args.ffmpeg)
        stat = output.stat()
        output_sha256 = sha256_file(output)
        if (
            recorded.get("output_sha256") != output_sha256
            or recorded.get("size") != stat.st_size
            or recorded.get("output_mtime_ns") != stat.st_mtime_ns
            or recorded.get("observed_chunks") != plan.expected_chunks
        ):
            raise MlxBatchError("PyTorch output hash/stat/chunk record is stale.")
        cache_dir = Path(str(recorded.get("cache_dir", ""))).expanduser()
        expected_names = [
            f"chunk_{index:04d}.wav" for index in range(1, plan.expected_chunks + 1)
        ]
        chunks_found = sorted(cache_dir.glob("chunk_*.wav")) if cache_dir.is_dir() else []
        if [path.name for path in chunks_found] != expected_names:
            raise MlxBatchError("PyTorch recorded cache chunk inventory is stale.")
        wavs = [probe_wav(path) for path in chunks_found]
        raw_duration = sum(item["duration_seconds"] for item in wavs)
        raw_hashes = [item["sha256"] for item in wavs]
        raw_frames = [item["frames"] for item in wavs]
        expected_duration = (
            raw_duration
            + float(settings.get("pause_ms", 0)) / 1000 * (plan.expected_chunks - 1)
        ) / float(settings.get("speed", 1.0))
        tolerance = max(0.5, expected_duration * 0.001)
        if abs(audio["duration_seconds"] - expected_duration) > tolerance:
            raise MlxBatchError("PyTorch output and recorded cache duration disagree.")
        metadata = {
            **audio,
            "cache_dir": str(cache_dir.resolve()),
            "observed_chunks": len(wavs),
            "raw_chunk_duration_seconds": raw_duration,
            "raw_chunk_frames": raw_frames,
            "raw_chunk_sha256s": raw_hashes,
            "expected_output_duration_seconds": expected_duration,
            "pause_policy": "between-chunks-only-legacy-pytorch",
            "pause_count": max(0, plan.expected_chunks - 1),
            "pause_ms": int(settings.get("pause_ms", 0)),
            "trailing_silence_ms": 0,
            "boundary_safe": False,
            "legacy_adoption": True,
            "output_sha256": output_sha256,
            "output_mtime_ns": stat.st_mtime_ns,
            "source_manifest": str(args.pytorch_manifest),
            "source_request_fingerprint": request_fingerprint,
            "verified_at": timestamp(),
        }
        profile = {
            "engine": PYTORCH_ENGINE,
            "source_manifest": str(args.pytorch_manifest),
            "settings": settings,
            "pause_policy": "between-chunks-only-legacy-pytorch",
            "legacy_adoption": True,
        }
        return ArtifactVerification(True, None, metadata, profile)
    except (MlxBatchError, OSError, ValueError, ZeroDivisionError) as exc:
        return ArtifactVerification(False, str(exc))


def empty_manifest() -> dict[str, Any]:
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "chapters": {}}


def load_hybrid_manifest(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise MlxBatchError(f"Hybrid manifest is missing: {path}")
        return empty_manifest()
    payload = read_json(path, "hybrid manifest")
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise MlxBatchError(f"Unsupported hybrid manifest schema: {path}")
    if not isinstance(payload.get("chapters"), dict):
        raise MlxBatchError(f"Hybrid manifest chapters must be an object: {path}")
    return payload


def base_entry(plan: ChapterPlan, previous: object = None) -> dict[str, Any]:
    prior = previous if isinstance(previous, dict) else {}
    prior_inputs_current = bool(prior) and (
        prior.get("part") == plan.chapter.part
        and prior.get("chapter") == plan.chapter.chapter
        and prior.get("title") == plan.chapter.title
        and _same_path(prior.get("source_path"), plan.chapter.source_path)
        and _same_path(prior.get("speech_path"), plan.chapter.speech_path)
        and _same_path(prior.get("output_path"), plan.chapter.output_path)
        and prior.get("speech_sha256") == plan.speech_sha256
        and prior.get("cleaned_sha256") == plan.cleaned_sha256
        and prior.get("expected_chunks") == plan.expected_chunks
    )
    if (
        prior.get("engine") == ENGINE
        and plan.request_fingerprint is not None
        and prior.get("request_fingerprint") != plan.request_fingerprint
    ):
        prior_inputs_current = False
    if not prior_inputs_current:
        prior = {}
    entry = {
        "part": plan.chapter.part,
        "chapter": plan.chapter.chapter,
        "title": plan.chapter.title,
        "source_path": str(plan.chapter.source_path),
        "speech_path": str(plan.chapter.speech_path),
        "output_path": str(plan.chapter.output_path),
        "speech_sha256": plan.speech_sha256,
        "speech_chars": plan.speech_chars,
        "cleaned_sha256": plan.cleaned_sha256,
        "cleaned_chars": plan.cleaned_chars,
        "expected_chunks": plan.expected_chunks,
        "request_fingerprint": prior.get(
            "request_fingerprint", plan.request_fingerprint
        ),
        "engine": prior.get("engine"),
        "status": prior.get("status", "pending" if not plan.error else "missing_speech"),
        "profile": prior.get("profile"),
        "verification": prior.get("verification"),
        "attempts": int(prior.get("attempts", 0)),
        "error": prior.get("error") or plan.error,
        "updated_at": prior.get("updated_at"),
    }
    for optional in ("adopted_existing", "started_at", "completed_at"):
        if optional in prior:
            entry[optional] = prior[optional]
    return entry


def refresh_manifest(
    manifest: dict[str, Any],
    args: argparse.Namespace,
    plans: Sequence[ChapterPlan],
    profile: dict[str, Any],
    model_identity: dict[str, Any] | None,
) -> None:
    chapters = manifest.setdefault("chapters", {})
    current_settings = generation_settings(args)
    settings_changed = (
        "settings" in manifest and manifest.get("settings") != current_settings
    )
    model_changed = (
        model_identity is not None
        and "model" in manifest
        and manifest.get("model") != model_identity
    )
    for plan in plans:
        previous = None if settings_changed or model_changed else chapters.get(plan.chapter.key)
        chapters[plan.chapter.key] = base_entry(plan, previous)
    effective_model = model_identity if model_identity is not None else manifest.get("model")
    effective_profile = (
        profile
        if model_identity is not None
        else manifest.get("profile", profile)
    )
    manifest.update(
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "subject": "4과목",
            "engine": "hybrid-pytorch-adoption-or-mlx-audio",
            "chapter_root": str(args.chapter_root),
            "speech_root": str(args.speech_root),
            "output_root": str(args.output_root),
            "model": effective_model,
            "profile": effective_profile,
            "settings": current_settings,
            "settings_fingerprint": json_digest(current_settings),
            "inventory": list(EXPECTED_INVENTORY),
            "updated_at": timestamp(),
        }
    )


def update_entry(
    manifest: dict[str, Any],
    plan: ChapterPlan,
    status: str,
    *,
    engine: str | None,
    profile: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    error: str | None = None,
    adopted: bool | None = None,
    increment_attempts: bool = False,
    request_fingerprint: str | None = None,
) -> None:
    previous = manifest["chapters"].get(plan.chapter.key)
    entry = base_entry(plan, previous)
    if increment_attempts:
        entry["attempts"] += 1
        entry["started_at"] = timestamp()
    entry.update(
        {
            "status": status,
            "engine": engine,
            "profile": profile,
            "verification": verification,
            "error": error,
            "request_fingerprint": request_fingerprint or plan.request_fingerprint,
            "updated_at": timestamp(),
        }
    )
    if verification is not None:
        entry["completed_at"] = timestamp()
    if adopted is not None:
        entry["adopted_existing"] = adopted
    manifest["chapters"][plan.chapter.key] = entry


def verification_matches_entry(
    entry: object,
    verification: ArtifactVerification,
    *,
    engine: str,
    request_fingerprint: str | None,
    status: str = "verified",
) -> bool:
    if not isinstance(entry, dict) or not verification.ok or verification.metadata is None:
        return False
    recorded = entry.get("verification")
    recorded_stable = dict(recorded) if isinstance(recorded, dict) else None
    observed_stable = dict(verification.metadata)
    if recorded_stable is not None:
        recorded_stable.pop("verified_at", None)
    observed_stable.pop("verified_at", None)
    return (
        entry.get("status") == status
        and entry.get("engine") == engine
        and entry.get("request_fingerprint") == request_fingerprint
        and entry.get("profile") == verification.profile
        and isinstance(recorded, dict)
        and recorded_stable == observed_stable
    )


def entry_inputs_are_current(entry: object, plan: ChapterPlan) -> bool:
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("part") == plan.chapter.part
        and entry.get("chapter") == plan.chapter.chapter
        and entry.get("title") == plan.chapter.title
        and _same_path(entry.get("source_path"), plan.chapter.source_path)
        and _same_path(entry.get("speech_path"), plan.chapter.speech_path)
        and _same_path(entry.get("output_path"), plan.chapter.output_path)
        and entry.get("speech_sha256") == plan.speech_sha256
        and entry.get("cleaned_sha256") == plan.cleaned_sha256
        and entry.get("expected_chunks") == plan.expected_chunks
    )


def check_manifest(
    args: argparse.Namespace,
    plans: Sequence[ChapterPlan],
    source_manifest: dict[str, Any] | None,
    adoption_verifier: Callable[[ChapterPlan, argparse.Namespace, dict[str, Any] | None], ArtifactVerification],
    mlx_verifier: Callable[[ChapterPlan, argparse.Namespace], ArtifactVerification],
) -> int:
    manifest = load_hybrid_manifest(args.manifest, required=True)
    if tuple(manifest.get("inventory", [])) != EXPECTED_INVENTORY:
        raise MlxBatchError("Hybrid manifest inventory is not the fixed 25 chapters.")
    chapters = manifest.get("chapters")
    if not isinstance(chapters, dict) or set(chapters) != set(EXPECTED_INVENTORY):
        raise MlxBatchError("Hybrid manifest must contain one entry for all 25 chapters.")
    expected_settings = generation_settings(args)
    if (
        manifest.get("subject") != "4과목"
        or manifest.get("engine") != "hybrid-pytorch-adoption-or-mlx-audio"
        or manifest.get("settings") != expected_settings
        or manifest.get("settings_fingerprint") != json_digest(expected_settings)
        or not _same_path(manifest.get("chapter_root"), args.chapter_root)
        or not _same_path(manifest.get("speech_root"), args.speech_root)
        or not _same_path(manifest.get("output_root"), args.output_root)
    ):
        raise MlxBatchError("Hybrid manifest header/settings are stale.")
    current_identity = next(
        (plan.cache_identity for plan in plans if plan.cache_identity is not None), None
    )
    if current_identity is not None and (
        manifest.get("model") != current_identity.get("model")
        or manifest.get("profile") != current_identity.get("profile")
    ):
        raise MlxBatchError("Hybrid manifest model/runtime profile is stale.")
    failed = False
    for plan in plans:
        entry = chapters.get(plan.chapter.key)
        if not entry_inputs_are_current(entry, plan):
            failed = True
            print(f"FAIL {plan.chapter.key}: manifest chapter inputs are stale")
            continue
        engine = entry.get("engine") if isinstance(entry, dict) else None
        if engine == PYTORCH_ENGINE:
            verification = adoption_verifier(plan, args, source_manifest)
            source_request = (
                verification.metadata.get("source_request_fingerprint")
                if verification.ok and verification.metadata
                else None
            )
            ok = verification_matches_entry(
                entry,
                verification,
                engine=PYTORCH_ENGINE,
                request_fingerprint=source_request,
            )
        elif engine == ENGINE:
            chunks_only_entry = (
                args.chunks_only
                and isinstance(entry, dict)
                and entry.get("status") == "chunks_verified"
            )
            verification = (
                verify_mlx_cache_artifact(plan)
                if chunks_only_entry
                else mlx_verifier(plan, args)
            )
            ok = verification_matches_entry(
                entry,
                verification,
                engine=ENGINE,
                request_fingerprint=plan.request_fingerprint,
                status="chunks_verified" if chunks_only_entry else "verified",
            )
        else:
            verification = ArtifactVerification(False, f"invalid engine/status: {engine}")
            ok = False
        if ok:
            print(f"OK {plan.chapter.key}: {engine}, {plan.expected_chunks} chunks")
        else:
            failed = True
            print(f"FAIL {plan.chapter.key}: {verification.reason or 'manifest is stale'}")
    print(f"SUMMARY total={len(plans)}, failed={int(failed)}")
    return 1 if failed else 0


def run_batch(
    args: argparse.Namespace,
    *,
    runtime_loader: Callable[[], MlxRuntime] = load_mlx_runtime,
    profile: dict[str, Any] | None = None,
    model_identity: dict[str, Any] | None = None,
    adoption_verifier: Callable[[ChapterPlan, argparse.Namespace, dict[str, Any] | None], ArtifactVerification] = verify_pytorch_adoption,
    mlx_verifier: Callable[[ChapterPlan, argparse.Namespace], ArtifactVerification] = verify_mlx_artifact,
    runner_factory: Callable[[argparse.Namespace, dict[str, Any], Callable[[], MlxRuntime]], Any] | None = None,
) -> int:
    inventory = discover_inventory(args)
    selected_keys = {chapter.key for chapter in select_chapters(inventory, args.only)}
    profile = profile or local_runtime_profile()
    model_error: str | None = None
    if model_identity is None:
        try:
            model_identity = inspect_model(
                Path(args.model), args.speaker, args.language
            )
        except MlxBatchError as exc:
            model_error = str(exc)
    all_plans = [analyze_chapter(chapter, args, model_identity, profile) for chapter in inventory]
    plans = [plan for plan in all_plans if plan.chapter.key in selected_keys]
    regeneration_keys = set(args.regenerate_groups)
    if regeneration_keys:
        if not args.only or regeneration_keys != selected_keys:
            raise MlxBatchError(
                "--regenerate-group chapter keys must exactly match explicit --only selectors."
            )
        for plan in plans:
            maximum_group = len(plan.groups)
            invalid = sorted(
                number
                for number in args.regenerate_groups.get(plan.chapter.key, set())
                if number > maximum_group
            )
            if invalid:
                raise MlxBatchError(
                    f"Invalid group number(s) for {plan.chapter.key}; "
                    f"valid range is 1..{maximum_group}: {invalid}"
                )
    source_manifest = load_optional_manifest(args.pytorch_manifest)

    if args.check:
        return check_manifest(
            args, plans, source_manifest, adoption_verifier, mlx_verifier
        )

    if args.dry_run:
        for plan in plans:
            if plan.error:
                print(f"MISSING {plan.chapter.key}: {plan.error}")
                continue
            adopted = adoption_verifier(plan, args, source_manifest)
            if adopted.ok:
                print(f"ADOPTABLE {plan.chapter.key}: PyTorch current verified")
            elif plan.chapter.output_path.exists():
                current = mlx_verifier(plan, args) if plan.cache_identity is not None else ArtifactVerification(False, model_error)
                print(
                    f"{'RECOVERABLE' if current.ok else 'CONFLICT'} {plan.chapter.key}: "
                    f"{current.reason or 'current MLX artifact'}"
                )
            else:
                suffix = f"; {model_error}" if model_error else ""
                override = args.regenerate_groups.get(plan.chapter.key, set())
                override_text = (
                    f", regenerate_groups={sorted(override)}, "
                    f"override_batch={args.regenerate_batch_size}, "
                    f"seed_offset={args.regenerate_seed_offset}"
                    if override
                    else ""
                )
                print(
                    f"GENERATE {plan.chapter.key}: {plan.expected_chunks} chunks, "
                    f"{len(plan.groups)} groups{override_text}{suffix}"
                )
                for group in plan.groups:
                    marker = (
                        " REGENERATE"
                        if group.stable_index + 1 in override
                        else ""
                    )
                    print(
                        f"  GROUP {plan.chapter.key}:{group.stable_index + 1} "
                        f"chunks={list(group.chunk_indices)} seed={group.seed}{marker}"
                    )
        print(f"SUMMARY total={len(plans)}, dry_run=1")
        return 0

    manifest = load_hybrid_manifest(args.manifest)
    refresh_manifest(manifest, args, all_plans, profile, model_identity)

    def persist() -> None:
        refresh_manifest(manifest, args, all_plans, profile, model_identity)
        atomic_write_json(args.manifest, manifest)

    persist()
    runner: Any | None = None
    failed = False
    counts = {"adopted": 0, "generated": 0, "recovered": 0, "failed": 0}

    for plan in plans:
        if plan.error:
            failed = True
            counts["failed"] += 1
            update_entry(
                manifest,
                plan,
                "missing_speech",
                engine=None,
                profile=None,
                verification=None,
                error=plan.error,
            )
            persist()
            print(f"FAIL {plan.chapter.key}: {plan.error}")
            if not args.keep_going:
                break
            continue

        if (
            args.regenerate_groups.get(plan.chapter.key)
            and plan.chapter.output_path.exists()
        ):
            reason = (
                "group regeneration is allowed only before a production MP3 exists; "
                "the existing output was not modified"
            )
            failed = True
            counts["failed"] += 1
            update_entry(
                manifest,
                plan,
                "failed",
                engine=ENGINE,
                profile=profile,
                verification=None,
                error=reason,
            )
            persist()
            print(f"FAIL {plan.chapter.key}: {reason}")
            if not args.keep_going:
                break
            continue

        adopted = adoption_verifier(plan, args, source_manifest)
        if adopted.ok and adopted.metadata is not None:
            request_fingerprint = adopted.metadata["source_request_fingerprint"]
            update_entry(
                manifest,
                plan,
                "verified",
                engine=PYTORCH_ENGINE,
                profile=adopted.profile,
                verification=adopted.metadata,
                adopted=True,
                request_fingerprint=request_fingerprint,
            )
            persist()
            counts["adopted"] += 1
            print(f"ADOPT {plan.chapter.key}: current PyTorch artifact")
            continue

        if plan.chapter.output_path.exists():
            current = (
                mlx_verifier(plan, args)
                if plan.cache_identity is not None
                else ArtifactVerification(False, model_error or "MLX request unavailable")
            )
            if current.ok and current.metadata is not None:
                update_entry(
                    manifest,
                    plan,
                    "verified",
                    engine=ENGINE,
                    profile=current.profile or profile,
                    verification=current.metadata,
                    adopted=False,
                )
                persist()
                counts["recovered"] += 1
                print(f"RECOVER {plan.chapter.key}: current MLX artifact")
                continue
            reason = (
                "existing output is neither a current verified PyTorch artifact nor "
                f"a current MLX artifact: {current.reason or adopted.reason}"
            )
            failed = True
            counts["failed"] += 1
            update_entry(
                manifest,
                plan,
                "failed",
                engine=None,
                profile=None,
                verification=None,
                error=reason,
            )
            persist()
            print(f"FAIL {plan.chapter.key}: {reason}")
            if not args.keep_going:
                break
            continue

        if model_error or plan.cache_identity is None:
            reason = model_error or "MLX cache identity unavailable"
            failed = True
            counts["failed"] += 1
            update_entry(
                manifest,
                plan,
                "failed",
                engine=ENGINE,
                profile=profile,
                verification=None,
                error=reason,
                increment_attempts=True,
            )
            persist()
            print(f"FAIL {plan.chapter.key}: {reason}")
            if not args.keep_going:
                break
            continue

        update_entry(
            manifest,
            plan,
            "running",
            engine=ENGINE,
            profile=profile,
            verification=None,
            increment_attempts=True,
        )
        persist()
        try:
            if runner is None:
                factory = runner_factory or (
                    lambda batch_args, batch_profile, loader: MlxBatchRunner(
                        batch_args, batch_profile, loader
                    )
                )
                runner = factory(args, profile, runtime_loader)
            runner.generate_chapter(plan)
            verification = (
                verify_mlx_cache_artifact(plan)
                if args.chunks_only
                else mlx_verifier(plan, args)
            )
            if not verification.ok or verification.metadata is None:
                raise MlxBatchError(
                    verification.reason or "MLX artifact verification failed"
                )
            update_entry(
                manifest,
                plan,
                "chunks_verified" if args.chunks_only else "verified",
                engine=ENGINE,
                profile=verification.profile or profile,
                verification=verification.metadata,
                adopted=False,
            )
            persist()
            counts["generated"] += 1
            label = "chunks committed" if args.chunks_only else "verified"
            print(f"DONE {plan.chapter.key}: {label} ({plan.expected_chunks} chunks)")
        except Exception as exc:
            failed = True
            counts["failed"] += 1
            update_entry(
                manifest,
                plan,
                "failed",
                engine=ENGINE,
                profile=profile,
                verification=None,
                error=str(exc),
            )
            persist()
            print(f"FAIL {plan.chapter.key}: {exc}")
            if not args.keep_going:
                break

    summary = ", ".join(f"{key}={value}" for key, value in counts.items() if value)
    print(f"SUMMARY total={len(plans)}" + (f", {summary}" if summary else ""))
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = resolve_arguments(parse_args(argv), Path.cwd().resolve())
        return run_batch(args)
    except (MlxBatchError, OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

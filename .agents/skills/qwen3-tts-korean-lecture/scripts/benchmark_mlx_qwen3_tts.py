#!/usr/bin/env python3
"""Benchmark MLX-Audio Qwen3-TTS without touching production chunk caches."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[4]
GENERATOR_PATH = Path(__file__).with_name("generate_qwen3_tts.py")
DEFAULT_NARRATION = PROJECT_ROOT / (
    "output/qwen3_tts_audio/"
    "4과목_Part01_Chapter03_경쟁입찰_참가자격신청하기_대본.txt"
)
DEFAULT_PYTORCH_CACHE = PROJECT_ROOT / (
    "output/qwen3_tts_audio/"
    ".4과목_Part01_Chapter03_경쟁입찰_참가자격신청하기_"
    "Qwen3-TTS_Sohee_qwen3tts_8058c8bc36d8"
)
DEFAULT_CHUNK_INDICES = (30, 33, 41)
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_INSTRUCT = "차분하고 명료한 한국어 강의 톤으로 또박또박 말해 주세요."
DEFAULT_MAX_CHARS = 160
DEFAULT_SEED = 1234
DEFAULT_TEMPERATURE = 0.9
DEFAULT_TOP_P = 1.0
DEFAULT_TOP_K = 50
DEFAULT_REPETITION_PENALTY = 1.05
DEFAULT_MAX_TOKENS = 1024
EXPECTED_SAMPLE_RATE = 24000
MANIFEST_SCHEMA_VERSION = 1


class BenchmarkError(RuntimeError):
    """Raised for a benchmark setup, generation, or verification failure."""


@dataclass(frozen=True)
class MlxRuntime:
    load_model: Callable[[Path], Any]
    write_audio: Callable[[Path, Any, int, str | None], None]
    set_seed: Callable[[int], None]
    versions: dict[str, str]


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


def load_generator_module(path: Path = GENERATOR_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("qwen3_tts_benchmark_generator", path)
    if spec is None or spec.loader is None:
        raise BenchmarkError(f"Unable to import the existing generator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local MLX-Audio Qwen3-TTS Sohee on selected narration chunks."
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_NARRATION)
    parser.add_argument("--model", required=True, help="Existing local MLX or HF model directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--chunk-indices",
        type=int,
        nargs="+",
        default=list(DEFAULT_CHUNK_INDICES),
        metavar="N",
    )
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--pytorch-cache-dir", type=Path, default=DEFAULT_PYTORCH_CACHE)
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--instruct", default=DEFAULT_INSTRUCT)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--top-p", type=float, default=DEFAULT_TOP_P)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=DEFAULT_REPETITION_PENALTY,
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def validate_args(args: argparse.Namespace, invocation_dir: Path) -> argparse.Namespace:
    args.file = resolve_path(args.file, invocation_dir)
    args.output_dir = resolve_path(args.output_dir, invocation_dir)
    if args.pytorch_cache_dir is not None:
        args.pytorch_cache_dir = resolve_path(args.pytorch_cache_dir, invocation_dir)
        if args.output_dir == args.pytorch_cache_dir:
            raise BenchmarkError(
                "--output-dir must not be the read-only PyTorch cache directory."
            )
    if args.batch_size < 1:
        raise BenchmarkError("--batch-size must be 1 or greater.")
    if args.max_chars < 50:
        raise BenchmarkError("--max-chars must be at least 50.")
    if args.max_tokens < 1:
        raise BenchmarkError("--max-tokens must be positive.")
    if args.top_k < 0:
        raise BenchmarkError("--top-k must be non-negative.")
    if not 0.0 <= args.top_p <= 1.0:
        raise BenchmarkError("--top-p must be between 0 and 1.")
    if args.temperature < 0.0:
        raise BenchmarkError("--temperature must be non-negative.")
    if args.repetition_penalty <= 0.0:
        raise BenchmarkError("--repetition-penalty must be positive.")
    if not args.file.is_file():
        raise BenchmarkError(f"Narration file not found: {args.file}")
    if not args.chunk_indices:
        raise BenchmarkError("At least one --chunk-indices value is required.")
    if any(index < 1 for index in args.chunk_indices):
        raise BenchmarkError("Chunk indices are one-based positive integers.")
    if len(args.chunk_indices) != len(set(args.chunk_indices)):
        raise BenchmarkError("Duplicate chunk indices are not allowed.")
    if not args.dry_run:
        model_path = Path(args.model).expanduser()
        if not model_path.is_absolute():
            model_path = invocation_dir / model_path
        model_path = model_path.resolve()
        if not model_path.is_dir():
            raise BenchmarkError(
                "--model must be an existing local directory; this benchmark does not download weights: "
                f"{model_path}"
            )
        args.model = str(model_path)
    return args


def probe_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise BenchmarkError(f"Invalid WAV file {path}: {exc}") from exc
    if channels != 1 or sample_width != 2 or sample_rate != EXPECTED_SAMPLE_RATE or frames <= 0:
        raise BenchmarkError(
            f"Unexpected WAV format for {path}: channels={channels}, width={sample_width}, "
            f"sample_rate={sample_rate}, frames={frames}"
        )
    return {
        "path": str(path),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def inspect_pytorch_reference(cache_dir: Path | None, index: int) -> dict[str, Any] | None:
    if cache_dir is None:
        return None
    path = cache_dir / f"chunk_{index:04d}.wav"
    if not path.is_file():
        return {"path": str(path), "exists": False}
    try:
        metadata = probe_wav(path)
    except BenchmarkError as exc:
        return {"path": str(path), "exists": True, "valid": False, "error": str(exc)}
    return {"exists": True, "valid": True, **metadata}


def build_plan(
    args: argparse.Namespace,
    generator: ModuleType,
) -> dict[str, Any]:
    source_bytes = args.file.read_bytes()
    source_text = source_bytes.decode("utf-8")
    cleaned = generator.clean_narration(source_text)
    chunks = generator.split_narration(cleaned, args.max_chars)
    selected: list[dict[str, Any]] = []
    for index in args.chunk_indices:
        if index > len(chunks):
            raise BenchmarkError(
                f"Chunk index {index} is outside the extracted range 1..{len(chunks)}."
            )
        text = chunks[index - 1]
        selected.append(
            {
                "index": index,
                "text": text,
                "characters": len(text),
                "text_sha256": sha256_text(text),
                "output_path": str(args.output_dir / f"mlx_chunk_{index:04d}.wav"),
                "pytorch_reference": inspect_pytorch_reference(args.pytorch_cache_dir, index),
            }
        )
    return {
        "source": {
            "path": str(args.file),
            "file_sha256": sha256_bytes(source_bytes),
            "cleaned_text_sha256": sha256_text(cleaned),
            "total_chunks": len(chunks),
            "max_chars": args.max_chars,
        },
        "model": args.model,
        "output_dir": str(args.output_dir),
        "batch_size": args.batch_size,
        "selected_chunks": selected,
    }


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def load_mlx_runtime() -> MlxRuntime:
    # Keep every MLX import inside this function so --dry-run never initializes Metal.
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


def atomic_write_wav(
    destination: Path,
    audio: Any,
    sample_rate: int,
    runtime: MlxRuntime,
) -> dict[str, Any]:
    if sample_rate != EXPECTED_SAMPLE_RATE:
        raise BenchmarkError(
            f"MLX-Audio returned unexpected sample rate {sample_rate}; expected {EXPECTED_SAMPLE_RATE}."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=".tmp.wav",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        runtime.write_audio(temporary, audio, sample_rate, "wav")
        metadata = probe_wav(temporary)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    metadata["path"] = str(destination)
    metadata["size_bytes"] = destination.stat().st_size
    metadata["sha256"] = sha256_file(destination)
    return metadata


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


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


def serial_generate(
    model: Any,
    selected: list[dict[str, Any]],
    args: argparse.Namespace,
    clock: Callable[[], float],
) -> tuple[dict[int, Any], list[dict[str, Any]], float]:
    results: dict[int, Any] = {}
    groups: list[dict[str, Any]] = []
    generation_seconds = 0.0
    for item in selected:
        started = clock()
        generated = list(
            model.generate_custom_voice(
                text=item["text"],
                speaker=args.speaker,
                language=args.language,
                instruct=args.instruct or None,
                **generation_kwargs(args),
            )
        )
        elapsed = clock() - started
        generation_seconds += elapsed
        if len(generated) != 1:
            raise BenchmarkError(
                f"Serial generation for chunk {item['index']} returned {len(generated)} results."
            )
        results[item["index"]] = generated[0]
        groups.append(
            {
                "chunk_indices": [item["index"]],
                "requested_batch_size": 1,
                "effective_batch_size": 1,
                "generation_wall_seconds": elapsed,
            }
        )
    return results, groups, generation_seconds


def batched_generate(
    model: Any,
    selected: list[dict[str, Any]],
    args: argparse.Namespace,
    clock: Callable[[], float],
) -> tuple[dict[int, Any], list[dict[str, Any]], float]:
    results: dict[int, Any] = {}
    groups: list[dict[str, Any]] = []
    generation_seconds = 0.0
    kwargs = generation_kwargs(args)
    for offset in range(0, len(selected), args.batch_size):
        group = selected[offset : offset + args.batch_size]
        started = clock()
        generated = list(
            model.batch_generate(
                texts=[item["text"] for item in group],
                voices=[args.speaker] * len(group),
                instructs=[args.instruct or None] * len(group),
                lang_code=args.language,
                **kwargs,
            )
        )
        elapsed = clock() - started
        generation_seconds += elapsed
        by_sequence: dict[int, Any] = {}
        for result in generated:
            sequence_index = int(result.sequence_idx)
            if sequence_index in by_sequence:
                raise BenchmarkError(f"Batch returned duplicate sequence index {sequence_index}.")
            by_sequence[sequence_index] = result
        expected = set(range(len(group)))
        if set(by_sequence) != expected:
            raise BenchmarkError(
                f"Batch result indices {sorted(by_sequence)} do not match expected {sorted(expected)}."
            )
        for sequence_index, item in enumerate(group):
            results[item["index"]] = by_sequence[sequence_index]
        groups.append(
            {
                "chunk_indices": [item["index"] for item in group],
                "requested_batch_size": args.batch_size,
                "effective_batch_size": len(group),
                "generation_wall_seconds": elapsed,
            }
        )
    return results, groups, generation_seconds


def run_benchmark(
    args: argparse.Namespace,
    plan: dict[str, Any],
    runtime: MlxRuntime,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    benchmark_started = clock()
    load_started = clock()
    model = runtime.load_model(Path(args.model))
    load_seconds = clock() - load_started
    runtime.set_seed(args.seed)

    selected = plan["selected_chunks"]
    if args.batch_size == 1:
        generated, groups, generation_seconds = serial_generate(model, selected, args, clock)
        mode = "serial"
    else:
        generated, groups, generation_seconds = batched_generate(model, selected, args, clock)
        mode = "batch"

    chunk_records: list[dict[str, Any]] = []
    total_audio_seconds = 0.0
    for item in selected:
        result = generated[item["index"]]
        output = atomic_write_wav(
            Path(item["output_path"]),
            result.audio,
            int(result.sample_rate),
            runtime,
        )
        total_audio_seconds += output["duration_seconds"]
        chunk_records.append(
            {
                **item,
                "output": output,
                "mlx_reported": {
                    "samples": int(result.samples),
                    "sample_rate": int(result.sample_rate),
                    "token_count": int(result.token_count),
                    "processing_time_seconds": float(result.processing_time_seconds),
                    "peak_memory_gb": float(result.peak_memory_usage),
                },
            }
        )

    if total_audio_seconds <= 0.0 or generation_seconds <= 0.0:
        raise BenchmarkError("Benchmark timing or generated audio duration is not positive.")
    audio_seconds_by_index = {
        item["index"]: item["output"]["duration_seconds"] for item in chunk_records
    }
    group_by_index: dict[int, dict[str, Any]] = {}
    for group in groups:
        if group["generation_wall_seconds"] <= 0.0:
            raise BenchmarkError("A batch group's generation wall time is not positive.")
        group_audio_seconds = sum(
            audio_seconds_by_index[index] for index in group["chunk_indices"]
        )
        group["audio_duration_seconds"] = group_audio_seconds
        group["wall_per_audio_rtf"] = (
            group["generation_wall_seconds"] / group_audio_seconds
        )
        group["audio_per_wall_realtime"] = (
            group_audio_seconds / group["generation_wall_seconds"]
        )
        for index in group["chunk_indices"]:
            group_by_index[index] = group
    for item in chunk_records:
        group = group_by_index[item["index"]]
        item["timing"] = {
            "shared_batch_chunk_indices": list(group["chunk_indices"]),
            "generation_wall_seconds": group["generation_wall_seconds"],
            "audio_duration_seconds": item["output"]["duration_seconds"],
            "group_wall_per_audio_rtf": group["wall_per_audio_rtf"],
        }
    completed_seconds = clock() - benchmark_started
    aggregate = {
        "model_load_wall_seconds": load_seconds,
        "generation_wall_seconds": generation_seconds,
        "total_benchmark_wall_seconds": completed_seconds,
        "audio_duration_seconds": total_audio_seconds,
        "wall_per_audio_rtf": generation_seconds / total_audio_seconds,
        "audio_per_wall_realtime": total_audio_seconds / generation_seconds,
        "total_benchmark_wall_per_audio_rtf": completed_seconds / total_audio_seconds,
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engine": "mlx-audio-qwen3-tts-custom-voice",
        "mode": mode,
        "source": plan["source"],
        "model": {
            "path": args.model,
            "config_sha256": (
                sha256_file(Path(args.model) / "config.json")
                if (Path(args.model) / "config.json").is_file()
                else None
            ),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": runtime.versions,
        },
        "settings": {
            "speaker": args.speaker,
            "language": args.language,
            "instruct": args.instruct,
            "batch_size": args.batch_size,
            "chunk_indices": list(args.chunk_indices),
            "max_chars": args.max_chars,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "top_k": args.top_k,
            "repetition_penalty": args.repetition_penalty,
            "max_tokens": args.max_tokens,
            "non_streaming": True,
            "expected_output": "24000 Hz mono signed 16-bit PCM WAV",
        },
        "randomness": {
            "seed": args.seed,
            "scope": "MLX global PRNG",
            "applied": "once after model load and immediately before generation",
            "batch_composition_affects_sampling": True,
        },
        "batch_groups": groups,
        "aggregate": aggregate,
        "chunks": chunk_records,
    }
    manifest_path = args.output_dir / "benchmark_mlx_qwen3_tts_manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    atomic_write_json(manifest_path, manifest)
    manifest["manifest_file_sha256"] = sha256_file(manifest_path)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    try:
        invocation_dir = Path.cwd()
        args = validate_args(parse_args(argv), invocation_dir)
        generator = load_generator_module()
        plan = build_plan(args, generator)
        if args.dry_run:
            print(json.dumps({"dry_run": True, **plan}, ensure_ascii=False, indent=2))
            return 0
        runtime = load_mlx_runtime()
        manifest = run_benchmark(args, plan, runtime)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except (BenchmarkError, ImportError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compare cached PyTorch and candidate Qwen3-TTS chunks with one local ASR run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPT_DIR / "generate_qwen3_tts.py"
VERIFIER_PATH = SCRIPT_DIR / "verify_qwen3_tts_audio.py"
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
DEFAULT_MAX_CHARS = 160
EXPECTED_SAMPLE_RATE = 24000
SILENCE_DB = -45.0
SILENCE_MIN_SECONDS = 0.8
LONG_SILENCE_SECONDS = 3.0
MIN_BLOCK_COVERAGE = 0.18
MIN_TAIL_COVERAGE = 0.18
MIN_CANDIDATE_SIMILARITY = 0.80
MAX_SIMILARITY_DROP = 0.05
MAX_COVERAGE_DROP = 0.05
MIN_LENGTH_RATIO = 0.80
MAX_LENGTH_RATIO = 1.20
SCHEMA_VERSION = 1


class AbAsrError(RuntimeError):
    """Raised when an A/B input or analysis result is invalid."""


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


def load_script(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AbAsrError(f"Unable to import project script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_generator_module() -> ModuleType:
    return load_script(GENERATOR_PATH, "qwen3_tts_ab_generator")


def load_verifier_module() -> ModuleType:
    return load_script(VERIFIER_PATH, "qwen3_tts_ab_verifier")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare local PyTorch-cache and candidate Qwen3-TTS WAV chunks with "
            "one MLX Whisper process."
        )
    )
    parser.add_argument("--narration", type=Path, default=DEFAULT_NARRATION)
    parser.add_argument("--pytorch-cache-dir", type=Path, default=DEFAULT_PYTORCH_CACHE)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument(
        "--chunk-indices",
        type=int,
        nargs="+",
        default=list(DEFAULT_CHUNK_INDICES),
        metavar="N",
    )
    parser.add_argument(
        "--asr-model",
        type=Path,
        required=True,
        help="Existing local MLX Whisper model directory; downloads are never attempted",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg executable")
    return parser.parse_args(argv)


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def validate_args(args: argparse.Namespace, invocation_dir: Path) -> argparse.Namespace:
    args.narration = resolve_path(args.narration, invocation_dir)
    args.pytorch_cache_dir = resolve_path(args.pytorch_cache_dir, invocation_dir)
    args.candidate_dir = resolve_path(args.candidate_dir, invocation_dir)
    args.asr_model = resolve_path(args.asr_model, invocation_dir)
    if args.output_json is not None:
        args.output_json = resolve_path(args.output_json, invocation_dir)
    if not args.narration.is_file():
        raise AbAsrError(f"Narration file not found: {args.narration}")
    if not args.pytorch_cache_dir.is_dir():
        raise AbAsrError(f"PyTorch cache directory not found: {args.pytorch_cache_dir}")
    if not args.candidate_dir.is_dir():
        raise AbAsrError(f"Candidate directory not found: {args.candidate_dir}")
    if not args.asr_model.is_dir():
        raise AbAsrError(
            "--asr-model must be an existing local directory; downloads are disabled: "
            f"{args.asr_model}"
        )
    if not args.chunk_indices or any(index < 1 for index in args.chunk_indices):
        raise AbAsrError("--chunk-indices must contain one-based positive integers")
    if len(args.chunk_indices) != len(set(args.chunk_indices)):
        raise AbAsrError("Duplicate chunk indices are not allowed")
    return args


def resolve_candidate_wav(candidate_dir: Path, index: int) -> Path:
    preferred = candidate_dir / f"mlx_chunk_{index:04d}.wav"
    fallback = candidate_dir / f"chunk_{index:04d}.wav"
    if preferred.is_file():
        return preferred
    if fallback.is_file():
        return fallback
    raise AbAsrError(
        f"Candidate WAV not found for chunk {index}: checked {preferred.name} and {fallback.name}"
    )


def probe_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            compression = handle.getcomptype()
    except (OSError, EOFError, wave.Error) as exc:
        raise AbAsrError(f"Invalid WAV file {path}: {exc}") from exc
    if (
        channels != 1
        or sample_width != 2
        or sample_rate != EXPECTED_SAMPLE_RATE
        or frames <= 0
        or compression != "NONE"
    ):
        raise AbAsrError(
            f"Expected 24 kHz mono 16-bit PCM WAV at {path}; got channels={channels}, "
            f"width={sample_width}, rate={sample_rate}, frames={frames}, codec={compression}"
        )
    return {
        "path": str(path),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "compression": compression,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_plan(args: argparse.Namespace, generator: ModuleType) -> dict[str, Any]:
    source_bytes = args.narration.read_bytes()
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AbAsrError(f"Narration is not valid UTF-8: {args.narration}") from exc
    cleaned = generator.clean_narration(source_text)
    chunks = generator.split_narration(cleaned, DEFAULT_MAX_CHARS)
    pairs: list[dict[str, Any]] = []
    for index in args.chunk_indices:
        if index > len(chunks):
            raise AbAsrError(
                f"Chunk index {index} is outside the extracted range 1..{len(chunks)}"
            )
        reference_path = args.pytorch_cache_dir / f"chunk_{index:04d}.wav"
        if not reference_path.is_file():
            raise AbAsrError(f"PyTorch reference WAV not found: {reference_path}")
        candidate_path = resolve_candidate_wav(args.candidate_dir, index)
        text = chunks[index - 1]
        pairs.append(
            {
                "index": index,
                "text": text,
                "text_sha256": sha256_text(text),
                "characters": len(text),
                "reference_path": reference_path,
                "candidate_path": candidate_path,
            }
        )
    return {
        "source": {
            "path": str(args.narration),
            "file_sha256": sha256_bytes(source_bytes),
            "cleaned_text_sha256": sha256_text(cleaned),
            "total_chunks": len(chunks),
            "max_chars": DEFAULT_MAX_CHARS,
        },
        "pairs": pairs,
    }


def load_transcriber() -> tuple[Callable[..., dict[str, Any]], str]:
    # Import once, after every local path and WAV has been validated.
    try:
        import mlx_whisper
    except ImportError as exc:
        raise AbAsrError("mlx_whisper is not installed in this Python runtime") from exc
    version = getattr(mlx_whisper, "__version__", None)
    if not version:
        try:
            version = importlib.metadata.version("mlx-whisper")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
    return mlx_whisper.transcribe, str(version)


def run_asr(
    audio: Path,
    model_path: Path,
    transcribe: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    result = transcribe(
        str(audio),
        path_or_hf_repo=str(model_path),
        language="ko",
        task="transcribe",
        verbose=None,
        condition_on_previous_text=False,
    )
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise AbAsrError(f"mlx_whisper returned an invalid result for {audio}")
    return result


def analyze_audio(
    *,
    audio: Path,
    expected_text: str,
    model_path: Path,
    ffmpeg: str,
    transcribe: Callable[..., dict[str, Any]],
    verifier: ModuleType,
) -> dict[str, Any]:
    audio_probe = probe_wav(audio)
    decode = verifier.decode_entire_audio(
        audio,
        ffmpeg,
        sample_rate=EXPECTED_SAMPLE_RATE,
        quiet_db=SILENCE_DB,
    )
    decode["probe_duration_delta_seconds"] = abs(
        decode["duration_seconds"] - audio_probe["duration_seconds"]
    )
    silence = verifier.detect_silence(
        audio,
        ffmpeg,
        audio_probe["duration_seconds"],
        silence_db=SILENCE_DB,
        minimum_seconds=SILENCE_MIN_SECONDS,
        long_seconds=LONG_SILENCE_SECONDS,
    )
    long_regions = [
        region
        for region in silence["regions"]
        if float(region["duration_seconds"]) >= LONG_SILENCE_SECONDS
    ]
    asr_result = run_asr(audio, model_path, transcribe)
    comparison = verifier.compare_transcript(
        expected_text,
        asr_result,
        audio_probe["duration_seconds"],
        min_block_coverage=MIN_BLOCK_COVERAGE,
        min_tail_coverage=MIN_TAIL_COVERAGE,
    )
    normalized_asr = verifier.normalize_text(asr_result["text"])
    segments = [item for item in asr_result.get("segments", []) if isinstance(item, dict)]
    issues = {
        "omissions": len(comparison["large_omissions"]),
        "repetitions": len(comparison["large_repetitions"]),
        "tail_missing": int(bool(comparison["tail"]["missing"])),
        "end_clipping": int(bool(decode["end_clipping_risk"])),
        "long_silence_regions": len(long_regions),
    }
    return {
        "audio": audio_probe,
        "decode": decode,
        "silence": {**silence, "long_regions_at_least_3_seconds": long_regions},
        "asr": {
            "language": str(asr_result.get("language", "ko")),
            "text": asr_result["text"],
            "text_sha256": sha256_text(asr_result["text"]),
            "normalized_text_sha256": sha256_text(normalized_asr),
            "text_characters": len(asr_result["text"]),
            "normalized_characters": len(normalized_asr),
            "segments": len(segments),
        },
        "comparison": comparison,
        "issue_counts": issues,
    }


def evaluate_pair(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    reference_comparison = reference["comparison"]
    candidate_comparison = candidate["comparison"]
    similarity_absolute = candidate_comparison["similarity"] >= MIN_CANDIDATE_SIMILARITY
    similarity_relative = (
        candidate_comparison["similarity"]
        >= reference_comparison["similarity"] - MAX_SIMILARITY_DROP
    )
    coverage_pass = (
        candidate_comparison["reference_coverage"]
        >= reference_comparison["reference_coverage"] - MAX_COVERAGE_DROP
    )
    length_ratio_pass = (
        MIN_LENGTH_RATIO
        <= candidate_comparison["length_ratio"]
        <= MAX_LENGTH_RATIO
    )
    issue_passes = {
        name: count == 0 for name, count in candidate["issue_counts"].items()
    }
    criteria = {
        "similarity": {
            "passed": similarity_absolute or similarity_relative,
            "candidate_at_least_0_80": similarity_absolute,
            "candidate_within_0_05_of_reference": similarity_relative,
        },
        "reference_coverage": {
            "passed": coverage_pass,
            "minimum": max(0.0, reference_comparison["reference_coverage"] - 0.05),
        },
        "length_ratio_0_8_to_1_2": length_ratio_pass,
        "zero_candidate_issues": issue_passes,
    }
    passed = (
        criteria["similarity"]["passed"]
        and coverage_pass
        and length_ratio_pass
        and all(issue_passes.values())
    )
    return {
        "passed": passed,
        "deltas_candidate_minus_reference": {
            "similarity": candidate_comparison["similarity"]
            - reference_comparison["similarity"],
            "reference_coverage": candidate_comparison["reference_coverage"]
            - reference_comparison["reference_coverage"],
            "length_ratio": candidate_comparison["length_ratio"]
            - reference_comparison["length_ratio"],
            "tail_coverage": candidate_comparison["tail"]["coverage"]
            - reference_comparison["tail"]["coverage"],
            "audio_duration_seconds": candidate["audio"]["duration_seconds"]
            - reference["audio"]["duration_seconds"],
        },
        "criteria": criteria,
    }


def build_report(
    args: argparse.Namespace,
    plan: dict[str, Any],
    *,
    ffmpeg: str,
    transcribe: Callable[..., dict[str, Any]],
    asr_version: str,
    verifier: ModuleType,
) -> dict[str, Any]:
    pair_reports: list[dict[str, Any]] = []
    for pair in plan["pairs"]:
        reference = analyze_audio(
            audio=pair["reference_path"],
            expected_text=pair["text"],
            model_path=args.asr_model,
            ffmpeg=ffmpeg,
            transcribe=transcribe,
            verifier=verifier,
        )
        candidate = analyze_audio(
            audio=pair["candidate_path"],
            expected_text=pair["text"],
            model_path=args.asr_model,
            ffmpeg=ffmpeg,
            transcribe=transcribe,
            verifier=verifier,
        )
        pair_reports.append(
            {
                "index": pair["index"],
                "text": pair["text"],
                "text_sha256": pair["text_sha256"],
                "characters": pair["characters"],
                "reference": reference,
                "candidate": candidate,
                "evaluation": evaluate_pair(reference, candidate),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(pair["evaluation"]["passed"] for pair in pair_reports),
        "source": plan["source"],
        "asr": {
            "engine": "mlx_whisper",
            "version": asr_version,
            "model_path": str(args.asr_model),
            "language": "ko",
            "condition_on_previous_text": False,
            "same_process": True,
            "transcriptions": len(pair_reports) * 2,
        },
        "thresholds": {
            "candidate_similarity_absolute": MIN_CANDIDATE_SIMILARITY,
            "maximum_similarity_drop_from_reference": MAX_SIMILARITY_DROP,
            "maximum_reference_coverage_drop": MAX_COVERAGE_DROP,
            "candidate_length_ratio": [MIN_LENGTH_RATIO, MAX_LENGTH_RATIO],
            "large_omission_block_coverage": MIN_BLOCK_COVERAGE,
            "tail_coverage": MIN_TAIL_COVERAGE,
            "long_silence_seconds": LONG_SILENCE_SECONDS,
            "silence_db": SILENCE_DB,
        },
        "pairs": pair_reports,
    }


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


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = validate_args(parse_args(argv), Path.cwd().resolve())
        generator = load_generator_module()
        verifier = load_verifier_module()
        plan = build_plan(args, generator)
        # Probe all six WAVs before importing MLX Whisper or initializing Metal.
        for pair in plan["pairs"]:
            probe_wav(pair["reference_path"])
            probe_wav(pair["candidate_path"])
        ffmpeg = verifier.find_program(args.ffmpeg, "ffmpeg")
        transcribe, asr_version = load_transcriber()
        report = build_report(
            args,
            plan,
            ffmpeg=ffmpeg,
            transcribe=transcribe,
            asr_version=asr_version,
            verifier=verifier,
        )
        if args.output_json is not None:
            atomic_write_json(args.output_json, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    except (AbAsrError, ImportError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

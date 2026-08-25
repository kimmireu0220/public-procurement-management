#!/usr/bin/env python3
"""Read-only structural and ASR QA for one Qwen3-TTS chapter MP3."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from array import array
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Keep the format contract in one place: the batch generator already owns it.
from generate_qwen3_tts_batch import BatchError, probe_mp3  # noqa: E402


DEFAULT_RUNTIME_PYTHON = Path("/Users/kimmireu/.cache/ai-content/qwen3tts-venv/bin/python")
DEFAULT_ASR_MODEL = "mlx-community/whisper-small-mlx"
RUNTIME_GUARD = "_QWEN3_TTS_AUDIO_QA_REEXEC"
SILENCE_START_RE = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
SILENCE_END_RE = re.compile(
    r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?)"
)


class AudioQaError(RuntimeError):
    """Raised when the input cannot be verified safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify one 24 kHz mono chapter MP3 against its Korean narration."
    )
    parser.add_argument("audio", type=Path, help="Chapter MP3 to inspect (never modified)")
    parser.add_argument("transcript", type=Path, help="UTF-8 narration used for synthesis")
    parser.add_argument("--model", default=DEFAULT_ASR_MODEL, help="Local MLX Whisper model or repo ID")
    parser.add_argument("--revision", default=None, help="Optional Hugging Face model revision")
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow downloading the public ASR model when it is not already cached",
    )
    parser.add_argument("--runtime-python", type=Path, help="Python containing mlx_whisper")
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg executable")
    parser.add_argument("--ffprobe", help="Explicit ffprobe executable")
    parser.add_argument(
        "--asr-json",
        type=Path,
        help="Use an existing raw MLX Whisper JSON result instead of running ASR",
    )
    parser.add_argument("--silence-db", type=float, default=-45.0)
    parser.add_argument("--silence-min-seconds", type=float, default=0.8)
    parser.add_argument("--long-silence-seconds", type=float, default=3.0)
    parser.add_argument("--min-similarity", type=float, default=0.45)
    parser.add_argument("--min-block-coverage", type=float, default=0.18)
    parser.add_argument("--min-tail-coverage", type=float, default=0.18)
    parser.add_argument("--json", action="store_true", help="Emit one JSON report")
    parser.add_argument(
        "--include-asr-text",
        action="store_true",
        help="Include the complete recognized text in JSON output",
    )
    return parser.parse_args(argv)


def resolve_input(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = invocation_dir / expanded
    return expanded.resolve()


def find_program(requested: str | None, name: str) -> str:
    if requested:
        candidate = Path(requested).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(requested)
        if found:
            return found
        raise AudioQaError(f"{name} executable not found: {requested}")
    found = shutil.which(name)
    fallback = Path("/opt/homebrew/bin") / name
    if found:
        return found
    if fallback.is_file():
        return str(fallback)
    raise AudioQaError(f"{name} is required but was not found")


def ensure_asr_runtime(args: argparse.Namespace) -> None:
    if args.asr_json is not None or importlib.util.find_spec("mlx_whisper") is not None:
        return
    if os.environ.get(RUNTIME_GUARD) == "1":
        raise AudioQaError("Configured ASR runtime does not contain mlx_whisper")
    configured = args.runtime_python
    if configured is None and os.environ.get("QWEN3_TTS_PYTHON"):
        configured = Path(os.environ["QWEN3_TTS_PYTHON"])
    runtime = (configured or DEFAULT_RUNTIME_PYTHON).expanduser()
    if not runtime.is_absolute():
        runtime = (Path.cwd() / runtime).absolute()
    if not runtime.is_file():
        raise AudioQaError(
            "MLX Whisper runtime not found; install mlx-whisper or pass --runtime-python "
            f"(checked {runtime})"
        )
    env = os.environ.copy()
    env[RUNTIME_GUARD] = "1"
    completed = subprocess.run([str(runtime), str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
    raise SystemExit(completed.returncode)


def resolve_asr_model(model: str, revision: str | None, allow_download: bool) -> str:
    candidate = Path(model).expanduser()
    if candidate.is_dir():
        return str(candidate.resolve())
    if candidate.is_absolute() or model.startswith("."):
        raise AudioQaError(f"ASR model directory not found: {candidate}")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise AudioQaError("huggingface_hub is required to resolve an MLX Whisper model") from exc
    try:
        snapshot = snapshot_download(repo_id=model, revision=revision, local_files_only=True)
    except Exception as local_exc:
        if not allow_download:
            raise AudioQaError(
                f"ASR model is not in the local cache: {model}; pass --allow-download to fetch it"
            ) from local_exc
        snapshot = snapshot_download(repo_id=model, revision=revision, local_files_only=False)
    return str(Path(snapshot).resolve())


def decode_entire_audio(
    audio: Path,
    ffmpeg: str,
    *,
    sample_rate: int = 24000,
    tail_seconds: float = 2.0,
    quiet_db: float = -45.0,
) -> dict[str, Any]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-xerror",
        "-i",
        str(audio),
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-codec:a",
        "pcm_s16le",
        "-f",
        "s16le",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise AudioQaError("ffmpeg pipes could not be opened")
    total_bytes = 0
    keep_bytes = max(2, round(sample_rate * tail_seconds) * 2)
    tail = bytearray()
    while True:
        chunk = process.stdout.read(1024 * 1024)
        if not chunk:
            break
        total_bytes += len(chunk)
        tail.extend(chunk)
        if len(tail) > keep_bytes:
            del tail[:-keep_bytes]
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        detail = stderr.strip() or f"exit {return_code}"
        raise AudioQaError(f"ffmpeg could not decode the complete MP3: {detail}")
    if total_bytes <= 0 or total_bytes % 2:
        raise AudioQaError(f"ffmpeg produced an invalid PCM byte count: {total_bytes}")

    if len(tail) % 2:
        del tail[-1]
    samples = array("h")
    samples.frombytes(tail)
    if sys.byteorder != "little":
        samples.byteswap()
    boundary = terminal_boundary_metrics(samples, sample_rate, quiet_db=quiet_db)
    tail_clipped = sum(1 for value in samples if abs(value) >= 32760)
    return {
        "complete": True,
        "pcm_bytes": total_bytes,
        "decoded_samples": total_bytes // 2,
        "duration_seconds": total_bytes / 2 / sample_rate,
        "tail_window_seconds": len(samples) / sample_rate,
        "trailing_quiet_seconds": boundary["trailing_quiet_ms"] / 1000,
        "last_50ms_rms_dbfs": window_rms_dbfs(samples, sample_rate, 0.05),
        "last_200ms_rms_dbfs": window_rms_dbfs(samples, sample_rate, 0.2),
        "tail_clipped_samples": tail_clipped,
        "terminal_boundary": boundary,
        "end_clipping_risk": not boundary["safe"],
    }


def amplitude_dbfs(value: float) -> float:
    """Return dBFS for an int16-domain amplitude or RMS value."""
    return 20.0 * math.log10(max(abs(float(value)) / 32768.0, 1e-12))


def window_rms_dbfs(samples: array, sample_rate: int, seconds: float) -> float | None:
    count = min(len(samples), max(1, round(sample_rate * seconds)))
    if not count:
        return None
    energy = sum(int(value) * int(value) for value in samples[-count:]) / count
    return amplitude_dbfs(math.sqrt(energy))


def terminal_release_metrics(samples: array, sample_rate: int) -> dict[str, Any]:
    """Detect an audible syllable dropping to silence within one 10 ms frame."""
    window = max(1, round(sample_rate * 0.010))
    scan = max(window * 2, round(sample_rate * 0.200))
    start = max(0, len(samples) - scan)
    start += (len(samples) - start) % window
    levels: list[float] = []
    for cursor in range(start, len(samples) - window + 1, window):
        chunk = samples[cursor : cursor + window]
        energy = sum(int(value) * int(value) for value in chunk) / len(chunk)
        levels.append(amplitude_dbfs(math.sqrt(energy)))
    audible_drops = [
        left - right
        for left, right in zip(levels, levels[1:])
        if left > -45.0
    ]
    maximum_drop = max(audible_drops, default=0.0)
    return {
        "scan_ms": 200.0,
        "window_ms": 10.0,
        "audible_floor_dbfs": -45.0,
        "max_10ms_drop_db": maximum_drop,
        "max_allowed_drop_db": 9.0,
        "safe": maximum_drop < 9.0,
    }


def terminal_boundary_metrics(
    samples: array, sample_rate: int, *, quiet_db: float = -45.0
) -> dict[str, Any]:
    """Measure whether the decoded MP3 reaches a quiet, non-abrupt ending."""
    if sample_rate <= 0 or not samples:
        raise AudioQaError("Decoded audio must contain samples at a positive sample rate")
    frame = max(1, round(sample_rate / 1000))
    quiet_frames = 0
    cursor = len(samples)
    while cursor - frame >= 0:
        chunk = samples[cursor - frame : cursor]
        energy = sum(int(value) * int(value) for value in chunk) / len(chunk)
        if amplitude_dbfs(math.sqrt(energy)) >= quiet_db:
            break
        quiet_frames += 1
        cursor -= frame
    final_rms_dbfs = window_rms_dbfs(samples, sample_rate, 0.005)
    if final_rms_dbfs is None:
        raise AudioQaError("Decoded tail is empty")
    final_sample_dbfs = amplitude_dbfs(samples[-1])
    release = terminal_release_metrics(samples, sample_rate)
    quiet_ms = quiet_frames * frame * 1000 / sample_rate
    reaches_quiet = quiet_ms >= 20.0 or final_rms_dbfs <= -45.0
    return {
        "trailing_quiet_ms": quiet_ms,
        "final_5ms_rms_dbfs": final_rms_dbfs,
        "final_sample_dbfs": final_sample_dbfs,
        "terminal_release": release,
        "safe": reaches_quiet and final_sample_dbfs <= -52.0 and release["safe"],
    }


def parse_silence_log(log: str, duration_seconds: float) -> list[dict[str, float]]:
    regions: list[dict[str, float]] = []
    open_start: float | None = None
    for line in log.splitlines():
        start = SILENCE_START_RE.search(line)
        if start:
            open_start = max(0.0, float(start.group(1)))
        end = SILENCE_END_RE.search(line)
        if end:
            end_seconds = min(duration_seconds, max(0.0, float(end.group(1))))
            logged_duration = max(0.0, float(end.group(2)))
            start_seconds = open_start
            if start_seconds is None:
                start_seconds = max(0.0, end_seconds - logged_duration)
            regions.append(
                {
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "duration_seconds": max(0.0, end_seconds - start_seconds),
                }
            )
            open_start = None
    if open_start is not None and duration_seconds >= open_start:
        regions.append(
            {
                "start_seconds": open_start,
                "end_seconds": duration_seconds,
                "duration_seconds": duration_seconds - open_start,
            }
        )
    return regions


def detect_silence(
    audio: Path,
    ffmpeg: str,
    duration_seconds: float,
    *,
    silence_db: float,
    minimum_seconds: float,
    long_seconds: float,
) -> dict[str, Any]:
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-nostats",
            "-i",
            str(audio),
            "-af",
            f"silencedetect=noise={silence_db:g}dB:d={minimum_seconds:g}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise AudioQaError(f"ffmpeg silencedetect failed: {detail}")
    regions = parse_silence_log(completed.stderr, duration_seconds)
    leading = regions[0]["duration_seconds"] if regions and regions[0]["start_seconds"] <= 0.05 else 0.0
    trailing = (
        regions[-1]["duration_seconds"]
        if regions and duration_seconds - regions[-1]["end_seconds"] <= 0.05
        else 0.0
    )
    internal_long = [
        region
        for region in regions
        if region["duration_seconds"] >= long_seconds
        and region["start_seconds"] > 0.05
        and duration_seconds - region["end_seconds"] > 0.05
    ]
    return {
        "threshold_db": silence_db,
        "minimum_seconds": minimum_seconds,
        "regions": regions,
        "leading_seconds": leading,
        "trailing_seconds": trailing,
        "internal_long_regions": internal_long,
        "maximum_seconds": max((region["duration_seconds"] for region in regions), default=0.0),
    }


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(character for character in normalized if character.isalnum())


def ngram_counter(text: str, width: int = 3) -> Counter[str]:
    if not text:
        return Counter()
    if len(text) < width:
        return Counter({text: 1})
    return Counter(text[index : index + width] for index in range(len(text) - width + 1))


def ngram_scores(reference: str, hypothesis: str, width: int = 3) -> dict[str, float]:
    reference_counts = ngram_counter(reference, width)
    hypothesis_counts = ngram_counter(hypothesis, width)
    common = sum((reference_counts & hypothesis_counts).values())
    reference_total = sum(reference_counts.values())
    hypothesis_total = sum(hypothesis_counts.values())
    return {
        "similarity": (2 * common / (reference_total + hypothesis_total))
        if reference_total + hypothesis_total
        else 1.0,
        "reference_coverage": common / reference_total if reference_total else 1.0,
        "hypothesis_precision": common / hypothesis_total if hypothesis_total else 1.0,
    }


def reference_blocks(text: str, target_chars: int = 240) -> list[tuple[str, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    blocks: list[tuple[str, str]] = []
    pending: list[str] = []
    pending_chars = 0
    for paragraph in paragraphs:
        normalized = normalize_text(paragraph)
        if pending and pending_chars + len(normalized) > target_chars * 1.5:
            raw = " ".join(pending)
            blocks.append((raw, normalize_text(raw)))
            pending = []
            pending_chars = 0
        pending.append(paragraph)
        pending_chars += len(normalized)
        if pending_chars >= target_chars:
            raw = " ".join(pending)
            blocks.append((raw, normalize_text(raw)))
            pending = []
            pending_chars = 0
    if pending:
        raw = " ".join(pending)
        blocks.append((raw, normalize_text(raw)))
    return blocks


def segment_text(segment: dict[str, Any]) -> str:
    return normalize_text(str(segment.get("text", "")))


def repeated_windows(
    segments: list[dict[str, Any]], reference: str, *, threshold: float = 0.90
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    normalized_reference = normalize_text(reference)
    reference_eight_grams = ngram_counter(normalized_reference, 8)
    for index in range(len(segments) - 1):
        for width in (1, 2, 3):
            if index + 2 * width > len(segments):
                continue
            left = "".join(segment_text(item) for item in segments[index : index + width])
            right = "".join(segment_text(item) for item in segments[index + width : index + 2 * width])
            if min(len(left), len(right)) < 30:
                continue
            similarity = ngram_scores(left, right)["similarity"]
            if similarity < threshold:
                continue
            anchors = set(ngram_counter(left, 8))
            source_also_repeats = bool(anchors) and (
                sum(1 for anchor in anchors if reference_eight_grams[anchor] >= 2) / len(anchors) >= 0.30
            )
            if source_also_repeats:
                continue
            findings.append(
                {
                    "segment_index": index,
                    "window_segments": width,
                    "start_seconds": float(segments[index].get("start", 0.0)),
                    "end_seconds": float(segments[index + 2 * width - 1].get("end", 0.0)),
                    "similarity": similarity,
                    "excerpt": str(segments[index].get("text", "")).strip()[:100],
                }
            )
            break
        if len(findings) >= 10:
            break
    return findings


def compare_transcript(
    reference: str,
    asr_result: dict[str, Any],
    duration_seconds: float,
    *,
    min_block_coverage: float,
    min_tail_coverage: float,
) -> dict[str, Any]:
    hypothesis_text = str(asr_result.get("text", ""))
    segments = [item for item in asr_result.get("segments", []) if isinstance(item, dict)]
    normalized_reference = normalize_text(reference)
    normalized_hypothesis = normalize_text(hypothesis_text)
    if not normalized_reference:
        raise AudioQaError("Transcript is empty after normalization")
    if not normalized_hypothesis:
        raise AudioQaError("ASR returned no recognizable text")
    scores = ngram_scores(normalized_reference, normalized_hypothesis)

    omissions: list[dict[str, Any]] = []
    for index, (raw_block, normalized_block) in enumerate(reference_blocks(reference)):
        if len(normalized_block) < 80:
            continue
        coverage = ngram_scores(normalized_block, normalized_hypothesis)["reference_coverage"]
        if coverage < min_block_coverage:
            omissions.append(
                {
                    "block_index": index,
                    "normalized_chars": len(normalized_block),
                    "coverage": coverage,
                    "excerpt": re.sub(r"\s+", " ", raw_block).strip()[:160],
                }
            )

    reference_tail = normalized_reference[-300:]
    hypothesis_tail_width = max(1200, round(len(normalized_hypothesis) * 0.15))
    hypothesis_tail = normalized_hypothesis[-hypothesis_tail_width:]
    tail_coverage = ngram_scores(reference_tail, hypothesis_tail)["reference_coverage"]
    last_asr_end = max((float(item.get("end", 0.0)) for item in segments), default=0.0)
    tail_gap_seconds = max(0.0, duration_seconds - last_asr_end)
    repetitions = repeated_windows(segments, reference)

    return {
        "method": "Unicode NFKC alphanumeric character trigram multiset",
        "normalized_reference_chars": len(normalized_reference),
        "normalized_asr_chars": len(normalized_hypothesis),
        "length_ratio": len(normalized_hypothesis) / len(normalized_reference),
        **scores,
        "large_omissions": omissions,
        "large_repetitions": repetitions,
        "tail": {
            "reference_chars": len(reference_tail),
            "searched_asr_tail_chars": len(hypothesis_tail),
            "coverage": tail_coverage,
            "last_asr_end_seconds": last_asr_end,
            "audio_gap_after_last_asr_seconds": tail_gap_seconds,
            "missing": tail_coverage < min_tail_coverage,
        },
    }


def load_asr_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudioQaError(f"Could not read ASR JSON {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise AudioQaError("ASR JSON must be an MLX Whisper object containing text and segments")
    return payload


def run_asr(audio: Path, model_source: str) -> dict[str, Any]:
    try:
        from mlx_whisper import transcribe
    except ImportError as exc:
        raise AudioQaError("mlx_whisper is not installed in the selected runtime") from exc
    result = transcribe(
        str(audio),
        path_or_hf_repo=model_source,
        language="ko",
        task="transcribe",
        verbose=None,
        condition_on_previous_text=False,
    )
    if not isinstance(result, dict):
        raise AudioQaError("MLX Whisper returned an invalid result")
    return result


def build_report(args: argparse.Namespace, invocation_dir: Path) -> dict[str, Any]:
    audio = resolve_input(args.audio, invocation_dir)
    transcript_path = resolve_input(args.transcript, invocation_dir)
    if not audio.is_file():
        raise AudioQaError(f"Audio file not found: {audio}")
    if not transcript_path.is_file():
        raise AudioQaError(f"Transcript file not found: {transcript_path}")
    try:
        transcript = transcript_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AudioQaError(f"Could not read transcript {transcript_path}: {exc}") from exc
    if not transcript.strip():
        raise AudioQaError(f"Transcript is empty: {transcript_path}")

    ffmpeg = find_program(args.ffmpeg, "ffmpeg")
    ffprobe = find_program(args.ffprobe, "ffprobe")
    try:
        audio_probe = probe_mp3(audio, ffprobe)
    except BatchError as exc:
        raise AudioQaError(str(exc)) from exc
    decode = decode_entire_audio(audio, ffmpeg, quiet_db=args.silence_db)
    decode["probe_duration_delta_seconds"] = abs(
        decode["duration_seconds"] - audio_probe["duration_seconds"]
    )
    silence = detect_silence(
        audio,
        ffmpeg,
        audio_probe["duration_seconds"],
        silence_db=args.silence_db,
        minimum_seconds=args.silence_min_seconds,
        long_seconds=args.long_silence_seconds,
    )

    if args.asr_json is not None:
        asr_path = resolve_input(args.asr_json, invocation_dir)
        asr_result = load_asr_json(asr_path)
        model_label = f"precomputed:{asr_path}"
    else:
        model_source = resolve_asr_model(args.model, args.revision, args.allow_download)
        asr_result = run_asr(audio, model_source)
        model_label = args.model
    comparison = compare_transcript(
        transcript,
        asr_result,
        audio_probe["duration_seconds"],
        min_block_coverage=args.min_block_coverage,
        min_tail_coverage=args.min_tail_coverage,
    )
    asr_segments = [item for item in asr_result.get("segments", []) if isinstance(item, dict)]

    warnings: list[str] = []
    failures: list[str] = []
    if decode["probe_duration_delta_seconds"] > 0.10:
        failures.append("decoded duration differs from ffprobe by more than 0.10 seconds")
    if decode["end_clipping_risk"]:
        failures.append("audio ends while the final 50 ms remains loud; possible end clipping")
    if decode["tail_clipped_samples"]:
        warnings.append("digitally clipped samples were found in the final two seconds")
    if silence["leading_seconds"] > 1.0:
        warnings.append("leading silence exceeds one second")
    if silence["trailing_seconds"] > 1.0:
        warnings.append("trailing silence exceeds one second")
    if silence["internal_long_regions"]:
        failures.append(
            f"{len(silence['internal_long_regions'])} internal silence region(s) exceed "
            f"{args.long_silence_seconds:g} seconds"
        )
    if comparison["similarity"] < args.min_similarity:
        failures.append(
            f"normalized transcript-ASR similarity {comparison['similarity']:.3f} is below "
            f"{args.min_similarity:.3f}"
        )
    if not 0.70 <= comparison["length_ratio"] <= 1.30:
        failures.append(f"normalized ASR/reference length ratio is {comparison['length_ratio']:.3f}")
    if comparison["large_omissions"]:
        failures.append(f"{len(comparison['large_omissions'])} possible large omission block(s)")
    if comparison["large_repetitions"]:
        failures.append(f"{len(comparison['large_repetitions'])} possible repeated ASR window(s)")
    if comparison["tail"]["missing"]:
        failures.append("the transcript ending was not found near the ASR ending")
    if comparison["tail"]["audio_gap_after_last_asr_seconds"] > 5.0:
        warnings.append("more than five seconds follow the final ASR segment")

    report: dict[str, Any] = {
        "ok": not failures,
        "audio_path": str(audio),
        "transcript_path": str(transcript_path),
        "audio": audio_probe,
        "decode": decode,
        "silence": silence,
        "asr": {
            "engine": "mlx_whisper",
            "model": model_label,
            "language": str(asr_result.get("language", "ko")),
            "segments": len(asr_segments),
            "text_chars": len(str(asr_result.get("text", ""))),
            "text_head": str(asr_result.get("text", "")).strip()[:160],
            "text_tail": str(asr_result.get("text", "")).strip()[-160:],
        },
        "comparison": comparison,
        "warnings": warnings,
        "failures": failures,
    }
    if args.include_asr_text:
        report["asr"]["text"] = str(asr_result.get("text", ""))
    return report


def print_summary(report: dict[str, Any]) -> None:
    comparison = report["comparison"]
    print(f"status: {'PASS' if report['ok'] else 'FAIL'}")
    print(f"audio: {report['audio_path']}")
    print(
        "format: "
        f"{report['audio']['codec']}, {report['audio']['sample_rate']} Hz, "
        f"{report['audio']['channels']} channel, {report['audio']['duration_seconds']:.3f} s"
    )
    print(
        "decode: complete, "
        f"duration delta {report['decode']['probe_duration_delta_seconds']:.3f} s, "
        f"tail quiet {report['decode']['trailing_quiet_seconds']:.3f} s, "
        f"end clipping risk={report['decode']['end_clipping_risk']}"
    )
    print(
        "silence: "
        f"{len(report['silence']['regions'])} region(s), "
        f"{len(report['silence']['internal_long_regions'])} internal long region(s)"
    )
    print(
        "ASR comparison: "
        f"similarity={comparison['similarity']:.3f}, "
        f"reference coverage={comparison['reference_coverage']:.3f}, "
        f"length ratio={comparison['length_ratio']:.3f}"
    )
    print(
        "content risks: "
        f"omissions={len(comparison['large_omissions'])}, "
        f"repetitions={len(comparison['large_repetitions'])}, "
        f"tail coverage={comparison['tail']['coverage']:.3f}"
    )
    for warning in report["warnings"]:
        print(f"warning: {warning}")
    for failure in report["failures"]:
        print(f"failure: {failure}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if argv is None:
            ensure_asr_runtime(args)
        report = build_report(args, Path.cwd().resolve())
    except SystemExit:
        raise
    except (AudioQaError, OSError, ValueError, subprocess.SubprocessError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

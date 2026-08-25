#!/usr/bin/env python3
"""Generate resumable Korean lecture audio with Qwen3-TTS CustomVoice Sohee."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime
from pathlib import Path


DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
DEFAULT_RUNTIME_PYTHON = Path("/Users/kimmireu/.cache/ai-content/qwen3tts-venv/bin/python")
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_INSTRUCT = "차분하고 명료한 한국어 강의 톤으로 또박또박 말해 주세요."
CACHE_VERSION = "1"
START_RE = re.compile(r"^\[\[SECTION_START\|(P\d{2})\|(C\d{2})\|(S\d{2})\|([^\]\r\n]+)\]\]$")
END_RE = re.compile(r"^\[\[SECTION_END\|(P\d{2})\|(C\d{2})\|(S\d{2})\]\]$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Korean Qwen3-TTS Sohee narration.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Target Korean narration")
    source.add_argument("--file", type=Path, help="UTF-8 Markdown or plain-text narration")
    source.add_argument("--stdin", action="store_true", help="Read narration from stdin")
    parser.add_argument("--output", type=Path, help="Single MP3 or WAV output")
    parser.add_argument("--split-sections", action="store_true", help="Create one file per SECTION block")
    parser.add_argument("--output-dir", type=Path, help="Directory for section audio")
    parser.add_argument("--format", choices=("mp3", "wav"), default="mp3")
    parser.add_argument("--model", default=os.environ.get("QWEN3_TTS_MODEL", DEFAULT_MODEL))
    parser.add_argument("--revision", default=None, help="Optional Hugging Face model revision")
    parser.add_argument("--allow-download", action="store_true", help="Download public model weights when not cached")
    parser.add_argument("--runtime-python", type=Path, help="Python executable containing qwen_tts")
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--instruct", default=DEFAULT_INSTRUCT)
    parser.add_argument("--max-chars", type=int, default=160)
    parser.add_argument("--pause-ms", type=int, default=250, help="Silence inserted between generated chunks")
    parser.add_argument("--speed", type=float, default=1.0, help="Post-process playback speed")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--clean-cache", action="store_true")
    return parser.parse_args()


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def ensure_runtime_python(args: argparse.Namespace) -> None:
    if os.environ.get("_QWEN3_TTS_UNIFIED_REEXEC") == "1":
        return
    if importlib.util.find_spec("qwen_tts") is not None and importlib.util.find_spec("torch") is not None:
        return
    configured = args.runtime_python or (
        Path(os.environ["QWEN3_TTS_PYTHON"]) if os.environ.get("QWEN3_TTS_PYTHON") else DEFAULT_RUNTIME_PYTHON
    )
    runtime_python = configured.expanduser()
    if not runtime_python.is_absolute():
        runtime_python = (Path.cwd() / runtime_python).absolute()
    if not runtime_python.is_file():
        raise RuntimeError(
            "Qwen3-TTS runtime Python not found. Install qwen-tts in an isolated environment "
            f"or set QWEN3_TTS_PYTHON; checked: {runtime_python}"
        )
    env = os.environ.copy()
    env["_QWEN3_TTS_UNIFIED_REEXEC"] = "1"
    completed = subprocess.run([str(runtime_python), str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
    raise SystemExit(completed.returncode)


def load_text(args: argparse.Namespace, invocation_dir: Path) -> str:
    if args.text is not None:
        text = args.text
    elif args.file is not None:
        text = resolve_path(args.file, invocation_dir).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise ValueError("The narration text is empty.")
    return text


def clean_narration(text: str) -> str:
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"[-*_]{3,}", line):
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = line.replace("**", "").replace("__", "").replace("`", "")
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def parse_sections(text: str) -> list[tuple[str, str, str, str, str]]:
    sections: list[tuple[str, str, str, str, str]] = []
    current: tuple[str, str, str, str] | None = None
    content: list[str] = []
    outside_nonblank: list[str] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        start = START_RE.fullmatch(line)
        end = END_RE.fullmatch(line)
        if "[[SECTION_" in line and start is None and end is None:
            raise ValueError(f"Malformed SECTION marker at line {line_number}.")
        if start:
            if current is not None:
                raise ValueError(f"Nested SECTION_START at line {line_number}.")
            current = start.groups()
            content = []
        elif end:
            if current is None:
                raise ValueError(f"SECTION_END without SECTION_START at line {line_number}.")
            if end.groups() != current[:3]:
                raise ValueError(f"Mismatched SECTION_END at line {line_number}.")
            spoken = clean_narration("\n".join(content))
            if not spoken:
                raise ValueError(f"Empty section {'_'.join(current[:3])}.")
            sections.append((*current, spoken))
            current = None
            content = []
        elif current is not None:
            content.append(raw)
        elif line:
            outside_nonblank.append(f"line {line_number}: {line[:80]}")
    if current is not None:
        raise ValueError(f"Unclosed SECTION_START for {'_'.join(current[:3])}.")
    if outside_nonblank:
        raise ValueError("Spoken text outside SECTION blocks: " + "; ".join(outside_nonblank[:3]))
    if not sections:
        raise ValueError("No valid SECTION blocks found.")
    ids = [section[:3] for section in sections]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate SECTION identifiers found.")
    if ids != sorted(ids):
        raise ValueError("SECTION identifiers are not in ascending Part/Chapter/subsection order.")
    return sections


def split_narration(text: str, max_chars: int) -> list[str]:
    if max_chars < 50:
        raise ValueError("--max-chars must be at least 50.")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", paragraph) if part.strip()]
        for sentence in sentences or [paragraph]:
            remaining = sentence
            while len(remaining) > max_chars:
                window = remaining[: max_chars + 1]
                split_at = max(window.rfind(mark) for mark in (" ", ",", ";", ":", "，", "；", "："))
                if split_at < max_chars // 2:
                    split_at = max_chars
                units.append(remaining[:split_at].strip())
                remaining = remaining[split_at:].strip()
            if remaining:
                units.append(remaining)
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def find_program(name: str) -> str:
    program = shutil.which(name)
    if program is not None:
        return program
    fallback = Path("/opt/homebrew/bin") / name
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError(f"{name} is required but was not found.")


def valid_wav(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 1024:
            return False
        with wave.open(str(path), "rb") as handle:
            return (
                handle.getnchannels() == 1
                and handle.getsampwidth() == 2
                and handle.getframerate() == 24000
                and handle.getnframes() > 0
            )
    except (OSError, EOFError, wave.Error):
        return False


def valid_output(path: Path) -> bool:
    if path.suffix.lower() == ".wav":
        return valid_wav(path)
    if not path.is_file() or path.stat().st_size < 1024:
        return False
    try:
        probe = subprocess.run(
            [find_program("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(probe.stdout.strip()) > 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False


def save_wav(path: Path, sample_rate: int, audio) -> None:
    import numpy as np

    values = np.asarray(audio).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Qwen3-TTS returned empty or non-finite audio.")
    if float(np.max(np.abs(values.astype(np.float32)))) < 1e-5:
        raise ValueError("Qwen3-TTS returned silent audio.")
    if values.dtype != np.int16:
        values = (np.clip(values.astype(np.float32), -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(values.astype("<i2", copy=False).tobytes())


def write_silence(path: Path, sample_rate: int, duration_ms: int) -> None:
    frames = round(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)


def merge_chunks(chunk_paths: list[Path], output: Path, speed: float, pause_ms: int) -> None:
    ffmpeg = find_program("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="qwen3-tts-merge-") as temp_dir:
        manifest = Path(temp_dir) / "chunks.txt"
        merge_paths: list[Path] = []
        if pause_ms and len(chunk_paths) > 1:
            with wave.open(str(chunk_paths[0]), "rb") as handle:
                sample_rate = handle.getframerate()
            silence = Path(temp_dir) / "silence.wav"
            write_silence(silence, sample_rate, pause_ms)
            for index, path in enumerate(chunk_paths):
                if index:
                    merge_paths.append(silence)
                merge_paths.append(path)
        else:
            merge_paths = chunk_paths
        lines = []
        for path in merge_paths:
            escaped = path.as_posix().replace("'", "'\\''")
            lines.append(f"file '{escaped}'\n")
        manifest.write_text("".join(lines), encoding="utf-8")
        speed_filter = ["-filter:a", f"atempo={speed:.6g}"] if speed != 1.0 else []
        codec = ["-codec:a", "libmp3lame", "-b:a", "128k"] if output.suffix.lower() == ".mp3" else ["-codec:a", "pcm_s16le"]
        temporary_output = output.parent / f".{output.stem}.tmp{output.suffix}"
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), *speed_filter, *codec, str(temporary_output)],
            check=True,
        )
        if not valid_output(temporary_output):
            temporary_output.unlink(missing_ok=True)
            raise RuntimeError(f"Invalid merged audio generated: {output}")
        os.replace(temporary_output, output)


def validate_model_snapshot(snapshot: Path, speaker: str, language: str) -> None:
    required = (
        snapshot / "config.json",
        snapshot / "model.safetensors",
        snapshot / "generation_config.json",
        snapshot / "speech_tokenizer" / "config.json",
        snapshot / "speech_tokenizer" / "model.safetensors",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Incomplete Qwen3-TTS model snapshot: " + ", ".join(str(path) for path in missing))
    config = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
    if config.get("tts_model_type") != "custom_voice":
        raise ValueError(f"Qwen3-TTS model is not a CustomVoice checkpoint: {snapshot}")
    talker = config.get("talker_config", {})
    speakers = {name.lower() for name in talker.get("spk_id", {})}
    languages = {name.lower() for name in talker.get("codec_language_id", {})}
    if speaker.lower() not in speakers:
        raise ValueError(f"Speaker {speaker!r} is not present in model config: {snapshot}")
    if language.lower() not in languages:
        raise ValueError(f"Language {language!r} is not present in model config: {snapshot}")


def resolve_model_source(model: str, revision: str | None, allow_download: bool, speaker: str, language: str) -> str:
    candidate = Path(model).expanduser()
    if candidate.is_dir():
        snapshot = candidate.resolve()
        validate_model_snapshot(snapshot, speaker, language)
        return str(snapshot)
    if candidate.is_absolute() or model.startswith("."):
        raise FileNotFoundError(f"Qwen3-TTS model directory not found: {candidate}")
    from huggingface_hub import snapshot_download

    try:
        resolved = snapshot_download(repo_id=model, revision=revision, local_files_only=True)
    except Exception as local_exc:
        if not allow_download:
            raise FileNotFoundError(
                f"Qwen3-TTS model is not available in the local cache: {model}. "
                "Pass --allow-download to fetch the public weights."
            ) from local_exc
        resolved = snapshot_download(repo_id=model, revision=revision, local_files_only=False)
    snapshot = Path(resolved).resolve()
    validate_model_snapshot(snapshot, speaker, language)
    return str(snapshot)


def select_device(requested: str) -> str:
    import torch

    if requested == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but is not available.")
    return requested


def build_pipeline(args: argparse.Namespace, model_source: str, device: str):
    import torch
    from qwen_tts import Qwen3TTSModel

    dtype = torch.float16 if device == "mps" else torch.float32
    print(f"Loading Qwen3-TTS CustomVoice on {device}: {model_source}", file=sys.stderr, flush=True)
    pipeline = Qwen3TTSModel.from_pretrained(
        model_source,
        device_map=device,
        dtype=dtype,
        attn_implementation="sdpa",
        local_files_only=True,
    )
    speakers = {speaker.lower() for speaker in pipeline.get_supported_speakers()}
    if args.speaker.lower() not in speakers:
        available = ", ".join(sorted(speakers))
        raise ValueError(f"Unsupported speaker {args.speaker!r}; available: {available}")
    return pipeline, device


def set_generation_seed(seed: int, device: str) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if device == "mps" and hasattr(torch, "mps"):
        torch.mps.manual_seed(seed)


def runtime_profile(device: str) -> dict[str, str]:
    import importlib.metadata
    import torch

    try:
        qwen_version = importlib.metadata.version("qwen-tts")
    except importlib.metadata.PackageNotFoundError:
        qwen_version = "unknown"
    return {
        "qwen_tts": qwen_version,
        "torch": torch.__version__,
        "device": device,
        "dtype": "float16" if device == "mps" else "float32",
        "attention": "sdpa",
    }


def cache_identity(
    args: argparse.Namespace,
    narration: str,
    model_source: str,
    profile: dict[str, str],
) -> str:
    payload = {
        "cache_version": CACHE_VERSION,
        "engine": "qwen3-tts-custom-voice",
        "model": model_source,
        "speaker": args.speaker.lower(),
        "language": args.language,
        "instruct": args.instruct,
        "narration": narration,
        "max_chars": args.max_chars,
        "seed": args.seed,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "repetition_penalty": args.repetition_penalty,
        "max_new_tokens": args.max_new_tokens,
        "runtime": profile,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def generate_output(
    args: argparse.Namespace,
    get_pipeline,
    narration: str,
    output: Path,
    model_source: str,
    device: str,
    profile: dict[str, str],
) -> None:
    chunks = split_narration(narration, args.max_chars)
    if not chunks:
        raise ValueError("The narration is empty after cleanup.")
    output.parent.mkdir(parents=True, exist_ok=True)
    identity = cache_identity(args, narration, model_source, profile)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    cache_dir = output.parent / f".{output.stem}_qwen3tts_{digest}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = [cache_dir / f"chunk_{index:04d}.wav" for index in range(1, len(chunks) + 1)]
    for index, chunk_path in enumerate(chunk_paths):
        if valid_wav(chunk_path):
            continue
        print(f"Generating {output.name}: chunk {index + 1}/{len(chunks)}", file=sys.stderr, flush=True)
        set_generation_seed(args.seed + index, device)
        pipeline = get_pipeline()
        wavs, sample_rate = pipeline.generate_custom_voice(
            text=chunks[index],
            language=args.language,
            speaker=args.speaker,
            instruct=args.instruct or None,
            non_streaming_mode=True,
            do_sample=True,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            repetition_penalty=args.repetition_penalty,
            subtalker_dosample=True,
            subtalker_temperature=args.temperature,
            subtalker_top_p=args.top_p,
            subtalker_top_k=args.top_k,
            max_new_tokens=args.max_new_tokens,
        )
        if len(wavs) != 1:
            raise RuntimeError(f"Qwen3-TTS returned no audio for chunk {index + 1}.")
        if sample_rate != 24000:
            raise RuntimeError(f"Qwen3-TTS returned unexpected sample rate {sample_rate} for chunk {index + 1}.")
        duration = len(wavs[0]) / sample_rate
        token_limit_seconds = args.max_new_tokens * 1920 / sample_rate
        if duration >= token_limit_seconds * 0.95:
            raise RuntimeError(f"Qwen3-TTS chunk {index + 1} reached the generation limit before a safe ending.")
        temporary_chunk = chunk_path.with_suffix(".tmp.wav")
        save_wav(temporary_chunk, int(sample_rate), wavs[0])
        if not valid_wav(temporary_chunk):
            temporary_chunk.unlink(missing_ok=True)
            raise RuntimeError(f"Invalid WAV generated for chunk {index + 1}.")
        os.replace(temporary_chunk, chunk_path)
    merge_chunks(chunk_paths, output, args.speed, args.pause_ms)
    if not valid_output(output):
        raise RuntimeError(f"Invalid final audio generated: {output}")
    if args.clean_cache:
        shutil.rmtree(cache_dir)


def safe_title(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", title).strip().replace(" ", "_")
    return cleaned[:60] or "section"


def default_output(text: str, suffix: str, invocation_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return invocation_dir / "output" / "qwen3_tts_audio" / f"narration_{stamp}_{digest}.{suffix}"


def validate_args(args: argparse.Namespace) -> None:
    if not 0.5 <= args.speed <= 2.0:
        raise ValueError("--speed must be between 0.5 and 2.0.")
    if not 0 < args.temperature <= 2.0:
        raise ValueError("--temperature must be greater than 0 and at most 2.")
    if not 0 < args.top_p <= 1.0:
        raise ValueError("--top-p must be greater than 0 and at most 1.")
    if args.top_k < 1:
        raise ValueError("--top-k must be at least 1.")
    if not 0.5 <= args.repetition_penalty <= 2.0:
        raise ValueError("--repetition-penalty must be between 0.5 and 2.0.")
    if args.max_new_tokens < 128:
        raise ValueError("--max-new-tokens must be at least 128.")
    if not 0 <= args.pause_ms <= 2000:
        raise ValueError("--pause-ms must be between 0 and 2000.")
    if args.output is not None and args.output_dir is not None:
        raise ValueError("Use --output for one file or --output-dir for sections, not both.")


def main() -> int:
    args = parse_args()
    try:
        invocation_dir = Path.cwd().resolve()
        validate_args(args)
        text = load_text(args, invocation_dir)
        has_markers = "[[SECTION_START|" in text or "[[SECTION_END|" in text
        if has_markers and not args.split_sections:
            raise ValueError("SECTION markers detected. Use --split-sections so control markers are not spoken.")
        if args.split_sections and args.output is not None:
            raise ValueError("--split-sections uses --output-dir, not --output.")
        if not args.split_sections and args.output_dir is not None:
            raise ValueError("--output-dir requires --split-sections.")
        requested_output = resolve_path(args.output, invocation_dir) if args.output is not None else None
        requested_output_dir = resolve_path(args.output_dir, invocation_dir) if args.output_dir is not None else None
        sections = parse_sections(text) if args.split_sections else None
        narration = None if sections is not None else clean_narration(text)
        if narration is not None and not narration:
            raise ValueError("The narration is empty after cleanup.")
        ensure_runtime_python(args)
        model_source = resolve_model_source(args.model, args.revision, args.allow_download, args.speaker, args.language)
        device = select_device(args.device)
        profile = runtime_profile(device)
        pipeline = None

        def get_pipeline():
            nonlocal pipeline
            if pipeline is None:
                pipeline, _ = build_pipeline(args, model_source, device)
            return pipeline

        outputs: list[Path] = []
        if sections is not None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = requested_output_dir or invocation_dir / "output" / "qwen3_tts_sections" / stamp
            for part, chapter, section, title, spoken in sections:
                output = output_dir / f"{part}_{chapter}_{section}_{safe_title(title)}.{args.format}"
                generate_output(args, get_pipeline, spoken, output, model_source, device, profile)
                outputs.append(output)
        else:
            output = requested_output or default_output(text, args.format, invocation_dir)
            if output.suffix.lower() not in {".mp3", ".wav"}:
                output = output.with_suffix(f".{args.format}")
            generate_output(args, get_pipeline, narration, output, model_source, device, profile)
            outputs.append(output)
        for output in outputs:
            print(output)
        return 0
    except (ImportError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

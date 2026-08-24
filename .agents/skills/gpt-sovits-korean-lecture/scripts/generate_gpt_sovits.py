#!/usr/bin/env python3
"""Generate resumable Korean GPT-SoVITS narration from an authorized voice."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime
from pathlib import Path


DEFAULT_REPO = Path("/Users/kimmireu/.cache/codex-gpt-sovits")
CACHE_VERSION = "3"
START_RE = re.compile(r"^\[\[SECTION_START\|(P\d{2})\|(C\d{2})\|(S\d{2})\|([^\]\r\n]+)\]\]$")
END_RE = re.compile(r"^\[\[SECTION_END\|(P\d{2})\|(C\d{2})\|(S\d{2})\]\]$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate authorized Korean GPT-SoVITS narration.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Target Korean narration")
    source.add_argument("--file", type=Path, help="UTF-8 Markdown or plain-text narration")
    source.add_argument("--stdin", action="store_true", help="Read narration from stdin")
    parser.add_argument("--ref-audio", type=Path, required=True, help="Authorized reference audio")
    transcript = parser.add_mutually_exclusive_group()
    transcript.add_argument("--ref-text", default="", help="Exact reference transcript")
    transcript.add_argument("--ref-text-file", type=Path, help="UTF-8 reference transcript")
    parser.add_argument("--output", type=Path, help="Single MP3 or WAV output")
    parser.add_argument("--split-sections", action="store_true", help="Create one file per SECTION block")
    parser.add_argument("--output-dir", type=Path, help="Directory for section audio")
    parser.add_argument("--format", choices=("mp3", "wav"), default="mp3")
    parser.add_argument("--repo", type=Path, default=None, help="GPT-SoVITS repository/runtime")
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--max-chars", type=int, default=220)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--clean-cache", action="store_true")
    parser.add_argument("--confirm-authorized", action="store_true")
    return parser.parse_args()


def repo_path(args: argparse.Namespace) -> Path:
    configured = args.repo or Path(os.environ.get("GPT_SOVITS_RUNTIME", str(DEFAULT_REPO)))
    return configured.expanduser().resolve()


def ensure_runtime_python(repo: Path) -> None:
    if os.environ.get("_GPT_SOVITS_UNIFIED_REEXEC") == "1":
        return
    candidates = (repo / "venv" / "bin" / "python", repo / ".conda" / "bin" / "python")
    runtime_python = next((path for path in candidates if path.is_file()), None)
    if runtime_python is None:
        checked = ", ".join(str(path) for path in candidates)
        raise RuntimeError(f"GPT-SoVITS runtime Python not found; checked: {checked}")
    env = os.environ.copy()
    env["_GPT_SOVITS_UNIFIED_REEXEC"] = "1"
    completed = subprocess.run([str(runtime_python), str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
    raise SystemExit(completed.returncode)


def load_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        text = args.text
    elif args.file is not None:
        text = args.file.expanduser().read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise ValueError("The narration text is empty.")
    return text


def load_reference_text(args: argparse.Namespace) -> str:
    if args.ref_text_file is not None:
        return args.ref_text_file.expanduser().read_text(encoding="utf-8").strip()
    return args.ref_text.strip()


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


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
            return handle.getnchannels() > 0 and handle.getframerate() > 0 and handle.getnframes() > 0
    except (OSError, EOFError, wave.Error):
        return False


def prepare_reference(source: Path, destination: Path) -> None:
    ffmpeg = find_program("ffmpeg")
    ffprobe = find_program("ffprobe")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
         "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1",
         "-t", "9.5", "-ar", "32000", "-ac", "1", "-c:a", "pcm_s16le", str(destination)],
        check=True,
    )
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(destination)],
        check=True, capture_output=True, text=True,
    )
    if float(probe.stdout.strip()) < 3.0:
        raise ValueError("The usable reference audio is shorter than 3 seconds.")


def save_wav(path: Path, sample_rate: int, audio) -> None:
    import numpy as np

    values = np.asarray(audio).reshape(-1)
    if values.dtype != np.int16:
        values = (np.clip(values.astype(np.float32), -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(values.astype("<i2", copy=False).tobytes())


def merge_chunks(chunk_paths: list[Path], output: Path) -> None:
    ffmpeg = find_program("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="gpt-sovits-merge-") as temp_dir:
        manifest = Path(temp_dir) / "chunks.txt"
        lines = []
        for path in chunk_paths:
            escaped = path.as_posix().replace("'", "'\\''")
            lines.append(f"file '{escaped}'\n")
        manifest.write_text("".join(lines), encoding="utf-8")
        codec = ["-codec:a", "libmp3lame", "-q:a", "2"] if output.suffix.lower() == ".mp3" else ["-codec:a", "pcm_s16le"]
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), *codec, str(output)], check=True)


def build_pipeline(repo: Path, device: str):
    if not (repo / "GPT_SoVITS" / "TTS_infer_pack" / "TTS.py").exists():
        raise FileNotFoundError(f"GPT-SoVITS repository not found: {repo}")
    os.chdir(repo)
    sys.path.insert(0, str(repo / "GPT_SoVITS"))
    sys.path.insert(0, str(repo))
    import soundfile as sf
    import torch
    import torchaudio

    def soundfile_load(path):
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        return torch.from_numpy(audio.T.copy()), sample_rate

    torchaudio.load = soundfile_load
    from TTS_infer_pack.TTS import TTS, TTS_Config

    base = repo / "GPT_SoVITS" / "pretrained_models"
    v2 = {
        "device": device, "is_half": False, "version": "v2",
        "t2s_weights_path": str(base / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"),
        "vits_weights_path": str(base / "gsv-v2final-pretrained" / "s2G2333k.pth"),
        "bert_base_path": str(base / "chinese-roberta-wwm-ext-large"),
        "cnhuhbert_base_path": str(base / "chinese-hubert-base"),
    }
    return TTS(TTS_Config({"custom": v2, "v2": v2}))


def generate_output(args: argparse.Namespace, pipeline, narration: str, output: Path, reference_wav: Path, ref_text: str, ref_digest: str) -> None:
    chunks = split_narration(narration, args.max_chars)
    if not chunks:
        raise ValueError("The narration is empty after cleanup.")
    output.parent.mkdir(parents=True, exist_ok=True)
    identity = "\n".join((CACHE_VERSION, ref_digest, ref_text, narration, str(args.max_chars), str(args.speed), str(args.seed)))
    cache_dir = output.parent / f".{output.stem}_gptsovits_{hashlib.sha256(identity.encode()).hexdigest()[:12]}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = [cache_dir / f"chunk_{index:04d}.wav" for index in range(1, len(chunks) + 1)]
    pending = [index for index, path in enumerate(chunk_paths) if not valid_wav(path)]
    for index in pending:
        print(f"Generating {output.name}: chunk {index + 1}/{len(chunks)}", file=sys.stderr, flush=True)
        request = {
            "text": chunks[index], "text_lang": "ko",
            "ref_audio_path": str(reference_wav), "prompt_text": ref_text, "prompt_lang": "ko",
            "text_split_method": "cut5", "batch_size": 4, "speed_factor": args.speed,
            "seed": args.seed + index, "parallel_infer": True, "repetition_penalty": 1.35,
        }
        result = None
        for result in pipeline.run(request):
            pass
        if result is None:
            raise RuntimeError(f"GPT-SoVITS returned no audio for chunk {index + 1}.")
        sample_rate, audio = result
        save_wav(chunk_paths[index], int(sample_rate), audio)
        if not valid_wav(chunk_paths[index]):
            raise RuntimeError(f"Invalid WAV generated for chunk {index + 1}.")
    merge_chunks(chunk_paths, output)
    if args.clean_cache:
        shutil.rmtree(cache_dir)


def safe_title(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", title).strip().replace(" ", "_")
    return cleaned[:60] or "section"


def default_output(text: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return Path.cwd() / "output" / "gpt_sovits_audio" / f"narration_{stamp}_{digest}.{suffix}"


def main() -> int:
    args = parse_args()
    try:
        repo = repo_path(args)
        ensure_runtime_python(repo)
        if not args.confirm_authorized:
            raise ValueError("Pass --confirm-authorized only after confirming voice authorization.")
        reference = args.ref_audio.expanduser().resolve()
        if not reference.is_file():
            raise FileNotFoundError(f"Reference audio not found: {reference}")
        if not 0.5 <= args.speed <= 2.0:
            raise ValueError("--speed must be between 0.5 and 2.0.")
        if args.output is not None and args.output_dir is not None:
            raise ValueError("Use --output for one file or --output-dir for sections, not both.")
        text = load_text(args)
        has_markers = "[[SECTION_START|" in text or "[[SECTION_END|" in text
        if has_markers and not args.split_sections:
            raise ValueError("SECTION markers detected. Use --split-sections so control markers are not spoken.")
        if args.split_sections and args.output is not None:
            raise ValueError("--split-sections uses --output-dir, not --output.")
        if not args.split_sections and args.output_dir is not None:
            raise ValueError("--output-dir requires --split-sections.")
        ref_text = load_reference_text(args)
        if not ref_text:
            print("warning: no reference transcript supplied; similarity and pronunciation may be worse.", file=sys.stderr)
        ref_digest = file_digest(reference)
        with tempfile.TemporaryDirectory(prefix="gpt-sovits-reference-") as temp_dir:
            prepared_reference = Path(temp_dir) / "reference.wav"
            prepare_reference(reference, prepared_reference)
            print(f"Loading GPT-SoVITS V2 on {args.device}.", file=sys.stderr, flush=True)
            pipeline = build_pipeline(repo, args.device)
            outputs: list[Path] = []
            if args.split_sections:
                sections = parse_sections(text)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = (args.output_dir or Path.cwd() / "output" / "gpt_sovits_sections" / stamp).expanduser().resolve()
                for part, chapter, section, title, spoken in sections:
                    output = output_dir / f"{part}_{chapter}_{section}_{safe_title(title)}.{args.format}"
                    generate_output(args, pipeline, spoken, output, prepared_reference, ref_text, ref_digest)
                    outputs.append(output)
            else:
                narration = clean_narration(text)
                output = (args.output or default_output(text, args.format)).expanduser().resolve()
                if output.suffix.lower() not in {".mp3", ".wav"}:
                    output = output.with_suffix(f".{args.format}")
                generate_output(args, pipeline, narration, output, prepared_reference, ref_text, ref_digest)
                outputs.append(output)
        for output in outputs:
            print(output)
        return 0
    except (ImportError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

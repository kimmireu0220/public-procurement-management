#!/usr/bin/env python3
"""Resume and verify sequential Qwen3-TTS generation for subject 4 chapters."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CHAPTER_ROOT = REPO_ROOT / "output" / "chapter_lectures" / "4과목"
DEFAULT_AUDIO_ROOT = REPO_ROOT / "output" / "qwen3_tts_audio"
DEFAULT_GENERATOR = Path(__file__).with_name("generate_qwen3_tts.py")
DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
DEFAULT_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"
DEFAULT_INSTRUCT = "차분하고 명료한 한국어 강의 톤으로 또박또박 말해 주세요."
MANIFEST_SCHEMA_VERSION = 1
CHAPTER_PATH_RE = re.compile(r"^part(?P<part>\d+)/chapter(?P<chapter>\d+)\.md$")


class BatchError(RuntimeError):
    """Raised for invalid inventory, configuration, or artifacts."""


@dataclass(frozen=True)
class Chapter:
    part: int
    chapter: int
    title: str
    source_path: Path
    speech_path: Path
    output_path: Path

    @property
    def key(self) -> str:
        return f"P{self.part:02d}-C{self.chapter:02d}"


@dataclass(frozen=True)
class ChapterPlan:
    chapter: Chapter
    speech_sha256: str | None
    speech_chars: int | None
    cleaned_chars: int | None
    expected_chunks: int | None
    request_fingerprint: str | None
    error: str | None = None


@dataclass(frozen=True)
class ArtifactVerification:
    ok: bool
    reason: str | None
    metadata: dict[str, Any] | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and verify all subject 4 Qwen3-TTS chapters sequentially."
    )
    parser.add_argument("--chapter-root", type=Path, default=DEFAULT_CHAPTER_ROOT)
    parser.add_argument("--speech-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--python", default=sys.executable, help="Python used to launch the generator")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision")
    parser.add_argument("--runtime-python", type=Path)
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--instruct", default=DEFAULT_INSTRUCT)
    parser.add_argument("--max-chars", type=int, default=160)
    parser.add_argument("--pause-ms", type=int, default=250)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PXX-CXX",
        help="Process only the selected chapter; may be repeated.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print the plan without writes")
    mode.add_argument("--check", action="store_true", help="Verify without writes or generation")
    return parser.parse_args(argv)


def resolve_path(path: Path, invocation_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (invocation_dir / expanded).resolve()


def resolve_executable_path(path: Path, invocation_dir: Path) -> Path:
    """Make an executable path absolute without dereferencing a virtualenv symlink."""
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = invocation_dir / expanded
    return expanded.absolute()


def resolve_arguments(args: argparse.Namespace, invocation_dir: Path) -> argparse.Namespace:
    args.chapter_root = resolve_path(args.chapter_root, invocation_dir)
    args.speech_root = resolve_path(args.speech_root, invocation_dir)
    args.output_root = resolve_path(args.output_root, invocation_dir)
    args.generator = resolve_path(args.generator, invocation_dir)
    args.manifest = (
        resolve_path(args.manifest, invocation_dir)
        if args.manifest is not None
        else args.output_root / "4과목_Qwen3-TTS_Sohee_manifest.json"
    )
    if args.runtime_python is not None:
        args.runtime_python = resolve_executable_path(args.runtime_python, invocation_dir)
    python = Path(args.python).expanduser()
    if python.parent != Path(".") or python.is_absolute():
        args.python = str(resolve_executable_path(python, invocation_dir))
    return args


def load_generator(path: Path) -> ModuleType:
    if not path.is_file():
        raise BatchError(f"Qwen3-TTS generator not found: {path}")
    spec = importlib.util.spec_from_file_location("qwen3_tts_batch_generator", path)
    if spec is None or spec.loader is None:
        raise BatchError(f"Unable to import Qwen3-TTS generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_title(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", title).strip().replace(" ", "_")
    return cleaned[:60] or "chapter"


def parse_front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise BatchError(f"Chapter front matter is missing: {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise BatchError(f"Chapter front matter is unclosed: {path}") from exc
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise BatchError(f"Malformed front matter in {path}: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata


def discover_chapters(
    chapter_root: Path,
    speech_root: Path,
    output_root: Path,
) -> list[Chapter]:
    if not chapter_root.is_dir():
        raise BatchError(f"Chapter root not found: {chapter_root}")
    chapters: list[Chapter] = []
    seen: set[tuple[int, int]] = set()
    for source in chapter_root.glob("part*/chapter*.md"):
        relative = source.relative_to(chapter_root).as_posix()
        match = CHAPTER_PATH_RE.fullmatch(relative)
        if match is None:
            raise BatchError(f"Unexpected chapter path: {source}")
        part = int(match.group("part"))
        chapter_number = int(match.group("chapter"))
        metadata = parse_front_matter(source)
        try:
            metadata_subject = int(metadata["subject"])
            metadata_part = int(metadata["part"])
            metadata_chapter = int(metadata["chapter"])
            title = metadata["title"].strip()
        except (KeyError, ValueError) as exc:
            raise BatchError(f"Incomplete chapter metadata: {source}") from exc
        if (metadata_subject, metadata_part, metadata_chapter) != (
            4,
            part,
            chapter_number,
        ):
            raise BatchError(f"Chapter path and metadata disagree: {source}")
        if not title:
            raise BatchError(f"Chapter title is empty: {source}")
        identity = (part, chapter_number)
        if identity in seen:
            raise BatchError(f"Duplicate chapter identifier P{part:02d}-C{chapter_number:02d}")
        seen.add(identity)
        prefix = (
            f"4과목_Part{part:02d}_Chapter{chapter_number:02d}_{safe_title(title)}"
        )
        chapters.append(
            Chapter(
                part=part,
                chapter=chapter_number,
                title=title,
                source_path=source.resolve(),
                speech_path=(speech_root / f"{prefix}_대본.txt").resolve(),
                output_path=(output_root / f"{prefix}_Qwen3-TTS_Sohee.mp3").resolve(),
            )
        )
    if not chapters:
        raise BatchError(f"No partNN/chapterNN.md files found under {chapter_root}")
    return sorted(chapters, key=lambda item: (item.part, item.chapter))


def select_chapters(chapters: list[Chapter], selectors: list[str]) -> list[Chapter]:
    if not selectors:
        return chapters
    selected: set[str] = set()
    for selector in selectors:
        normalized = selector.upper()
        if re.fullmatch(r"P\d{2}-C\d{2}", normalized) is None:
            raise BatchError(f"Invalid --only selector {selector!r}; expected PXX-CXX")
        selected.add(normalized)
    known = {chapter.key for chapter in chapters}
    unknown = selected - known
    if unknown:
        raise BatchError("Unknown --only selector(s): " + ", ".join(sorted(unknown)))
    return [chapter for chapter in chapters if chapter.key in selected]


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def generation_settings(args: argparse.Namespace, generator_sha256: str) -> dict[str, Any]:
    return {
        "generator_sha256": generator_sha256,
        "model": args.model,
        "revision": args.revision,
        "device": args.device,
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
        "max_new_tokens": args.max_new_tokens,
    }


def analyze_chapter(
    chapter: Chapter,
    generator: ModuleType,
    settings: dict[str, Any],
) -> ChapterPlan:
    if not chapter.speech_path.is_file():
        return ChapterPlan(chapter, None, None, None, None, None, "speech-ready text missing")
    try:
        raw = chapter.speech_path.read_text(encoding="utf-8")
        cleaned = generator.clean_narration(raw)
        chunks = generator.split_narration(cleaned, int(settings["max_chars"]))
    except (OSError, UnicodeError, ValueError) as exc:
        return ChapterPlan(chapter, None, None, None, None, None, str(exc))
    if not chunks:
        return ChapterPlan(chapter, None, len(raw), len(cleaned), 0, None, "speech text is empty")
    speech_sha256 = file_digest(chapter.speech_path)
    request = {
        "chapter": chapter.key,
        "speech_sha256": speech_sha256,
        "output_path": str(chapter.output_path),
        "settings": settings,
    }
    return ChapterPlan(
        chapter=chapter,
        speech_sha256=speech_sha256,
        speech_chars=len(raw),
        cleaned_chars=len(cleaned),
        expected_chunks=len(chunks),
        request_fingerprint=json_digest(request),
    )


def probe_mp3(path: Path, ffprobe: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size < 1024:
        raise BatchError(f"MP3 output is missing or too small: {path}")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise BatchError(f"ffprobe failed for {path}: {detail}")
    try:
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        duration = float(payload["format"]["duration"])
        size = int(payload["format"]["size"])
        codec = str(stream["codec_name"])
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BatchError(f"Invalid ffprobe response for {path}") from exc
    if codec != "mp3" or sample_rate != 24000 or channels != 1 or duration <= 0 or size < 1024:
        raise BatchError(
            f"Unexpected MP3 format for {path}: "
            f"codec={codec}, sample_rate={sample_rate}, channels={channels}, duration={duration}"
        )
    return {
        "codec": codec,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_seconds": duration,
        "size": size,
    }


def wav_duration(path: Path) -> float | None:
    try:
        if not path.is_file() or path.stat().st_size < 1024:
            return None
        with wave.open(str(path), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() != 24000
                or handle.getnframes() <= 0
            ):
                return None
            return handle.getnframes() / handle.getframerate()
    except (OSError, EOFError, wave.Error):
        return None


def inspect_chunk_cache(
    output: Path,
    expected_chunks: int,
    final_duration: float,
    pause_ms: int,
    speed: float,
) -> dict[str, Any]:
    candidates = [
        path
        for path in output.parent.glob(f".{output.stem}_qwen3tts_*")
        if path.is_dir()
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
    expected_names = [f"chunk_{index:04d}.wav" for index in range(1, expected_chunks + 1)]
    reasons: list[str] = []
    for candidate in candidates:
        chunks = sorted(candidate.glob("chunk_*.wav"))
        if [path.name for path in chunks] != expected_names:
            reasons.append(f"{candidate.name}: expected {expected_chunks}, found {len(chunks)}")
            continue
        durations = [wav_duration(path) for path in chunks]
        if any(duration is None for duration in durations):
            reasons.append(f"{candidate.name}: invalid 24 kHz mono PCM chunk")
            continue
        valid_durations = [duration for duration in durations if duration is not None]
        chunk_seconds = sum(valid_durations)
        expected_duration = (chunk_seconds + pause_ms / 1000 * (expected_chunks - 1)) / speed
        tolerance = max(0.5, expected_duration * 0.001)
        if abs(final_duration - expected_duration) > tolerance:
            reasons.append(
                f"{candidate.name}: output duration {final_duration:.3f}s != "
                f"expected {expected_duration:.3f}s"
            )
            continue
        return {
            "cache_dir": str(candidate.resolve()),
            "observed_chunks": len(chunks),
            "chunk_duration_seconds": round(chunk_seconds, 6),
            "expected_output_duration_seconds": round(expected_duration, 6),
        }
    detail = "; ".join(reasons[:3]) if reasons else "no matching cache directory"
    raise BatchError(f"Chunk cache verification failed for {output.name}: {detail}")


def verify_artifacts(plan: ChapterPlan, args: argparse.Namespace) -> ArtifactVerification:
    if plan.expected_chunks is None:
        return ArtifactVerification(False, plan.error or "expected chunk count unavailable")
    try:
        audio = probe_mp3(plan.chapter.output_path, args.ffprobe)
        cache = inspect_chunk_cache(
            plan.chapter.output_path,
            plan.expected_chunks,
            float(audio["duration_seconds"]),
            args.pause_ms,
            args.speed,
        )
        stat = plan.chapter.output_path.stat()
        metadata = {
            **audio,
            **cache,
            "output_sha256": file_digest(plan.chapter.output_path),
            "output_mtime_ns": stat.st_mtime_ns,
            "verified_at": timestamp(),
        }
        return ArtifactVerification(True, None, metadata)
    except (BatchError, OSError) as exc:
        return ArtifactVerification(False, str(exc))


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_manifest() -> dict[str, Any]:
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "chapters": {}}


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_manifest()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchError(f"Unable to read batch manifest: {path}") from exc
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BatchError(f"Unsupported batch manifest schema: {path}")
    if not isinstance(payload.get("chapters"), dict):
        raise BatchError(f"Batch manifest chapters must be an object: {path}")
    return payload


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def base_entry(plan: ChapterPlan, previous: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "part": plan.chapter.part,
        "chapter": plan.chapter.chapter,
        "title": plan.chapter.title,
        "source_path": str(plan.chapter.source_path),
        "speech_path": str(plan.chapter.speech_path),
        "output_path": str(plan.chapter.output_path),
        "speech_sha256": plan.speech_sha256,
        "speech_chars": plan.speech_chars,
        "cleaned_chars": plan.cleaned_chars,
        "expected_chunks": plan.expected_chunks,
        "request_fingerprint": plan.request_fingerprint,
        "attempts": int((previous or {}).get("attempts", 0)),
    }


def manifest_entry_is_current(entry: object, plan: ChapterPlan) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("status") != "verified":
        return False
    if entry.get("request_fingerprint") != plan.request_fingerprint:
        return False
    verification = entry.get("verification")
    if not isinstance(verification, dict) or not plan.chapter.output_path.is_file():
        return False
    stat = plan.chapter.output_path.stat()
    return (
        verification.get("size") == stat.st_size
        and verification.get("output_mtime_ns") == stat.st_mtime_ns
        and verification.get("observed_chunks") == plan.expected_chunks
    )


def manifest_matches_verification(
    entry: object,
    plan: ChapterPlan,
    verification: ArtifactVerification,
) -> bool:
    if not isinstance(entry, dict) or not verification.ok or verification.metadata is None:
        return False
    recorded = entry.get("verification")
    return (
        entry.get("status") == "verified"
        and entry.get("request_fingerprint") == plan.request_fingerprint
        and isinstance(recorded, dict)
        and recorded.get("output_sha256") == verification.metadata.get("output_sha256")
        and recorded.get("observed_chunks") == plan.expected_chunks
    )


def build_generator_command(args: argparse.Namespace, chapter: Chapter) -> list[str]:
    command = [
        args.python,
        str(args.generator),
        "--file",
        str(chapter.speech_path),
        "--output",
        str(chapter.output_path),
        "--format",
        "mp3",
        "--model",
        args.model,
        "--device",
        args.device,
        "--speaker",
        args.speaker,
        "--language",
        args.language,
        "--instruct",
        args.instruct,
        "--max-chars",
        str(args.max_chars),
        "--pause-ms",
        str(args.pause_ms),
        "--speed",
        str(args.speed),
        "--seed",
        str(args.seed),
        "--temperature",
        str(args.temperature),
        "--top-p",
        str(args.top_p),
        "--top-k",
        str(args.top_k),
        "--repetition-penalty",
        str(args.repetition_penalty),
        "--max-new-tokens",
        str(args.max_new_tokens),
    ]
    if args.revision:
        command.extend(("--revision", args.revision))
    if args.runtime_python is not None:
        command.extend(("--runtime-python", str(args.runtime_python)))
    if args.allow_download:
        command.append("--allow-download")
    return command


def invoke_generator(args: argparse.Namespace, chapter: Chapter) -> int:
    completed = subprocess.run(build_generator_command(args, chapter), cwd=REPO_ROOT)
    return completed.returncode


class PersistentGeneratorRunner:
    """Run chapter generation in-process while sharing one loaded model pipeline."""

    def __init__(self, args: argparse.Namespace, generator: ModuleType) -> None:
        self.args = args
        self.generator = generator
        self.generation_args = argparse.Namespace(
            **vars(args),
            clean_cache=False,
            output=None,
            output_dir=None,
        )
        self.model_source: str | None = None
        self.device: str | None = None
        self.profile: dict[str, str] | None = None
        self.pipeline: Any | None = None
        self.initialized = False

    def initialize(self) -> None:
        if self.initialized:
            return
        self.generator.validate_args(self.generation_args)
        self.model_source = self.generator.resolve_model_source(
            self.args.model,
            self.args.revision,
            self.args.allow_download,
            self.args.speaker,
            self.args.language,
        )
        self.device = self.generator.select_device(self.args.device)
        self.profile = self.generator.runtime_profile(self.device)
        self.initialized = True

    def get_pipeline(self) -> Any:
        self.initialize()
        if self.pipeline is None:
            assert self.model_source is not None
            assert self.device is not None
            self.pipeline, _ = self.generator.build_pipeline(
                self.generation_args,
                self.model_source,
                self.device,
            )
        return self.pipeline

    def __call__(self, _args: argparse.Namespace, chapter: Chapter) -> int:
        try:
            self.initialize()
            assert self.model_source is not None
            assert self.device is not None
            assert self.profile is not None
            raw = chapter.speech_path.read_text(encoding="utf-8")
            narration = self.generator.clean_narration(raw)
            if not narration:
                raise ValueError("The narration is empty after cleanup.")
            self.generator.generate_output(
                self.generation_args,
                self.get_pipeline,
                narration,
                chapter.output_path,
                self.model_source,
                self.device,
                self.profile,
            )
            print(chapter.output_path)
            return 0
        except (
            ImportError,
            OSError,
            ValueError,
            RuntimeError,
            subprocess.CalledProcessError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1


def in_process_runtime_available() -> bool:
    return (
        importlib.util.find_spec("qwen_tts") is not None
        and importlib.util.find_spec("torch") is not None
    )


def executable_path(value: str | Path) -> Path | None:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.absolute()
    if candidate.parent == Path("."):
        located = shutil.which(str(candidate))
        return Path(located).absolute() if located else None
    return (Path.cwd() / candidate).absolute()


def select_in_process_python(
    args: argparse.Namespace,
    generator: ModuleType,
    excluded: set[Path] | None = None,
) -> Path:
    excluded = excluded or set()
    candidates: list[Path] = []
    if args.runtime_python is not None:
        candidates.append(args.runtime_python)
    configured_python = executable_path(args.python)
    if configured_python is not None and configured_python != Path(sys.executable).absolute():
        candidates.append(configured_python)
    if os.environ.get("QWEN3_TTS_PYTHON"):
        candidates.append(Path(os.environ["QWEN3_TTS_PYTHON"]).expanduser())
    candidates.append(generator.DEFAULT_RUNTIME_PYTHON)
    for candidate in candidates:
        absolute = candidate if candidate.is_absolute() else (Path.cwd() / candidate).absolute()
        if absolute.is_file() and absolute not in excluded:
            return absolute
    checked = ", ".join(str(path) for path in candidates)
    raise BatchError(f"Qwen3-TTS in-process runtime Python not found; checked: {checked}")


def ensure_in_process_runtime(args: argparse.Namespace, generator: ModuleType) -> None:
    """Re-exec the whole batch once so all chapters can share the Qwen pipeline."""
    current_python = Path(sys.executable).absolute()
    visited = {
        Path(item).absolute()
        for item in os.environ.get("_QWEN3_TTS_BATCH_REEXEC", "").split(os.pathsep)
        if item
    }
    configured_python = executable_path(args.python)
    preferred_python = (
        configured_python
        if configured_python is not None
        and configured_python != current_python
        and configured_python not in visited
        and configured_python.is_file()
        else None
    )
    if preferred_python is None and in_process_runtime_available():
        return
    excluded = visited | {current_python}
    runtime_python = preferred_python or select_in_process_python(args, generator, excluded)
    env = os.environ.copy()
    env["_QWEN3_TTS_BATCH_REEXEC"] = os.pathsep.join(
        str(path) for path in sorted(excluded, key=str)
    )
    completed = subprocess.run(
        [str(runtime_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=Path.cwd(),
        env=env,
    )
    raise SystemExit(completed.returncode)


def refresh_manifest_header(
    manifest: dict[str, Any],
    args: argparse.Namespace,
    settings: dict[str, Any],
    chapters: list[Chapter],
) -> None:
    manifest.update(
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "subject": "4과목",
            "chapter_root": str(args.chapter_root),
            "speech_root": str(args.speech_root),
            "output_root": str(args.output_root),
            "generator": str(args.generator),
            "settings": settings,
            "settings_fingerprint": json_digest(settings),
            "inventory": [chapter.key for chapter in chapters],
            "updated_at": timestamp(),
        }
    )


def update_manifest_entry(
    manifest: dict[str, Any],
    plan: ChapterPlan,
    status: str,
    *,
    verification: dict[str, Any] | None = None,
    error: str | None = None,
    adopted: bool | None = None,
    increment_attempts: bool = False,
) -> None:
    previous = manifest["chapters"].get(plan.chapter.key)
    entry = base_entry(plan, previous if isinstance(previous, dict) else None)
    if increment_attempts:
        entry["attempts"] += 1
        entry["started_at"] = timestamp()
    entry["status"] = status
    entry["updated_at"] = timestamp()
    if verification is not None:
        entry["verification"] = verification
        entry["completed_at"] = timestamp()
    if error:
        entry["error"] = error
    if adopted is not None:
        entry["adopted_existing"] = adopted
    manifest["chapters"][plan.chapter.key] = entry


def run_batch(
    args: argparse.Namespace,
    *,
    verifier: Callable[[ChapterPlan, argparse.Namespace], ArtifactVerification] = verify_artifacts,
    generator_runner: Callable[[argparse.Namespace, Chapter], int] | None = None,
) -> int:
    generator = load_generator(args.generator)
    generator_sha256 = file_digest(args.generator)
    settings = generation_settings(args, generator_sha256)
    inventory = discover_chapters(args.chapter_root, args.speech_root, args.output_root)
    chapters = select_chapters(inventory, args.only)
    plans = [analyze_chapter(chapter, generator, settings) for chapter in chapters]
    manifest = load_manifest(args.manifest)
    refresh_manifest_header(manifest, args, settings, inventory)
    counts = {
        "skipped": 0,
        "adopted": 0,
        "generated": 0,
        "would_generate": 0,
        "missing": 0,
        "failed": 0,
        "checked": 0,
    }
    failed = False
    runner = generator_runner

    def persist() -> None:
        refresh_manifest_header(manifest, args, settings, inventory)
        write_manifest(args.manifest, manifest)

    for plan in plans:
        key = plan.chapter.key
        previous = manifest["chapters"].get(key)
        if plan.error:
            counts["missing"] += 1
            failed = True
            print(f"MISSING {key}: {plan.error} ({plan.chapter.speech_path})")
            if not args.dry_run and not args.check:
                update_manifest_entry(manifest, plan, "missing_speech", error=plan.error)
                persist()
            continue

        if not args.check and manifest_entry_is_current(previous, plan):
            counts["skipped"] += 1
            print(f"SKIP {key}: verified ({plan.expected_chunks} chunks)")
            continue

        previous_fingerprint = (
            previous.get("request_fingerprint") if isinstance(previous, dict) else None
        )
        request_changed = previous_fingerprint not in (None, plan.request_fingerprint)
        verification = (
            ArtifactVerification(False, "request changed; existing output is stale")
            if request_changed
            else verifier(plan, args)
        )

        if args.check:
            if manifest_matches_verification(previous, plan, verification):
                counts["checked"] += 1
                print(f"OK {key}: {plan.expected_chunks} chunks, ffprobe/cache verified")
            else:
                counts["failed"] += 1
                failed = True
                reason = verification.reason or "manifest is missing or stale"
                print(f"FAIL {key}: {reason}")
            continue

        if verification.ok:
            if args.dry_run:
                counts["adopted"] += 1
                print(f"ADOPTABLE {key}: {plan.expected_chunks} chunks")
            else:
                counts["adopted"] += 1
                update_manifest_entry(
                    manifest,
                    plan,
                    "verified",
                    verification=verification.metadata,
                    adopted=True,
                )
                persist()
                print(f"ADOPT {key}: existing output verified ({plan.expected_chunks} chunks)")
            continue

        if args.dry_run:
            counts["would_generate"] += 1
            print(
                f"GENERATE {key}: {plan.expected_chunks} chunks -> {plan.chapter.output_path}"
            )
            continue

        update_manifest_entry(manifest, plan, "running", increment_attempts=True)
        persist()
        print(f"RUN {key}: {plan.expected_chunks} chunks -> {plan.chapter.output_path}")
        if runner is None:
            runner = PersistentGeneratorRunner(args, generator)
        returncode = runner(args, plan.chapter)
        if returncode != 0:
            counts["failed"] += 1
            failed = True
            reason = f"generator exited with status {returncode}"
            update_manifest_entry(manifest, plan, "failed", error=reason)
            persist()
            print(f"FAIL {key}: {reason}")
            if not args.keep_going:
                break
            continue
        generated_verification = verifier(plan, args)
        if not generated_verification.ok:
            counts["failed"] += 1
            failed = True
            reason = generated_verification.reason or "artifact verification failed"
            update_manifest_entry(manifest, plan, "failed", error=reason)
            persist()
            print(f"FAIL {key}: {reason}")
            if not args.keep_going:
                break
            continue
        counts["generated"] += 1
        update_manifest_entry(
            manifest,
            plan,
            "verified",
            verification=generated_verification.metadata,
            adopted=False,
        )
        persist()
        print(f"DONE {key}: verified ({plan.expected_chunks} chunks)")

    summary = ", ".join(f"{name}={value}" for name, value in counts.items() if value)
    print(f"SUMMARY total={len(plans)}" + (f", {summary}" if summary else ""))
    if args.dry_run:
        return 0
    return 1 if failed else 0


def main() -> int:
    try:
        args = resolve_arguments(parse_args(), Path.cwd().resolve())
        if not args.dry_run and not args.check:
            ensure_in_process_runtime(args, load_generator(args.generator))
        return run_batch(args)
    except (BatchError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

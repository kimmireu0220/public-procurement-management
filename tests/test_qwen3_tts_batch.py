from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / ".agents" / "skills" / "qwen3-tts-korean-lecture" / "scripts"
BATCH_SCRIPT = SKILL_SCRIPTS / "generate_qwen3_tts_batch.py"
GENERATOR_SCRIPT = SKILL_SCRIPTS / "generate_qwen3_tts.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Qwen3TtsBatchTest(unittest.TestCase):
    batch: ClassVar[Any]
    generator: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.batch = load_module(BATCH_SCRIPT, "qwen3_tts_batch_test_module")
        cls.generator = load_module(GENERATOR_SCRIPT, "qwen3_tts_generator_for_batch_test")

    def write_chapter(
        self,
        chapter_root: Path,
        part: int,
        chapter: int,
        title: str,
        *,
        metadata_part: int | None = None,
    ) -> Path:
        path = chapter_root / f"part{part:02d}" / f"chapter{chapter:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "subject: 4\n"
            f"part: {metadata_part if metadata_part is not None else part}\n"
            f"chapter: {chapter}\n"
            f"title: {title}\n"
            "---\n\n"
            "원문\n",
            encoding="utf-8",
        )
        return path

    def make_args(self, root: Path, *extra: str):
        args = self.batch.parse_args(
            [
                "--chapter-root",
                str(root / "chapters"),
                "--speech-root",
                str(root / "audio"),
                "--output-root",
                str(root / "audio"),
                "--manifest",
                str(root / "manifest.json"),
                "--generator",
                str(GENERATOR_SCRIPT),
                *extra,
            ]
        )
        return self.batch.resolve_arguments(args, root.resolve())

    def chapter_for(self, args, part: int = 1, chapter: int = 1):
        chapters = self.batch.discover_chapters(
            args.chapter_root,
            args.speech_root,
            args.output_root,
        )
        return next(item for item in chapters if (item.part, item.chapter) == (part, chapter))

    def write_wav(self, path: Path, seconds: float) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        frames = round(24000 * seconds)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(b"\x01\x00" * frames)

    def verified_metadata(self, output: Path, expected_chunks: int) -> dict:
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.is_file():
            output.write_bytes(b"m" * 2048)
        stat = output.stat()
        return {
            "codec": "mp3",
            "sample_rate": 24000,
            "channels": 1,
            "duration_seconds": 10.0,
            "size": stat.st_size,
            "cache_dir": str(output.parent / ".cache"),
            "observed_chunks": expected_chunks,
            "chunk_duration_seconds": 9.75,
            "expected_output_duration_seconds": 10.0,
            "output_sha256": self.batch.file_digest(output),
            "output_mtime_ns": stat.st_mtime_ns,
            "verified_at": "2026-08-25T00:00:00+00:00",
        }

    def test_inventory_is_numeric_and_maps_to_existing_flat_naming(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chapter_root = root / "chapters"
            self.write_chapter(chapter_root, 2, 1, "둘째 파트")
            self.write_chapter(chapter_root, 1, 10, "열번째")
            self.write_chapter(chapter_root, 1, 2, "안전/제목")

            chapters = self.batch.discover_chapters(
                chapter_root,
                root / "speech",
                root / "audio",
            )

            self.assertEqual([item.key for item in chapters], ["P01-C02", "P01-C10", "P02-C01"])
            self.assertEqual(
                chapters[0].speech_path.name,
                "4과목_Part01_Chapter02_안전_제목_대본.txt",
            )
            self.assertEqual(
                chapters[0].output_path.name,
                "4과목_Part01_Chapter02_안전_제목_Qwen3-TTS_Sohee.mp3",
            )

    def test_inventory_rejects_path_and_metadata_disagreement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chapter_root = root / "chapters"
            self.write_chapter(chapter_root, 1, 1, "제목", metadata_part=2)
            with self.assertRaisesRegex(self.batch.BatchError, "disagree"):
                self.batch.discover_chapters(chapter_root, root / "speech", root / "audio")

    def test_expected_chunk_count_is_calculated_from_prepared_speech(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "동적 청크")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text(
                "\n\n".join("가" * 159 for _ in range(54)),
                encoding="utf-8",
            )
            settings = self.batch.generation_settings(args, "generator-sha")

            plan = self.batch.analyze_chapter(chapter, self.generator, settings)

            self.assertIsNone(plan.error)
            self.assertEqual(plan.expected_chunks, 54)
            self.assertEqual(plan.cleaned_chars, 54 * 159 + 53 * 2)

    def test_probe_mp3_requires_24khz_mono_mp3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "chapter.mp3"
            output.write_bytes(b"m" * 2048)
            payload = {
                "streams": [{"codec_name": "mp3", "sample_rate": "24000", "channels": 1}],
                "format": {"duration": "12.5", "size": "2048"},
            }
            completed = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
            with mock.patch.object(self.batch.subprocess, "run", return_value=completed):
                result = self.batch.probe_mp3(output, "ffprobe")
            self.assertEqual(result["duration_seconds"], 12.5)

            payload["streams"][0]["sample_rate"] = "44100"
            completed.stdout = json.dumps(payload)
            with mock.patch.object(self.batch.subprocess, "run", return_value=completed):
                with self.assertRaisesRegex(self.batch.BatchError, "Unexpected MP3"):
                    self.batch.probe_mp3(output, "ffprobe")

    def test_chunk_cache_verifies_count_format_and_final_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "chapter.mp3"
            cache = root / ".chapter_qwen3tts_abc123"
            self.write_wav(cache / "chunk_0001.wav", 1.0)
            self.write_wav(cache / "chunk_0002.wav", 2.0)

            result = self.batch.inspect_chunk_cache(output, 2, 3.25, 250, 1.0)

            self.assertEqual(result["observed_chunks"], 2)
            self.assertEqual(result["chunk_duration_seconds"], 3.0)
            with self.assertRaisesRegex(self.batch.BatchError, "expected 3"):
                self.batch.inspect_chunk_cache(output, 3, 3.5, 250, 1.0)

    def test_generator_command_is_explicit_and_keeps_chunk_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(
                root,
                "--revision",
                "rev-a",
                "--runtime-python",
                str(root / "runtime python"),
                "--allow-download",
            )
            self.write_chapter(args.chapter_root, 1, 1, "실행")
            chapter = self.chapter_for(args)

            command = self.batch.build_generator_command(args, chapter)

            self.assertEqual(command[0], args.python)
            self.assertIn(str(chapter.speech_path), command)
            self.assertIn(str(chapter.output_path), command)
            self.assertIn("--revision", command)
            self.assertIn("--runtime-python", command)
            self.assertIn("--allow-download", command)
            self.assertNotIn("--clean-cache", command)

    def test_python_executable_keeps_virtualenv_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            virtualenv_python = root / "venv" / "bin" / "python"
            virtualenv_python.parent.mkdir(parents=True)
            virtualenv_python.symlink_to(Path(sys.executable))

            args = self.batch.parse_args(
                [
                    "--chapter-root",
                    str(root / "chapters"),
                    "--python",
                    str(virtualenv_python),
                    "--runtime-python",
                    str(virtualenv_python),
                ]
            )
            resolved = self.batch.resolve_arguments(args, root.resolve())

            self.assertEqual(resolved.python, str(virtualenv_python.absolute()))
            self.assertEqual(resolved.runtime_python, virtualenv_python.absolute())
            self.assertNotEqual(Path(resolved.python), virtualenv_python.resolve())

    def test_in_process_runtime_reexec_honors_configured_python_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            virtualenv_python = root / "venv" / "bin" / "python"
            virtualenv_python.parent.mkdir(parents=True)
            virtualenv_python.symlink_to(Path(sys.executable))
            args = self.make_args(root, "--python", str(virtualenv_python))
            completed = mock.Mock(returncode=0)

            with (
                mock.patch.object(self.batch, "in_process_runtime_available", return_value=True),
                mock.patch.object(self.batch.subprocess, "run", return_value=completed) as run,
                mock.patch.object(self.batch.sys, "argv", ["batch.py", "--dry-run"]),
            ):
                with self.assertRaises(SystemExit) as raised:
                    self.batch.ensure_in_process_runtime(args, self.generator)

            self.assertEqual(raised.exception.code, 0)
            command = run.call_args.args[0]
            self.assertEqual(command[0], str(virtualenv_python.absolute()))
            self.assertEqual(command[2:], ["--dry-run"])
            self.assertIn("_QWEN3_TTS_BATCH_REEXEC", run.call_args.kwargs["env"])

    def test_existing_flat_output_is_adopted_without_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "공공조달 참여 준비하기")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("준비된 음성 대본입니다.", encoding="utf-8")
            chapter.output_path.write_bytes(b"m" * 2048)
            generator_runner = mock.Mock(return_value=0)

            def verifier(plan, _args):
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            result = self.batch.run_batch(
                args,
                verifier=verifier,
                generator_runner=generator_runner,
            )

            self.assertEqual(result, 0)
            generator_runner.assert_not_called()
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            entry = manifest["chapters"]["P01-C01"]
            self.assertEqual(entry["status"], "verified")
            self.assertTrue(entry["adopted_existing"])
            self.assertEqual(entry["output_path"], str(chapter.output_path))

    def test_current_verified_output_is_fast_skipped_without_ffprobe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "건너뛰기")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("동일한 대본입니다.", encoding="utf-8")
            chapter.output_path.write_bytes(b"m" * 2048)

            def initial_verifier(plan, _args):
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            self.assertEqual(self.batch.run_batch(args, verifier=initial_verifier), 0)
            verifier = mock.Mock(side_effect=AssertionError("ffprobe must not run"))
            runner = mock.Mock(return_value=0)

            result = self.batch.run_batch(args, verifier=verifier, generator_runner=runner)

            self.assertEqual(result, 0)
            verifier.assert_not_called()
            runner.assert_not_called()

    def test_changed_speech_is_not_adopted_and_is_regenerated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "변경")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("첫 대본입니다.", encoding="utf-8")
            chapter.output_path.write_bytes(b"m" * 2048)

            def verifier(plan, _args):
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            self.assertEqual(self.batch.run_batch(args, verifier=verifier), 0)
            chapter.speech_path.write_text("수정된 대본입니다.", encoding="utf-8")
            runner = mock.Mock(return_value=0)

            result = self.batch.run_batch(args, verifier=verifier, generator_runner=runner)

            self.assertEqual(result, 0)
            runner.assert_called_once()
            entry = json.loads(args.manifest.read_text(encoding="utf-8"))["chapters"]["P01-C01"]
            self.assertFalse(entry["adopted_existing"])
            self.assertEqual(entry["attempts"], 1)

    def test_generation_runs_one_chapter_at_a_time_in_inventory_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 2, 1, "둘")
            self.write_chapter(args.chapter_root, 1, 2, "하나")
            chapters = self.batch.discover_chapters(
                args.chapter_root,
                args.speech_root,
                args.output_root,
            )
            for chapter in chapters:
                chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
                chapter.speech_path.write_text(f"{chapter.key} 대본입니다.", encoding="utf-8")
            order: list[str] = []

            def runner(_args, chapter):
                order.append(chapter.key)
                chapter.output_path.write_bytes(b"m" * 2048)
                return 0

            def verifier(plan, _args):
                if not plan.chapter.output_path.is_file():
                    return self.batch.ArtifactVerification(False, "missing")
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            result = self.batch.run_batch(args, verifier=verifier, generator_runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(order, ["P01-C02", "P02-C01"])
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            self.assertTrue(all(entry["status"] == "verified" for entry in manifest["chapters"].values()))

    def test_persistent_runner_reuses_model_profile_and_pipeline_across_chapters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--device", "mps")
            self.write_chapter(args.chapter_root, 1, 1, "첫 장")
            self.write_chapter(args.chapter_root, 1, 2, "둘째 장")
            chapters = self.batch.discover_chapters(
                args.chapter_root,
                args.speech_root,
                args.output_root,
            )
            for chapter in chapters:
                chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
                chapter.speech_path.write_text(f" {chapter.key} 대본입니다. ", encoding="utf-8")

            fake_generator = mock.Mock()
            fake_generator.clean_narration.side_effect = lambda text: text.strip()
            fake_generator.resolve_model_source.return_value = "/models/qwen"
            fake_generator.select_device.return_value = "mps"
            fake_generator.runtime_profile.return_value = {
                "qwen_tts": "test",
                "torch": "test",
                "device": "mps",
                "dtype": "float16",
                "attention": "sdpa",
            }
            pipeline = object()
            fake_generator.build_pipeline.return_value = (pipeline, "mps")
            generated: list[tuple[str, str, object]] = []

            def generate_output(
                generation_args,
                get_pipeline,
                narration,
                output,
                model_source,
                device,
                profile,
            ):
                self.assertIs(get_pipeline(), pipeline)
                self.assertIs(get_pipeline(), pipeline)
                self.assertEqual(model_source, "/models/qwen")
                self.assertEqual(device, "mps")
                self.assertEqual(profile["attention"], "sdpa")
                self.assertFalse(generation_args.clean_cache)
                generated.append((output.name, narration, get_pipeline()))

            fake_generator.generate_output.side_effect = generate_output
            runner = self.batch.PersistentGeneratorRunner(args, fake_generator)

            self.assertEqual(runner(args, chapters[0]), 0)
            self.assertEqual(runner(args, chapters[1]), 0)

            fake_generator.validate_args.assert_called_once_with(runner.generation_args)
            fake_generator.resolve_model_source.assert_called_once()
            fake_generator.select_device.assert_called_once_with("mps")
            fake_generator.runtime_profile.assert_called_once_with("mps")
            fake_generator.build_pipeline.assert_called_once()
            self.assertEqual([item[1] for item in generated], ["P01-C01 대본입니다.", "P01-C02 대본입니다."])
            self.assertTrue(all(item[2] is pipeline for item in generated))

    def test_default_persistent_runner_honors_single_only_selector(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C02")
            self.write_chapter(args.chapter_root, 1, 1, "앞 장")
            self.write_chapter(args.chapter_root, 1, 2, "선택 장")
            chapters = self.batch.discover_chapters(
                args.chapter_root,
                args.speech_root,
                args.output_root,
            )
            for chapter in chapters:
                chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
                chapter.speech_path.write_text(f"{chapter.key} 대본입니다.", encoding="utf-8")

            generated: list[str] = []

            def run(_args, chapter):
                generated.append(chapter.key)
                chapter.output_path.write_bytes(b"m" * 2048)
                return 0

            runner = mock.Mock(side_effect=run)

            def verifier(plan, _args):
                if not plan.chapter.output_path.is_file():
                    return self.batch.ArtifactVerification(False, "missing")
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            with mock.patch.object(
                self.batch,
                "PersistentGeneratorRunner",
                return_value=runner,
            ) as runner_factory:
                result = self.batch.run_batch(args, verifier=verifier)

            self.assertEqual(result, 0)
            runner_factory.assert_called_once()
            runner.assert_called_once()
            self.assertEqual(generated, ["P01-C02"])
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["inventory"], ["P01-C01", "P01-C02"])
            self.assertEqual(set(manifest["chapters"]), {"P01-C02"})

    def test_only_processes_selected_chapter_but_keeps_full_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C02")
            self.write_chapter(args.chapter_root, 1, 1, "앞 장")
            self.write_chapter(args.chapter_root, 1, 2, "선택 장")
            chapters = self.batch.discover_chapters(
                args.chapter_root,
                args.speech_root,
                args.output_root,
            )
            for chapter in chapters:
                chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
                chapter.speech_path.write_text(f"{chapter.key} 대본입니다.", encoding="utf-8")
            generated: list[str] = []

            def runner(_args, chapter):
                generated.append(chapter.key)
                chapter.output_path.write_bytes(b"m" * 2048)
                return 0

            def verifier(plan, _args):
                if not plan.chapter.output_path.is_file():
                    return self.batch.ArtifactVerification(False, "missing")
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            result = self.batch.run_batch(args, verifier=verifier, generator_runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(generated, ["P01-C02"])
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["inventory"], ["P01-C01", "P01-C02"])
            self.assertEqual(set(manifest["chapters"]), {"P01-C02"})

    def test_only_rejects_unknown_or_malformed_selector(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P99-C99")
            self.write_chapter(args.chapter_root, 1, 1, "장")
            with self.assertRaisesRegex(self.batch.BatchError, "Unknown --only"):
                self.batch.run_batch(args)

            malformed = self.make_args(root, "--only", "1-1")
            with self.assertRaisesRegex(self.batch.BatchError, "Invalid --only"):
                self.batch.run_batch(malformed)

    def test_failed_generation_is_recorded_and_stops_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "실패")
            self.write_chapter(args.chapter_root, 1, 2, "다음")
            chapters = self.batch.discover_chapters(
                args.chapter_root,
                args.speech_root,
                args.output_root,
            )
            for chapter in chapters:
                chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
                chapter.speech_path.write_text("대본입니다.", encoding="utf-8")
            runner = mock.Mock(return_value=7)
            missing = self.batch.ArtifactVerification(False, "missing")

            result = self.batch.run_batch(
                args,
                verifier=lambda _plan, _args: missing,
                generator_runner=runner,
            )

            self.assertEqual(result, 1)
            self.assertEqual(runner.call_count, 1)
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["chapters"]["P01-C01"]["status"], "failed")
            self.assertNotIn("P01-C02", manifest["chapters"])

    def test_dry_run_never_writes_or_invokes_generator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--dry-run")
            self.write_chapter(args.chapter_root, 1, 1, "계획")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("계획 대본입니다.", encoding="utf-8")
            runner = mock.Mock(return_value=0)
            missing = self.batch.ArtifactVerification(False, "missing")

            result = self.batch.run_batch(
                args,
                verifier=lambda _plan, _args: missing,
                generator_runner=runner,
            )

            self.assertEqual(result, 0)
            self.assertFalse(args.manifest.exists())
            runner.assert_not_called()

    def test_dry_run_does_not_construct_default_persistent_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--dry-run")
            self.write_chapter(args.chapter_root, 1, 1, "계획")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("계획 대본입니다.", encoding="utf-8")
            missing = self.batch.ArtifactVerification(False, "missing")

            with mock.patch.object(self.batch, "PersistentGeneratorRunner") as runner_factory:
                result = self.batch.run_batch(
                    args,
                    verifier=lambda _plan, _args: missing,
                )

            self.assertEqual(result, 0)
            self.assertFalse(args.manifest.exists())
            runner_factory.assert_not_called()

    def test_check_reprobes_but_does_not_rewrite_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_chapter(args.chapter_root, 1, 1, "검사")
            chapter = self.chapter_for(args)
            chapter.speech_path.parent.mkdir(parents=True)
            chapter.speech_path.write_text("검사 대본입니다.", encoding="utf-8")
            chapter.output_path.write_bytes(b"m" * 2048)

            def verifier(plan, _args):
                return self.batch.ArtifactVerification(
                    True,
                    None,
                    self.verified_metadata(plan.chapter.output_path, plan.expected_chunks),
                )

            self.assertEqual(self.batch.run_batch(args, verifier=verifier), 0)
            before = args.manifest.read_bytes()
            check_args = self.make_args(root, "--check")

            result = self.batch.run_batch(check_args, verifier=verifier)

            self.assertEqual(result, 0)
            self.assertEqual(args.manifest.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

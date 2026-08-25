from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "qwen3-tts-korean-lecture"
    / "scripts"
    / "generate_qwen3_tts_mlx_batch.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeModel:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.batch_calls: list[dict[str, Any]] = []
        self.duplicate = duplicate

    @staticmethod
    def result(sequence_idx: int, *, token_count: int = 20, samples: int = 12000):
        return SimpleNamespace(
            sequence_idx=sequence_idx,
            audio=[0.1, -0.1],
            samples=samples,
            sample_rate=24000,
            token_count=token_count,
            processing_time_seconds=1.0,
            peak_memory_usage=2.0,
        )

    def batch_generate(self, **kwargs):
        self.batch_calls.append(kwargs)
        count = len(kwargs["texts"])
        if self.duplicate:
            return [self.result(0), self.result(0)]
        return [self.result(index) for index in reversed(range(count))]


class Qwen3TtsMlxBatchTest(unittest.TestCase):
    mlx: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.mlx = load_module(SCRIPT, "qwen3_tts_mlx_batch_test_module")

    def write_chapter(self, chapter_root: Path, key: str) -> None:
        part = int(key[1:3])
        chapter = int(key[5:7])
        path = chapter_root / f"part{part:02d}" / f"chapter{chapter:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "subject: 4\n"
            f"part: {part}\n"
            f"chapter: {chapter}\n"
            f"title: 테스트 {key}\n"
            "---\n\n"
            "원문\n",
            encoding="utf-8",
        )

    def make_args(self, root: Path, *extra: str):
        chapter_root = root / "chapters"
        for key in self.mlx.EXPECTED_INVENTORY:
            self.write_chapter(chapter_root, key)
        model = root / "model"
        model.mkdir(parents=True, exist_ok=True)
        (model / "config.json").write_text(
            json.dumps(
                {
                    "model_type": "qwen3_tts",
                    "tts_model_type": "custom_voice",
                    "talker_config": {
                        "spk_id": {"Sohee": 0},
                        "codec_language_id": {"Korean": 0},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (model / "generation_config.json").write_text("{}\n", encoding="utf-8")
        speech_tokenizer = model / "speech_tokenizer"
        speech_tokenizer.mkdir(exist_ok=True)
        (speech_tokenizer / "config.json").write_text("{}\n", encoding="utf-8")
        self.write_safetensors(model / "model.safetensors", "BF16")
        self.write_safetensors(speech_tokenizer / "model.safetensors", "F32")
        args = self.mlx.parse_args(
            [
                "--chapter-root",
                str(chapter_root),
                "--speech-root",
                str(root / "audio"),
                "--output-root",
                str(root / "audio"),
                "--manifest",
                str(root / "hybrid.json"),
                "--pytorch-manifest",
                str(root / "pytorch.json"),
                "--model",
                str(model),
                *extra,
            ]
        )
        args = self.mlx.resolve_arguments(args, root.resolve())
        chapters = self.mlx.discover_inventory(args)
        for chapter in chapters:
            chapter.speech_path.parent.mkdir(parents=True, exist_ok=True)
            chapter.speech_path.write_text(
                f"{chapter.key}의 준비된 음성 대본입니다.", encoding="utf-8"
            )
        return args

    def write_safetensors(self, path: Path, dtype: str) -> None:
        width = 2 if dtype == "BF16" else 4
        header = json.dumps(
            {
                "tensor": {
                    "dtype": dtype,
                    "shape": [1],
                    "data_offsets": [0, width],
                }
            },
            separators=(",", ":"),
        ).encode("utf-8")
        path.write_bytes(len(header).to_bytes(8, "little") + header + b"\0" * width)

    def profile(self) -> dict[str, Any]:
        return {
            "engine": self.mlx.ENGINE,
            "python": "test",
            "platform": "test",
            "packages": {
                "mlx-audio": "0.5.0",
                "mlx": "0.32.0",
                "mlx-metal": "0.32.0",
                "transformers": "5.14.0",
            },
            "source_weights": "original-hugging-face-bfloat16",
            "batch_script_sha256": "script-sha",
        }

    def plan_for(self, args, key: str = "P01-C01", text: str | None = None):
        chapter = next(
            chapter
            for chapter in self.mlx.discover_inventory(args)
            if chapter.key == key
        )
        if text is not None:
            chapter.speech_path.write_text(text, encoding="utf-8")
        return self.mlx.analyze_chapter(
            chapter,
            args,
            self.mlx.inspect_model(Path(args.model)),
            self.profile(),
        )

    def write_wav(self, path: Path, frames: int = 12000) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(b"\x01\x00" * frames)

    def runtime(self, model: FakeModel, *, fail_write_number: int | None = None):
        loads: list[Path] = []
        seeds: list[int] = []
        writes: list[Path] = []

        def load_model(path: Path):
            loads.append(path)
            return model

        def write_audio(path: Path, _audio, _sample_rate: int, _format: str | None):
            writes.append(path)
            if fail_write_number is not None and len(writes) == fail_write_number:
                raise OSError("injected group write failure")
            self.write_wav(path)

        runtime = self.mlx.MlxRuntime(
            load_model=load_model,
            write_audio=write_audio,
            set_seed=seeds.append,
            versions=dict(self.profile()["packages"]),
        )
        return runtime, loads, seeds, writes

    def false_verification(self, *_args):
        return self.mlx.ArtifactVerification(False, "not current")

    def adopted_verification(self, plan, *_args):
        return self.mlx.ArtifactVerification(
            True,
            None,
            {
                "output_sha256": "adopted-sha",
                "observed_chunks": plan.expected_chunks,
                "cache_dir": "/pytorch/cache",
                "source_request_fingerprint": f"source-{plan.chapter.key}",
            },
            {"engine": self.mlx.PYTORCH_ENGINE, "settings": {}},
        )

    def generated_verification(self, plan, *_args):
        return self.mlx.ArtifactVerification(
            True,
            None,
            {
                "output_sha256": "mlx-sha",
                "observed_chunks": plan.expected_chunks,
                "cache_dir": str(plan.cache_dir),
                "cache_identity_sha256": plan.cache_identity_sha256,
                "boundary_safe": True,
            },
            self.profile(),
        )

    def test_fixed_inventory_has_25_chapters_and_rejects_a_missing_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.assertEqual(
                [chapter.key for chapter in self.mlx.discover_inventory(args)],
                list(self.mlx.EXPECTED_INVENTORY),
            )
            (args.chapter_root / "part08" / "chapter02.md").unlink()
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "fixed 25"):
                self.mlx.discover_inventory(args)

    def test_dry_run_is_lazy_and_never_writes_manifest_or_imports_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--dry-run", "--only", "P01-C01")
            runtime_loader = mock.Mock(side_effect=AssertionError("must stay lazy"))

            result = self.mlx.run_batch(
                args,
                runtime_loader=runtime_loader,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.false_verification,
            )

            self.assertEqual(result, 0)
            self.assertFalse(args.manifest.exists())
            runtime_loader.assert_not_called()

    def test_regenerate_group_cli_requires_safe_chunks_only_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "chunks-only"):
                self.make_args(
                    root,
                    "--only",
                    "P01-C01",
                    "--regenerate-group",
                    "P01-C01:1",
                )
            args = self.make_args(
                root,
                "--chunks-only",
                "--only",
                "P01-C01",
                "--regenerate-group",
                "P01-C01:1",
                "--regenerate-seed-offset",
                "500",
                "--regenerate-batch-size",
                "1",
            )
            self.assertEqual(args.regenerate_groups, {"P01-C01": {1}})
            self.assertEqual(args.regenerate_seed_offset, 500)
            self.assertEqual(args.regenerate_batch_size, 1)

    def test_cache_identity_covers_engine_packages_weights_narration_settings_and_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "3")
            plan = self.plan_for(args)
            identity = plan.cache_identity

            self.assertEqual(identity["engine"], self.mlx.ENGINE)
            self.assertEqual(identity["profile"]["packages"]["mlx-audio"], "0.5.0")
            self.assertIn("model.safetensors", identity["model"]["safetensors_sha256"])
            self.assertEqual(identity["narration"]["speech_sha256"], plan.speech_sha256)
            self.assertEqual(identity["settings"]["pause_ms"], 250)
            self.assertEqual(identity["settings"]["batch_size"], 3)
            self.assertEqual(
                identity["batch_plan"]["algorithm"],
                "fixed-character-length-bucket-v1",
            )

    def test_length_bucket_plan_and_group_seeds_are_deterministic(self):
        chunks = ["가" * 17, "나" * 64, "다" * 33, "라" * 63, "마" * 18]

        first = self.mlx.build_group_plan(chunks, batch_size=2, base_seed=1234)
        second = self.mlx.build_group_plan(chunks, batch_size=2, base_seed=1234)

        self.assertEqual(first, second)
        self.assertEqual([group.seed for group in first], list(range(1234, 1234 + len(first))))
        for group in first:
            buckets = {(len(chunks[index - 1]) - 1) // 16 for index in group.chunk_indices}
            self.assertEqual(buckets, {group.length_bucket})

    def test_batch_result_mapping_reorders_and_rejects_duplicate_or_missing_indices(self):
        results = [FakeModel.result(2), FakeModel.result(0), FakeModel.result(1)]
        mapped = self.mlx.map_batch_results(results, 3)
        self.assertEqual(list(mapped), [2, 0, 1])
        self.assertEqual(mapped[0].sequence_idx, 0)
        with self.assertRaisesRegex(self.mlx.MlxBatchError, "duplicate"):
            self.mlx.map_batch_results([FakeModel.result(0), FakeModel.result(0)], 2)
        with self.assertRaisesRegex(self.mlx.MlxBatchError, "do not match"):
            self.mlx.map_batch_results([FakeModel.result(0)], 2)

    def test_group_commit_is_atomic_and_incomplete_group_is_regenerated_whole(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "4")
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            self.assertEqual(len(plan.groups), 1)
            group = plan.groups[0]
            self.mlx.write_cache_identity(plan)
            failing_model = FakeModel()
            failing_runtime, _loads, _seeds, _writes = self.runtime(
                failing_model, fail_write_number=2
            )

            with self.assertRaisesRegex(OSError, "injected"):
                self.mlx.generate_group(plan, group, args, failing_model, failing_runtime)

            self.assertFalse(self.mlx.group_commit_path(plan, group).exists())
            self.assertEqual(
                list(self.mlx.group_generation_root(plan, group).glob("generation_*")),
                [],
            )

            good_model = FakeModel()
            good_runtime, _loads, seeds, writes = self.runtime(good_model)
            self.mlx.generate_group(plan, group, args, good_model, good_runtime)
            self.assertTrue(self.mlx.group_is_committed(plan, group))
            first_hashes = {
                index: self.mlx.sha256_file(self.mlx.chunk_path(plan, index))
                for index in group.chunk_indices
            }

            # A missing selector leaves any immutable generation unselected.  The
            # next attempt regenerates the whole group and selects it atomically.
            self.mlx.group_commit_path(plan, group).unlink()
            rewrite_model = FakeModel()
            rewrite_runtime, _loads, rewrite_seeds, rewrite_writes = self.runtime(rewrite_model)
            self.mlx.generate_group(plan, group, args, rewrite_model, rewrite_runtime)

            self.assertEqual(seeds, [group.seed])
            self.assertEqual(rewrite_seeds, [group.seed])
            self.assertEqual(len(writes), len(group.chunk_indices))
            self.assertEqual(len(rewrite_writes), len(group.chunk_indices))
            self.assertTrue(self.mlx.group_is_committed(plan, group))
            self.assertEqual(
                first_hashes,
                {
                    index: self.mlx.sha256_file(self.mlx.chunk_path(plan, index))
                    for index in group.chunk_indices
                },
            )

    def test_group_override_keeps_previous_commit_on_failure_then_selects_alternate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "3")
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            group = plan.groups[0]
            self.mlx.write_cache_identity(plan)
            base_model = FakeModel()
            base_runtime, _loads, _seeds, _writes = self.runtime(base_model)
            self.mlx.generate_group(plan, group, args, base_model, base_runtime)
            commit_path = self.mlx.group_commit_path(plan, group)
            committed_before = commit_path.read_bytes()
            hashes_before = {
                index: self.mlx.sha256_file(self.mlx.chunk_path(plan, index))
                for index in group.chunk_indices
            }

            failing_model = FakeModel()
            failing_runtime, _loads, _seeds, _writes = self.runtime(
                failing_model, fail_write_number=2
            )
            with self.assertRaisesRegex(OSError, "injected"):
                self.mlx.generate_group(
                    plan,
                    group,
                    args,
                    failing_model,
                    failing_runtime,
                    seed_offset=500,
                    override_batch_size=1,
                )
            self.assertEqual(commit_path.read_bytes(), committed_before)
            self.assertTrue(self.mlx.group_is_committed(plan, group))
            self.assertEqual(
                hashes_before,
                {
                    index: self.mlx.sha256_file(self.mlx.chunk_path(plan, index))
                    for index in group.chunk_indices
                },
            )

            alternate_model = FakeModel()
            alternate_runtime, _loads, seeds, writes = self.runtime(alternate_model)
            commit = self.mlx.generate_group(
                plan,
                group,
                args,
                alternate_model,
                alternate_runtime,
                seed_offset=500,
                override_batch_size=1,
            )
            self.assertEqual(
                seeds,
                [group.seed + 500, group.seed + 501],
            )
            self.assertEqual(len(writes), len(group.chunk_indices))
            self.assertEqual(commit["generation"]["mode"], "override")
            self.assertEqual(commit["generation"]["batch_size"], 1)
            self.assertTrue(self.mlx.group_is_committed(plan, group))

    def test_atomic_selector_interruption_preserves_prior_selected_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "3")
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            group = plan.groups[0]
            self.mlx.write_cache_identity(plan)
            base_model = FakeModel()
            base_runtime, _loads, _seeds, _writes = self.runtime(base_model)
            self.mlx.generate_group(plan, group, args, base_model, base_runtime)
            selector_path = self.mlx.group_commit_path(plan, group)
            selector_before = selector_path.read_bytes()
            selected_paths_before = {
                index: self.mlx.chunk_path(plan, index)
                for index in group.chunk_indices
            }
            hashes_before = {
                index: self.mlx.sha256_file(path)
                for index, path in selected_paths_before.items()
            }
            real_replace = self.mlx.os.replace

            def interrupt_selector(source, destination):
                if Path(destination) == selector_path:
                    raise OSError("injected selector interruption")
                return real_replace(source, destination)

            alternate_model = FakeModel()
            alternate_runtime, _loads, _seeds, _writes = self.runtime(
                alternate_model
            )
            with mock.patch.object(
                self.mlx.os, "replace", side_effect=interrupt_selector
            ):
                with self.assertRaisesRegex(OSError, "selector interruption"):
                    self.mlx.generate_group(
                        plan,
                        group,
                        args,
                        alternate_model,
                        alternate_runtime,
                        seed_offset=500,
                        override_batch_size=1,
                    )

            self.assertEqual(selector_path.read_bytes(), selector_before)
            self.assertTrue(self.mlx.group_is_committed(plan, group))
            self.assertEqual(
                {
                    index: self.mlx.chunk_path(plan, index)
                    for index in group.chunk_indices
                },
                selected_paths_before,
            )
            self.assertEqual(
                {
                    index: self.mlx.sha256_file(self.mlx.chunk_path(plan, index))
                    for index in group.chunk_indices
                },
                hashes_before,
            )
            # The completed alternate directory can remain orphaned safely; the
            # old selector still identifies one coherent prior generation.
            self.assertEqual(
                len(
                    list(
                        self.mlx.group_generation_root(plan, group).glob(
                            "generation_*"
                        )
                    )
                ),
                2,
            )

    def test_initial_selector_interruption_has_no_commit_and_resume_rebuilds_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "3")
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            group = plan.groups[0]
            self.mlx.write_cache_identity(plan)
            model = FakeModel()
            runtime, _loads, _seeds, _writes = self.runtime(model)
            real_replace = self.mlx.os.replace

            def interrupt_selector(source, destination):
                if Path(destination) == self.mlx.group_commit_path(plan, group):
                    raise OSError("injected selector interruption")
                return real_replace(source, destination)

            with mock.patch.object(
                self.mlx.os, "replace", side_effect=interrupt_selector
            ):
                with self.assertRaisesRegex(OSError, "selector interruption"):
                    self.mlx.generate_group(plan, group, args, model, runtime)

            self.assertFalse(self.mlx.group_commit_path(plan, group).exists())
            self.assertEqual(
                len(
                    list(
                        self.mlx.group_generation_root(plan, group).glob(
                            "generation_*"
                        )
                    )
                ),
                1,
            )
            resumed_model = FakeModel()
            resumed_runtime, _loads, seeds, writes = self.runtime(resumed_model)
            self.mlx.generate_group(
                plan, group, args, resumed_model, resumed_runtime
            )
            self.assertEqual(seeds, [group.seed])
            self.assertEqual(len(writes), len(group.chunk_indices))
            self.assertTrue(self.mlx.group_is_committed(plan, group))

    def test_durable_publish_fsyncs_mp3_before_receipt_and_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            temporary_output = root / "verified.tmp.mp3"
            output = root / "chapter.mp3"
            receipt_path = root / "merge.commit.json"
            temporary_output.write_bytes(b"encoded-mp3")
            receipt = {"output": {"sha256": "test"}}
            events: list[tuple[str, Path]] = []

            with (
                mock.patch.object(
                    self.mlx,
                    "fsync_file",
                    side_effect=lambda path: events.append(("fsync", path)),
                ),
                mock.patch.object(
                    self.mlx,
                    "atomic_write_json",
                    side_effect=lambda path, _payload: events.append(
                        ("receipt", path)
                    ),
                ),
                mock.patch.object(
                    self.mlx.os,
                    "link",
                    side_effect=lambda _source, destination: events.append(
                        ("link", destination)
                    ),
                ),
                mock.patch.object(
                    self.mlx,
                    "fsync_directory",
                    side_effect=lambda path: events.append(("directory", path)),
                ),
            ):
                self.mlx.durable_publish_mp3(
                    temporary_output, output, receipt_path, receipt
                )

            self.assertEqual(
                events,
                [
                    ("fsync", temporary_output),
                    ("receipt", receipt_path),
                    ("link", output),
                    ("directory", output.parent),
                ],
            )

    def test_runner_resumes_committed_groups_and_loads_model_only_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "4")
            plan = self.plan_for(
                args,
                text=("가" * 150 + ".\n\n" + "나" * 120 + "."),
            )
            self.assertEqual(len(plan.groups), 2)
            self.mlx.write_cache_identity(plan)
            first_model = FakeModel()
            first_runtime, _loads, _seeds, _writes = self.runtime(first_model)
            self.mlx.generate_group(plan, plan.groups[0], args, first_model, first_runtime)

            resume_model = FakeModel()
            resume_runtime, loads, seeds, _writes = self.runtime(resume_model)
            runner = self.mlx.MlxBatchRunner(
                args, self.profile(), runtime_loader=lambda: resume_runtime
            )
            with mock.patch.object(self.mlx, "merge_chapter") as merge:
                runner.generate_chapter(plan)

            self.assertEqual(len(resume_model.batch_calls), 1)
            self.assertEqual(seeds, [plan.groups[1].seed])
            self.assertEqual(loads, [Path(args.model)])
            merge.assert_called_once_with(plan, args)
            self.assertEqual(self.mlx.verify_mlx_cache(plan)["observed_groups"], 2)

    def test_token_and_duration_generation_limit_guards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            safe = self.mlx.guard_generation_result(FakeModel.result(0), args, 1)
            self.assertEqual(safe["reported_samples"], 12000)
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "generation limit"):
                self.mlx.guard_generation_result(
                    FakeModel.result(0, token_count=1000), args, 1
                )
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "generation limit"):
                self.mlx.guard_generation_result(
                    FakeModel.result(0, samples=1_900_000), args, 1
                )

    def test_chunks_only_commits_cache_without_mp3_and_records_repairable_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(
                root, "--chunks-only", "--only", "P01-C01"
            )
            self.assertEqual(args.batch_size, 3)
            model = FakeModel()
            runtime, loads, seeds, _writes = self.runtime(model)

            result = self.mlx.run_batch(
                args,
                runtime_loader=lambda: runtime,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.false_verification,
            )

            self.assertEqual(result, 0)
            plan = self.plan_for(args)
            self.assertFalse(plan.chapter.output_path.exists())
            self.assertEqual(loads, [Path(args.model)])
            self.assertEqual(seeds, [plan.groups[0].seed])
            entry = json.loads(args.manifest.read_text(encoding="utf-8"))["chapters"]["P01-C01"]
            self.assertEqual(entry["status"], "chunks_verified")
            self.assertEqual(entry["engine"], self.mlx.ENGINE)
            self.assertTrue(entry["verification"]["chunks_only"])
            before = args.manifest.read_bytes()
            check_args = self.make_args(
                root, "--check", "--chunks-only", "--only", "P01-C01"
            )
            runtime_loader = mock.Mock(side_effect=AssertionError("must stay lazy"))
            checked = self.mlx.run_batch(
                check_args,
                runtime_loader=runtime_loader,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(check_args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.false_verification,
            )
            self.assertEqual(checked, 0)
            self.assertEqual(args.manifest.read_bytes(), before)
            runtime_loader.assert_not_called()

    def test_pytorch_adoption_requires_current_request_hash_stat_and_recorded_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), "--batch-size", "4")
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            plan.chapter.output_path.write_bytes(b"m" * 2048)
            cache = Path(temp_dir) / "pytorch-cache"
            for index in range(1, plan.expected_chunks + 1):
                self.write_wav(cache / f"chunk_{index:04d}.wav")
            settings = {
                "generator_sha256": self.mlx.sha256_file(self.mlx.GENERATOR_PATH),
                "model": args.model,
                "revision": None,
                "device": "mps",
                "speaker": "Sohee",
                "language": "Korean",
                "instruct": self.mlx.DEFAULT_INSTRUCT,
                "max_chars": 160,
                "pause_ms": 250,
                "speed": 1.0,
                "seed": 1234,
                "temperature": 0.9,
                "top_p": 1.0,
                "top_k": 50,
                "repetition_penalty": 1.05,
                "max_new_tokens": 1024,
            }
            request = {
                "chapter": plan.chapter.key,
                "speech_sha256": plan.speech_sha256,
                "output_path": str(plan.chapter.output_path),
                "settings": settings,
            }
            stat = plan.chapter.output_path.stat()
            source = {
                "schema_version": 1,
                "inventory": list(self.mlx.EXPECTED_INVENTORY),
                "generator": str(self.mlx.GENERATOR_PATH),
                "settings": settings,
                "settings_fingerprint": self.mlx.PYTORCH_BATCH.json_digest(settings),
                "chapters": {
                    plan.chapter.key: {
                        "status": "verified",
                        "speech_sha256": plan.speech_sha256,
                        "expected_chunks": plan.expected_chunks,
                        "speech_path": str(plan.chapter.speech_path),
                        "output_path": str(plan.chapter.output_path),
                        "request_fingerprint": self.mlx.PYTORCH_BATCH.json_digest(request),
                        "verification": {
                            "output_sha256": self.mlx.sha256_file(plan.chapter.output_path),
                            "size": stat.st_size,
                            "output_mtime_ns": stat.st_mtime_ns,
                            "observed_chunks": plan.expected_chunks,
                            "cache_dir": str(cache),
                        },
                    }
                },
            }
            expected_duration = plan.expected_chunks * 0.5 + (plan.expected_chunks - 1) * 0.25
            with (
                mock.patch.object(
                    self.mlx,
                    "probe_mp3",
                    return_value={
                        "codec": "mp3",
                        "sample_rate": 24000,
                        "channels": 1,
                        "bit_rate": 128000,
                        "duration_seconds": expected_duration,
                        "size": stat.st_size,
                    },
                ),
                mock.patch.object(self.mlx, "verify_full_decode"),
            ):
                verified = self.mlx.verify_pytorch_adoption(plan, args, source)
                self.assertTrue(verified.ok, verified.reason)
                self.assertTrue(verified.metadata["legacy_adoption"])
                self.assertFalse(verified.metadata["boundary_safe"])
                self.assertEqual(verified.metadata["trailing_silence_ms"], 0)
                source["chapters"][plan.chapter.key]["speech_sha256"] = "stale"
                stale = self.mlx.verify_pytorch_adoption(plan, args, source)
                self.assertFalse(stale.ok)

    def test_adoption_never_constructs_runner_and_manifest_has_all_25_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C01")
            runner_factory = mock.Mock(side_effect=AssertionError("must not generate"))

            result = self.mlx.run_batch(
                args,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(args.model)),
                adoption_verifier=self.adopted_verification,
                mlx_verifier=self.false_verification,
                runner_factory=runner_factory,
            )

            self.assertEqual(result, 0)
            runner_factory.assert_not_called()
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["inventory"], list(self.mlx.EXPECTED_INVENTORY))
            self.assertEqual(set(manifest["chapters"]), set(self.mlx.EXPECTED_INVENTORY))
            entry = manifest["chapters"]["P01-C01"]
            self.assertEqual(entry["engine"], self.mlx.PYTORCH_ENGINE)
            self.assertEqual(entry["status"], "verified")
            self.assertEqual(entry["request_fingerprint"], "source-P01-C01")
            self.assertTrue(entry["adopted_existing"])

    def test_existing_unverified_output_is_never_overwritten_and_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C01")
            plan = self.plan_for(args)
            plan.chapter.output_path.write_bytes(b"do-not-overwrite" * 100)
            before = plan.chapter.output_path.read_bytes()
            runner_factory = mock.Mock(side_effect=AssertionError("must not generate"))

            result = self.mlx.run_batch(
                args,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.false_verification,
                runner_factory=runner_factory,
            )

            self.assertEqual(result, 1)
            self.assertEqual(plan.chapter.output_path.read_bytes(), before)
            runner_factory.assert_not_called()
            entry = json.loads(args.manifest.read_text(encoding="utf-8"))["chapters"]["P01-C01"]
            self.assertEqual(entry["status"], "failed")

    def test_generated_entry_and_check_only_use_current_mlx_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C01")
            runner = mock.Mock()
            runner_factory = mock.Mock(return_value=runner)

            result = self.mlx.run_batch(
                args,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.generated_verification,
                runner_factory=runner_factory,
            )

            self.assertEqual(result, 0)
            runner.generate_chapter.assert_called_once()
            entry = json.loads(args.manifest.read_text(encoding="utf-8"))["chapters"]["P01-C01"]
            plan = self.plan_for(args)
            self.assertEqual(entry["engine"], self.mlx.ENGINE)
            self.assertEqual(entry["status"], "verified")
            self.assertEqual(entry["request_fingerprint"], plan.request_fingerprint)
            self.assertTrue(entry["verification"]["boundary_safe"])

            check_args = self.make_args(root, "--check", "--only", "P01-C01")
            before = check_args.manifest.read_bytes()
            checked = self.mlx.run_batch(
                check_args,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(check_args.model)),
                adoption_verifier=self.false_verification,
                mlx_verifier=self.generated_verification,
            )
            self.assertEqual(checked, 0)
            self.assertEqual(check_args.manifest.read_bytes(), before)

    def test_final_verification_counts_one_250ms_pad_per_chunk_including_tail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            plan = self.plan_for(
                args,
                text=("가" * 100 + ".\n\n" + "나" * 99 + "."),
            )
            plan.chapter.output_path.write_bytes(b"m" * 2048)
            cache = {
                "cache_dir": str(plan.cache_dir),
                "cache_identity_sha256": plan.cache_identity_sha256,
                "observed_chunks": 2,
                "observed_groups": 1,
                "raw_chunk_duration_seconds": 1.0,
                "raw_digital_clipping_samples": 0,
                "raw_chunk_frames": [12000, 12000],
                "raw_chunk_sha256s": ["a", "b"],
            }
            with (
                mock.patch.object(self.mlx, "verify_mlx_cache", return_value=cache),
                mock.patch.object(
                    self.mlx,
                    "probe_mp3",
                    return_value={
                        "codec": "mp3",
                        "sample_rate": 24000,
                        "channels": 1,
                        "bit_rate": 128000,
                        "duration_seconds": 1.5,
                        "size": plan.chapter.output_path.stat().st_size,
                    },
                ),
                mock.patch.object(self.mlx, "verify_full_decode"),
                mock.patch.object(
                    self.mlx,
                    "verify_tail_silence",
                    return_value={"end_clipping_risk": 0},
                ),
                mock.patch.object(
                    self.mlx,
                    "verify_boundary_silence",
                    return_value={
                        "expected_boundaries": 2,
                        "verified_boundaries": 2,
                        "boundary_clipping_risk": 0,
                    },
                ),
                mock.patch.object(
                    self.mlx,
                    "verify_merge_receipt",
                    return_value={
                        "path": str(plan.cache_dir / "merge.commit.json"),
                        "sha256": "receipt-sha",
                        "output_sha256": self.mlx.sha256_file(
                            plan.chapter.output_path
                        ),
                        "created_at": "2026-08-25T00:00:00+00:00",
                    },
                ),
                mock.patch.object(self.mlx, "local_runtime_profile", return_value=self.profile()),
            ):
                verification = self.mlx.verify_mlx_artifact(plan, args)

            self.assertTrue(verification.ok, verification.reason)
            self.assertEqual(verification.metadata["pause_count"], 2)
            self.assertEqual(verification.metadata["trailing_silence_ms"], 250)
            self.assertEqual(verification.metadata["expected_output_duration_seconds"], 1.5)
            self.assertTrue(verification.metadata["boundary_safe"])

    def test_merge_receipt_cryptographically_binds_cache_order_and_mp3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            plan = self.plan_for(args)
            plan.cache_dir.mkdir(parents=True, exist_ok=True)
            plan.chapter.output_path.write_bytes(b"m" * 2048)
            cache = {
                "raw_chunk_sha256s": ["raw-sha"],
                "raw_chunk_frames": [12000],
            }
            audio = {
                "codec": "mp3",
                "sample_rate": 24000,
                "channels": 1,
                "bit_rate": 128000,
                "duration_seconds": 0.75,
                "size": plan.chapter.output_path.stat().st_size,
            }
            receipt = {
                "schema_version": self.mlx.CACHE_SCHEMA_VERSION,
                "cache_identity_sha256": plan.cache_identity_sha256,
                "request_fingerprint": plan.request_fingerprint,
                "raw_chunk_sha256s": cache["raw_chunk_sha256s"],
                "raw_chunk_frames": cache["raw_chunk_frames"],
                "pause_policy": "after-every-raw-chunk-including-final",
                "pause_count": 1,
                "pause_ms": 250,
                "output": {
                    **audio,
                    "sha256": self.mlx.sha256_file(plan.chapter.output_path),
                },
                "created_at": "2026-08-25T00:00:00+00:00",
            }
            self.mlx.atomic_write_json(self.mlx.merge_receipt_path(plan), receipt)

            verified = self.mlx.verify_merge_receipt(plan, args, cache, audio)
            self.assertEqual(
                verified["output_sha256"],
                self.mlx.sha256_file(plan.chapter.output_path),
            )
            plan.chapter.output_path.write_bytes(b"different" * 300)
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "does not bind"):
                self.mlx.verify_merge_receipt(plan, args, cache, audio)

    def test_boundary_qa_requires_silence_at_every_inserted_pad(self):
        completed = mock.Mock(
            returncode=0,
            stdout=b"",
            stderr=(
                b"silence_start: 0.500\n"
                b"silence_end: 0.750 | silence_duration: 0.250\n"
                b"silence_start: 1.250\n"
                b"silence_end: 1.500 | silence_duration: 0.250\n"
            ),
        )
        with (
            mock.patch.object(self.mlx, "find_program", return_value="ffmpeg"),
            mock.patch.object(self.mlx.subprocess, "run", return_value=completed),
        ):
            verified = self.mlx.verify_boundary_silence(
                Path("chapter.mp3"), "ffmpeg", [12000, 12000], 250
            )
        self.assertEqual(verified["verified_boundaries"], 2)

        completed.stderr = (
            b"silence_start: 0.500\n"
            b"silence_end: 0.750 | silence_duration: 0.250\n"
        )
        with (
            mock.patch.object(self.mlx, "find_program", return_value="ffmpeg"),
            mock.patch.object(self.mlx.subprocess, "run", return_value=completed),
        ):
            with self.assertRaisesRegex(self.mlx.MlxBatchError, "missing safe"):
                self.mlx.verify_boundary_silence(
                    Path("chapter.mp3"), "ffmpeg", [12000, 12000], 250
                )

    def test_check_only_verifies_selected_entry_without_mlx_runtime_or_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--only", "P01-C01")
            self.assertEqual(
                self.mlx.run_batch(
                    args,
                    profile=self.profile(),
                    model_identity=self.mlx.inspect_model(Path(args.model)),
                    adoption_verifier=self.adopted_verification,
                    mlx_verifier=self.false_verification,
                ),
                0,
            )
            before = args.manifest.read_bytes()
            check_args = self.make_args(root, "--check", "--only", "P01-C01")
            runtime_loader = mock.Mock(side_effect=AssertionError("must stay lazy"))

            result = self.mlx.run_batch(
                check_args,
                runtime_loader=runtime_loader,
                profile=self.profile(),
                model_identity=self.mlx.inspect_model(Path(check_args.model)),
                adoption_verifier=self.adopted_verification,
                mlx_verifier=self.false_verification,
            )

            self.assertEqual(result, 0)
            self.assertEqual(args.manifest.read_bytes(), before)
            runtime_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()

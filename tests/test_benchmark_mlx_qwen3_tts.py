from __future__ import annotations

import contextlib
import importlib.util
import io
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
    / "benchmark_mlx_qwen3_tts.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class IncrementingClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


class FakeModel:
    def __init__(self) -> None:
        self.serial_calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []

    @staticmethod
    def result(sequence_idx: int | None = None):
        payload = {
            "audio": [0.1, -0.1],
            "samples": 12000,
            "sample_rate": 24000,
            "token_count": 20,
            "processing_time_seconds": 1.25,
            "peak_memory_usage": 3.5,
        }
        if sequence_idx is not None:
            payload["sequence_idx"] = sequence_idx
        return SimpleNamespace(**payload)

    def generate_custom_voice(self, **kwargs):
        self.serial_calls.append(kwargs)
        yield self.result()

    def batch_generate(self, **kwargs):
        self.batch_calls.append(kwargs)
        for sequence_idx in range(len(kwargs["texts"])):
            yield self.result(sequence_idx)


class BenchmarkMlxQwen3TtsTest(unittest.TestCase):
    benchmark: ClassVar[Any]
    generator: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = load_module(SCRIPT, "benchmark_mlx_qwen3_tts_test_module")
        cls.generator = cls.benchmark.load_generator_module()

    def write_narration(self, path: Path, count: int = 4) -> None:
        path.write_text(
            "\n\n".join(
                f"청크 {index}의 문장입니다. " + ("가" * 80)
                for index in range(1, count + 1)
            ),
            encoding="utf-8",
        )

    def write_wav(self, path: Path, seconds: float = 0.5, sample_rate: int = 24000) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x01\x00" * round(sample_rate * seconds))

    def make_args(self, root: Path, *extra: str):
        narration = root / "narration.txt"
        if not narration.exists():
            self.write_narration(narration)
        model = root / "model"
        model.mkdir(exist_ok=True)
        (model / "config.json").write_text('{"model_type":"qwen3_tts"}\n')
        args = self.benchmark.parse_args(
            [
                "--file",
                str(narration),
                "--model",
                str(model),
                "--output-dir",
                str(root / "benchmark"),
                "--pytorch-cache-dir",
                str(root / "pytorch-cache"),
                "--chunk-indices",
                "1",
                "2",
                "3",
                *extra,
            ]
        )
        return self.benchmark.validate_args(args, root)

    def fake_runtime(self, model: FakeModel, seeds: list[int], loads: list[Path]):
        def load_model(path: Path):
            loads.append(path)
            return model

        def write_audio(path: Path, _audio, _sample_rate: int, _format: str | None):
            self.write_wav(path)

        return self.benchmark.MlxRuntime(
            load_model=load_model,
            write_audio=write_audio,
            set_seed=seeds.append,
            versions={
                "mlx-audio": "0.5.0",
                "mlx": "0.32.0",
                "mlx-metal": "0.32.0",
                "transformers": "5.14.0",
            },
        )

    def test_default_real_narration_selects_difficult_chunks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.benchmark.parse_args(
                [
                    "--model",
                    "dry-model",
                    "--output-dir",
                    str(root / "out"),
                    "--dry-run",
                ]
            )
            args = self.benchmark.validate_args(args, ROOT)
            plan = self.benchmark.build_plan(args, self.generator)

            self.assertEqual(
                [item["index"] for item in plan["selected_chunks"]],
                [30, 33, 41],
            )
            self.assertIn("8근무시간", plan["selected_chunks"][0]["text"])
            self.assertIn("직접생산확인증명서", plan["selected_chunks"][1]["text"])
            self.assertIn("4대 보험", plan["selected_chunks"][2]["text"])

    def test_dry_run_extracts_plan_without_importing_mlx_or_creating_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--dry-run")
            argv = [
                "--file",
                str(args.file),
                "--model",
                "not-a-local-model",
                "--output-dir",
                str(args.output_dir),
                "--pytorch-cache-dir",
                str(args.pytorch_cache_dir),
                "--chunk-indices",
                "1",
                "2",
                "3",
                "--dry-run",
            ]
            stdout = io.StringIO()
            with mock.patch.object(
                self.benchmark,
                "load_mlx_runtime",
                side_effect=AssertionError("MLX import path must not run"),
            ), contextlib.redirect_stdout(stdout):
                result = self.benchmark.main(argv)

            self.assertEqual(result, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["source"]["total_chunks"], 4)
            self.assertFalse(args.output_dir.exists())

    def test_serial_loads_once_seeds_once_and_writes_verified_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            self.write_wav(args.pytorch_cache_dir / "chunk_0001.wav", seconds=0.25)
            plan = self.benchmark.build_plan(args, self.generator)
            model = FakeModel()
            seeds: list[int] = []
            loads: list[Path] = []

            manifest = self.benchmark.run_benchmark(
                args,
                plan,
                self.fake_runtime(model, seeds, loads),
                clock=IncrementingClock(),
            )

            self.assertEqual(len(loads), 1)
            self.assertEqual(seeds, [1234])
            self.assertEqual(len(model.serial_calls), 3)
            self.assertEqual(model.batch_calls, [])
            self.assertEqual(manifest["mode"], "serial")
            self.assertEqual(manifest["randomness"]["scope"], "MLX global PRNG")
            self.assertGreater(manifest["aggregate"]["wall_per_audio_rtf"], 0)
            self.assertTrue(manifest["chunks"][0]["pytorch_reference"]["valid"])
            for item in manifest["chunks"]:
                output = Path(item["output"]["path"])
                self.assertTrue(output.is_file())
                self.assertEqual(item["output"]["sample_rate"], 24000)
                self.assertEqual(item["output"]["channels"], 1)
                self.assertEqual(item["output"]["sha256"], self.benchmark.sha256_file(output))
            manifest_path = args.output_dir / "benchmark_mlx_qwen3_tts_manifest.json"
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["settings"]["temperature"], 0.9)
            self.assertEqual(stored["settings"]["instruct"], self.benchmark.DEFAULT_INSTRUCT)

    def test_batch_uses_official_batch_api_in_requested_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, "--batch-size", "2")
            plan = self.benchmark.build_plan(args, self.generator)
            model = FakeModel()

            manifest = self.benchmark.run_benchmark(
                args,
                plan,
                self.fake_runtime(model, [], []),
                clock=IncrementingClock(),
            )

            self.assertEqual(model.serial_calls, [])
            self.assertEqual([len(call["texts"]) for call in model.batch_calls], [2, 1])
            self.assertEqual(model.batch_calls[0]["voices"], ["Sohee", "Sohee"])
            self.assertEqual(model.batch_calls[0]["lang_code"], "Korean")
            self.assertEqual(manifest["mode"], "batch")
            self.assertEqual(
                [group["effective_batch_size"] for group in manifest["batch_groups"]],
                [2, 1],
            )

    def test_invalid_batch_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(self.benchmark.BenchmarkError, "batch-size"):
                self.make_args(root, "--batch-size", "0")

    def test_output_directory_cannot_be_pytorch_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            narration = root / "narration.txt"
            self.write_narration(narration)
            shared = root / "shared"
            with self.assertRaisesRegex(self.benchmark.BenchmarkError, "read-only"):
                self.benchmark.validate_args(
                    self.benchmark.parse_args(
                        [
                            "--file",
                            str(narration),
                            "--model",
                            "dry-model",
                            "--output-dir",
                            str(shared),
                            "--pytorch-cache-dir",
                            str(shared),
                            "--dry-run",
                        ]
                    ),
                    root,
                )

    def test_atomic_wav_rejects_wrong_sample_rate_without_final_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            destination = root / "bad.wav"
            runtime = self.fake_runtime(FakeModel(), [], [])
            with self.assertRaisesRegex(self.benchmark.BenchmarkError, "sample rate"):
                self.benchmark.atomic_write_wav(destination, [0.0], 16000, runtime)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()

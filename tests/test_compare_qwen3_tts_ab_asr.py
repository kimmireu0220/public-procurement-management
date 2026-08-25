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


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "qwen3-tts-korean-lecture"
    / "scripts"
    / "compare_qwen3_tts_ab_asr.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CompareQwen3TtsAbAsrTest(unittest.TestCase):
    compare: ClassVar[Any]
    generator: ClassVar[Any]
    verifier: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.compare = load_module(SCRIPT, "compare_qwen3_tts_ab_asr_test_module")
        cls.generator = cls.compare.load_generator_module()
        cls.verifier = cls.compare.load_verifier_module()

    def write_narration(self, path: Path, count: int = 4) -> None:
        path.write_text(
            "\n\n".join(
                f"청크 {index}의 검증 문장입니다. " + ("가" * 80)
                for index in range(1, count + 1)
            ),
            encoding="utf-8",
        )

    def write_wav(
        self,
        path: Path,
        *,
        sample_rate: int = 24000,
        channels: int = 1,
        seconds: float = 1.0,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x01\x00" * round(sample_rate * seconds) * channels)

    def make_args(self, root: Path):
        narration = root / "narration.txt"
        self.write_narration(narration)
        pytorch_cache = root / "pytorch"
        candidate = root / "candidate"
        model = root / "asr-model"
        model.mkdir()
        for index in (1, 2, 3):
            self.write_wav(pytorch_cache / f"chunk_{index:04d}.wav")
            self.write_wav(candidate / f"mlx_chunk_{index:04d}.wav")
        args = self.compare.parse_args(
            [
                "--narration",
                str(narration),
                "--pytorch-cache-dir",
                str(pytorch_cache),
                "--candidate-dir",
                str(candidate),
                "--chunk-indices",
                "1",
                "2",
                "3",
                "--asr-model",
                str(model),
            ]
        )
        return self.compare.validate_args(args, root)

    def fake_verifier(self):
        def decode(_audio, _ffmpeg, *, sample_rate, quiet_db):
            self.assertEqual(sample_rate, 24000)
            self.assertEqual(quiet_db, -45.0)
            return {
                "complete": True,
                "duration_seconds": 1.0,
                "end_clipping_risk": False,
                "tail_clipped_samples": 0,
            }

        def silence(
            _audio,
            _ffmpeg,
            _duration,
            *,
            silence_db,
            minimum_seconds,
            long_seconds,
        ):
            self.assertEqual(silence_db, -45.0)
            self.assertEqual(minimum_seconds, 0.8)
            self.assertEqual(long_seconds, 3.0)
            return {
                "threshold_db": silence_db,
                "minimum_seconds": minimum_seconds,
                "regions": [],
                "leading_seconds": 0.0,
                "trailing_seconds": 0.0,
                "internal_long_regions": [],
                "maximum_seconds": 0.0,
            }

        return SimpleNamespace(
            decode_entire_audio=decode,
            detect_silence=silence,
            normalize_text=self.verifier.normalize_text,
            compare_transcript=self.verifier.compare_transcript,
        )

    def test_plan_reuses_generator_chunking_and_resolves_both_sides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            plan = self.compare.build_plan(args, self.generator)

            self.assertEqual(plan["source"]["total_chunks"], 4)
            self.assertEqual([pair["index"] for pair in plan["pairs"]], [1, 2, 3])
            self.assertTrue(plan["pairs"][0]["reference_path"].name.startswith("chunk_"))
            self.assertTrue(plan["pairs"][0]["candidate_path"].name.startswith("mlx_chunk_"))

    def test_build_report_transcribes_all_six_wavs_in_one_callable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            plan = self.compare.build_plan(args, self.generator)
            expected_by_index = {pair["index"]: pair["text"] for pair in plan["pairs"]}
            calls: list[tuple[str, dict[str, Any]]] = []

            def transcribe(audio: str, **kwargs):
                calls.append((audio, kwargs))
                index = int(Path(audio).stem.rsplit("_", 1)[1])
                return {
                    "text": expected_by_index[index],
                    "language": "ko",
                    "segments": [
                        {"start": 0.0, "end": 0.9, "text": expected_by_index[index]}
                    ],
                }

            report = self.compare.build_report(
                args,
                plan,
                ffmpeg="/mock/ffmpeg",
                transcribe=transcribe,
                asr_version="mock-1",
                verifier=self.fake_verifier(),
            )

            self.assertEqual(len(calls), 6)
            self.assertEqual({call[1]["language"] for call in calls}, {"ko"})
            self.assertEqual(
                {call[1]["condition_on_previous_text"] for call in calls}, {False}
            )
            self.assertEqual(
                {call[1]["path_or_hf_repo"] for call in calls}, {str(args.asr_model)}
            )
            self.assertTrue(report["ok"])
            self.assertEqual(report["asr"]["transcriptions"], 6)
            self.assertTrue(all(pair["evaluation"]["passed"] for pair in report["pairs"]))

    def test_relative_similarity_can_pass_below_absolute_threshold(self):
        def side(similarity: float, coverage: float = 0.9, ratio: float = 1.0):
            return {
                "audio": {"duration_seconds": 1.0},
                "comparison": {
                    "similarity": similarity,
                    "reference_coverage": coverage,
                    "length_ratio": ratio,
                    "tail": {"coverage": 0.9},
                },
                "issue_counts": {
                    "omissions": 0,
                    "repetitions": 0,
                    "tail_missing": 0,
                    "end_clipping": 0,
                    "long_silence_regions": 0,
                },
            }

        evaluation = self.compare.evaluate_pair(side(0.81), side(0.77))
        self.assertFalse(evaluation["criteria"]["similarity"]["candidate_at_least_0_80"])
        self.assertTrue(
            evaluation["criteria"]["similarity"]["candidate_within_0_05_of_reference"]
        )
        self.assertTrue(evaluation["passed"])
        self.assertFalse(self.compare.evaluate_pair(side(0.90), side(0.70))["passed"])

    def test_probe_rejects_non_24k_mono_wav(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "stereo.wav"
            self.write_wav(path, channels=2)
            with self.assertRaisesRegex(self.compare.AbAsrError, "24 kHz mono"):
                self.compare.probe_wav(path)

    def test_asr_model_must_be_existing_local_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root)
            args.asr_model = root / "missing-model"
            with self.assertRaisesRegex(self.compare.AbAsrError, "existing local directory"):
                self.compare.validate_args(args, root)

    def test_atomic_json_round_trip_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.json"
            self.compare.atomic_write_json(path, {"ok": True, "한글": "값"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["한글"], "값")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

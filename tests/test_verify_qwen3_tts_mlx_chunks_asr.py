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
    / "verify_qwen3_tts_mlx_chunks_asr.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class VerifyQwen3TtsMlxChunksAsrTest(unittest.TestCase):
    qa: ClassVar[Any]
    compare: ClassVar[Any]
    generator: ClassVar[Any]
    verifier: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.qa = load_module(SCRIPT, "verify_qwen3_tts_mlx_chunks_asr_test_module")
        cls.compare = cls.qa.load_compare_module()
        cls.generator = cls.qa.load_generator_module()
        cls.verifier = cls.qa.load_verifier_module()

    def write_narration(self, path: Path, count: int = 4) -> None:
        path.write_text(
            "\n\n".join(
                f"청크 {index}의 검증 문장입니다. " + ("가" * 90) + "."
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
            handle.writeframes(
                b"\x01\x00" * round(sample_rate * seconds) * channels
            )

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def make_args(
        self,
        root: Path,
        *,
        chunk_indices: tuple[int, ...] | None = None,
        wav_indices: tuple[int, ...] = (1, 2, 3, 4),
    ):
        narration = root / "narration.txt"
        cache = root / "candidate-cache"
        model = root / "asr-model"
        self.write_narration(narration)
        model.mkdir()
        cache.mkdir()
        for index in wav_indices:
            self.write_wav(cache / f"chunk_{index:04d}.wav")
        argv = [
            "--narration",
            str(narration),
            "--candidate-cache-dir",
            str(cache),
            "--asr-model",
            str(model),
        ]
        if chunk_indices is not None:
            argv.extend(["--chunk-indices", *(str(index) for index in chunk_indices)])
        return self.qa.validate_args(self.qa.parse_args(argv), root)

    def make_versioned_cache(
        self,
        args,
        *,
        selected_group_indices: tuple[int, ...] = (0, 1),
    ) -> dict[str, Any]:
        args.candidate_cache_dir.mkdir(parents=True, exist_ok=True)
        raw = args.narration.read_text(encoding="utf-8")
        cleaned = self.generator.clean_narration(raw)
        chunks = self.generator.split_narration(cleaned, 160)
        group_chunk_indices = ((1, 3), (2, 4))
        groups: list[dict[str, Any]] = []
        for stable_index, indices in enumerate(group_chunk_indices):
            text_hashes = [self.qa.sha256_text(chunks[index - 1]) for index in indices]
            group: dict[str, Any] = {
                "stable_index": stable_index,
                "seed": 1234 + stable_index,
                "length_bucket": 6,
                "chunk_indices": list(indices),
                "character_lengths": [len(chunks[index - 1]) for index in indices],
                "text_sha256s": text_hashes,
            }
            group["fingerprint"] = self.qa.json_digest(
                {
                    "algorithm": "fixed-character-length-bucket-v1",
                    "stable_index": stable_index,
                    "length_bucket": group["length_bucket"],
                    "chunk_indices": group["chunk_indices"],
                    "character_lengths": group["character_lengths"],
                    "text_sha256s": group["text_sha256s"],
                }
            )
            groups.append(group)
        identity = {
            "cache_schema_version": 1,
            "narration": {
                "speech_sha256": self.qa.sha256_file(args.narration),
                "cleaned_sha256": self.qa.sha256_text(cleaned),
                "cleaned_chars": len(cleaned),
                "chunk_text_sha256s": [
                    self.qa.sha256_text(text) for text in chunks
                ],
            },
            "settings": {"max_chars": 160},
            "batch_plan": {
                "algorithm": "fixed-character-length-bucket-v1",
                "groups": groups,
            },
        }
        identity_sha256 = self.qa.json_digest(identity)
        self.write_json(
            args.candidate_cache_dir / "cache_identity.json",
            {"cache_identity_sha256": identity_sha256, "identity": identity},
        )
        selectors: dict[int, Path] = {}
        manifests: dict[int, Path] = {}
        wavs: dict[int, Path] = {}
        for group_index in selected_group_indices:
            group = groups[group_index]
            generation_relative = (
                f"group_{group_index:04d}_generations/generation_test{group_index}"
            )
            generation_dir = args.candidate_cache_dir / generation_relative
            records: list[dict[str, Any]] = []
            for chunk_index in group["chunk_indices"]:
                wav = generation_dir / f"chunk_{chunk_index:04d}.wav"
                self.write_wav(wav)
                wavs[chunk_index] = wav
                records.append(
                    {
                        "chunk_index": chunk_index,
                        "text_sha256": self.qa.sha256_text(chunks[chunk_index - 1]),
                        "sha256": self.qa.sha256_file(wav),
                    }
                )
            manifest = {
                "schema_version": 1,
                "cache_identity_sha256": identity_sha256,
                "group_fingerprint": group["fingerprint"],
                "stable_group_index": group_index,
                "chunks": records,
            }
            manifest_path = generation_dir / "generation.json"
            self.write_json(manifest_path, manifest)
            selector = {
                "schema_version": 1,
                "cache_identity_sha256": identity_sha256,
                "group_fingerprint": group["fingerprint"],
                "stable_group_index": group_index,
                "generation_dir": generation_relative,
                "generation_manifest_sha256": self.qa.sha256_file(manifest_path),
            }
            selector_path = (
                args.candidate_cache_dir / f"group_{group_index:04d}.commit.json"
            )
            self.write_json(selector_path, selector)
            selectors[group_index] = selector_path
            manifests[group_index] = manifest_path
        return {
            "groups": groups,
            "selectors": selectors,
            "manifests": manifests,
            "wavs": wavs,
        }

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
            find_program=lambda _requested, _name: "/mock/ffmpeg",
        )

    def test_full_plan_reuses_exact_generator_split_and_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir))
            plan = self.qa.build_plan(args, self.generator, self.compare)

            self.assertEqual(plan["source"]["max_chars"], 160)
            self.assertEqual(plan["source"]["total_chunks"], 4)
            self.assertEqual(plan["selected_chunk_indices"], [1, 2, 3, 4])
            self.assertTrue(plan["cache"]["full_inventory_required"])
            self.assertEqual(
                [item["candidate_path"].name for item in plan["candidates"]],
                [f"chunk_{index:04d}.wav" for index in range(1, 5)],
            )

    def test_selected_chunks_do_not_require_unselected_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(
                Path(temp_dir), chunk_indices=(1, 3), wav_indices=(1, 3)
            )
            plan = self.qa.build_plan(args, self.generator, self.compare)

            self.assertEqual(plan["selected_chunk_indices"], [1, 3])
            self.assertFalse(plan["cache"]["full_inventory_required"])
            self.assertEqual([item["index"] for item in plan["candidates"]], [1, 3])

    def test_versioned_full_cache_resolves_selected_generation_wavs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), wav_indices=())
            fixture = self.make_versioned_cache(args)

            plan = self.qa.build_plan(args, self.generator, self.compare)

            self.assertEqual(plan["cache"]["format"], "versioned-immutable-groups")
            self.assertEqual(plan["cache"]["identity_groups"], 2)
            self.assertEqual(plan["cache"]["resolved_group_indices"], [0, 1])
            self.assertEqual([item["index"] for item in plan["candidates"]], [1, 2, 3, 4])
            self.assertEqual(plan["candidates"][0]["candidate_path"], fixture["wavs"][1])
            self.assertEqual(
                plan["candidates"][0]["cache_binding"]["stable_group_index"], 0
            )

    def test_versioned_selected_resolution_does_not_require_unselected_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(
                Path(temp_dir), chunk_indices=(1,), wav_indices=()
            )
            self.make_versioned_cache(args, selected_group_indices=(0,))

            plan = self.qa.build_plan(args, self.generator, self.compare)

            self.assertEqual(plan["cache"]["identity_groups"], 2)
            self.assertEqual(plan["cache"]["resolved_group_indices"], [0])
            self.assertEqual([item["index"] for item in plan["candidates"]], [1])

    def test_versioned_cache_rejects_unsafe_and_stale_selectors(self):
        for mutation, message in (
            ("unsafe", "Unsafe selected generation directory"),
            ("stale", "Group selector 0 is stale or corrupt"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp_dir:
                args = self.make_args(
                    Path(temp_dir), chunk_indices=(1,), wav_indices=()
                )
                fixture = self.make_versioned_cache(args, selected_group_indices=(0,))
                selector_path = fixture["selectors"][0]
                selector = json.loads(selector_path.read_text(encoding="utf-8"))
                if mutation == "unsafe":
                    selector["generation_dir"] = "../outside"
                else:
                    selector["group_fingerprint"] = "0" * 64
                self.write_json(selector_path, selector)

                with self.assertRaisesRegex(self.qa.MlxChunkQaError, message):
                    self.qa.build_plan(args, self.generator, self.compare)

    def test_versioned_cache_rejects_manifest_union_and_recorded_wav_hash_changes(self):
        for mutation, message in (
            ("union", "chunk index union is not exact"),
            ("wav", "WAV SHA is stale"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp_dir:
                args = self.make_args(
                    Path(temp_dir), chunk_indices=(1,), wav_indices=()
                )
                fixture = self.make_versioned_cache(args, selected_group_indices=(0,))
                if mutation == "union":
                    manifest_path = fixture["manifests"][0]
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["chunks"].pop()
                    self.write_json(manifest_path, manifest)
                    selector_path = fixture["selectors"][0]
                    selector = json.loads(selector_path.read_text(encoding="utf-8"))
                    selector["generation_manifest_sha256"] = self.qa.sha256_file(
                        manifest_path
                    )
                    self.write_json(selector_path, selector)
                else:
                    with fixture["wavs"][1].open("ab") as handle:
                        handle.write(b"changed")

                with self.assertRaisesRegex(self.qa.MlxChunkQaError, message):
                    self.qa.build_plan(args, self.generator, self.compare)

    def test_full_plan_rejects_missing_or_extra_chunk_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), wav_indices=(1, 2, 3))
            with self.assertRaisesRegex(
                self.qa.MlxChunkQaError, "Full candidate cache inventory mismatch"
            ):
                self.qa.build_plan(args, self.generator, self.compare)

    def test_report_transcribes_each_selected_wav_once_without_reference_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = self.make_args(Path(temp_dir), chunk_indices=(1, 3, 4))
            plan = self.qa.build_plan(args, self.generator, self.compare)
            expected_by_index = {
                item["index"]: item["text"] for item in plan["candidates"]
            }
            calls: list[tuple[str, dict[str, Any]]] = []

            def transcribe(audio: str, **kwargs):
                calls.append((audio, kwargs))
                index = int(Path(audio).stem.rsplit("_", 1)[1])
                text = expected_by_index[index]
                return {
                    "text": text,
                    "language": "ko",
                    "segments": [{"start": 0.0, "end": 0.9, "text": text}],
                }

            report = self.qa.build_report(
                args,
                plan,
                ffmpeg="/mock/ffmpeg",
                transcribe=transcribe,
                asr_version="mock-1",
                compare=self.compare,
                verifier=self.fake_verifier(),
            )

            self.assertEqual(len(calls), 3)
            self.assertEqual(
                {call[1]["path_or_hf_repo"] for call in calls},
                {str(args.asr_model)},
            )
            self.assertEqual(
                {call[1]["condition_on_previous_text"] for call in calls}, {False}
            )
            self.assertTrue(report["asr"]["same_process"])
            self.assertEqual(report["asr"]["transcriptions"], 3)
            self.assertTrue(report["ok"])
            self.assertTrue(all(chunk["evaluation"]["passed"] for chunk in report["chunks"]))
            self.assertNotIn("reference", report["chunks"][0])
            self.assertIn("no-reference-cache", report["comparison_mode"])

    def test_absolute_evaluation_flags_content_and_structural_failures(self):
        args = SimpleNamespace(
            min_similarity=0.80,
            min_reference_coverage=0.75,
            min_length_ratio=0.80,
            max_length_ratio=1.20,
        )
        candidate = {
            "comparison": {
                "similarity": 0.70,
                "reference_coverage": 0.65,
                "length_ratio": 1.35,
            },
            "decode": {
                "probe_duration_delta_seconds": 0.10,
                "tail_clipped_samples": 2,
            },
            "issue_counts": {
                "omissions": 1,
                "repetitions": 1,
                "tail_missing": 1,
                "end_clipping": 1,
                "long_silence_regions": 1,
            },
        }

        evaluation = self.qa.evaluate_candidate(candidate, args)

        self.assertFalse(evaluation["passed"])
        self.assertEqual(
            set(evaluation["failures"]),
            {
                "low_normalized_similarity",
                "low_reference_coverage",
                "asr_reference_length_ratio_out_of_range",
                "decoded_duration_mismatch",
                "likely_omission",
                "likely_repetition",
                "narration_tail_missing",
                "long_silence_at_least_3_seconds",
                "digital_full_scale_samples_in_tail",
            },
        )
        self.assertEqual(
            evaluation["advisories"],
            ["raw_terminal_boundary_risk_before_final_250ms_pad"],
        )
        self.assertFalse(
            evaluation["criteria"]["raw_terminal_boundary_advisory"][
                "strict_failure"
            ]
        )

    def test_spoken_korean_and_rendered_alphanumeric_codes_normalize_equivalently(self):
        spoken = (
            "사업 코드는 엔씨, 이공이칠, 영사/영일입니다. "
            "요구번호는 알 대시 영영일입니다. 증거등급은 에이입니다."
        )
        rendered = (
            "사업 코드는 NC-2027-04/01입니다. "
            "요구번호는 R-001입니다. 증거등급은 A입니다."
        )

        canonical_spoken, events = self.qa.canonicalize_code_equivalents(spoken)
        canonical_rendered, _ = self.qa.canonicalize_code_equivalents(rendered)

        self.assertEqual(
            self.verifier.normalize_text(canonical_spoken),
            self.verifier.normalize_text(canonical_rendered),
        )
        self.assertEqual(
            [event["canonical"] for event in events],
            ["NC20270401", "R001", "A"],
        )

    def test_code_aware_comparison_passes_chunk_61_but_preserves_korean_word_error(self):
        reference = (
            "네 번째 사업 식별자는 엔씨, 이공이칠, 영사입니다. "
            "첫 번째 사업인 엔씨, 이공이칠, 영일의 본공고입니다. "
            "공식 연계번호와 기관, 사업명이 일치하지만 계획보다 기간이 달라졌습니다. "
            "증거등급은 에이이며 적합성을 다시 검토합니다."
        )
        hypothesis = (
            "네 번째 사업 식별자는 NC-2027-04입니다. "
            "첫 번째 사업인 NC-2027-01의 본 공고입니다. "
            "공식 연계번호와 기관, 사업명이 일치하지만 계획보다 기관이 달라졌습니다. "
            "증거 등급은 A이며 적합성을 다시 검토합니다."
        )
        asr = {
            "text": hypothesis,
            "segments": [{"start": 0.0, "end": 21.24, "text": hypothesis}],
        }

        raw = self.verifier.compare_transcript(
            reference,
            asr,
            21.36,
            min_block_coverage=0.18,
            min_tail_coverage=0.18,
        )
        comparison = self.qa.compare_transcript_code_aware(
            self.verifier,
            reference,
            asr,
            21.36,
            min_block_coverage=0.18,
            min_tail_coverage=0.18,
        )
        candidate = {
            "comparison": comparison,
            "decode": {
                "probe_duration_delta_seconds": 0.0,
                "tail_clipped_samples": 0,
            },
            "issue_counts": {
                "omissions": 0,
                "repetitions": 0,
                "tail_missing": 0,
                "end_clipping": 0,
                "long_silence_regions": 0,
            },
        }
        args = SimpleNamespace(
            min_similarity=0.80,
            min_reference_coverage=0.75,
            min_length_ratio=0.80,
            max_length_ratio=1.20,
        )

        self.assertLess(raw["similarity"], 0.80)
        self.assertGreater(comparison["similarity"], 0.90)
        self.assertGreater(comparison["reference_coverage"], 0.90)
        self.assertLess(comparison["similarity"], 1.0)
        self.assertTrue(self.qa.evaluate_candidate(candidate, args)["passed"])
        canonical_hypothesis = self.qa.canonicalize_code_equivalents(hypothesis)[0]
        self.assertIn("기관이 달라졌습니다", canonical_hypothesis)
        self.assertNotIn("기간이 달라졌습니다", canonical_hypothesis)

    def test_code_normalization_does_not_hide_omitted_korean_content(self):
        required_detail = (
            "공식 연계번호와 기관과 사업명을 확인하고 계획보다 기간이 달라졌는지 "
            "원문 근거를 다시 대조합니다. "
        ) * 3
        reference = (
            "사업 식별자는 엔씨, 이공이칠, 영사입니다. " + required_detail
        )
        hypothesis = "사업 식별자는 NC-2027-04입니다."
        comparison = self.qa.compare_transcript_code_aware(
            self.verifier,
            reference,
            {
                "text": hypothesis,
                "segments": [{"start": 0.0, "end": 3.0, "text": hypothesis}],
            },
            3.1,
            min_block_coverage=0.18,
            min_tail_coverage=0.18,
        )

        self.assertLess(comparison["similarity"], 0.40)
        self.assertLess(comparison["reference_coverage"], 0.25)
        self.assertTrue(comparison["large_omissions"])
        self.assertTrue(comparison["tail"]["missing"])

    def test_ordinary_korean_letter_names_and_number_like_words_are_unchanged(self):
        ordinary = (
            "비 기관에서 씨가 말한 기간이 달라졌습니다. "
            "일일이 확인하고 삼일째 이어진 일을 기록합니다. "
            "이 12개월 사업은 일반 문장입니다."
        )

        canonical, events = self.qa.canonicalize_code_equivalents(ordinary)

        self.assertEqual(canonical, ordinary)
        self.assertEqual(events, [])

    def test_main_returns_one_and_atomically_writes_a_quality_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, chunk_indices=(1,))
            report_path = root / "qa-report.json"
            argv = [
                "--narration",
                str(args.narration),
                "--candidate-cache-dir",
                str(args.candidate_cache_dir),
                "--asr-model",
                str(args.asr_model),
                "--chunk-indices",
                "1",
                "--output-json",
                str(report_path),
            ]

            def unrelated_transcript(_audio: str, **_kwargs):
                return {
                    "text": "완전히 다른 내용만 짧게 인식했습니다.",
                    "language": "ko",
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 0.8,
                            "text": "완전히 다른 내용만 짧게 인식했습니다.",
                        }
                    ],
                }

            with (
                mock.patch.object(self.qa, "load_generator_module", return_value=self.generator),
                mock.patch.object(self.qa, "load_compare_module", return_value=self.compare),
                mock.patch.object(self.qa, "load_verifier_module", return_value=self.fake_verifier()),
                mock.patch.object(
                    self.compare,
                    "load_transcriber",
                    return_value=(unrelated_transcript, "mock-1"),
                ),
                mock.patch("builtins.print"),
            ):
                return_code = self.qa.main(argv)

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(return_code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["summary"]["failed_chunk_indices"], [1])
            self.assertEqual(list(root.glob(f".{report_path.name}.*.tmp")), [])

    def test_summary_only_prints_compact_json_but_writes_full_atomic_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, chunk_indices=(1,))
            plan = self.qa.build_plan(args, self.generator, self.compare)
            expected_text = plan["candidates"][0]["text"]
            report_path = root / "full-qa-report.json"
            argv = [
                "--narration",
                str(args.narration),
                "--candidate-cache-dir",
                str(args.candidate_cache_dir),
                "--asr-model",
                str(args.asr_model),
                "--chunk-indices",
                "1",
                "--output-json",
                str(report_path),
                "--summary-only",
            ]

            def exact_transcript(_audio: str, **_kwargs):
                return {
                    "text": expected_text,
                    "language": "ko",
                    "segments": [
                        {"start": 0.0, "end": 0.9, "text": expected_text}
                    ],
                }

            with (
                mock.patch.object(self.qa, "load_generator_module", return_value=self.generator),
                mock.patch.object(self.qa, "load_compare_module", return_value=self.compare),
                mock.patch.object(self.qa, "load_verifier_module", return_value=self.fake_verifier()),
                mock.patch.object(
                    self.compare,
                    "load_transcriber",
                    return_value=(exact_transcript, "mock-1"),
                ),
                mock.patch("builtins.print") as print_mock,
            ):
                return_code = self.qa.main(argv)

            stdout_payload = json.loads(print_mock.call_args.args[0])
            full_payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(return_code, 0)
            self.assertEqual(
                list(stdout_payload),
                ["ok", "source", "cache", "asr", "thresholds", "summary"],
            )
            self.assertNotIn("chunks", stdout_payload)
            self.assertNotIn("comparison_mode", stdout_payload)
            self.assertIn("chunks", full_payload)
            self.assertEqual(len(full_payload["chunks"]), 1)
            self.assertEqual(stdout_payload["summary"], full_payload["summary"])
            self.assertEqual(list(root.glob(f".{report_path.name}.*.tmp")), [])

    def test_compact_stdout_report_keeps_only_documented_fields(self):
        report = {
            "ok": False,
            "source": {"total_chunks": 4},
            "cache": {"path": "/cache"},
            "asr": {"transcriptions": 2},
            "thresholds": {"normalized_similarity": 0.8},
            "summary": {"failed_chunks": 1},
            "schema_version": 1,
            "comparison_mode": "absolute",
            "chunks": [{"index": 1}],
        }

        compact = self.qa.compact_stdout_report(report)

        self.assertEqual(
            list(compact),
            ["ok", "source", "cache", "asr", "thresholds", "summary"],
        )
        self.assertNotIn("chunks", compact)

    def test_invalid_local_model_and_duplicate_indices_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = self.make_args(root, chunk_indices=(1,))
            args.asr_model = root / "missing"
            with self.assertRaisesRegex(
                self.qa.MlxChunkQaError, "existing local directory"
            ):
                self.qa.validate_args(args, root)

            duplicate_args = self.qa.parse_args(
                [
                    "--narration",
                    str(root / "narration.txt"),
                    "--candidate-cache-dir",
                    str(root / "candidate-cache"),
                    "--asr-model",
                    str(root / "asr-model"),
                    "--chunk-indices",
                    "1",
                    "1",
                ]
            )
            with self.assertRaisesRegex(
                self.qa.MlxChunkQaError, "Duplicate chunk indices"
            ):
                self.qa.validate_args(duplicate_args, root)


if __name__ == "__main__":
    unittest.main()

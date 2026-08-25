from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "qwen3-tts-korean-lecture" / "scripts" / "generate_qwen3_tts.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("qwen3_tts_generator", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Qwen3TtsGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def args_for_cache(self, **overrides):
        values = {
            "speaker": "Sohee",
            "language": "Korean",
            "instruct": "차분한 강의",
            "max_chars": 160,
            "seed": 1234,
            "temperature": 0.9,
            "top_p": 1.0,
            "top_k": 50,
            "repetition_penalty": 1.05,
            "max_new_tokens": 1024,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_default_contract_uses_official_sohee_without_reference_audio(self):
        with mock.patch.object(sys, "argv", ["generate_qwen3_tts.py", "--text", "안녕하세요."]):
            args = self.generator.parse_args()
        self.assertEqual(args.model, "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
        self.assertEqual(args.speaker, "Sohee")
        self.assertEqual(args.language, "Korean")
        self.assertEqual(args.device, "auto")
        self.assertFalse(hasattr(args, "ref_audio"))
        self.assertFalse(hasattr(args, "confirm_authorized"))

    def test_module_import_does_not_require_torch_or_qwen_tts(self):
        self.assertIsNotNone(self.generator)
        self.assertNotIn("qwen_tts", self.generator.__dict__)
        self.assertNotIn("torch", self.generator.__dict__)

    def test_markdown_cleanup_and_split_preserve_order(self):
        source = "# 제목\n\n- **첫 문장입니다.**\n- `둘째 문장입니다.`\n\n셋째 문장입니다."
        cleaned = self.generator.clean_narration(source)
        self.assertEqual(cleaned, "제목\n\n첫 문장입니다.\n둘째 문장입니다.\n\n셋째 문장입니다.")
        chunks = self.generator.split_narration(cleaned, 50)
        self.assertTrue(chunks)
        self.assertTrue(all(0 < len(chunk) <= 50 for chunk in chunks))
        self.assertLess(chunks[0].find("제목"), chunks[-1].rfind("셋째"))

    def test_long_unbroken_text_is_hard_split_without_loss(self):
        text = "가" * 121
        chunks = self.generator.split_narration(text, 50)
        self.assertEqual([len(chunk) for chunk in chunks], [50, 50, 21])
        self.assertEqual("".join(chunks), text)

    def test_section_parser_validates_order_and_control_text(self):
        text = "\n".join(
            (
                "[[SECTION_START|P01|C01|S01|첫 구간]]",
                "첫 문장입니다.",
                "[[SECTION_END|P01|C01|S01]]",
                "[[SECTION_START|P01|C01|S02|둘째 구간]]",
                "둘째 문장입니다.",
                "[[SECTION_END|P01|C01|S02]]",
            )
        )
        sections = self.generator.parse_sections(text)
        self.assertEqual([section[:3] for section in sections], [("P01", "C01", "S01"), ("P01", "C01", "S02")])
        self.assertNotIn("SECTION", " ".join(section[4] for section in sections))
        with self.assertRaisesRegex(ValueError, "outside SECTION"):
            self.generator.parse_sections("제작 메모\n" + text)
        with self.assertRaisesRegex(ValueError, "Mismatched"):
            self.generator.parse_sections(text.replace("SECTION_END|P01|C01|S01", "SECTION_END|P01|C01|S09", 1))

    def test_cache_identity_changes_for_every_audio_affecting_field(self):
        profile = {"qwen_tts": "0.1.1", "torch": "2.13", "device": "mps", "dtype": "float16", "attention": "sdpa"}
        base_args = self.args_for_cache()
        base = self.generator.cache_identity(base_args, "대본", "/model/rev-a", profile)
        changes = {
            "speaker": "Vivian",
            "language": "English",
            "instruct": "빠르게",
            "max_chars": 200,
            "seed": 99,
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 10,
            "repetition_penalty": 1.2,
            "max_new_tokens": 512,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = self.generator.cache_identity(self.args_for_cache(**{field: value}), "대본", "/model/rev-a", profile)
                self.assertNotEqual(base, changed)
        self.assertNotEqual(base, self.generator.cache_identity(base_args, "다른 대본", "/model/rev-a", profile))
        self.assertNotEqual(base, self.generator.cache_identity(base_args, "대본", "/model/rev-b", profile))
        cpu_profile = dict(profile, device="cpu", dtype="float32")
        self.assertNotEqual(base, self.generator.cache_identity(base_args, "대본", "/model/rev-a", cpu_profile))
        self.assertEqual(json.loads(base)["engine"], "qwen3-tts-custom-voice")

    def test_relative_paths_resolve_from_invocation_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            invocation = Path(temp_dir).resolve()
            self.assertEqual(
                self.generator.resolve_path(Path("output/sample.mp3"), invocation),
                invocation / "output" / "sample.mp3",
            )
            self.assertTrue(str(self.generator.default_output("대본", "mp3", invocation)).startswith(str(invocation / "output")))

    def test_model_snapshot_preflight_requires_custom_voice_sohee_korean(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir)
            (snapshot / "speech_tokenizer").mkdir()
            for relative in ("model.safetensors", "generation_config.json", "speech_tokenizer/config.json", "speech_tokenizer/model.safetensors"):
                path = snapshot / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            config = {
                "tts_model_type": "custom_voice",
                "talker_config": {"spk_id": {"sohee": 1}, "codec_language_id": {"korean": 2}},
            }
            (snapshot / "config.json").write_text(json.dumps(config), encoding="utf-8")
            self.generator.validate_model_snapshot(snapshot, "Sohee", "Korean")
            config["tts_model_type"] = "base"
            (snapshot / "config.json").write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CustomVoice"):
                self.generator.validate_model_snapshot(snapshot, "Sohee", "Korean")

    def test_wav_validation_rejects_empty_and_accepts_pcm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.wav"
            self.assertFalse(self.generator.valid_wav(path))
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(44100)
                handle.writeframes(b"\x01\x00" * 44100 * 2)
            self.assertFalse(self.generator.valid_wav(path))
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(24000)
                handle.writeframes(b"\x01\x00" * 24000)
            self.assertTrue(self.generator.valid_wav(path))

    def test_runtime_reexec_guard_prevents_recursion(self):
        args = argparse.Namespace(runtime_python=Path("/missing/python"))
        with mock.patch.dict(os.environ, {"_QWEN3_TTS_UNIFIED_REEXEC": "1"}, clear=False):
            with mock.patch.object(self.generator.subprocess, "run") as run:
                self.generator.ensure_runtime_python(args)
                run.assert_not_called()

    def test_runtime_reexec_preserves_virtualenv_python_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "python-target"
            target.write_bytes(b"python")
            runtime = root / "venv" / "bin" / "python"
            runtime.parent.mkdir(parents=True)
            runtime.symlink_to(target)
            args = argparse.Namespace(runtime_python=runtime)
            completed = mock.Mock(returncode=0)
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(self.generator.importlib.util, "find_spec", return_value=None):
                    with mock.patch.object(self.generator.subprocess, "run", return_value=completed) as run:
                        with self.assertRaises(SystemExit) as raised:
                            self.generator.ensure_runtime_python(args)
            self.assertEqual(raised.exception.code, 0)
            self.assertEqual(run.call_args.args[0][0], str(runtime))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import io
import math
import struct
import sys
import unittest
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
QA_SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "qwen3-tts-korean-lecture"
    / "scripts"
    / "verify_qwen3_tts_audio.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Qwen3TtsAudioQaTest(unittest.TestCase):
    qa: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.qa = load_module(QA_SCRIPT, "qwen3_tts_audio_qa_test_module")

    def test_normalization_and_ngram_similarity_ignore_spacing_and_punctuation(self):
        reference = "입찰 참가자격은, 공고 기준일에 확인합니다."
        hypothesis = "입찰참가자격은 공고기준일에 확인합니다"

        normalized = self.qa.normalize_text(reference)
        scores = self.qa.ngram_scores(normalized, self.qa.normalize_text(hypothesis))

        self.assertEqual(normalized, "입찰참가자격은공고기준일에확인합니다")
        self.assertEqual(scores["similarity"], 1.0)
        self.assertEqual(scores["reference_coverage"], 1.0)

    def test_silence_parser_closes_a_trailing_open_region(self):
        log = """
[silencedetect @ 0x1] silence_start: 0
[silencedetect @ 0x1] silence_end: 1.25 | silence_duration: 1.25
[silencedetect @ 0x1] silence_start: 8.5
"""

        regions = self.qa.parse_silence_log(log, 10.0)

        self.assertEqual(len(regions), 2)
        self.assertEqual(regions[0]["duration_seconds"], 1.25)
        self.assertEqual(regions[1]["start_seconds"], 8.5)
        self.assertEqual(regions[1]["end_seconds"], 10.0)

    def test_complete_decode_counts_all_samples_and_checks_quiet_tail(self):
        sample_rate = 24000
        loud = [round(9000 * math.sin(index / 8)) for index in range(sample_rate)]
        fade = [
            round(
                9000
                * math.sin(index / 8)
                * math.exp(-8 * index / round(sample_rate * 0.1))
            )
            for index in range(round(sample_rate * 0.1))
        ]
        quiet = [0] * round(sample_rate * 0.1)
        pcm = b"".join(struct.pack("<h", sample) for sample in [*loud, *fade, *quiet])
        process = mock.Mock()
        process.stdout = io.BytesIO(pcm)
        process.stderr = io.BytesIO(b"")
        process.wait.return_value = 0

        with mock.patch.object(self.qa.subprocess, "Popen", return_value=process):
            result = self.qa.decode_entire_audio(Path("chapter.mp3"), "ffmpeg")

        self.assertTrue(result["complete"])
        self.assertEqual(result["decoded_samples"], len(loud) + len(fade) + len(quiet))
        self.assertAlmostEqual(result["duration_seconds"], 1.2, places=3)
        self.assertGreaterEqual(result["trailing_quiet_seconds"], 0.1)
        self.assertFalse(result["end_clipping_risk"])

    def test_terminal_boundary_flags_an_audible_abrupt_end(self):
        samples = [8000 if index % 2 else -8000 for index in range(24000)]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        sample_array = self.qa.array("h")
        sample_array.frombytes(pcm)

        result = self.qa.terminal_boundary_metrics(sample_array, 24000)

        self.assertFalse(result["safe"])
        self.assertLess(result["trailing_quiet_ms"], 20.0)
        self.assertGreater(result["final_5ms_rms_dbfs"], -45.0)

    def test_comparison_reports_large_omission_repetition_and_tail_loss(self):
        first = (
            "발주기관의 법적 지위와 공고의 적용 규정을 차례대로 확인하고 "
            "계약 목적물의 성질을 규격서에서 다시 검토합니다. "
        ) * 4
        omitted = (
            "직접생산 확인은 제조물품 등록과 구분하며 유효기간과 세부품명을 대조합니다. "
            "공급물품 등록만으로 제조 요건을 대신할 수 없습니다. "
        ) * 4
        ending = (
            "마지막으로 허가와 면허의 기준일을 확인한 뒤 증빙의 만료 여부를 기록합니다. "
            "이제 핵심 순서를 소리 내어 회상해 보세요. "
        ) * 4
        repeated = (
            "이 문장은 합성 과정의 예기치 않은 반복을 찾아내기 위한 서로 다른 낱말의 긴 검사 구간입니다"
        )
        asr_text = first + repeated + repeated
        asr = {
            "text": asr_text,
            "segments": [
                {"start": 0.0, "end": 12.0, "text": first},
                {"start": 12.0, "end": 18.0, "text": repeated},
                {"start": 18.0, "end": 24.0, "text": repeated},
            ],
        }

        result = self.qa.compare_transcript(
            "\n\n".join((first, omitted, repeated, ending)),
            asr,
            30.0,
            min_block_coverage=0.30,
            min_tail_coverage=0.30,
        )

        self.assertTrue(result["large_omissions"])
        self.assertTrue(result["large_repetitions"])
        self.assertTrue(result["tail"]["missing"])
        self.assertEqual(result["tail"]["audio_gap_after_last_asr_seconds"], 6.0)

    def test_exact_transcript_has_no_content_risks(self):
        reference = (
            "공고에서 정한 참가자격과 세부품명을 확인합니다. "
            "증빙의 기준일과 유효기간도 각각 대조합니다. "
        ) * 8
        asr = {
            "text": reference,
            "segments": [{"start": 0.0, "end": 15.0, "text": reference}],
        }

        result = self.qa.compare_transcript(
            reference,
            asr,
            15.2,
            min_block_coverage=0.18,
            min_tail_coverage=0.18,
        )

        self.assertEqual(result["similarity"], 1.0)
        self.assertEqual(result["large_omissions"], [])
        self.assertEqual(result["large_repetitions"], [])
        self.assertFalse(result["tail"]["missing"])


if __name__ == "__main__":
    unittest.main()

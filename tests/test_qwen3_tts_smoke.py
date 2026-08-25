from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "qwen3-tts-korean-lecture" / "scripts" / "generate_qwen3_tts.py"


@unittest.skipUnless(os.environ.get("RUN_QWEN3_TTS_SMOKE") == "1", "set RUN_QWEN3_TTS_SMOKE=1 for real synthesis")
class Qwen3TtsSmokeTest(unittest.TestCase):
    def test_real_sohee_short_wav(self):
        with tempfile.TemporaryDirectory(prefix="qwen3-tts-smoke-") as temp_dir:
            output = Path(temp_dir) / "sohee_smoke.wav"
            env = os.environ.copy()
            env["HF_HUB_OFFLINE"] = "1"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--text",
                    "안녕하세요. 공공조달관리사 음성 합성 점검입니다.",
                    "--device",
                    "mps",
                    "--output",
                    str(output),
                    "--clean-cache",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=1200,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.is_file())
            with wave.open(str(output), "rb") as handle:
                self.assertEqual(handle.getnchannels(), 1)
                self.assertEqual(handle.getsampwidth(), 2)
                self.assertEqual(handle.getframerate(), 24000)
                duration = handle.getnframes() / handle.getframerate()
            self.assertGreater(duration, 0.5)
            self.assertLess(duration, 60)


if __name__ == "__main__":
    unittest.main()

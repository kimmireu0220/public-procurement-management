from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from verify_legal_sources import (  # noqa: E402
    DEFAULT_MANIFEST,
    snapshot_evidence_profile,
    verify_manifest,
)


class LegalSourceManifestTests(unittest.TestCase):
    def test_repository_bundle_is_valid(self) -> None:
        self.assertEqual(verify_manifest(), [])

    def test_repository_reports_article_text_and_metadata_shells_separately(self) -> None:
        profile = snapshot_evidence_profile()

        self.assertEqual(len(profile["article_text"]), 12)
        self.assertEqual(len(profile["metadata_shell"]), 22)
        self.assertIn("state_contract_decree", profile["metadata_shell"])
        self.assertIn("negotiated_contract_criteria", profile["article_text"])

    def test_hash_tampering_and_unlisted_snapshot_are_reported(self) -> None:
        original = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        entry = dict(original["sources"][0])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            source = DEFAULT_MANIFEST.parent / entry["snapshot"]
            copied = snapshots / Path(entry["snapshot"]).name
            shutil.copyfile(source, copied)
            (snapshots / "unlisted.html").write_text("unlisted", encoding="utf-8")

            entry["snapshot"] = f"snapshots/{copied.name}"
            entry["sha256"] = "0" * 64
            manifest = {
                "schema_version": 1,
                "retrieved_at": original["retrieved_at"],
                "provider": original["provider"],
                "sources": [entry],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            errors = verify_manifest(manifest_path)

        self.assertTrue(any("SHA-256 불일치" in error for error in errors))
        self.assertIn("manifest에 없는 snapshot: unlisted.html", errors)

    def test_manifest_hash_matches_copied_snapshot(self) -> None:
        original = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        entry = dict(original["sources"][0])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            source = DEFAULT_MANIFEST.parent / entry["snapshot"]
            copied = snapshots / Path(entry["snapshot"]).name
            shutil.copyfile(source, copied)
            entry["snapshot"] = f"snapshots/{copied.name}"
            entry["sha256"] = hashlib.sha256(copied.read_bytes()).hexdigest()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "retrieved_at": original["retrieved_at"],
                        "provider": original["provider"],
                        "sources": [entry],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(verify_manifest(manifest_path), [])


if __name__ == "__main__":
    unittest.main()

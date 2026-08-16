from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from private_source_inventory import (  # noqa: E402
    DEFAULT_MANIFEST,
    build_payload,
    load_inventory,
    verify_inventory,
)


class PrivateSourceInventoryTests(unittest.TestCase):
    def test_repository_inventory_metadata_is_valid(self) -> None:
        inventory = load_inventory(DEFAULT_MANIFEST)
        self.assertEqual(len(inventory), 1300)

    def test_build_and_verify_detects_local_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "private"
            image = source_root / "1과목" / "Part 1" / "page_0001.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"test-jpeg-payload")
            manifest_path = source_root / "inventory.json"
            manifest_path.write_text(
                json.dumps(build_payload(source_root), ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual(verify_inventory(manifest_path, source_root), ([], True))
            image.write_bytes(b"tampered")
            errors, checked_local = verify_inventory(manifest_path, source_root)

        self.assertTrue(checked_local)
        self.assertTrue(any("크기 불일치" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

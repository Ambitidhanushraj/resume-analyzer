import hashlib
import tempfile
import unittest
from pathlib import Path

from backend.evaluate import _example_source
from backend.tests.test_analysis import pdf_bytes


class CorpusSourceTests(unittest.TestCase):
    def test_changed_original_uses_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "original.pdf").write_bytes(pdf_bytes("Changed source"))
            (root / "snapshot.txt").write_text("Reviewed source")
            example = {
                "path": "original.pdf", "text_path": "snapshot.txt",
                "text_sha256": hashlib.sha256(b"Reviewed source").hexdigest(),
            }
            self.assertEqual(_example_source(example, root / "manifest.json"),
                             ("cached_text", "Reviewed source"))

    def test_missing_original_and_changed_snapshot_are_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "snapshot.txt").write_text("Changed source")
            example = {
                "path": "missing.pdf", "text_path": "snapshot.txt",
                "text_sha256": hashlib.sha256(b"Reviewed source").hexdigest(),
            }
            self.assertEqual(_example_source(example, root / "manifest.json"),
                             ("unavailable", None))

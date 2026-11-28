"""Acceptance guards must fail when a bad implementation hides its own effects."""
from pathlib import Path
import tempfile
import unittest

from rdc_operator import adapters
from scripts.smoke_recovery import ReadOnlyGuard


class RecoverySmokeGuardTests(unittest.TestCase):
    def test_swallowed_same_byte_write_is_still_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rdc-smoke-guard-") as tmp:
            path = Path(tmp) / "owned.txt"
            path.write_bytes(b"unchanged")
            guard = ReadOnlyGuard()

            def mutation():
                try:
                    path.write_bytes(b"unchanged")
                except RuntimeError:
                    pass
                return {"status": "review_required"}

            with self.assertRaises(RuntimeError):
                guard.assess(mutation)
            self.assertEqual(guard.attempts, ["open_write"])
            self.assertEqual(path.read_bytes(), b"unchanged")

    def test_swallowed_adapter_attempt_is_still_rejected(self):
        guard = ReadOnlyGuard()

        def mutation():
            try:
                adapters.execute("synthetic", {}, {}, Path("unused"))
            except RuntimeError:
                pass
            return {"status": "review_required"}

        with self.assertRaises(RuntimeError):
            guard.assess(mutation)
        self.assertEqual(guard.attempts, ["adapter.execute"])

    def test_real_read_is_allowed_and_empty_directory_creation_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rdc-smoke-guard-") as tmp:
            root = Path(tmp)
            path = root / "owned.txt"
            path.write_bytes(b"evidence")
            guard = ReadOnlyGuard()
            self.assertEqual(guard.assess(path.read_bytes), b"evidence")
            self.assertEqual(guard.attempts, [])
            with self.assertRaises(RuntimeError):
                guard.assess((root / "unwanted-directory").mkdir)
            self.assertFalse((root / "unwanted-directory").exists())
            self.assertEqual(guard.attempts, ["os.mkdir"])


if __name__ == "__main__":
    unittest.main()

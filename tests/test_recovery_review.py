"""Independent malformed-state regressions; isolated local files only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rdc_operator.common import KitError
from rdc_operator.recovery import assess_resume, save_checkpoint


class RecoveryIndependentReview(unittest.TestCase):
    def document(self, stop="none"):
        return {"schema_version": 1, "task_id": "review-task", "scope_sha256": "b" * 64,
                "route": {"link_id": "fixture-link", "device_id": "fixture-device",
                          "observed_utc": datetime.now(timezone.utc).isoformat()},
                "event": "same_connection", "request_ids": [], "handles": [],
                "stop_reason": stop}

    def test_json_null_checkpoint_is_corruption_not_absence(self):
        with tempfile.TemporaryDirectory(prefix="rdc-independent-") as tmp:
            state = Path(tmp).resolve() / "state"
            config = {"schema_version": 1}
            save_checkpoint(self.document("quota"), config, state, expected_revision=0)
            saved = state / "checkpoints/review-task.json"
            saved.write_text("null\n", encoding="utf-8")
            corrupted = saved.read_bytes()
            with self.assertRaises(KitError) as caught:
                save_checkpoint(self.document(), config, state, expected_revision=0)
            self.assertEqual(caught.exception.code, "invalid_checkpoint")
            self.assertEqual(saved.read_bytes(), corrupted)

    def test_nul_state_path_has_structured_error(self):
        doc = self.document()
        context = {key: doc[key] for key in
                   ("schema_version", "scope_sha256", "route", "event", "stop_reason")}
        for operation in (
                lambda: save_checkpoint(doc, {"schema_version": 1}, Path("bad\0state"), expected_revision=0),
                lambda: assess_resume("review-task", context, {"schema_version": 1}, Path("bad\0state"))):
            with self.subTest(operation=operation), self.assertRaises(KitError):
                operation()

    def test_readback_failure_after_commit_is_uncertain_and_retains_revision(self):
        with tempfile.TemporaryDirectory(prefix="rdc-postcommit-") as tmp:
            state = Path(tmp).resolve() / "state"
            config = {"schema_version": 1}
            save_checkpoint(self.document(), config, state, expected_revision=0)
            with mock.patch("rdc_operator.recovery._bundle", side_effect=KitError(
                    "checkpoint_unreadable", "Synthetic post-commit read failure")):
                with self.assertRaises(KitError) as caught:
                    save_checkpoint(self.document(), config, state, expected_revision=1)
            self.assertTrue(caught.exception.uncertain)
            self.assertEqual(caught.exception.code, "checkpoint_commit_unconfirmed")
            persisted = json.loads((state / "checkpoints/review-task.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["revision"], 2)
            with self.assertRaises(KitError) as retry:
                save_checkpoint(self.document(), config, state, expected_revision=1)
            self.assertEqual(retry.exception.code, "checkpoint_conflict")


if __name__ == "__main__":
    unittest.main()

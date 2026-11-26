"""Focus must stay explicit, bound, observed and non-replaying."""
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch

from rdc_operator import adapters
from rdc_operator.common import KitError, atomic_json
from rdc_operator.core import execute_request


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.config = {"schema_version": 1, "allowed_roots": [str(self.root)],
                       "winapp": ["fixture-winapp"], "observation_ttl_seconds": 120}
        self.identity = {"window": 123, "pid": 7, "thread_id": 8,
                         "process_started": "111", "executable": "c:\\owned-fixture.exe"}
        self.record = {"schema_version": 1, "observation_id": "obs-fixture",
                       "observed_at": time.time(), "window": 123, "identity": self.identity,
                       "selectors": {}, "winapp": self.config["winapp"]}
        atomic_json(self.state / "observations" / "obs-fixture.json", self.record)
        self.request = {"request_id": "focus-once", "action": "desktop.focus",
                        "args": {"observation_id": "obs-fixture"}}
        self.reply = {"exit_code": 0, "stdout_json": {"elementId": "", "hwnd": 123},
                      "timed_out": False, "output_truncated": False}
        self.observed = {"status": "observed", "identity": self.identity,
                         "observation_id": "obs-new"}
        root = patch.object(adapters, "_root_window", return_value=123)
        self.root_query = root.start()
        self.addCleanup(root.stop)

    def test_focus_requires_apply_and_rejects_unscoped_fields(self):
        with patch.object(adapters, "_winapp") as run:
            with self.assertRaises(KitError) as err:
                execute_request(self.request, self.config, self.state)
            self.assertEqual(err.exception.code, "apply_required")
            for extra in ({"window": 456}, {"selector": "unobserved"}, {"force": True}):
                request = {**self.request, "args": {**self.request["args"], **extra}}
                with self.assertRaises(KitError) as err:
                    execute_request(request, self.config, self.state, apply=True)
                self.assertEqual(err.exception.code, "invalid_arguments")
            run.assert_not_called()

    def test_verified_focus_is_explicit_once_and_replay_is_observation_only(self):
        with patch.object(adapters, "_window_identity", return_value=self.identity), \
             patch.object(adapters, "_winapp", return_value=self.reply) as run, \
             patch.object(adapters, "_capture_observation", return_value=self.observed), \
             patch.object(adapters, "_foreground_window", return_value=123):
            first = execute_request(self.request, self.config, self.state, apply=True)
            replay = execute_request(self.request, self.config, self.state)
        self.assertEqual(first["status"], "completed")
        self.assertTrue(first["result"]["verification"]["focus_effect_verified"])
        self.assertFalse(first["result"]["verification"]["application_effect_verified"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[1], ["focus", "-w", "123"])

    def test_foreground_change_after_ack_is_unknown_without_retry(self):
        with patch.object(adapters, "_window_identity", return_value=self.identity), \
             patch.object(adapters, "_winapp", return_value=self.reply) as run, \
             patch.object(adapters, "_capture_observation", return_value=self.observed), \
             patch.object(adapters, "_foreground_window", return_value=456):
            result = execute_request(self.request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertFalse(result["result"]["verification"]["focus_effect_verified"])
        self.assertEqual(run.call_count, 1)

    def test_focus_refusal_may_have_restored_window_so_is_not_pre_effect(self):
        refused = {**self.reply, "exit_code": 1,
                   "stderr_json": {"error": {"code": "foreground_not_target"}}}
        with patch.object(adapters, "_window_identity", return_value=self.identity), \
             patch.object(adapters, "_winapp", return_value=refused) as run:
            result = execute_request(self.request, self.config, self.state, apply=True)
            replay = execute_request(self.request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertEqual(result["result"]["code"], "foreground_not_target")
        self.assertTrue(replay["replayed"])
        self.assertEqual(run.call_count, 1)

    def test_changed_identity_does_not_get_focused(self):
        with patch.object(adapters, "_window_identity", return_value={**self.identity, "process_started": "222"}), \
             patch.object(adapters, "_winapp") as run:
            result = execute_request(self.request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["result"]["error"]["code"], "target_changed")
        run.assert_not_called()

    def test_reparented_window_with_same_process_identity_does_not_focus_parent(self):
        self.root_query.return_value = 456
        with patch.object(adapters, "_window_identity", return_value=self.identity), \
             patch.object(adapters, "_winapp") as run:
            result = execute_request(self.request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["result"]["error"]["code"], "top_level_target_required")
        run.assert_not_called()

    def test_wrong_hwnd_ack_is_unknown_and_does_not_trigger_post_actions(self):
        with patch.object(adapters, "_window_identity", return_value=self.identity), \
             patch.object(adapters, "_winapp", return_value={**self.reply, "stdout_json": {"elementId": "", "hwnd": 456}}), \
             patch.object(adapters, "_capture_observation") as observe:
            result = execute_request(self.request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertEqual(result["result"]["code"], "invalid_action_acknowledgement")
        observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()

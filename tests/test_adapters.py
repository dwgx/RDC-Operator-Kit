import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from rdc_operator import adapters as a
from rdc_operator.common import KitError, atomic_json, read_json


def result(payload=None, stderr="", exit_code=0, **changes):
    value = {"argv": [], "stdout": json.dumps(payload) if payload is not None else "",
             "stderr": stderr, "stdout_json": payload, "stderr_json": None,
             "exit_code": exit_code, "timed_out": False, "output_truncated": False}
    value.update(changes)
    return value


def screen(stderr="# alive=True\n"):
    return result({"size": {"rows": 24, "cols": 80}, "lines": [{"row": 0, "text": ">>> "}],
                   "io": {"local_cut": "drained"}}, stderr)


def binding(canonical="txt-input-a123", **changes):
    element = {"selector": canonical, "type": "Edit", "name": "Fixture input",
               "isEnabled": True, "isOffscreen": False, **changes}
    return result({"elementId": canonical, "element": element, "properties": {}})


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.config = {"schema_version": 1, "allowed_roots": [str(self.root)],
                       "smartcli": [sys.executable], "winapp": [sys.executable],
                       "observation_ttl_seconds": 120}
        self.identity = {"window": 123, "pid": 7, "thread_id": 8,
                         "process_started": "111", "executable": "c:\\fixture.exe"}

    def session(self, phase="active"):
        record = {"session": "fixture", "upstream_session": "rdck-" + "a" * 32,
                  "phase": phase, "smartcli": [sys.executable]}
        atomic_json(self.state / "sessions" / "fixture.json", record)
        return record

    def observation(self, observed_at=None):
        record = {"schema_version": 1, "observation_id": "obs-fixture",
                  "observed_at": time.time() if observed_at is None else observed_at,
                  "window": 123, "identity": self.identity, "winapp": [sys.executable],
                  "selectors": {"txt-input-a123": {"isEnabled": True, "isOffscreen": False}}}
        atomic_json(self.state / "observations" / "obs-fixture.json", record)
        return record

    def test_unknown_fields_do_not_start_a_program(self):
        with patch.object(a, "run_command") as run, self.assertRaises(KitError):
            a.execute("terminal.start", {"session": "fixture", "command": "echo test", "cwd": str(self.root), "force": True}, self.config, self.state)
        run.assert_not_called()

    def test_windows_quoted_executable_is_refused_before_daemon_start(self):
        for command in ('"C:/space path/python.exe" -i', "'C:/space path/python.exe' -i"):
            with patch.object(a.os, "name", "nt"), patch.object(a, "run_command") as run, self.assertRaises(KitError) as err:
                a.execute("terminal.start", {"session": "fixture", "command": command, "cwd": str(self.root)}, self.config, self.state)
            self.assertEqual(err.exception.code, "unsupported_command_quoting")
            run.assert_not_called()

    def test_start_records_custody_before_timeout(self):
        def timeout(argv, **kwargs):
            record = read_json(self.state / "sessions" / "fixture.json")
            self.assertEqual(record["phase"], "starting")
            self.assertIn(record["upstream_session"], argv)
            return result(timed_out=True, exit_code=-1)
        with patch.object(a, "run_command", side_effect=timeout):
            answer = a.execute("terminal.start", {"session": "fixture", "command": "echo test", "cwd": str(self.root)}, self.config, self.state)
        self.assertEqual(answer["status"], "outcome_unknown")
        self.assertEqual(read_json(self.state / "sessions" / "fixture.json")["phase"], "outcome_unknown")

    def test_start_bad_post_observation_remains_unknown(self):
        def respond(argv, **kwargs):
            if "start" in argv:
                sid = argv[argv.index("--id") + 1]
                return result({"ok": True, "sid": sid})
            return result({"unexpected": "shape"})
        with patch.object(a, "run_command", side_effect=respond):
            answer = a.execute("terminal.start", {"session": "fixture", "command": "echo test", "cwd": str(self.root)}, self.config, self.state)
        self.assertEqual(answer["status"], "outcome_unknown")

    def test_send_uses_stdin_and_does_not_claim_application_effect(self):
        self.session()
        text = '/model 中文 "quoted"\nsecond line'
        with patch.object(a, "run_command", side_effect=[result(), screen()]) as run:
            answer = a.execute("terminal.send_text", {"session": "fixture", "text": text, "newline": True}, self.config, self.state)
        sent = run.call_args_list[0]
        self.assertEqual(sent.kwargs["text"], text)
        self.assertIn("--stdin", sent.args[0])
        self.assertNotIn(text, sent.args[0])
        self.assertEqual(answer["status"], "completed")
        self.assertFalse(answer["verification"]["application_effect_verified"])

    def test_trailing_newline_is_not_silently_stripped(self):
        self.session()
        with patch.object(a, "run_command") as run, self.assertRaises(KitError) as err:
            a.execute("terminal.send_text", {"session": "fixture", "text": "must-preserve\n"}, self.config, self.state)
        self.assertEqual(err.exception.code, "unsupported_text")
        run.assert_not_called()

    def test_wait_exit_zero_but_no_match_is_not_success(self):
        self.session()
        with patch.object(a, "run_command", return_value=screen("# matched=False exited=False alive=True\n")):
            answer = a.execute("terminal.wait", {"session": "fixture", "pattern": "not-here", "timeout_ms": 20}, self.config, self.state)
        self.assertEqual(answer["status"], "failed")
        self.assertFalse(answer["condition_met"])

    def test_stable_without_drained_io_is_not_success(self):
        self.session()
        raw = screen("# reason=STABLE exited=False alive=True\n")
        raw["stdout_json"]["io"]["local_cut"] = "unknown"
        with patch.object(a, "run_command", return_value=raw):
            answer = a.execute("terminal.wait", {"session": "fixture"}, self.config, self.state)
        self.assertFalse(answer["condition_met"])

    def test_close_ack_does_not_destroy_ownership_or_claim_exit(self):
        record = self.session()
        with patch.object(a, "run_command", return_value=result({"ok": True, "closed": True, "sid": record["upstream_session"]})):
            answer = a.execute("terminal.close", {"session": "fixture"}, self.config, self.state)
        self.assertTrue(answer["close_acknowledged"])
        self.assertEqual(answer["status"], "outcome_unknown")
        self.assertFalse(answer["verification"]["child_exit_confirmed"])
        self.assertTrue((self.state / "sessions" / "fixture.json").exists())

    def test_stale_future_and_nan_observation_are_refused(self):
        for timestamp in (time.time() - 500, time.time() + 500, float("nan")):
            record = self.observation()
            record["observed_at"] = timestamp
            # Deliberately emulate corrupt external JSON; atomic_json disallows NaN.
            path = self.state / "observations" / "obs-fixture.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            with patch.object(a, "run_command") as run, self.assertRaises(KitError):
                a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
            run.assert_not_called()

    def test_reused_pid_does_not_receive_input(self):
        self.observation()
        changed = {**self.identity, "process_started": "222"}
        with patch.object(a, "_window_identity", return_value=changed), patch.object(a, "run_command") as run, self.assertRaises(KitError) as err:
            a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
        self.assertEqual(err.exception.code, "target_changed")
        run.assert_not_called()

    def test_browser_process_is_routed_away(self):
        for executable in ("C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe", "chrome", "FIREFOX.EXE"):
            with self.assertRaises(KitError) as err:
                a._reject_browser(executable)
            self.assertEqual(err.exception.code, "browser_surface_required")

    def test_set_value_zero_exit_with_wrong_value_is_unknown(self):
        self.observation()
        with patch.object(a, "_window_identity", return_value=self.identity), \
             patch.object(a, "_winapp", side_effect=[binding(), result({"elementId": "txt-input-a123", "hwnd": 123}), result({"text": "wrong"})]), \
             patch.object(a, "_capture_observation", return_value={"status": "observed", "identity": self.identity}):
            answer = a.execute("desktop.set_value", {"observation_id": "obs-fixture", "selector": "txt-input-a123", "value": "expected"}, self.config, self.state)
        self.assertEqual(answer["status"], "outcome_unknown")
        self.assertFalse(answer["verification"]["application_effect_verified"])

    def test_malformed_success_ack_is_not_hidden_by_post_inspect(self):
        self.observation()
        with patch.object(a, "_window_identity", return_value=self.identity), \
             patch.object(a, "_winapp", side_effect=[binding(), result({"foo": "bar"})]), \
             patch.object(a, "_capture_observation", return_value={"status": "observed"}) as observed:
            answer = a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
        self.assertEqual(answer["status"], "outcome_unknown")
        self.assertFalse(answer["verification"]["action_acknowledged"])
        observed.assert_not_called()

    def test_invoke_cannot_silently_fall_back_to_an_ancestor(self):
        self.observation()
        ack = {"elementId": "other-ancestor", "hwnd": 123, "pattern": "InvokePattern",
               "requestedAction": "invoke", "performedAction": "invoke"}
        with patch.object(a, "_window_identity", return_value=self.identity), \
             patch.object(a, "_winapp", side_effect=[binding(), result(ack)]) as call:
            answer = a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
        self.assertIn("--action", call.call_args.args[1])
        self.assertEqual(answer["status"], "outcome_unknown")

    def test_automation_id_is_bound_before_using_canonical_action_ack(self):
        record = self.observation()
        record["selectors"] = {"FixtureInput": {"type": "Edit", "name": "Fixture input",
                                                   "isEnabled": True, "isOffscreen": False}}
        atomic_json(self.state / "observations" / "obs-fixture.json", record)
        with patch.object(a, "_window_identity", return_value=self.identity), \
             patch.object(a, "_winapp", side_effect=[binding(),
                 result({"elementId": "txt-input-a123", "hwnd": 123}),
                 result({"elementId": "txt-input-a123", "text": "expected"})]) as call, \
             patch.object(a, "_capture_observation", return_value={"status": "observed", "identity": self.identity}):
            answer = a.execute("desktop.set_value", {"observation_id": "obs-fixture", "selector": "FixtureInput", "value": "expected"}, self.config, self.state)
        self.assertEqual(call.call_args_list[0].args[1], ["get-property", "FixtureInput", "-w", "123"])
        self.assertEqual(call.call_args_list[1].args[1], ["set-value", "txt-input-a123", "expected", "-w", "123"])
        self.assertEqual(call.call_args_list[2].args[1], ["get-value", "txt-input-a123", "-w", "123"])
        self.assertEqual(answer["status"], "completed")
        self.assertTrue(answer["verification"]["application_effect_verified"])

    def test_bad_canonical_binding_cannot_mutate(self):
        record = self.observation()
        record["selectors"]["txt-input-a123"]["type"] = "Edit"
        atomic_json(self.state / "observations" / "obs-fixture.json", record)
        malformed = binding()
        malformed["stdout_json"]["element"]["selector"] = "different"
        for response in (result({"elementId": "txt-input-a123"}), malformed, binding(type="Button")):
            with patch.object(a, "_window_identity", return_value=self.identity), \
                 patch.object(a, "_winapp", return_value=response) as call, self.assertRaises(KitError):
                a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.args[1][0], "get-property")

    def test_window_identity_change_during_read_cannot_mutate(self):
        self.observation()
        changed = {**self.identity, "process_started": "222"}
        with patch.object(a, "_window_identity", side_effect=[self.identity, changed]), \
             patch.object(a, "_winapp", return_value=binding()) as call, self.assertRaises(KitError) as err:
            a.execute("desktop.invoke", {"observation_id": "obs-fixture", "selector": "txt-input-a123"}, self.config, self.state)
        self.assertEqual(err.exception.code, "target_changed")
        self.assertEqual(call.call_count, 1)

    def test_reused_window_in_post_observation_is_unknown(self):
        self.observation()
        changed = {**self.identity, "process_started": "222"}
        with patch.object(a, "_window_identity", return_value=self.identity), \
             patch.object(a, "_winapp", side_effect=[binding(),
                 result({"elementId": "txt-input-a123", "hwnd": 123}),
                 result({"elementId": "txt-input-a123", "text": "expected"})]), \
             patch.object(a, "_capture_observation", return_value={"status": "observed", "identity": changed}):
            answer = a.execute("desktop.set_value", {"observation_id": "obs-fixture", "selector": "txt-input-a123", "value": "expected"}, self.config, self.state)
        self.assertEqual(answer["status"], "outcome_unknown")
        self.assertFalse(answer["verification"]["application_effect_verified"])
        self.assertFalse(answer["verification"]["window_identity_checked_after_action"])

    def test_key_object_and_flag_pattern_are_validation_errors(self):
        self.session()
        for action, args in (("terminal.send_key", {"session": "fixture", "key": []}),
                             ("terminal.wait", {"session": "fixture", "pattern": "--help"})):
            with self.assertRaises(KitError):
                a.validate(action, args, self.config, self.state)

    def test_duplicate_selector_is_rejected(self):
        tree = {"windows": [{"hwnd": 123, "elements": [{"selector": "same"}, {"selector": "same"}]}]}
        with self.assertRaises(KitError) as err:
            a._selectors(tree, 123)
        self.assertEqual(err.exception.code, "ambiguous_selector")

    def test_state_subdir_symlink_cannot_redirect_custody(self):
        self.state.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.state / "sessions").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError) as err:
            a.validate("terminal.start", {"session": "fixture", "command": "echo test", "cwd": str(self.root)}, self.config, self.state)
        self.assertEqual(err.exception.code, "unsafe_state")


if __name__ == "__main__":
    unittest.main()

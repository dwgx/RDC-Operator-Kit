"""Independent engine acceptance tests; no SmartCLI, GUI, browser, or model calls.

The injected operations are local Python fixtures. One test starts a second
Python fixture process to verify the advertised cross-process state lock.
"""

from __future__ import annotations

import copy
import json
import multiprocessing
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rdc_operator import common
from rdc_operator.common import KitError
from rdc_operator.core import execute_request


class SimulatedCrash(BaseException):
    """Not an ordinary adapter error: unwind without manufacturing a result."""


def _hold_state_lock(request, config, state, entered, release, result_queue):
    """A test-only child; it never launches an application or uses the network."""
    try:
        def hold(*args, **kwargs):
            entered.set()
            if not release.wait(15):
                raise RuntimeError("test fixture release timed out")
            return {"status": "completed", "fixture": "lock-owner"}

        result = execute_request(
            request, config, Path(state), apply=True, operation=hold
        )
        result_queue.put(("ok", result.get("status")))
    except BaseException as error:
        result_queue.put(("error", type(error).__name__, str(error)))


class EngineAcceptanceReview(unittest.TestCase):
    """Exercise externally observable contract properties, not helper internals."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-review-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = self.root / "owned workspace 中文"
        self.cwd.mkdir()
        self.state = self.root / "state"
        self.config = {
            "schema_version": 1,
            "allowed_roots": [str(self.root)],
            "smartcli": [sys.executable],
            "winapp": [sys.executable],
            "observation_ttl_seconds": 120,
        }
        self.request = {
            "request_id": "review-request-1",
            "action": "terminal.start",
            "args": {
                "session": "review-session",
                "command": "fixture-only-never-executed",
                "cwd": str(self.cwd),
            },
        }

    def execute(self, *, request=None, config=None, operation=None, apply=True):
        return execute_request(
            copy.deepcopy(self.request if request is None else request),
            copy.deepcopy(self.config if config is None else config),
            self.state,
            apply=apply,
            operation=operation,
        )

    def assert_conflict(self, call):
        with self.assertRaises(KitError) as error:
            call()
        self.assertIn("conflict", error.exception.code)

    def test_same_request_is_replayed_without_second_effect(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append("happened")
            return {"status": "completed", "fixture_value": "exact-value"}

        first = self.execute(operation=operation)
        second = self.execute(operation=operation)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], first["status"])
        self.assertIs(second.get("replayed"), True)
        self.assertEqual(effects, ["happened"])

    def test_same_semantics_with_reordered_json_keys_is_replay(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        self.execute(operation=operation)
        reordered = {
            "args": dict(reversed(list(self.request["args"].items()))),
            "action": self.request["action"],
            "request_id": self.request["request_id"],
        }
        receipt = self.execute(request=reordered, operation=operation)
        self.assertIs(receipt.get("replayed"), True)
        self.assertEqual(effects, [1])

    def test_same_id_changed_payload_is_conflict(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        self.execute(operation=operation)
        changed = copy.deepcopy(self.request)
        changed["args"]["command"] = "different-command"
        self.assert_conflict(
            lambda: self.execute(request=changed, operation=operation)
        )
        self.assertEqual(effects, [1])

    def test_same_id_changed_effective_config_is_conflict(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        self.execute(operation=operation)
        changed = copy.deepcopy(self.config)
        changed["smartcli"] = [sys.executable, "--different-prefix"]
        self.assert_conflict(
            lambda: self.execute(config=changed, operation=operation)
        )
        self.assertEqual(effects, [1])

    def test_missing_apply_has_no_effect_and_does_not_reserve_request(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        with self.assertRaises(KitError):
            self.execute(operation=operation, apply=False)
        self.assertEqual(effects, [])
        receipt = self.execute(operation=operation, apply=True)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(effects, [1])

    def test_completed_result_can_be_read_without_reapplying(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        self.execute(operation=operation)
        receipt = self.execute(operation=operation, apply=False)
        self.assertIs(receipt.get("replayed"), True)
        self.assertEqual(effects, [1])

    def test_known_failed_result_is_not_automatically_executed_again(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "failed", "reason": "fixture-known-failure"}

        first = self.execute(operation=operation)
        second = self.execute(operation=operation)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(second["status"], "failed")
        self.assertIs(second.get("replayed"), True)
        self.assertEqual(effects, [1])

    def test_uncertain_adapter_result_is_never_reexecuted(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "outcome_unknown", "reason": "response-lost"}

        first = self.execute(operation=operation)
        self.assertEqual(first["status"], "outcome_unknown")
        try:
            second = self.execute(operation=operation)
        except KitError as error:
            self.assertTrue(error.uncertain)
        else:
            self.assertEqual(second["status"], "outcome_unknown")
            self.assertIs(second.get("replayed"), True)
        self.assertEqual(effects, [1])

    def test_crash_after_effect_preserves_intent_and_blocks_reexecution(self):
        marker = self.cwd / "effect-count.txt"

        def crash(*args, **kwargs):
            marker.write_text("one-effect\n", encoding="utf-8")
            raise SimulatedCrash("after effect, before completed receipt")

        with self.assertRaises(SimulatedCrash):
            self.execute(operation=crash)

        def forbidden_second_effect(*args, **kwargs):
            with marker.open("a", encoding="utf-8") as output:
                output.write("second-effect\n")
            return {"status": "completed"}

        with self.assertRaises(KitError) as error:
            self.execute(operation=forbidden_second_effect)
        self.assertTrue(error.exception.uncertain)
        self.assertEqual(marker.read_text(encoding="utf-8"), "one-effect\n")

    def test_unexpected_adapter_exception_is_uncertain_and_not_retried(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            raise RuntimeError("fixture lost its upstream response")

        try:
            first = self.execute(operation=operation)
        except KitError as error:
            self.assertTrue(error.uncertain)
        else:
            self.assertEqual(first["status"], "outcome_unknown")
        try:
            second = self.execute(operation=operation)
        except KitError as error:
            self.assertTrue(error.uncertain)
        else:
            self.assertEqual(second["status"], "outcome_unknown")
            self.assertIs(second.get("replayed"), True)
        self.assertEqual(effects, [1])

    def test_invalid_adapter_status_cannot_become_success(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "MAGIC_SUCCESS"}

        try:
            receipt = self.execute(operation=operation)
        except KitError:
            pass
        else:
            self.assertIn(receipt["status"], {"failed", "outcome_unknown"})
        try:
            replay = self.execute(operation=operation)
        except KitError:
            pass
        else:
            self.assertIn(replay["status"], {"failed", "outcome_unknown"})
        self.assertEqual(effects, [1])

    def test_distinct_request_ids_have_independent_results(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed", "sequence": len(effects)}

        first = self.execute(operation=operation)
        distinct = copy.deepcopy(self.request)
        distinct["request_id"] = "review-request-2"
        distinct["args"]["session"] = "review-session-2"
        second = self.execute(request=distinct, operation=operation)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "completed")
        self.assertFalse(second.get("replayed", False))
        self.assertEqual(effects, [1, 1])

    def test_corrupted_existing_receipt_is_uncertain_and_never_reexecutes(self):
        effects = []

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        self.execute(operation=operation)
        receipt_path = self.state / "requests" / "review-request-1.receipt.json"
        receipt_path.write_text('{"status":', encoding="utf-8")
        with self.assertRaises(KitError) as error:
            self.execute(operation=operation)
        self.assertTrue(error.exception.uncertain,
                        "A damaged execution record cannot prove no effect")
        self.assertEqual(effects, [1])

    def test_receipt_commit_failure_leaves_intent_and_never_reexecutes(self):
        effects = []
        real_atomic_json = common.atomic_json

        def fail_receipt(path, value):
            if Path(path).name.endswith(".receipt.json"):
                raise OSError("fixture storage failure after effect")
            return real_atomic_json(path, value)

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        with patch("rdc_operator.core.atomic_json", side_effect=fail_receipt):
            with self.assertRaises((OSError, KitError)):
                self.execute(operation=operation)
        with self.assertRaises(KitError) as error:
            self.execute(operation=operation)
        self.assertTrue(error.exception.uncertain)
        self.assertEqual(effects, [1])

    def test_unknown_action_is_rejected_before_effect(self):
        effects = []
        request = copy.deepcopy(self.request)
        request["action"] = "terminal.not-a-supported-action"

        def operation(*args, **kwargs):
            effects.append(1)
            return {"status": "completed"}

        with self.assertRaises(KitError):
            self.execute(request=request, operation=operation)
        self.assertEqual(effects, [])

    def test_cross_process_state_lock_rejects_competing_effect(self):
        context = multiprocessing.get_context("spawn")
        entered = context.Event()
        release = context.Event()
        result_queue = context.Queue()
        process = context.Process(
            target=_hold_state_lock,
            args=(self.request, self.config, str(self.state), entered, release,
                  result_queue),
        )
        process.start()
        effects = []
        try:
            self.assertTrue(entered.wait(12), "fixture never entered operation")
            other = copy.deepcopy(self.request)
            other["request_id"] = "review-competing-request"
            other["args"]["session"] = "review-competing-session"

            def competing(*args, **kwargs):
                effects.append(1)
                return {"status": "completed"}

            with self.assertRaises(KitError) as error:
                self.execute(request=other, operation=competing)
            self.assertIn("busy", error.exception.code)
            self.assertEqual(effects, [])
        finally:
            release.set()
            process.join(12)
            if process.is_alive():
                process.terminate()
                process.join(5)
        self.assertEqual(process.exitcode, 0)
        self.assertEqual(result_queue.get(timeout=2), ("ok", "completed"))
        result_queue.close()
        result_queue.join_thread()


class CommandCleanupReview(unittest.TestCase):
    def test_winapp_does_not_inherit_an_unrelated_workflow_id(self):
        from rdc_operator import adapters

        captured = []

        class CompletedChild:
            returncode = 0

            def poll(self):
                return 0

        def spawn(*args, **kwargs):
            captured.append(kwargs["env"])
            return CompletedChild()

        with patch.dict("os.environ", {"WINAPP_UI_WORKFLOW_ID": "foreign-workflow",
                                       "RDC_REVIEW_ENV_MARKER": "preserved"}):
            with patch("rdc_operator.common.subprocess.Popen", side_effect=spawn):
                adapters._winapp(["fixture-never-launched"], ["status", "-w", "1"])
        self.assertEqual(len(captured), 1)
        self.assertNotIn("WINAPP_UI_WORKFLOW_ID", captured[0])
        self.assertEqual(captured[0]["RDC_REVIEW_ENV_MARKER"], "preserved")

    def test_interruption_reaps_only_the_owned_direct_child(self):
        class OwnedChild:
            returncode = None
            stopped = False
            waited = False
            interrupted = False

            def poll(self):
                if not self.interrupted:
                    self.interrupted = True
                    raise KeyboardInterrupt("fixture interrupt during command")
                return self.returncode

            def kill(self):
                self.stopped = True
                self.returncode = -9

            def terminate(self):
                self.stopped = True
                self.returncode = -15

            def wait(self, timeout=None):
                self.waited = True
                return self.returncode

        child = OwnedChild()
        with patch("rdc_operator.common.subprocess.Popen", return_value=child):
            with self.assertRaises(KeyboardInterrupt):
                common.run_command(["fixture-never-launched"], timeout=2)
        self.assertTrue(child.stopped,
                        "Releasing the state lock with a live child permits overlapping effects")
        self.assertTrue(child.waited, "Owned child must be reaped before returning")


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"),
                     "These fixtures exercise the Linux installer with bash")
class LinuxInstallerBoundaryReview(unittest.TestCase):
    """No pip install is performed: both cases must reject before that point."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-install-review-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "source with spaces 中文"
        scripts = self.root / "scripts"
        scripts.mkdir(parents=True)
        source = Path(__file__).resolve().parents[1] / "scripts" / "install.sh"
        self.script = scripts / "install.sh"
        shutil.copyfile(source, self.script)

    def run_installer(self):
        env = dict(os.environ)
        env["RDC_PYTHON"] = sys.executable
        return subprocess.run([shutil.which("bash"), str(self.script)],
                              env=env, capture_output=True, text=True, timeout=15)

    def test_unowned_existing_environment_is_preserved_and_rejected(self):
        venv = self.root / ".venv"
        venv.mkdir()
        sentinel = venv / "existing-owner.txt"
        sentinel.write_text("preserve-me", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve-me")
        self.assertFalse((self.root / ".rdc-install.json").exists())

    def test_owned_marker_does_not_authorize_a_linked_other_environment(self):
        foreign = self.base / "unrelated-fixture-environment"
        binary = foreign / "bin" / "python"
        binary.parent.mkdir(parents=True)
        executed = self.base / "foreign-interpreter-was-executed"
        binary.write_text("#!/bin/sh\n: > " + shlex.quote(str(executed)) +
                          "\nexit 0\n", encoding="utf-8")
        binary.chmod(0o700)
        (self.root / ".venv").symlink_to(foreign, target_is_directory=True)
        (self.root / ".rdc-install.json").write_text(json.dumps({
            "project": "rdc-operator-kit", "install_root": str(self.root),
            "schema_version": 1,
        }), encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0,
                            "A matching marker must not adopt a linked environment")
        self.assertFalse(executed.exists(),
                         "Installer executed a Python outside its owned environment")


if __name__ == "__main__":
    unittest.main()

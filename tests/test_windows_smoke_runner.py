"""Behavioral tests of the suite runner, without operating a Windows desktop."""
from argparse import Namespace
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rdc_operator.common import KitError, read_json
from scripts import smoke_windows as smoke


class FakeProcess:
    pid = 42

    def __init__(self):
        self.returncode = None
        self.kills = 0

    def poll(self):
        return self.returncode

    def kill(self):
        self.kills += 1
        self.returncode = -1

    def wait(self, timeout):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("owned fixture", timeout)
        return self.returncode


class WindowsSmokeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.options = Namespace(output=self.root / "run", deadline_seconds=10,
            python=Path(sys.executable), powershell=Path("C:/Program Files/PowerShell/7/pwsh.exe"),
            config=self.root / "config.json", terminal_python=None, mcp_python=None)

    def runner(self, clock=lambda: 0.0):
        return smoke.WindowsSmoke(self.options, clock=clock)

    def test_failed_case_cannot_be_hidden_by_later_success(self):
        runner = self.runner()
        observed_progress = []

        def fail():
            observed_progress.append(read_json(runner.output / "summary.json")["cases"][0]["status"])
            raise RuntimeError("deliberate fixture failure")

        with redirect_stdout(io.StringIO()):
            code = runner.run([("first", "offline", fail),
                               ("second", "offline", lambda: {"status": "passed"})])
        report = read_json(runner.output / "summary.json")
        self.assertEqual(observed_progress, ["running"])
        self.assertEqual([row["status"] for row in report["cases"]], ["failed", "passed"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(code, 1)
        self.assertIn("deliberate fixture failure", report["cases"][0]["error"])

    def test_deadline_prevents_starting_later_cases_and_persists_not_run(self):
        current = [0.0]
        runner = self.runner(lambda: current[0])
        later = []

        def first():
            current[0] = 11
            return {"status": "passed"}

        with redirect_stdout(io.StringIO()):
            code = runner.run([("first", "offline", first),
                               ("second", "offline", lambda: later.append(True))])
        report = read_json(runner.output / "summary.json")
        self.assertEqual(later, [])
        self.assertEqual(report["cases"][1]["status"], "not_run")
        self.assertEqual(report["cases"][1]["reason"], "suite_deadline")
        self.assertEqual(code, 2)

    def test_interrupt_keeps_partial_report_and_stops_following_work(self):
        runner = self.runner()

        def interrupt():
            raise KeyboardInterrupt()

        with redirect_stdout(io.StringIO()):
            code = runner.run([("first", "offline", interrupt),
                               ("second", "offline", lambda: self.fail("must not run"))])
        report = read_json(runner.output / "summary.json")
        self.assertEqual([row["status"] for row in report["cases"]], ["interrupted", "not_run"])
        self.assertEqual(report["halt_reason"], "operator_interrupt")
        self.assertEqual(code, 1)

    def test_missing_optional_mcp_is_skipped_and_never_reported_as_all_pass(self):
        runner = self.runner()
        with redirect_stdout(io.StringIO()):
            code = runner.run([("mcp", "real_owned_fixture", runner.mcp)])
        report = read_json(runner.output / "summary.json")
        self.assertEqual(report["cases"][0]["status"], "skipped")
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(code, 2)

    def test_changed_window_is_not_closed_and_only_held_process_is_terminated(self):
        runner = self.runner()
        child = FakeProcess()
        original = {"window": 123, "pid": 42, "process_started": "old"}
        replacement = {**original, "process_started": "new"}
        with patch.object(smoke, "_window_identity", return_value=replacement), \
             patch.object(smoke, "_close_window") as close:
            result = runner.cleanup_fixture(child, original, self.root / "missing-witness.json")
        close.assert_not_called()
        self.assertEqual(child.kills, 1)
        self.assertTrue(result["direct_child_only"])
        self.assertEqual(result["possible_descendants"], "unknown")
        self.assertFalse(result["verified"])
        self.assertIsNotNone(runner.halt_reason)

    def test_redirector_pid_does_not_authorize_adopting_the_fixture(self):
        runner = self.runner()
        witness = self.root / "witness.json"
        witness.write_text('{"pid":77,"hwnd":123,"last_event":"ready"}', encoding="utf-8")
        with patch.object(smoke, "_window_identity") as query:
            with self.assertRaisesRegex(RuntimeError, "PID differs"):
                runner.wait_fixture(FakeProcess(), witness, "desktop")
        query.assert_not_called()

    def test_interrupt_during_gui_cleanup_collects_owned_child_and_keeps_receipt(self):
        runner = self.runner()
        child = FakeProcess()
        identity = {"window": 123, "pid": child.pid, "process_started": "owned"}

        def interrupt_normal_wait(timeout):
            if child.poll() is None:
                raise KeyboardInterrupt()
            return child.poll()

        child.wait = interrupt_normal_wait
        with patch.object(smoke.subprocess, "Popen", return_value=child), \
             patch.object(runner, "wait_fixture", return_value=({"hwnd": 123}, identity)), \
             patch("rdc_operator.windows.inspect_windows_context", return_value={"read_only": True}), \
             patch.object(runner, "command", return_value={"status": "passed"}), \
             patch.object(runner, "child_report", return_value={"status": "passed"}), \
             patch.object(smoke, "_window_identity", return_value=identity), \
             patch.object(smoke, "_close_window", return_value=True), \
             redirect_stdout(io.StringIO()):
            code = runner.run([("desktop", "owned_gui", lambda: runner.gui("desktop")),
                               ("later", "offline", lambda: self.fail("must stop after interrupted cleanup"))])
        report = read_json(runner.output / "summary.json")
        cleanup = report["cases"][0]["cleanup"]
        self.assertEqual(code, 1)
        self.assertEqual(child.kills, 1)
        self.assertTrue(cleanup["exited"])
        self.assertTrue(cleanup["interrupted"])
        self.assertTrue(cleanup["direct_child_only"])
        self.assertFalse(cleanup["verified"])
        self.assertEqual(report["cases"][1]["status"], "not_run")

    def test_nested_smoke_closed_window_gets_grace_for_held_process_exit(self):
        runner = self.runner()
        child = FakeProcess()
        identity = {"window": 123, "pid": child.pid, "process_started": "owned"}
        witness = self.root / "closed-witness.json"
        witness.write_text('{"pid":42,"hwnd":123,"last_event":"closed"}', encoding="utf-8")

        def finish_after_window_destruction(timeout):
            self.assertLessEqual(timeout, 2)
            child.returncode = 0
            return 0

        child.wait = finish_after_window_destruction
        with patch.object(smoke, "_window_identity", side_effect=KitError("window_not_found", "Target HWND no longer exists")), \
             patch.object(smoke, "_close_window") as close:
            result = runner.cleanup_fixture(child, identity, witness)
        close.assert_not_called()
        self.assertEqual(child.kills, 0)
        self.assertTrue(result["window_already_closed"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["forced"])
        self.assertIsNone(runner.halt_reason)

    def test_existing_output_is_not_overwritten(self):
        self.options.output.mkdir()
        marker = self.options.output / "summary.json"
        marker.write_text('{"old":"evidence"}', encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.runner()
        self.assertEqual(marker.read_text(), '{"old":"evidence"}')

    def test_failed_child_report_is_preserved_without_masking_nonzero_exit(self):
        runner = self.runner()
        report = runner.output / "child.json"
        report.write_text('{"status":"failed","checks":[{"pass":false}]}', encoding="utf-8")
        result = runner.child_report({"status": "failed", "exit_code": 1}, report, runner.output)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["child_summary"], str(report))
        self.assertEqual(result["child_status"], "failed")
        self.assertTrue(result["child_summary_available"])

    def test_timed_out_owned_process_is_collected_and_later_work_stops(self):
        self.options.deadline_seconds = 3
        runner = smoke.WindowsSmoke(self.options)
        executable = getattr(sys, "_base_executable", sys.executable)
        with redirect_stdout(io.StringIO()):
            code = runner.run([("deadline_child", "real_stdlib_fixture", lambda: runner.command(
                "deadline-child", [executable, "-u", "-c", "import time; print('owned ready', flush=True); time.sleep(10)"], timeout=.15)),
                ("later", "offline", lambda: self.fail("uncertain cleanup must stop the suite"))])
        report = read_json(runner.output / "summary.json")
        first = report["cases"][0]
        self.assertEqual(code, 1)
        self.assertEqual(first["status"], "outcome_unknown")
        self.assertTrue(first["cleanup"]["forced"])
        self.assertTrue(first["cleanup"]["exited"])
        self.assertEqual(first["cleanup"]["possible_descendants"], "unknown")
        self.assertEqual(report["cases"][1]["status"], "not_run")
        self.assertLess(report["elapsed_seconds"], 3)

    def test_core_counts_preserve_skips_and_failures(self):
        self.assertEqual(smoke.unittest_counts("Ran 105 tests in 2.1s\n\nOK (skipped=7)\n"),
                         {"run": 105, "passed": 98, "skipped": 7, "failures": 0, "errors": 0})
        result = smoke.unittest_counts("Ran 10 tests in 0.1s\n\nFAILED (failures=2, errors=1, skipped=1)\n")
        self.assertEqual(result, {"run": 10, "passed": 6, "skipped": 1, "failures": 2, "errors": 1})
        self.assertIsNone(smoke.unittest_counts("launch failed before unittest")["run"])


if __name__ == "__main__":
    unittest.main()

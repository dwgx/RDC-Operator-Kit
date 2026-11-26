"""Observable counterexamples; every process is the owned synthetic fixture."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("liveness_probe", PROJECT / "scripts" / "probe_terminal_liveness.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class LivenessTests(unittest.TestCase):
    def check_cleanup(self, result):
        self.assertTrue(result["cleanup"]["direct_child_exit_confirmed"])
        self.assertTrue(result["cleanup"]["readers_joined"])
        self.assertFalse(result["final_observation"]["alive"])
        self.assertTrue(probe.expectations(result), result)

    def test_silence_does_not_identify_compute_versus_input_wait(self):
        for case in ("silent", "silent-input"):
            with self.subTest(case=case):
                result = probe.run_case(case)
                self.assertEqual(result["classification"], "running_silent")
                observed = result["decision_observation"]
                self.assertTrue(observed["alive"])
                self.assertEqual(observed["stdout"]["bytes_read"], 0)
                self.assertEqual(observed["stderr"]["bytes_read"], 0)
                self.assertFalse(observed["waiting_input_declared"])
                self.assertLess(result["max_observation_return_latency_ms"], 250)
                self.assertLess(result["wall_time_ms"], 3000)
                self.check_cleanup(result)

    def test_declared_input_wait_continues_and_verifies_business_witness(self):
        result = probe.run_case("waiting-input")
        self.assertTrue(result["before_input"]["alive"])
        self.assertTrue(result["before_input"]["waiting_input_declared"])
        self.assertFalse(result["before_input"]["completion_marker_seen"])
        self.assertTrue(result["semantic_verified"])
        self.assertTrue(result["independent_witness_valid"])
        self.assertEqual(result["witness_verification"]["fixture_pid"],
                         result["launch_identity"]["held_process_pid"])
        self.assertEqual(result["witness_verification"]["reason"], "matched")
        self.assertEqual(result["final_observation"]["exit_code"], 0)
        self.check_cleanup(result)

    def test_flood_drains_both_streams_and_bounds_retained_payload(self):
        result = probe.run_case("flood", capture_limit=1024)
        self.assertEqual(result["classification"], "output_limit_reached")
        for name in ("stdout", "stderr"):
            stream = result["final_observation"][name]
            self.assertGreater(stream["bytes_read"], 4096)
            self.assertLessEqual(stream["bytes_retained"], 1024)
            self.assertTrue(stream["truncated"])
        self.assertFalse(result["semantic_verified"])
        self.check_cleanup(result)

    def test_deadline_is_distinct_from_no_output_and_cleanup_is_confirmed(self):
        result = probe.run_case("timeout", deadline_ms=400)
        self.assertEqual(result["classification"], "deadline_exceeded")
        self.assertTrue(result["decision_observation"]["alive"])
        self.assertGreaterEqual(result["decision_observation"]["elapsed_ms"], 400)
        self.assertLess(result["wall_time_ms"], 3000)
        self.assertFalse(result["semantic_verified"])
        self.check_cleanup(result)

    def test_exit_zero_without_business_marker_is_not_completion(self):
        result = probe.run_case("exit-no-marker")
        self.assertEqual(result["final_observation"]["exit_code"], 0)
        self.assertFalse(result["semantic_verified"])
        self.assertFalse(result["final_observation"]["completion_marker_seen"])
        self.check_cleanup(result)

    def test_ready_prompt_is_not_business_completion(self):
        result = probe.run_case("ready-only")
        self.assertTrue(result["decision_observation"]["alive"])
        self.assertTrue(result["final_observation"]["ready_marker_seen"])
        self.assertFalse(result["semantic_verified"])
        self.check_cleanup(result)

    def test_marker_requires_fresh_token_and_independent_witness(self):
        matching = probe.run_case("marker-no-witness")
        self.assertTrue(matching["final_observation"]["completion_marker_seen"])
        self.assertFalse(matching["semantic_verified"])
        stale = probe.run_case("wrong-token")
        self.assertFalse(stale["final_observation"]["completion_marker_seen"])
        self.assertFalse(stale["semantic_verified"])
        self.check_cleanup(matching)
        self.check_cleanup(stale)

    def test_cancel_uses_only_held_child_and_leaves_another_fixture_running(self):
        with tempfile.TemporaryDirectory() as directory:
            first = probe.OwnedFixture("silent", Path(directory))
            second = probe.OwnedFixture("silent", Path(directory))
            try:
                cleanup = first.finish("test_cancel_isolation")
                self.assertTrue(cleanup["direct_child_exit_confirmed"])
                self.assertTrue(second.observe()["alive"])
                self.assertFalse(cleanup["arbitrary_pid_selection"])
                self.assertEqual(first.finish("repeat"), cleanup)
            finally:
                first.finish("test_finally")
                second.finish("test_finally")

    def test_arbitrary_command_or_pid_is_not_an_attachment_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                probe.OwnedFixture("12345", Path(directory))

    def test_windows_redirector_pid_mismatch_is_rejected_without_adopting_pid(self):
        # Reproduce the observed Windows launcher's two-PID topology as evidence,
        # without starting or signalling an arbitrary PID on this test host.
        with tempfile.TemporaryDirectory() as directory:
            witness = Path(directory) / "witness.json"
            fake = SimpleNamespace(witness=witness, token="a" * 32,
                                   child=SimpleNamespace(pid=41001))
            value = {"token": fake.token, "case": "waiting-input", "value": 42,
                     "input_accepted": True, "pid": 41002}
            witness.write_text(json.dumps(value), encoding="utf-8")
            rejected = probe._witness_evidence(fake)
            self.assertEqual(rejected["reason"], "pid_mismatch")
            self.assertTrue(rejected["present"])
            self.assertFalse(probe._witness_valid(fake))
            self.assertEqual(fake.child.pid, 41001)
            value["pid"] = fake.child.pid
            witness.write_text(json.dumps(value), encoding="utf-8")
            self.assertTrue(probe._witness_valid(fake))

    def test_windows_stdlib_fixture_selects_existing_base_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            requested = Path(directory) / "venv-python.exe"
            base = Path(directory) / "base-python.exe"
            requested.touch()
            base.touch()
            with patch.object(probe.sys, "platform", "win32"), \
                 patch.object(probe.sys, "executable", str(requested)), \
                 patch.object(probe.sys, "_base_executable", str(base), create=True):
                identity = probe._fixture_interpreter()
            self.assertEqual(identity["selected_executable"], str(base.resolve()))
            self.assertEqual(identity["requested_executable"], str(requested))

    def test_windows_missing_base_executable_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(probe.sys, "platform", "win32"), \
                 patch.object(probe.sys, "_base_executable", "", create=True), \
                 patch.object(probe.subprocess, "Popen") as popen:
                with self.assertRaises(RuntimeError):
                    probe.OwnedFixture("silent", Path(directory))
                popen.assert_not_called()


class LivenessCheckpointTests(unittest.TestCase):
    def call_main(self, directory, *extra):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = probe.main(["--output-dir", str(directory), *extra])
        return code, json.loads(stream.getvalue())

    def test_launch_failure_retains_completed_real_fixture_and_stops_later_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            original = probe.run_case
            attempted = []
            def fail_second(case):
                attempted.append(case)
                if len(attempted) == 1:
                    return original(case)
                saved = json.loads(next(output.rglob("summary.json")).read_text())
                self.assertEqual(len(saved["cases"]), 1)
                self.assertTrue(saved["cases"][0]["cleanup"]["direct_child_exit_confirmed"])
                raise OSError("synthetic second fixture launch failure")
            with patch.object(probe, "CASES", ("silent", "silent-input", "wrong-token")), \
                    patch.object(probe, "run_case", fail_second):
                code, emitted = self.call_main(output)
            saved = json.loads(Path(emitted["summary"]).read_text())
            self.assertEqual(code, 1)
            self.assertEqual(attempted, ["silent", "silent-input"])
            self.assertEqual(saved["status"], "FAIL")
            self.assertEqual(len(saved["cases"]), 1)
            self.assertEqual(saved["error"]["type"], "OSError")
            self.assertEqual(saved["active_case"], "silent-input")
            self.assertIsNone(saved["incomplete_case"]["cleanup_verified"])
            self.assertTrue(emitted["summary_current"])

    def test_interrupt_retains_completed_case_and_returns_130_without_later_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = probe.run_case
            attempted = []
            def interrupt_second(case):
                attempted.append(case)
                if len(attempted) == 1:
                    return original(case)
                raise KeyboardInterrupt()
            with patch.object(probe, "CASES", ("silent", "silent-input", "wrong-token")), \
                    patch.object(probe, "run_case", interrupt_second):
                code, emitted = self.call_main(Path(temporary))
            saved = json.loads(Path(emitted["summary"]).read_text())
            self.assertEqual(code, 130)
            self.assertEqual(attempted, ["silent", "silent-input"])
            self.assertEqual(saved["status"], "FAIL")
            self.assertTrue(saved["interrupted"])
            self.assertEqual(saved["exit_code"], 130)
            self.assertEqual(len(saved["cases"]), 1)
            self.assertTrue(saved["cases"][0]["cleanup"]["direct_child_exit_confirmed"])

    def test_initial_archive_failure_does_not_launch_fixture_or_claim_saved_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe, "atomic_json", side_effect=PermissionError("synthetic denied write")) as writer, \
                    patch.object(probe, "run_case") as run:
                code, emitted = self.call_main(Path(temporary))
            self.assertEqual(code, 3)
            self.assertEqual(emitted["status"], "FAIL")
            self.assertIsNone(emitted["summary"])
            self.assertFalse(emitted["summary_current"])
            self.assertIn("PermissionError", emitted["archive_error"])
            self.assertLessEqual(writer.call_count, 2)
            run.assert_not_called()

    def test_final_archive_failure_replaces_possible_pass_with_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = probe.atomic_json
            raised = False
            def failing_after_replace(path, value):
                nonlocal raised
                original(path, value)
                if value["phase"] == "finished" and not raised:
                    raised = True
                    raise OSError("synthetic failure after final replace")
            with patch.object(probe, "atomic_json", failing_after_replace):
                code, emitted = self.call_main(Path(temporary), "--case", "exit-no-marker")
            saved = json.loads(Path(emitted["summary"]).read_text())
            self.assertEqual(code, 3)
            self.assertEqual(emitted["status"], "FAIL")
            self.assertEqual(saved["status"], "FAIL")
            self.assertEqual(saved["exit_code"], 3)
            self.assertIn("after final replace", saved["archive_error"])
            self.assertTrue(emitted["summary_current"])

    def test_successful_real_fixture_keeps_existing_pass_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            code, emitted = self.call_main(Path(temporary), "--case", "waiting-input")
            saved = json.loads(Path(emitted["summary"]).read_text())
            self.assertEqual(code, 0)
            self.assertEqual(emitted["status"], "PASS")
            self.assertEqual(saved["status"], "PASS")
            self.assertTrue(emitted["summary_current"])
            self.assertIsNone(saved["active_case"])
            self.assertTrue(saved["cases"][0]["semantic_verified"])

    def test_interrupt_after_final_replace_archives_failure_and_returns_130(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = probe.atomic_json
            interrupted = False
            def interrupt_after_replace(path, value):
                nonlocal interrupted
                original(path, value)
                if value["phase"] == "finished" and not interrupted:
                    interrupted = True
                    raise KeyboardInterrupt()
            with patch.object(probe, "atomic_json", interrupt_after_replace):
                code, emitted = self.call_main(Path(temporary), "--case", "exit-no-marker")
            saved = json.loads(Path(emitted["summary"]).read_text())
            self.assertEqual(code, 130)
            self.assertEqual(saved["status"], "FAIL")
            self.assertTrue(saved["interrupted"])
            self.assertEqual(saved["exit_code"], 130)
            self.assertTrue(emitted["summary_current"])
            self.assertIn("KeyboardInterrupt", saved["archive_error"])


if __name__ == "__main__":
    unittest.main()

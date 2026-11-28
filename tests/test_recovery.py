"""Recovery regressions use owned local fixtures, never RDC or real adapters."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from rdc_operator import common, mcp_server, recovery
from rdc_operator.cli import main
from rdc_operator.common import KitError, atomic_json
from rdc_operator.core import execute_request, state_lock
from rdc_operator.recovery import assess_resume, read_recovery_document, save_checkpoint


class LostReply(BaseException):
    """Simulate interruption after an effect, before a receipt exists."""


def _compete(document, config, state, now, barrier, queue):
    try:
        barrier.wait(timeout=15)
        answer = save_checkpoint(document, config, Path(state), expected_revision=1, now=now)
        queue.put(("saved", answer["revision"]))
    except KitError as exc:
        queue.put(("rejected", exc.code))
    except BaseException as exc:
        queue.put(("fixture_error", type(exc).__name__))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-recovery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / "original state 中文"
        self.now = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
        self.config = {"schema_version": 1, "smartcli": [sys.executable],
                       "allowed_roots": [str(self.root)], "private": "PRIVATE_CONFIG_SENTINEL"}
        self.document = {"schema_version": 1, "task_id": "owned-task", "scope_sha256": "a" * 64,
                         "route": {"link_id": "PRIVATE_LINK_SENTINEL", "device_id": "PRIVATE_DEVICE_SENTINEL",
                                   "observed_utc": self.now.isoformat()},
                         "event": "same_connection", "request_ids": ["effect-1"],
                         "handles": [{"kind": kind, "id": f"PRIVATE_{kind}_HANDLE"} for kind in
                                     ("rdc_call", "process", "search", "terminal", "browser_tab", "desktop_observation")],
                         "stop_reason": "none"}
        self.request = {"request_id": "effect-1", "action": "terminal.start",
                        "args": {"session": "owned-fixture", "command": "fixture-never-executed",
                                 "cwd": str(self.root)}}

    def save(self, document=None, expected=0, **kwargs):
        return save_checkpoint(deepcopy(self.document if document is None else document), self.config,
                               kwargs.pop("state", self.state), expected_revision=expected,
                               now=kwargs.pop("now", self.now), **kwargs)

    def context(self, **changes):
        result = {key: deepcopy(self.document[key]) for key in
                  ("schema_version", "scope_sha256", "route", "event", "stop_reason")}
        result.update(changes)
        return result

    def resume(self, context=None, **kwargs):
        return assess_resume("owned-task", self.context() if context is None else context,
                             kwargs.pop("config", self.config), kwargs.pop("state", self.state),
                             now=kwargs.pop("now", self.now), **kwargs)

    def checkpoint_path(self, state=None):
        return (state or self.state) / recovery.CHECKPOINT_DIRECTORY / "owned-task.json"

    def execute(self, operation=None, state=None, config=None):
        return execute_request(self.request, self.config if config is None else config,
                               self.state if state is None else state, apply=True,
                               operation=operation or (lambda *_: {"status": "completed", "private": "PRIVATE_OUTPUT_SENTINEL"}))

    def snapshot(self, root=None):
        return {str(path.relative_to(root or self.state)): path.read_bytes()
                for path in (root or self.state).rglob("*") if path.is_file()}

    def write_records(self, *, intent=True, receipt="completed", digest="d" * 64):
        records = self.state / "requests"
        records.mkdir(parents=True, exist_ok=True)
        if intent:
            atomic_json(records / "effect-1.intent.json", {"schema_version": 1, "request_id": "effect-1",
                        "state": "prepared", "digest": "d" * 64,
                        "private": "PRIVATE_INTENT_COMMAND"})
        if receipt is not None:
            atomic_json(records / "effect-1.receipt.json", {"schema_version": 1, "request_id": "effect-1",
                        "status": receipt, "digest": digest, "result": {"private": "PRIVATE_OUTPUT_SENTINEL"}})

    def test_actual_gap_same_id_in_different_state_can_duplicate_effect(self):
        effects = []
        operation = lambda *_: (effects.append("effect") or {"status": "completed"})
        self.save()
        self.execute(operation)
        self.assertTrue(self.execute(operation)["replayed"])
        wrong = self.root / "mistaken-new-state"
        self.execute(operation, state=wrong)
        self.assertEqual(effects, ["effect", "effect"], "Preserve the real pre-existing state-scope gap")
        before = self.snapshot(wrong)
        with self.assertRaises(KitError) as caught:
            self.resume(state=wrong)
        self.assertEqual(caught.exception.code, "marker_not_found")
        self.assertEqual(before, self.snapshot(wrong))

    def test_effect_with_lost_receipt_requires_reconciliation_without_replay(self):
        witness = self.root / "effect-witness.txt"
        self.save()

        def lose_reply(*_):
            witness.write_text("one effect", encoding="utf-8")
            raise LostReply()

        with self.assertRaises(LostReply):
            self.execute(lose_reply)
        before = self.snapshot()
        plan = self.resume(self.context(event="user_reconnected"))
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["requests"][0]["record_state"], "intent_without_receipt")
        with self.assertRaises(KitError) as caught:
            self.execute(lambda *_: self.fail("An interrupted operation was replayed"))
        self.assertEqual(caught.exception.code, "outcome_unknown")
        self.assertEqual(witness.read_text(), "one effect")
        self.assertEqual(before, self.snapshot())

    def test_saved_statuses_are_preserved_without_disclosing_private_results(self):
        self.save()
        for status in ("completed", "observed", "failed", "outcome_unknown"):
            with self.subTest(status=status):
                self.write_records(receipt=status)
                plan = self.resume()
                self.assertEqual(plan["requests"][0]["saved_receipt_status"], status)
                self.assertEqual(plan["status"], "review_required" if status in {"completed", "observed"} else "blocked")
                encoded = json.dumps(plan)
                for private in ("PRIVATE_", str(self.root), "safe_to_execute", "fixture-never-executed"):
                    self.assertNotIn(private, encoded)
                for key in ("actions_exposed", "automatic_replay_allowed", "execution_authorized",
                            "physical_device_verified", "request_config_binding_verified",
                            "live_verification_performed", "snapshot_atomic", "scope_content_verified"):
                    self.assertIs(plan[key], False)
                self.assertIs(plan["fresh_observation_required"], True)

    def test_missing_orphan_mismatched_and_corrupt_records_do_not_become_retryable(self):
        self.save()
        self.assertEqual(self.resume()["requests"][0]["record_state"], "no_records_observed")
        self.write_records(intent=False)
        self.assertEqual(self.resume()["requests"][0]["reason"], "receipt_without_intent")
        self.write_records(digest="e" * 64)
        self.assertEqual(self.resume()["requests"][0]["reason"], "record_digest_mismatch")
        receipt = self.state / "requests/effect-1.receipt.json"
        for raw in ('{"status":"PRIVATE_CORRUPTED_CONTENT"', '{"a":1,"a":2}', '{"x":1e999}'):
            receipt.write_text(raw, encoding="utf-8")
            plan = self.resume()
            self.assertEqual(plan["status"], "blocked")
            self.assertEqual(plan["requests"][0]["record_state"], "unavailable")
            self.assertNotIn("PRIVATE_CORRUPTED_CONTENT", json.dumps(plan))

    def test_existing_request_config_binding_is_explicitly_unverified(self):
        old_config = {**self.config, "private": "DIFFERENT_HISTORICAL_CONFIG"}
        self.execute(config=old_config)
        self.save()
        plan = self.resume()
        self.assertEqual(plan["requests"][0]["saved_receipt_status"], "completed")
        self.assertIs(plan["request_config_binding_verified"], False)
        self.assertIs(plan["requests"][0]["request_config_binding_verified"], False)
        self.assertNotIn("DIFFERENT_HISTORICAL_CONFIG", json.dumps(plan))

    def test_scope_and_config_mismatch_block_and_cannot_change_saved_identity(self):
        self.save()
        self.write_records()
        self.assertIn("config_mismatch", self.resume(config={**self.config, "new": True})["blocking_reasons"])
        changed = self.context(scope_sha256="b" * 64)
        self.assertIn("scope_mismatch", self.resume(changed)["blocking_reasons"])
        for document, config in (({**self.document, "scope_sha256": "b" * 64}, self.config),
                                 (self.document, {**self.config, "new": True})):
            before = self.snapshot()
            with self.assertRaises(KitError):
                save_checkpoint(document, config, self.state, expected_revision=1, now=self.now)
            self.assertEqual(before, self.snapshot())

    def test_copy_to_another_directory_and_replaced_marker_are_rejected(self):
        self.save()
        copied = self.root / "copied-state"
        shutil.copytree(self.state, copied)
        with self.assertRaises(KitError) as caught:
            self.resume(state=copied)
        self.assertEqual(caught.exception.code, "state_path_mismatch")
        marker_path = self.state / recovery.MARKER_NAME
        marker = read_recovery_document(marker_path)
        marker["state_id"] = str(uuid.uuid4())
        atomic_json(marker_path, marker)
        for action in (lambda: self.resume(), lambda: self.save(expected=1)):
            with self.assertRaises(KitError) as caught:
                action()
            self.assertEqual(caught.exception.code, "checkpoint_state_mismatch")

    def test_missing_state_marker_or_checkpoint_never_initializes_replacement(self):
        absent = self.root / "absent"
        with self.assertRaises(KitError):
            self.resume(state=absent)
        self.assertFalse(absent.exists())
        self.state.mkdir()
        with self.assertRaises(KitError):
            self.resume()
        self.assertEqual(list(self.state.iterdir()), [])
        self.save()
        self.checkpoint_path().unlink()
        before = self.snapshot()
        with self.assertRaises(KitError):
            self.resume()
        self.assertEqual(before, self.snapshot())

    def test_missing_marker_cannot_be_recreated_over_any_existing_checkpoint(self):
        self.save()
        (self.state / recovery.MARKER_NAME).unlink()
        different = {**self.document, "task_id": "another-task"}
        before = self.snapshot()
        with self.assertRaises(KitError) as caught:
            self.save(different)
        self.assertEqual(caught.exception.code, "marker_not_found")
        self.assertEqual(before, self.snapshot())

    def test_checkpoint_change_during_request_sampling_blocks_incomplete_plan(self):
        self.save()
        self.write_records()
        original = mcp_server.ReadOnlyOperator.call
        changed = {**self.document, "request_ids": ["effect-1", "new-unknown-request"]}

        def race(operator, name, arguments):
            result = original(operator, name, arguments)
            self.save(changed, expected=1)
            return result

        with patch.object(mcp_server.ReadOnlyOperator, "call", race):
            plan = self.resume()
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("recovery_records_changed_during_observation", plan["blocking_reasons"])
        self.assertEqual(plan["checkpoint_revision"], 1)
        self.assertEqual(read_recovery_document(self.checkpoint_path())["revision"], 2)

    def test_marker_change_during_request_sampling_is_not_accepted(self):
        self.save()
        self.write_records()
        original = mcp_server.ReadOnlyOperator.call

        def race(operator, name, arguments):
            result = original(operator, name, arguments)
            marker_path = self.state / recovery.MARKER_NAME
            marker = read_recovery_document(marker_path)
            marker["state_id"] = str(uuid.uuid4())
            atomic_json(marker_path, marker)
            return result

        with patch.object(mcp_server.ReadOnlyOperator, "call", race):
            plan = self.resume()
        self.assertIn("recovery_records_unavailable_after_sampling", plan["blocking_reasons"])

    def test_changing_request_receipt_between_samples_is_inconclusive(self):
        self.save()
        self.write_records()
        original, reads = mcp_server._read_saved_record, []

        def race(path, kind):
            if kind == "receipt":
                reads.append(1)
                if len(reads) == 2:
                    self.write_records(receipt="outcome_unknown")
            return original(path, kind)

        with patch.object(mcp_server, "_read_saved_record", side_effect=race):
            plan = self.resume()
        self.assertEqual(plan["requests"][0]["reason"], "records_changed_during_observation")
        self.assertIsNone(plan["requests"][0]["saved_receipt_status"])
        self.assertEqual(plan["status"], "blocked")

    def test_route_time_boundaries_future_naive_and_timezone_offsets(self):
        self.save()
        self.write_records()
        for delta, reason in ((301, "route_sample_stale"), (-1, "route_sample_in_future")):
            context = self.context()
            context["route"]["observed_utc"] = (self.now - timedelta(seconds=delta)).isoformat()
            self.assertIn(reason, self.resume(context)["blocking_reasons"])
            document = deepcopy(self.document)
            document["route"] = context["route"]
            with self.assertRaises(KitError) as caught:
                self.save(document, state=self.root / f"invalid-time-{delta}")
            self.assertEqual(caught.exception.code, reason)
        context = self.context()
        context["route"]["observed_utc"] = "2026-11-28T21:00:00+09:00"
        self.assertEqual(self.resume(context)["status"], "review_required")
        context["route"]["observed_utc"] = "2026-11-28T12:00:00"
        with self.assertRaises(KitError) as caught:
            self.resume(context)
        self.assertEqual(caught.exception.code, "invalid_route_time")
        document = deepcopy(self.document)
        document["route"]["observed_utc"] = (self.now - timedelta(seconds=300)).isoformat()
        boundary = self.root / "exactly-300-seconds"
        self.save(document, state=boundary)
        context = self.context()
        context["route"] = document["route"]
        self.assertNotIn("route_sample_stale", self.resume(context, state=boundary)["blocking_reasons"])

    def test_changed_device_and_same_ids_reconnection_invalidate_route_handles(self):
        self.save()
        self.write_records()
        for changed in ("device", "link", "event"):
            context = self.context()
            if changed == "event":
                context["event"] = "user_reconnected"
            else:
                context["route"][f"{changed}_id"] = "new-id-even-if-display-name-is-unchanged"
            plan = self.resume(context)
            self.assertTrue(plan["route_handles_invalidated_for_plan"])
            self.assertEqual(plan["status"], "review_required")
            handles = {item["kind"]: item for item in plan["handles"]}
            for kind in ("rdc_call", "search", "terminal", "browser_tab", "desktop_observation"):
                self.assertEqual(handles[kind]["assessment"], "invalidated_for_plan")
            self.assertEqual(handles["process"]["requirement"], "verify_pid_creation_time_executable_and_task_ownership")
            self.assertFalse(handles["process"]["live_verification_performed"])
        unchanged = self.resume()
        self.assertTrue(unchanged["fresh_observation_required"])
        self.assertFalse(unchanged["physical_device_verified"])

    def test_route_generation_and_removed_handle_history_prevent_relabelling(self):
        self.assertEqual(self.save()["route_generation"], 1)
        value = deepcopy(self.document)
        value["route"]["observed_utc"] = (self.now + timedelta(seconds=1)).isoformat()
        self.assertEqual(self.save(value, expected=1, now=self.now + timedelta(seconds=1))["route_generation"], 1)
        value["handles"] = []
        self.save(value, expected=2, now=self.now + timedelta(seconds=1))
        value["event"] = "user_reconnected"
        self.assertEqual(self.save(value, expected=3, now=self.now + timedelta(seconds=1))["route_generation"], 2)
        value["event"] = "same_connection"
        value["handles"] = deepcopy(self.document["handles"])
        with self.assertRaises(KitError) as caught:
            self.save(value, expected=4, now=self.now + timedelta(seconds=1))
        self.assertEqual(caught.exception.code, "stale_handle_reuse")
        value["handles"] = [{"kind": "rdc_call", "id": "new-call-for-generation-2"}]
        self.assertEqual(self.save(value, expected=4, now=self.now + timedelta(seconds=1))["route_generation"], 2)
        value["route"]["device_id"] = "new-device"
        with self.assertRaises(KitError):
            self.save(value, expected=5, now=self.now + timedelta(seconds=1))
        value["handles"] = []
        self.assertEqual(self.save(value, expected=5, now=self.now + timedelta(seconds=1))["route_generation"], 3)

    def test_handle_history_bound_fails_without_forgetting_old_ownership(self):
        value = {**self.document, "handles": [{"kind": "process", "id": "old-pid"}]}
        with patch.object(recovery, "MAX_HANDLE_HISTORY", 2):
            self.save(value)
            value["handles"] = [{"kind": "process", "id": "new-pid"}]
            self.save(value, expected=1)
            before = self.snapshot()
            value["handles"] = [{"kind": "process", "id": "third-pid"}]
            with self.assertRaises(KitError) as caught:
                self.save(value, expected=2)
            self.assertEqual(caught.exception.code, "handle_history_full")
            self.assertEqual(before, self.snapshot())

    def test_requests_and_hard_stops_cannot_be_erased_by_update_or_reconnection(self):
        for stop in ("quota", "policy_refused", "cancelled"):
            with self.subTest(stop=stop):
                state = self.root / stop
                value = {**self.document, "stop_reason": stop}
                self.save(value, state=state)
                for replacement in ("none", "disconnected", "cancelled" if stop != "cancelled" else "quota"):
                    with self.assertRaises(KitError) as caught:
                        self.save({**value, "stop_reason": replacement}, expected=1, state=state)
                    self.assertEqual(caught.exception.code, "stop_reason_retained")
                context = self.context(event="user_reconnected")
                context["route"]["link_id"] = "a-new-account-does-not-clear-this"
                self.assertIn(f"stop_{stop}", self.resume(context, state=state)["blocking_reasons"])
        self.save()
        with self.assertRaises(KitError) as caught:
            self.save({**self.document, "request_ids": []}, expected=1)
        self.assertEqual(caught.exception.code, "request_ids_retained")

    def test_connection_pause_requires_explicit_fresh_reconnection(self):
        for stop in ("disconnected", "auth_required"):
            state = self.root / stop
            value = {**self.document, "stop_reason": stop, "handles": [], "request_ids": []}
            self.save(value, state=state)
            self.assertIn(f"stop_{stop}", self.resume(state=state)["blocking_reasons"])
            reconnect = self.context(event="user_reconnected")
            plan = self.resume(reconnect, state=state)
            self.assertEqual(plan["status"], "review_required")
            stale = deepcopy(reconnect)
            stale["route"]["observed_utc"] = (self.now - timedelta(seconds=301)).isoformat()
            self.assertIn(f"stop_{stop}", self.resume(stale, state=state)["blocking_reasons"])
            clear = {**value, "stop_reason": "none"}
            with self.assertRaises(KitError) as caught:
                self.save(clear, expected=1, state=state)
            self.assertEqual(caught.exception.code, "reconnection_required")
            clear["event"] = "user_reconnected"
            self.assertEqual(self.save(clear, expected=1, state=state)["route_generation"], 2)

    def test_compare_and_swap_and_existing_execution_lock_prevent_overwrite(self):
        self.save()
        self.save(expected=1)
        before = self.snapshot()
        for expected in (0, 1, 3):
            with self.assertRaises(KitError) as caught:
                self.save(expected=expected)
            self.assertEqual(caught.exception.code, "checkpoint_conflict")
        with state_lock(self.state):
            with self.assertRaises(KitError) as caught:
                self.save(expected=2)
            self.assertEqual(caught.exception.code, "busy")
        self.assertEqual(before, self.snapshot())

    def test_two_real_processes_with_same_revision_only_one_commits(self):
        self.save()
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = []
        for suffix in ("a", "b"):
            value = {**self.document, "request_ids": ["effect-1", f"writer-{suffix}"]}
            process = ctx.Process(target=_compete, args=(value, self.config, str(self.state),
                                  self.now, barrier, queue))
            process.start()
            processes.append(process)
        try:
            answers = [queue.get(timeout=20), queue.get(timeout=20)]
        finally:
            for process in processes:
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            queue.close()
            queue.join_thread()
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertEqual(sum(answer == ("saved", 2) for answer in answers), 1)
        self.assertEqual(sum(answer[0] == "rejected" and answer[1] in {"busy", "checkpoint_conflict"}
                             for answer in answers), 1)
        saved = read_recovery_document(self.checkpoint_path())
        self.assertEqual(saved["revision"], 2)
        self.assertEqual(len(saved["request_ids"]), 2)

    def test_replace_failure_preserves_existing_records_and_reports_uncertainty(self):
        self.save()
        self.write_records()
        before = self.snapshot()
        with patch.object(common.os, "replace", side_effect=OSError("PRIVATE_DISK_FAILURE")):
            with self.assertRaises(KitError) as caught:
                self.save(expected=1)
        self.assertEqual(caught.exception.code, "checkpoint_persistence_failed")
        self.assertTrue(caught.exception.uncertain)
        self.assertNotIn("PRIVATE_DISK_FAILURE", caught.exception.message)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list(self.state.rglob("*.tmp")), [])

    def test_failure_after_replace_is_an_uncertain_commit_not_an_automatic_retry(self):
        self.save()

        def write_then_fail(path, value):
            atomic_json(path, value)
            raise OSError("directory durability acknowledgement lost")

        with patch.object(recovery, "atomic_json", side_effect=write_then_fail):
            with self.assertRaises(KitError) as caught:
                self.save(expected=1)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(read_recovery_document(self.checkpoint_path())["revision"], 2)
        with self.assertRaises(KitError) as caught:
            self.save(expected=1)
        self.assertEqual(caught.exception.code, "checkpoint_conflict")

    def test_marker_write_failure_never_claims_checkpoint_saved(self):
        with patch.object(recovery, "atomic_json", side_effect=OSError("fixture full disk")):
            with self.assertRaises(KitError) as caught:
                self.save()
        self.assertEqual(caught.exception.code, "checkpoint_persistence_failed")
        self.assertFalse(self.checkpoint_path().exists())
        self.assertFalse((self.state / recovery.MARKER_NAME).exists())

    def test_resume_uses_no_writable_open_lock_adapter_subprocess_or_network(self):
        self.save()
        self.execute()
        (self.state / ".lock").unlink()
        before, real_open = self.snapshot(), os.open

        def read_only_open(path, flags, *args, **kwargs):
            self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), 0)
            return real_open(path, flags, *args, **kwargs)

        with ExitStack() as stack:
            for target in ("rdc_operator.recovery.state_lock", "rdc_operator.recovery.atomic_json",
                           "os.mkdir", "os.replace", "subprocess.Popen", "socket.socket",
                           "rdc_operator.adapters.execute", "rdc_operator.omp.execute"):
                stack.enter_context(patch(target, side_effect=AssertionError(f"Forbidden resume side effect: {target}")))
            stack.enter_context(patch("os.open", side_effect=read_only_open))
            plan = self.resume()
        self.assertEqual(plan["status"], "review_required")
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.state / ".lock").exists())

    def test_symlinked_state_records_directories_and_inputs_are_rejected(self):
        self.save()
        outside = self.root / "outside.json"
        outside.write_text('{"private":"OUTSIDE_SENTINEL"}', encoding="utf-8")
        probe = self.root / "symlink-probe"
        try:
            probe.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError):
            read_recovery_document(probe)
        linked_state = self.root / "linked-state"
        linked_state.symlink_to(self.state, target_is_directory=True)
        for action in (lambda: self.resume(state=linked_state), lambda: self.save(state=linked_state, expected=1)):
            with self.assertRaises(KitError):
                action()
        for path in (self.state / recovery.MARKER_NAME, self.checkpoint_path()):
            original = path.read_bytes()
            path.unlink()
            path.symlink_to(outside)
            try:
                for action in (lambda: self.resume(), lambda: self.save(expected=1)):
                    with self.assertRaises(KitError):
                        action()
            finally:
                path.unlink()
                path.write_bytes(original)
        folder = self.state / recovery.CHECKPOINT_DIRECTORY
        parked = self.state / "parked"
        folder.rename(parked)
        folder.symlink_to(parked, target_is_directory=True)
        for action in (lambda: self.resume(), lambda: self.save(expected=1)):
            with self.assertRaises(KitError):
                action()
        self.assertEqual(outside.read_text(), '{"private":"OUTSIDE_SENTINEL"}')

    def test_hardlinked_marker_checkpoint_lock_and_input_are_rejected(self):
        self.save()
        for path in (self.state / recovery.MARKER_NAME, self.checkpoint_path(), self.state / ".lock"):
            linked = self.root / "hard-link"
            try:
                os.link(path, linked)
            except OSError:
                self.skipTest("hard-link creation unavailable")
            original = linked.read_bytes()
            try:
                with self.assertRaises(KitError):
                    self.save(expected=1)
                if path.name != ".lock":
                    with self.assertRaises(KitError):
                        self.resume()
                    with self.assertRaises(KitError):
                        read_recovery_document(linked)
                self.assertEqual(linked.read_bytes(), original)
            finally:
                linked.unlink()

    @unittest.skipUnless(hasattr(os, "mkfifo") and os.name != "nt", "POSIX FIFO semantics")
    def test_fifo_checkpoint_is_rejected_without_waiting_for_writer(self):
        self.save()
        self.checkpoint_path().unlink()
        os.mkfifo(self.checkpoint_path())
        with self.assertRaises(KitError) as caught:
            self.resume()
        self.assertEqual(caught.exception.code, "unsafe_checkpoint")

    def test_oversized_and_invalid_saved_schema_are_not_accepted(self):
        self.save()
        path = self.checkpoint_path()
        original = path.read_bytes()
        with path.open("wb") as handle:
            handle.truncate(mcp_server.MAX_RECEIPT_BYTES + 1)
        with self.assertRaises(KitError) as caught:
            self.resume()
        self.assertEqual(caught.exception.code, "checkpoint_too_large")
        for key, value in (("schema_version", True), ("revision", True), ("route_generation", 0),
                           ("extra", "PRIVATE_BAD_FIELD"), ("state_id", "different-marker")):
            payload = json.loads(original)
            payload[key] = value
            atomic_json(path, payload)
            with self.assertRaises(KitError):
                self.resume()

    def test_closed_input_schema_ids_types_and_bounds_fail_before_state_creation(self):
        cases = [({**self.document, "extra": True}), ({**self.document, "schema_version": True}),
                 ({**self.document, "event": "automatic_relogin"}),
                 ({**self.document, "request_ids": ["effect-1", "effect-1"]}),
                 ({**self.document, "request_ids": [f"id-{i}" for i in range(129)]}),
                 ({**self.document, "handles": [{"kind": "process", "id": str(i)} for i in range(129)]}),
                 ({**self.document, "handles": [{"kind": "pid", "id": "123"}]}),
                 ({**self.document, "handles": [{"kind": "process", "id": "x\ncontrol"}]}),
                 ({**self.document, "handles": [{"kind": "process", "id": "x" * 257}]}),
                 ({**self.document, "scope_sha256": 12}), ({**self.document, "stop_reason": []})]
        for bad in ("../task", "CON", "lpt1", "C:\\task", "name:stream", "中文", "x" * 65, 1):
            cases.append({**self.document, "task_id": bad})
            cases.append({**self.document, "request_ids": [bad]})
        for value in cases:
            with self.subTest(value=value), self.assertRaises(KitError):
                self.save(value)
            self.assertFalse(self.state.exists())
        for revision in (True, -1, 1.0, "0"):
            with self.subTest(revision=revision), self.assertRaises(KitError):
                self.save(expected=revision)
            self.assertFalse(self.state.exists())
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":1e999}', '[]'):
            source = self.root / "malformed.json"
            source.write_text(raw, encoding="utf-8")
            with self.assertRaises(KitError):
                read_recovery_document(source)

    def test_context_schema_is_closed_and_does_not_accept_permissions_or_extra_routes(self):
        self.save()
        cases = [self.context(permission_granted=True), self.context(event=True), self.context(stop_reason="retry"),
                 self.context(schema_version=True), self.context(scope_sha256="short")]
        route = deepcopy(self.document["route"])
        route["device_name"] = "same human-readable name is not identity"
        cases.append(self.context(route=route))
        for value in cases:
            with self.subTest(value=value), self.assertRaises(KitError):
                self.resume(value)

    @unittest.skipUnless(os.name == "nt", "Windows path aliases and kernel path checks")
    def test_windows_short_and_case_alias_preserve_canonical_state_binding(self):
        import ctypes
        from ctypes import wintypes
        self.save()
        self.write_records()
        fn = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        fn.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        fn.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        size = fn(str(self.state), buffer, len(buffer))
        if not size or size >= len(buffer):
            self.skipTest("short-name conversion is unavailable on this filesystem")
        aliases = [Path(buffer.value), Path(str(self.state).swapcase())]
        for alias in aliases:
            self.assertEqual(self.resume(state=alias)["status"], "review_required")
        self.assertEqual(self.save(expected=1, state=aliases[0])["revision"], 2)

    def test_cli_recovery_requires_explicit_state_and_old_call_default_is_preserved(self):
        for args in (["checkpoint", "missing.json", "--expected-revision", "0"],
                     ["resume", "owned-task", "--context", "missing.json"]):
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                result = main(args)
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(error.getvalue())["error"]["code"], "explicit_state_required")
            self.assertEqual(output.getvalue(), "")
        with patch("rdc_operator.cli.read_json", side_effect=[self.config, self.request]), \
                patch("rdc_operator.cli.execute_request", return_value={"status": "observed"}) as execute, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(main(["call", "fixture.json"]), 0)
        self.assertEqual(execute.call_args.args[2], Path(".rdc-state"))

    def test_cli_exit_codes_and_output_are_read_only_review_statuses(self):
        config_path, input_path, context_path = (self.root / name for name in ("config.json", "checkpoint.json", "context.json"))
        document = deepcopy(self.document)
        document["route"]["observed_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(config_path, self.config)
        atomic_json(input_path, document)
        context = {key: deepcopy(document[key]) for key in ("schema_version", "scope_sha256", "route", "event", "stop_reason")}
        atomic_json(context_path, context)
        prefix = ["--config", str(config_path), "--state", str(self.state)]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(prefix + ["checkpoint", str(input_path), "--expected-revision", "0"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "checkpoint_saved")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(prefix + ["resume", "owned-task", "--context", str(context_path)]), 1)
        self.write_records()
        before = self.snapshot()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(prefix + ["resume", "owned-task", "--context", str(context_path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "review_required")
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()

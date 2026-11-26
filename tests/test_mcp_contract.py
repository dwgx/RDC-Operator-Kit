"""Read-only business contract tests; the optional SDK is not required."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.metadata
import io
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
from typing import get_args
import unittest
from unittest.mock import patch

from rdc_operator.common import KitError
import rdc_operator.mcp_server as mcp_server
from rdc_operator.mcp_server import MAX_RECEIPT_BYTES, ReadOnlyOperator, build_server, main
from scripts.smoke_mcp import (_validate_direct_identity, _validate_ready_witness,
                               _validate_return_witness, _validate_windows_identity,
                               _same_json, _matching_result_channels)


class McpSmokeEvidenceTests(unittest.TestCase):
    def response(self, structured, text=None):
        return SimpleNamespace(is_error=False, structured_content=structured,
            content=[SimpleNamespace(type="text", text=json.dumps(structured) if text is None else text)])

    def test_saved_receipt_comparison_preserves_boolean_and_number_types(self):
        saved = {"status": "outcome_unknown", "result": {"semantic_verified": False, "items": [1]}}
        changed = deepcopy(saved)
        changed["result"]["semantic_verified"] = 0
        self.assertEqual(saved, changed)  # Reproduce the old Python-equality false positive.
        self.assertFalse(_same_json(saved, changed))
        changed = deepcopy(saved)
        changed["result"]["items"][0] = True
        self.assertFalse(_same_json(saved, changed))
        self.assertTrue(_same_json(saved, dict(reversed(list(saved.items())))))

    def test_capability_text_cannot_replace_false_with_zero(self):
        result = self.response({"runtime_probes_performed": False}, '{"runtime_probes_performed":0}')
        self.assertFalse(_matching_result_channels(result))
        result.content[0].text = '{"runtime_probes_performed":false}'
        self.assertTrue(_matching_result_channels(result))

    def test_status_text_cannot_hide_fields_or_add_another_content_block(self):
        value = {"record_state": "intent_without_receipt", "snapshot_atomic": False}
        result = self.response(value, json.dumps({**value, "intent": "STATUS_PRIVATE_SENTINEL"}))
        self.assertFalse(_matching_result_channels(result))
        result = self.response(value)
        result.content.append(SimpleNamespace(type="text", text="STATUS_PRIVATE_SENTINEL"))
        self.assertFalse(_matching_result_channels(result))
        self.assertTrue(_matching_result_channels(self.response(value)))

    def test_malformed_or_non_json_success_payloads_fail_evidence_check(self):
        for raw in ('{"ok":false,"ok":false}', '{"ok":NaN}', '{"ok":1e999}', '{', '[]'):
            with self.subTest(raw=raw):
                self.assertFalse(_matching_result_channels(self.response({"ok": False}, raw)))
        for value in (float("nan"), float("inf"), (1,), {1: "numeric key"}):
            with self.subTest(value=value):
                self.assertFalse(_same_json(value, value))
        result = self.response({"ok": False})
        result.is_error = True
        self.assertFalse(_matching_result_channels(result))


class ReadOnlyMcpContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdck-mcp-contract-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        (self.state / "requests").mkdir(parents=True)
        self.config = {"schema_version": 1, "smartcli": ["SECRET_MACHINE_PATH", "TOKEN_MUST_NOT_LEAK"],
                       "winapp": [], "omp": {"wrapper": "PRIVATE_WRAPPER_PATH"},
                       "allowed_roots": ["PRIVATE_ROOT"]}
        self.operator = ReadOnlyOperator(self.config, self.state)

    def write_receipt(self, rid="sample", **values):
        payload = {"schema_version": 1, "request_id": rid, "status": "outcome_unknown",
                   "result": {"semantic_verified": False}, **values}
        path = self.state / "requests" / f"{rid}.receipt.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, payload

    def write_intent(self, rid="sample", **values):
        payload = {"schema_version": 1, "request_id": rid, "state": "prepared",
                   "digest": "a" * 64, "action": "terminal.input",
                   "args": {"command": "PRIVATE_INTENT_COMMAND", "path": "PRIVATE_INTENT_PATH"}, **values}
        path = self.state / "requests" / f"{rid}.intent.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, payload

    def test_capabilities_redact_configuration_and_do_not_launch(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        with patch("subprocess.Popen") as launch:
            value = self.operator.call("operator_capabilities", {})
        launch.assert_not_called()
        encoded = json.dumps(value)
        for secret in ("SECRET_MACHINE_PATH", "TOKEN_MUST_NOT_LEAK", "PRIVATE_WRAPPER_PATH", "PRIVATE_ROOT"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(value["configured"], {"terminal": True, "desktop": False, "omp_preview": True})
        self.assertFalse(value["runtime_probes_performed"])
        self.assertFalse(value["actions_exposed"])
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))

    def test_saved_unknown_receipt_stays_unknown_and_unchanged(self):
        path, payload = self.write_receipt()
        before = path.read_bytes()
        answer = self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(answer["receipt"], payload)
        self.assertFalse(answer["live_verification_performed"])
        self.assertFalse(answer["receipt_authenticity_verified"])
        self.assertEqual(path.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Windows short-name path semantics")
    def test_windows_short_state_path_reads_same_receipt_and_status(self):
        import ctypes
        from ctypes import wintypes

        fn = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        fn.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        fn.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        size = fn(str(self.state), buffer, len(buffer))
        if not size or size >= len(buffer):
            self.skipTest("short-name conversion is unavailable on this filesystem")
        short = Path(buffer.value)
        if os.path.normcase(str(short)) == os.path.normcase(str(self.state.resolve())):
            self.skipTest("this fixture has no distinct 8.3 alias; no policy was changed")
        self.write_intent()
        path, payload = self.write_receipt(digest="a" * 64)
        before = path.read_bytes()
        operator = ReadOnlyOperator(self.config, short)
        self.assertEqual(operator.call("operator_receipt", {"request_id": "sample"})["receipt"], payload)
        value = operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(value["record_state"], "receipt_recorded")
        self.assertEqual(value["saved_receipt_status"], "outcome_unknown")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(operator.call("operator_request_status", {"request_id": "missing"})[
            "record_state"], "no_records_observed")

    @unittest.skipUnless(os.name == "nt", "Windows junction and HANDLE path semantics")
    def test_windows_transient_parent_junction_never_reads_outside_handle(self):
        import shutil
        import subprocess

        command = shutil.which("cmd.exe")
        if not command:
            self.skipTest("cmd.exe is required for the owned junction fixture")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "sample.receipt.json").write_text('{"private":"OUTSIDE_SENTINEL"}', encoding="utf-8")
        requests = self.state / "requests"
        parked = self.state / "requests-parked"
        probe = self.root / "junction-probe"

        def make_junction(path):
            return subprocess.run([command, "/d", "/c", "mklink", "/J", str(path), str(outside)],
                                  capture_output=True, timeout=5, check=False)

        available = make_junction(probe)
        if available.returncode:
            self.skipTest("directory junction creation is unavailable for this user or filesystem")
        probe.rmdir()
        self.write_receipt()
        original_check, original_open = mcp_server._unlinked, os.open
        checked, opened = [], []

        def replace_after_check(path):
            original_check(path)
            if not checked:
                checked.append(path)
                requests.rename(parked)
                self.assertEqual(make_junction(requests).returncode, 0)

        def open_then_restore(path, flags):
            # Hold the outside HANDLE while restoring an entirely ordinary
            # path. A post-open link scan alone would now miss the redirect.
            fd = original_open(path, flags)
            opened.append(fd)
            requests.rmdir()
            parked.rename(requests)
            return fd

        try:
            with patch.object(mcp_server, "_unlinked", side_effect=replace_after_check), \
                    patch.object(mcp_server.os, "open", side_effect=open_then_restore), \
                    patch.object(mcp_server.os, "fdopen") as read:
                with self.assertRaises(KitError) as caught:
                    self.operator.call("operator_receipt", {"request_id": "sample"})
                self.assertEqual(caught.exception.code, "unsafe_state")
                self.assertIn("outside the fixed path", caught.exception.message)
                read.assert_not_called()
            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError):
                os.fstat(opened[0])
        finally:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass  # The expected rejection already closed this handle.
            if parked.exists():
                if requests.exists():
                    requests.rmdir()
                parked.rename(requests)

    def test_invalid_id_never_opens_a_receipt(self):
        for name in ("operator_receipt", "operator_request_status"):
            for rid in ("../outside", "/absolute", "C:\\outside", "x/y", "x\\y", "sample.receipt.json",
                        "sample\0", "CON", "lpt1", "x" * 65, "中文", 17, None):
                with self.subTest(name=name, rid=rid), patch("rdc_operator.mcp_server._open_receipt") as read:
                    with self.assertRaises(KitError) as caught:
                        self.operator.call(name, {"request_id": rid})
                    self.assertEqual(caught.exception.code, "invalid_request_id")
                    read.assert_not_called()

    def test_tool_arguments_cannot_override_scope(self):
        for name, args in (("operator_capabilities", {"config": "elsewhere"}),
                           ("operator_receipt", {"request_id": "sample", "state": "elsewhere"}),
                           ("operator_request_status", {"request_id": "sample", "command": "PRIVATE_COMMAND"}),
                           ("operator_request_status", {}),
                           ("operator_receipt", {}), ("operator_capabilities", []),
                           ("desktop.click", {})):
            with self.subTest(name=name, args=args), self.assertRaises(KitError):
                self.operator.call(name, args)

    def test_missing_receipt_is_reported_without_path_details(self):
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "missing"})
        self.assertEqual(caught.exception.code, "receipt_not_found")
        self.assertNotIn(str(self.root), caught.exception.message)

    def test_malformed_or_wrong_identity_receipts_are_rejected(self):
        path, _ = self.write_receipt()
        bad = ["[]", "{", '{"schema_version":1,"request_id":"sample","status":"done"}',
               '{"schema_version":1,"request_id":"different","status":"completed"}',
               '{"schema_version":1,"request_id":"sample","status":[]}',
               '{"schema_version":true,"request_id":"sample","status":"completed"}',
               '{"schema_version":1,"request_id":"sample","status":"completed","v":NaN}',
               '{"schema_version":1,"request_id":"sample","status":"completed","v":1e999}',
               '{"schema_version":1,"request_id":"sample","status":"completed","status":"failed"}']
        for raw in bad:
            with self.subTest(raw=raw):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(KitError):
                    self.operator.call("operator_receipt", {"request_id": "sample"})

    def test_receipt_file_symlink_cannot_read_outside(self):
        outside = self.root / "outside.json"
        outside.write_text('{"private":"not a receipt"}', encoding="utf-8")
        linked = self.state / "requests" / "sample.receipt.json"
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_state")

    def test_requests_directory_symlink_cannot_read_outside(self):
        outside = self.root / "outside"
        outside.mkdir()
        requests = self.state / "requests"
        requests.rmdir()
        try:
            requests.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_state")

    def test_linked_state_is_rejected_at_startup(self):
        linked = self.root / "linked"
        try:
            linked.symlink_to(self.state, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError):
            ReadOnlyOperator(self.config, linked)

    def test_hard_link_receipt_is_rejected(self):
        original, _ = self.write_receipt()
        try:
            os.link(original, self.root / "outside-hard-link.json")
        except OSError:
            self.skipTest("hard links unavailable on this filesystem")
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_receipt")

    def test_oversized_file_is_not_returned(self):
        path, _ = self.write_receipt()
        with path.open("wb") as handle:
            handle.truncate(MAX_RECEIPT_BYTES + 1)
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "receipt_too_large")

    @unittest.skipUnless(hasattr(os, "mkfifo") and os.name != "nt", "POSIX FIFO only")
    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        path = self.state / "requests" / "sample.receipt.json"
        os.mkfifo(path)
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_receipt", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_receipt")

    def test_missing_sdk_is_stderr_only_and_does_not_create_state(self):
        output, error = io.StringIO(), io.StringIO()
        state = self.root / "not-created"
        with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError), \
                redirect_stdout(output), redirect_stderr(error):
            code = main(["--config", str(self.root / "unused.json"), "--state", str(state)])
        self.assertEqual(code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("mcp==2.3.0", error.getvalue())
        self.assertFalse(state.exists())

    def test_no_records_is_only_an_observation_and_does_not_create_state(self):
        absent = self.root / "absent-state"
        operator = ReadOnlyOperator(self.config, absent)
        with patch("subprocess.Popen") as launch:
            value = operator.call("operator_request_status", {"request_id": "missing"})
        self.assertEqual(value["record_state"], "no_records_observed")
        self.assertIsNone(value["saved_receipt_status"])
        self.assertIs(value["snapshot_atomic"], False)
        self.assertIs(value["live_verification_performed"], False)
        self.assertIs(value["actions_exposed"], False)
        self.assertNotIn("running", value)
        self.assertNotIn("retryable", value)
        self.assertNotIn("cancel", value)
        self.assertFalse(absent.exists())
        launch.assert_not_called()

    def test_prepared_intent_summary_redacts_content_and_never_claims_running(self):
        path, _ = self.write_intent()
        before = path.read_bytes()
        value = self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(value["record_state"], "intent_without_receipt")
        self.assertEqual(value["reason"], "receipt_not_observed")
        self.assertIsNone(value["saved_receipt_status"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(set(value), {"schema_version", "source", "request_id", "record_state", "reason",
            "saved_receipt_status", "snapshot_atomic", "live_verification_performed",
            "record_authenticity_verified", "actions_exposed"})
        encoded = json.dumps(value)
        for secret in ("PRIVATE_INTENT_COMMAND", "PRIVATE_INTENT_PATH", "terminal.input", "a" * 64,
                       str(self.root), "running", "retryable", "cancel"):
            self.assertNotIn(secret, encoded)

    def test_matching_saved_receipts_keep_each_original_status_without_success_claim(self):
        self.write_intent()
        for status in ("observed", "completed", "failed", "outcome_unknown"):
            with self.subTest(status=status):
                path, _ = self.write_receipt(status=status, digest="a" * 64,
                                            result={"command": "PRIVATE_RECEIPT_COMMAND"})
                before = path.read_bytes()
                value = self.operator.call("operator_request_status", {"request_id": "sample"})
                self.assertEqual(value["record_state"], "receipt_recorded")
                self.assertEqual(value["saved_receipt_status"], status)
                self.assertIs(value["live_verification_performed"], False)
                self.assertIs(value["record_authenticity_verified"], False)
                self.assertNotIn("PRIVATE_RECEIPT_COMMAND", json.dumps(value))
                self.assertNotIn("result", value)
                self.assertEqual(path.read_bytes(), before)

    def test_orphan_or_mismatched_receipt_never_becomes_completed_request(self):
        self.write_receipt(status="completed", digest="a" * 64)
        orphan = self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(orphan["record_state"], "inconclusive")
        self.assertEqual(orphan["reason"], "receipt_without_intent")
        self.assertIsNone(orphan["saved_receipt_status"])
        self.write_intent()
        for digest in ("b" * 64, None, "PRIVATE_INVALID_DIGEST", {"path": "PRIVATE_PATH"}):
            with self.subTest(digest=digest):
                self.write_receipt(status="completed", digest=digest)
                value = self.operator.call("operator_request_status", {"request_id": "sample"})
                self.assertEqual(value["record_state"], "inconclusive")
                self.assertEqual(value["reason"], "record_digest_mismatch")
                self.assertIsNone(value["saved_receipt_status"])
                self.assertNotIn("PRIVATE", json.dumps(value))

    def test_new_records_between_samples_are_inconclusive(self):
        original, calls = mcp_server._read_saved_record, []
        def concurrent_writer(path, kind):
            calls.append(kind)
            if len(calls) == 3:
                self.write_intent()
                self.write_receipt(status="completed", digest="a" * 64)
            return original(path, kind)
        with patch("rdc_operator.mcp_server._read_saved_record", side_effect=concurrent_writer):
            value = self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(len(calls), 4)
        self.assertEqual(value["record_state"], "inconclusive")
        self.assertEqual(value["reason"], "records_changed_during_observation")
        self.assertIsNone(value["saved_receipt_status"])

    def test_replaced_record_with_same_selected_fields_is_still_inconclusive(self):
        path, intent = self.write_intent()
        self.write_receipt(status="completed", digest="a" * 64)
        original, calls = mcp_server._read_saved_record, []
        def concurrent_writer(record_path, kind):
            calls.append(kind)
            if len(calls) == 3:
                replacement = self.root / "replacement.json"
                replacement.write_text(json.dumps(dict(intent, args={"command": "NEW_PRIVATE_COMMAND"})),
                                       encoding="utf-8")
                replacement.replace(path)
            return original(record_path, kind)
        with patch("rdc_operator.mcp_server._read_saved_record", side_effect=concurrent_writer):
            value = self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(value["record_state"], "inconclusive")
        self.assertEqual(value["reason"], "records_changed_during_observation")
        self.assertNotIn("NEW_PRIVATE_COMMAND", json.dumps(value))

    def test_invalid_intent_and_foreign_receipt_fail_without_content_disclosure(self):
        path, intent = self.write_intent()
        for changes in ({"schema_version": True}, {"request_id": "PRIVATE_OTHER_ID"},
                        {"state": "running"}, {"digest": "PRIVATE_DIGEST"}):
            with self.subTest(changes=changes):
                path.write_text(json.dumps(dict(intent, **changes)), encoding="utf-8")
                with self.assertRaises(KitError) as caught:
                    self.operator.call("operator_request_status", {"request_id": "sample"})
                self.assertEqual(caught.exception.code, "invalid_intent")
                self.assertNotIn("PRIVATE", caught.exception.message)
                self.assertNotIn(str(self.root), caught.exception.message)
        self.write_intent()
        receipt, payload = self.write_receipt()
        receipt.write_text(json.dumps(dict(payload, request_id="PRIVATE_OTHER_ID")), encoding="utf-8")
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "invalid_receipt")
        self.assertNotIn("PRIVATE", caught.exception.message)

    def test_status_rejects_linked_and_oversized_intents(self):
        path, _ = self.write_intent()
        outside = self.root / "private-intent.json"
        path.replace(outside)
        try:
            path.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable for this user")
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_state")
        path.unlink()
        os.link(outside, path)
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "unsafe_intent")
        path.unlink()
        with path.open("wb") as handle:
            handle.truncate(MAX_RECEIPT_BYTES + 1)
        with self.assertRaises(KitError) as caught:
            self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "intent_too_large")

    def test_intent_changed_during_open_read_is_refused(self):
        path, _ = self.write_intent()
        original, calls = os.fstat, []
        def changed(fd):
            calls.append(fd)
            if len(calls) == 2:
                with path.open("ab") as writer:
                    writer.write(b" ")
            return original(fd)
        with patch("rdc_operator.mcp_server.os.fstat", side_effect=changed):
            with self.assertRaises(KitError) as caught:
                self.operator.call("operator_request_status", {"request_id": "sample"})
        self.assertEqual(caught.exception.code, "intent_changed")


class McpOutputModelTests(unittest.TestCase):
    """Real optional Pydantic models with a registration stub; not SDK/wire tests."""
    def setUp(self):
        try:
            import pydantic
        except ImportError:
            self.skipTest("optional Pydantic dependency is not installed")
        if pydantic.__version__.split(".")[0] != "2":
            self.skipTest("optional Pydantic 2 dependency is not installed")
        self.ValidationError = pydantic.ValidationError
        class Value:
            def __init__(self, **values):
                self.__dict__.update(values)
        class Server(Value):
            def __init__(self, *args, **values):
                super().__init__(**values)
                self.tools = {}
            def tool(self, **options):
                def register(function):
                    self.tools[function.__name__] = function
                    return function
                return register
        root, server, types = ModuleType("mcp"), ModuleType("mcp.server"), ModuleType("mcp.types")
        root.__path__ = []
        server.MCPServer = Server
        types.CallToolResult = types.TextContent = types.ToolAnnotations = Value
        fixture = tempfile.TemporaryDirectory(prefix="rdck-mcp-model-")
        self.addCleanup(fixture.cleanup)
        self.operator = ReadOnlyOperator({"schema_version": 1}, Path(fixture.name) / "absent-state")
        with patch("rdc_operator.mcp_server.require_sdk"), patch.dict("sys.modules", {
                "mcp": root, "mcp.server": server, "mcp.types": types}):
            self.server = build_server(self.operator)

    def test_success_schema_matches_manual_result_without_coercing_false_or_integer(self):
        function = self.server.tools["operator_capabilities"]
        model = get_args(function.__annotations__["return"])[1]
        value = function().structured_content
        self.assertEqual(model.model_validate(value).model_dump(), value)
        schema = model.model_json_schema()
        self.assertEqual(schema["type"], "object")
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(schema["properties"]["runtime_probes_performed"]["const"], False)
        for changes in ({"runtime_probes_performed": "false"}, {"runtime_probes_performed": 0},
                        {"actions_exposed": True}, {"schema_version": True}, {"private": "PRIVATE_VALUE"}):
            with self.subTest(changes=changes), self.assertRaises(self.ValidationError):
                model.model_validate(dict(value, **changes))

    def test_receipt_model_preserves_opaque_content_but_status_model_refuses_it(self):
        receipt_model = get_args(self.server.tools["operator_receipt"].__annotations__["return"])[1]
        status_model = get_args(self.server.tools["operator_request_status"].__annotations__["return"])[1]
        receipt = {"schema_version": 1, "source": "saved_receipt", "receipt": {
            "schema_version": 1, "request_id": "known", "status": "completed",
            "result": {"command": "PRIVATE_COMMAND"}}, "live_verification_performed": False,
            "receipt_authenticity_verified": False}
        self.assertEqual(receipt_model.model_validate(receipt).model_dump(), receipt)
        with self.assertRaises(self.ValidationError):
            receipt_model.model_validate(dict(receipt, receipt=dict(receipt["receipt"], status="running")))
        safe = self.operator.call("operator_request_status", {"request_id": "unknown"})
        self.assertEqual(status_model.model_validate(safe).model_dump(), safe)
        for changes in ({"intent": {"command": "PRIVATE_COMMAND"}}, {"record_state": "running"},
                        {"saved_receipt_status": "cancelled"}, {"snapshot_atomic": 0}):
            with self.subTest(changes=changes), self.assertRaises(self.ValidationError):
                status_model.model_validate(dict(safe, **changes))


class McpSmokeIdentityTests(unittest.TestCase):
    """Synthetic OS records test rejection decisions; real Win32 calls need Windows smoke."""
    def setUp(self):
        self.nonce = "unique-launch-nonce"
        self.ready = {"nonce": self.nonce, "pid": 101, "ppid": 100}
        self.launcher = r"C:\owned\.venv-mcp\Scripts\python.exe"
        self.worker_image = r"C:\Python\python.exe"
        self.parent = {"pid": 100, "ppid": 50, "image": self.launcher,
                       "creation_filetime": 1020, "alive_during_query": True}
        self.worker = {"pid": 101, "ppid": 100, "image": self.worker_image,
                       "creation_filetime": 1050, "alive_during_query": True}

    def validate(self, **changes):
        args = {"ready": deepcopy(self.ready), "sdk_pid": 100, "caller_pid": 50,
                "parent": deepcopy(self.parent), "worker": deepcopy(self.worker),
                "launch_before": 1000, "observed_after": 1100,
                "launcher_image": self.launcher, "worker_image": self.worker_image}
        args.update(changes)
        return _validate_windows_identity(**args)

    def test_ready_witness_requires_fresh_nonce_and_integer_identity(self):
        witness = dict(self.ready, stage="ready")
        self.assertEqual(_validate_ready_witness(witness, self.nonce), self.ready)
        for fields in ({"nonce": "previous-launch"}, {"stage": "returned"},
                       {"pid": True}, {"pid": -1}, {"ppid": 0}, {"ppid": "100"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                _validate_ready_witness(dict(witness, **fields), self.nonce)

    def test_verified_windows_redirector_and_direct_child_are_supported(self):
        self.assertEqual(self.validate()["mode"], "windows-venv-redirector")
        direct = dict(self.parent, image=self.worker_image)
        result = self.validate(ready=dict(self.ready, pid=100, ppid=50), parent=direct, worker=direct)
        self.assertEqual(result["mode"], "windows-direct-child")
        self.assertEqual(result["worker"]["pid"], result["sdk_pid"])

    def test_windows_wrong_worker_or_parent_chain_is_rejected(self):
        bad = [
            {"ready": dict(self.ready, pid=202)},
            {"ready": dict(self.ready, ppid=202)},
            {"parent": dict(self.parent, pid=202)},
            {"parent": dict(self.parent, ppid=202)},
            {"worker": dict(self.worker, ppid=202), "ready": dict(self.ready, ppid=202)},
            {"worker": dict(self.worker, pid=202)},
        ]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate(**changes)

    def test_windows_unrelated_executable_or_dead_process_is_rejected(self):
        for key, original in (("parent", self.parent), ("worker", self.worker)):
            for fields in ({"image": r"C:\unrelated\python.exe"}, {"alive_during_query": False}):
                with self.subTest(key=key, fields=fields), self.assertRaises(ValueError):
                    self.validate(**{key: dict(original, **fields)})

    def test_windows_stale_reused_or_future_creation_identity_is_rejected(self):
        for key, original in (("parent", self.parent), ("worker", self.worker)):
            for created in (999, 1101, True):
                with self.subTest(key=key, created=created), self.assertRaises(ValueError):
                    self.validate(**{key: dict(original, creation_filetime=created)})
        with self.assertRaises(ValueError):
            self.validate(worker=dict(self.worker, creation_filetime=1010))
        with self.assertRaises(ValueError):
            self.validate(launch_before=1101)
        direct = dict(self.parent, image=self.worker_image)
        with self.assertRaises(ValueError):
            self.validate(ready=dict(self.ready, pid=100, ppid=50), parent=direct,
                          worker=dict(direct, creation_filetime=1050))

    def test_non_windows_still_requires_sdk_direct_pid_and_parent(self):
        direct = dict(self.ready, pid=100, ppid=50)
        self.assertEqual(_validate_direct_identity(direct, 100, 50)["mode"], "direct-child")
        for fields in ({"pid": 101}, {"ppid": 51}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                _validate_direct_identity(dict(direct, **fields), 100, 50)

    def test_normal_return_requires_the_same_worker_and_nonce(self):
        witness = dict(self.ready, stage="returned", exit_code=0, returned_from_server=True)
        self.assertTrue(_validate_return_witness(witness, self.ready))
        for fields in ({"nonce": "another-launch"}, {"pid": 100}, {"ppid": 50},
                       {"stage": "ready"}, {"exit_code": 1}, {"exit_code": False},
                       {"returned_from_server": False}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                _validate_return_witness(dict(witness, **fields), self.ready)


if __name__ == "__main__":
    unittest.main()

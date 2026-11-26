"""Real official-SDK stdio smoke, using only newly owned synthetic request records.

This is separate from offline contract tests. It never starts desktop/terminal
adapters or model calls. SDK-private hooks only observe the exact pinned SDK's
real child handle and parser; they do not replace protocol or transport behavior.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import ntpath
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from unittest.mock import patch
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import rdc_operator
from rdc_operator.common import KitError, atomic_json, strict_json
from rdc_operator.mcp_server import SDK_VERSION, require_sdk


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _same_json(left, right):
    """Compare JSON values without Python's bool/int coercion or key ordering."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (all(type(key) is str for key in left) and left.keys() == right.keys()
                and all(_same_json(value, right[key]) for key, value in left.items()))
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    if type(left) is float:
        return math.isfinite(left) and math.isfinite(right) and left == right
    if left is None or type(left) in (str, bool, int):
        return left == right
    return False


def _matching_result_channels(result):
    """The Kit's success contract has exactly one JSON text block and one object."""
    try:
        if (result.is_error is not False or len(result.content) != 1
                or result.content[0].type != "text"
                or type(result.structured_content) is not dict):
            return False
        return _same_json(strict_json(result.content[0].text), result.structured_content)
    except (AttributeError, TypeError, ValueError, RecursionError):
        return False


def _validate_ready_witness(value, nonce):
    if not isinstance(value, dict) or value.get("stage") != "ready" or value.get("nonce") != nonce:
        raise ValueError("ready witness does not belong to this launch")
    if any(type(value.get(key)) is not int or value[key] <= 0 for key in ("pid", "ppid")):
        raise ValueError("ready witness has invalid process identifiers")
    return {key: value[key] for key in ("nonce", "pid", "ppid")}


def _validate_direct_identity(ready, sdk_pid, caller_pid):
    if ready["pid"] != sdk_pid or ready["ppid"] != caller_pid:
        raise ValueError("ready witness is not the SDK-held direct child")
    return {"mode": "direct-child", "sdk_pid": sdk_pid, "worker": dict(ready)}


def _windows_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing executable identity")
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return ntpath.normcase(ntpath.normpath(value))


def _validate_windows_identity(ready, sdk_pid, caller_pid, parent, worker,
                               launch_before, observed_after, launcher_image, worker_image):
    """Validate independently queried identities; a witness PID never grants ownership."""
    if type(launch_before) is not int or type(observed_after) is not int or launch_before > observed_after:
        raise ValueError("invalid launch clock interval")
    for label, observed in (("SDK process", parent), ("worker", worker)):
        if observed.get("alive_during_query") is not True:
            raise ValueError(f"{label} was not alive during identity queries")
        created = observed.get("creation_filetime")
        if type(created) is not int or not launch_before <= created <= observed_after:
            raise ValueError(f"{label} creation time is outside this launch")
    if parent["pid"] != sdk_pid or parent["ppid"] != caller_pid:
        raise ValueError("SDK-held process does not belong to this caller")
    if worker["pid"] != ready["pid"] or worker["ppid"] != ready["ppid"]:
        raise ValueError("witness and OS worker identities differ")
    direct = worker["pid"] == sdk_pid
    if worker["ppid"] != (caller_pid if direct else sdk_pid):
        raise ValueError("worker parent is not the SDK-held process")
    if worker["creation_filetime"] < parent["creation_filetime"]:
        raise ValueError("worker predates its SDK-held parent")
    if direct and worker["creation_filetime"] != parent["creation_filetime"]:
        raise ValueError("same PID has inconsistent creation identity")
    expected_parent = worker_image if direct else launcher_image
    if _windows_path(parent["image"]) != _windows_path(expected_parent):
        raise ValueError("SDK-held executable differs from the actual launch route")
    if _windows_path(worker["image"]) != _windows_path(worker_image):
        raise ValueError("worker executable differs from sys._base_executable")
    return {"mode": "windows-direct-child" if direct else "windows-venv-redirector",
            "sdk_pid": sdk_pid, "sdk_process": dict(parent), "worker": dict(worker),
            "launch_before_filetime": launch_before, "observed_after_filetime": observed_after,
            "clock_scope": "Windows UTC FILETIME; clock discontinuity fails closed, not a monotonic clock"}


def _validate_return_witness(value, ready):
    if not isinstance(value, dict) or any(value.get(key) != ready[key] for key in ("nonce", "pid", "ppid")):
        raise ValueError("return witness does not match the validated worker and nonce")
    if any(type(value.get(key)) is not int for key in ("pid", "ppid", "exit_code")) or \
            value.get("stage") != "returned" or value["exit_code"] != 0 or \
            value.get("returned_from_server") is not True:
        raise ValueError("worker did not report a normal zero return from the server")
    return True


class _WindowsQueries:
    """Read-only OS observations. No termination access or termination method."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        class ProcessEntry(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
        self.ProcessEntry = ProcessEntry
        signatures = {
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "GetProcessId": ([wintypes.HANDLE], wintypes.DWORD),
            "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            "QueryFullProcessImageNameW": ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "GetExitCodeProcess": ([wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "GetSystemTimePreciseAsFileTime": ([ctypes.POINTER(wintypes.FILETIME)], None),
            "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            "Process32FirstW": ([wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
            "Process32NextW": ([wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def _error(self):
        return self.ctypes.WinError(self.ctypes.get_last_error())

    @staticmethod
    def _ticks(value):
        return (value.dwHighDateTime << 32) | value.dwLowDateTime

    def now(self):
        value = self.wintypes.FILETIME()
        self.kernel.GetSystemTimePreciseAsFileTime(self.ctypes.byref(value))
        return self._ticks(value)

    def open(self, pid):
        # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE; never PROCESS_TERMINATE.
        handle = self.kernel.OpenProcess(0x1000 | 0x00100000, False, pid)
        if not handle:
            raise self._error()
        return handle

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise self._error()

    def _parent_pid(self, pid):
        snapshot = self.kernel.CreateToolhelp32Snapshot(0x00000002, 0)
        if not snapshot or snapshot == self.ctypes.c_void_p(-1).value:
            raise self._error()
        try:
            entry = self.ProcessEntry()
            entry.dwSize = self.ctypes.sizeof(entry)
            found = self.kernel.Process32FirstW(snapshot, self.ctypes.byref(entry))
            while found:
                if entry.th32ProcessID == pid:
                    return entry.th32ParentProcessID
                found = self.kernel.Process32NextW(snapshot, self.ctypes.byref(entry))
            raise ValueError("process absent from the OS process snapshot")
        finally:
            self.close(snapshot)

    def _creation(self, handle):
        values = [self.wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(self.ctypes.byref(value) for value in values)):
            raise self._error()
        return self._ticks(values[0])

    def _pid(self, handle):
        pid = self.kernel.GetProcessId(handle)
        if not pid:
            raise self._error()
        return pid

    def observe(self, handle):
        # An open handle fixes kernel identity. Liveness brackets the PID snapshot.
        if self.kernel.WaitForSingleObject(handle, 0) != 0x00000102:
            raise ValueError("process is not alive before identity queries")
        pid, created = self._pid(handle), self._creation(handle)
        size = self.wintypes.DWORD(32768)
        image = self.ctypes.create_unicode_buffer(size.value)
        if not self.kernel.QueryFullProcessImageNameW(handle, 0, image, self.ctypes.byref(size)):
            raise self._error()
        ppid = self._parent_pid(pid)
        if self.kernel.WaitForSingleObject(handle, 0) != 0x00000102:
            raise ValueError("process exited during identity queries")
        return {"pid": pid, "ppid": ppid, "image": image.value,
                "creation_filetime": created, "alive_during_query": True}

    def exited(self, handle, expected):
        # Test the signaled state first; exit code 259 alone does not mean alive.
        if self.kernel.WaitForSingleObject(handle, 5000) != 0:
            raise ValueError("held worker handle did not become signaled")
        exit_code = self.wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(handle, self.ctypes.byref(exit_code)):
            raise self._error()
        pid, created = self._pid(handle), self._creation(handle)
        if pid != expected["pid"] or created != expected["creation_filetime"] or exit_code.value != 0:
            raise ValueError("held worker exit identity or exit code does not match")
        return {"pid": pid, "creation_filetime": created, "signaled": True, "exit_code": exit_code.value}


async def one_session(mode, fixture, config, state, launcher, expected):
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client import stdio as transport

    evidence = fixture / mode
    evidence.mkdir()
    ready_witness = evidence / "server-ready.json"
    exit_witness = evidence / "server-exit.json"
    nonce = uuid.uuid4().hex
    windows = _WindowsQueries() if os.name == "nt" else None
    query_handles = []
    launch_before, process_identity, worker_exit, worker_handle, ready = None, None, None, None, None
    captured_processes, raw_lines, parser_errors = [], [], []
    create_original = transport._create_platform_compatible_process
    parse_original = transport._parse_line

    async def capture_process(*args, **kwargs):
        nonlocal launch_before
        launch_before = windows.now() if windows else None
        process = await create_original(*args, **kwargs)
        captured_processes.append(process)
        return process

    def capture_line(line):
        raw_lines.append(line)
        parsed = parse_original(line)
        if isinstance(parsed, Exception):
            parser_errors.append(type(parsed).__name__)
        return parsed

    checks = []
    def check(name, condition):
        checks.append({"name": name, "pass": bool(condition)})
        if not condition:
            raise AssertionError(name)

    def verify(name, function, *args, **kwargs):
        try:
            result = function(*args, **kwargs)
        except Exception:
            checks.append({"name": name, "pass": False})
            raise
        check(name, True)
        return result

    params = StdioServerParameters(command=sys.executable,
        args=["-X", "utf8", str(launcher), str(config), str(state),
              str(ready_witness), str(exit_witness), nonce],
        cwd=str(PROJECT), env={"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    started = time.monotonic()
    negotiated = None
    try:
        with (evidence / "server.stderr.log").open("w", encoding="utf-8") as errlog:
            with patch.object(transport, "_create_platform_compatible_process", capture_process), \
                    patch.object(transport, "_parse_line", capture_line), anyio.fail_after(30):
                async with transport.stdio_client(params, errlog=errlog) as streams:
                    async with ClientSession(*streams, read_timeout_seconds=10) as session:
                        if mode == "modern":
                            await session.discover()
                        else:
                            await session.initialize()
                        negotiated = session.protocol_version
                        expected_version = "2026-07-28" if mode == "modern" else "2025-11-25"
                        check("negotiated-protocol", negotiated == expected_version)
                        check("one-owned-process", len(captured_processes) == 1)
                        process = captured_processes[0]
                        check("sdk-held-process-alive-during-session", process.returncode is None)
                        ready = verify("ready-witness-bound-to-launch", _validate_ready_witness,
                                       json.loads(ready_witness.read_text("utf-8")), nonce)
                        if windows:
                            parent_handle = windows.open(process.pid)
                            query_handles.append(parent_handle)
                            parent = windows.observe(parent_handle)
                            worker_handle = parent_handle
                            worker = parent
                            if ready["pid"] != process.pid:
                                worker_handle = windows.open(ready["pid"])
                                query_handles.append(worker_handle)
                                worker = windows.observe(worker_handle)
                            process_identity = verify("owned-live-process-identity", _validate_windows_identity,
                                ready, process.pid, os.getpid(), parent, worker, launch_before, windows.now(),
                                str(Path(sys.executable).resolve()), str(Path(sys._base_executable).resolve()))
                        else:
                            process_identity = verify("owned-live-process-identity", _validate_direct_identity,
                                                      ready, process.pid, os.getpid())
                        listing = await session.list_tools()
                        names = sorted(tool.name for tool in listing.tools)
                        check("exactly-three-read-only-tools", names == [
                            "operator_capabilities", "operator_receipt", "operator_request_status"])
                        check("annotations-and-closed-input-schema", all(
                            tool.annotations is not None and tool.annotations.read_only_hint is True and
                            tool.input_schema.get("additionalProperties") is False for tool in listing.tools))
                        check("discoverable-closed-object-output-schemas", all(
                            isinstance(tool.output_schema, dict) and tool.output_schema.get("type") == "object" and
                            tool.output_schema.get("additionalProperties") is False for tool in listing.tools))
                        caps = await session.call_tool("operator_capabilities", {})
                        check("capabilities-not-probed", not caps.is_error and
                              caps.structured_content["runtime_probes_performed"] is False and
                              caps.structured_content["actions_exposed"] is False)
                        check("capabilities-redacted", "SENSITIVE_SENTINEL" not in json.dumps(caps.structured_content))
                        check("structured-output-keeps-json-text", _matching_result_channels(caps))
                        receipt = await session.call_tool("operator_receipt", {"request_id": "fixture-receipt"})
                        check("receipt-json-text-matches-structured-output", _matching_result_channels(receipt))
                        check("exact-saved-receipt", not receipt.is_error and
                              _same_json(receipt.structured_content["receipt"], expected))
                        check("read-does-not-claim-live-verification", receipt.structured_content[
                            "live_verification_performed"] is False and expected["status"] == "outcome_unknown")
                        invalid = await session.call_tool("operator_receipt", {"request_id": "../outside"})
                        check("invalid-path-id-refused", invalid.is_error and
                              invalid.structured_content["error"]["code"] == "invalid_request_id")
                        override = await session.call_tool("operator_receipt", {
                            "request_id": "fixture-receipt", "state": str(fixture / "outside")})
                        check("scope-override-refused", override.is_error and
                              override.structured_content["error"]["code"] == "invalid_arguments")
                        extra = await session.call_tool("operator_capabilities", {"run_doctor": True})
                        check("extra-capability-argument-refused", extra.is_error)
                        missing = await session.call_tool("operator_receipt", {"request_id": "missing"})
                        check("missing-receipt-refused", missing.is_error and
                              missing.structured_content["error"]["code"] == "receipt_not_found")
                        status_results = {}
                        for rid, expected_state, saved_status in (
                                ("fixture-receipt", "receipt_recorded", "outcome_unknown"),
                                ("fixture-intent", "intent_without_receipt", None),
                                ("missing", "no_records_observed", None),
                                ("fixture-orphan", "inconclusive", None),
                                ("fixture-mismatch", "inconclusive", None)):
                            result = await session.call_tool("operator_request_status", {"request_id": rid})
                            check(f"status-json-text-matches-{rid}", _matching_result_channels(result))
                            check(f"saved-status-{rid}", not result.is_error and
                                  result.structured_content["record_state"] == expected_state and
                                  result.structured_content["saved_receipt_status"] == saved_status)
                            status_results[rid] = result.structured_content
                        check("status-summary-redacts-record-content", "STATUS_PRIVATE_SENTINEL" not in
                              json.dumps(status_results) and all("intent" not in value and "receipt" not in value
                                                               for value in status_results.values()))
                        check("status-summary-never-claims-live-or-atomic-verification", all(
                            value["snapshot_atomic"] is False and value["live_verification_performed"] is False and
                            value["record_authenticity_verified"] is False and value["actions_exposed"] is False
                            for value in status_results.values()))
                        status_override = await session.call_tool("operator_request_status", {
                            "request_id": "fixture-intent", "state": str(fixture / "outside")})
                        check("status-scope-override-refused", status_override.is_error and
                              status_override.structured_content["error"]["code"] == "invalid_arguments")
                        # Only the owned fixture launcher injects this malformed
                        # success value. It must fail server-side output validation,
                        # rather than merely publishing a decorative output schema.
                        invalid_output = await session.call_tool("operator_request_status", {
                            "request_id": "fixture-schema-invalid"})
                        check("sdk-rejects-injected-invalid-success-output", invalid_output.is_error is True)
        check("held-process-exit-zero", captured_processes[0].returncode == 0)
        witness = json.loads(exit_witness.read_text("utf-8"))
        verify("normal-return-after-stdin-eof", _validate_return_witness, witness, ready)
        if windows:
            worker_exit = verify("held-worker-handle-exit-zero", windows.exited,
                                 worker_handle, process_identity["worker"])
        check("sdk-parsed-stdout-has-no-nonprotocol-lines", bool(raw_lines) and not parser_errors)
        status, error = "passed", None
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        for handle in reversed(query_handles):
            try:
                windows.close(handle)
            except OSError as exc:
                status, error = "failed", f"query handle close failed: {exc}"
        # Record lines actually consumed by the SDK parser. The SDK can discard
        # shutdown drain bytes; this is not a claim about unobserved drain bytes.
        (evidence / "server.stdout.ndjson").write_text("\n".join(raw_lines) + ("\n" if raw_lines else ""),
                                                     encoding="utf-8")
    return {"mode": mode, "protocol_version": negotiated, "status": status, "checks": checks,
            "error": error, "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "owned_processes": [{"pid": proc.pid, "exit_code": proc.returncode} for proc in captured_processes],
            "protocol_lines_observed": len(raw_lines), "parser_errors": parser_errors,
            "ready_witness": str(ready_witness), "process_identity": process_identity,
            "held_worker_exit": worker_exit,
            "normal_eof_witness": str(exit_witness),
            "stdout_scope": "lines consumed by the official SDK parser; shutdown drain not independently captured"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="new, nonexistent evidence directory")
    parser.add_argument("--mode", choices=["modern", "legacy", "both"], default="both")
    args = parser.parse_args()
    try:
        require_sdk()
    except KitError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    if args.output_dir:
        output = args.output_dir.absolute()
        output.mkdir(parents=True, exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix="rdck-mcp-"))
    fixture = output / "fixture 中文 space"
    fixture.mkdir()
    state = fixture / "state"
    (state / "requests").mkdir(parents=True)
    config = fixture / "config.json"
    atomic_json(config, {"schema_version": 1, "smartcli": ["SENSITIVE_SENTINEL_EXECUTABLE"],
                         "winapp": [], "omp": {"wrapper": "SENSITIVE_SENTINEL_WRAPPER"},
                         "allowed_roots": [str(fixture)]})
    expected = {"schema_version": 1, "request_id": "fixture-receipt", "status": "outcome_unknown",
                "digest": "a" * 64,
                "result": {"nonce": uuid.uuid4().hex, "semantic_verified": False},
                "fixture": "synthetic saved receipt; no operation was executed"}
    receipt = state / "requests" / "fixture-receipt.receipt.json"
    atomic_json(receipt, expected)
    original_hash = _digest(receipt)
    for rid in ("fixture-receipt", "fixture-intent", "fixture-mismatch"):
        atomic_json(state / "requests" / f"{rid}.intent.json", {
            "schema_version": 1, "request_id": rid, "state": "prepared", "digest": "a" * 64,
            "action": "STATUS_PRIVATE_SENTINEL_ACTION", "args": {
                "command": "STATUS_PRIVATE_SENTINEL_COMMAND", "path": "STATUS_PRIVATE_SENTINEL_PATH"}})
    for rid in ("fixture-orphan", "fixture-mismatch"):
        atomic_json(state / "requests" / f"{rid}.receipt.json", dict(expected, request_id=rid,
            digest="b" * 64, status="completed", result={"output": "STATUS_PRIVATE_SENTINEL_OUTPUT"}))
    original_records = {path.name: _digest(path) for path in (state / "requests").iterdir()}
    launcher = fixture / "server_fixture_launcher.py"
    launcher.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(PROJECT)!r})\n"
        "from rdc_operator.common import atomic_json\n"
        "from rdc_operator.mcp_server import ReadOnlyOperator, main\n"
        "original_call=ReadOnlyOperator.call\n"
        "def fixture_call(self,name,arguments):\n"
        "    value=original_call(self,name,arguments)\n"
        "    if name=='operator_request_status' and arguments.get('request_id')=='fixture-schema-invalid':\n"
        "        return dict(value,snapshot_atomic=0)\n"
        "    return value\n"
        "ReadOnlyOperator.call=fixture_call\n"
        "identity={'nonce':sys.argv[5],'pid':os.getpid(),'ppid':os.getppid()}\n"
        "atomic_json(Path(sys.argv[3]),dict(identity,stage='ready'))\n"
        "code=main(['--config',sys.argv[1],'--state',sys.argv[2]])\n"
        "atomic_json(Path(sys.argv[4]),dict(identity,stage='returned',exit_code=code,returned_from_server=True))\n"
        "raise SystemExit(code)\n", encoding="utf-8")
    import anyio
    async def run():
        results = []
        for mode in (["modern", "legacy"] if args.mode == "both" else [args.mode]):
            results.append(await one_session(mode, fixture, config, state, launcher, expected))
        return results
    results = anyio.run(run)
    unchanged = _digest(receipt) == original_hash
    records_unchanged = {path.name: _digest(path) for path in (state / "requests").iterdir()} == original_records
    try:
        kit_distribution_version = importlib.metadata.version("rdc-operator-kit")
    except importlib.metadata.PackageNotFoundError:
        kit_distribution_version = None
    report = {"schema_version": 1, "status": "passed" if unchanged and records_unchanged and all(
        item["status"] == "passed" for item in results) else "failed",
        "tested_at_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "sdk_version": SDK_VERSION,
        "smoke_execution": "source_tree", "installed_package_validation": False,
        "kit_source_version": rdc_operator.__version__, "kit_module_file": str(Path(rdc_operator.__file__).resolve()),
        "kit_distribution_version": kit_distribution_version,
        "scope": "real SDK stdio processes, synthetic read-only fixtures; no desktop, terminal, browser or models",
        "fault_injection": "owned launcher returns integer 0 for one false-only status flag; SDK must reject it",
        "receipt_unchanged": unchanged, "request_records_unchanged": records_unchanged, "sessions": results,
        "source_sha256": {str(path.relative_to(PROJECT)): _digest(path) for path in
                          [PROJECT / "rdc_operator/__init__.py", PROJECT / "rdc_operator/mcp_server.py",
                           Path(__file__).resolve()]},
        "dependencies": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
                         if dist.metadata.get("Name")}}
    atomic_json(output / "summary.json", report)
    print(json.dumps({"status": report["status"], "summary": str(output / "summary.json"),
                      "protocols_tested": [item["protocol_version"] for item in results],
                      "receipt_unchanged": unchanged, "request_records_unchanged": records_unchanged},
                     ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

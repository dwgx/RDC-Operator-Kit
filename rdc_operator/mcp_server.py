"""Optional, read-only stdio transport. No HTTP or action execution tools.

The business contract imports without the MCP extra. Protocol handling belongs
to the pinned official SDK; config and state are trusted operator startup inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Annotated, Literal

from . import __version__
from .common import KitError, read_json


SDK_VERSION = "2.3.0"
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
TOOL_FIELDS = {"operator_capabilities": set(), "operator_receipt": {"request_id"},
               "operator_request_status": {"request_id"}}
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_STATUSES = {"observed", "completed", "failed", "outcome_unknown"}
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


def require_sdk() -> None:
    try:
        installed = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    if installed != SDK_VERSION:
        found = installed or "not installed"
        raise KitError("mcp_dependency_required",
                       f"This entry requires mcp=={SDK_VERSION}; found {found}. "
                       "Install the project's optional [mcp] extra in its private environment.")


def _unlinked(path: Path) -> None:
    """Reject symlinks and Windows reparse points in every existing component."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) &
                                         getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            raise KitError("unsafe_state", "State and receipts cannot use links or reparse points")


def _opened_windows_path(fd: int) -> str:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = kernel.GetFinalPathNameByHandleW
    fn.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    fn.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    size = fn(msvcrt.get_osfhandle(fd), buffer, len(buffer), 0)
    if not size or size >= len(buffer):
        raise KitError("unsafe_state", "Cannot verify the opened receipt's final path")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.normpath(value))


def _open_receipt(path: Path) -> int:
    _unlinked(path)
    if os.name == "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            # Verify the opened HANDLE, before reading bytes, so a redirected
            # parent path cannot turn a tool argument into an outside-file read.
            if _opened_windows_path(fd) != os.path.normcase(os.path.normpath(str(path))):
                raise KitError("unsafe_state", "Opened receipt is outside the fixed path")
            _unlinked(path)
            return fd
        except BaseException:
            os.close(fd)
            raise
    # Walk by directory descriptors, never following an intermediate symlink.
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise KitError("unsupported_platform", "Safe local receipt opening is unavailable")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            following = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=directory)
            os.close(directory)
            directory = following
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                       dir_fd=directory)
    finally:
        os.close(directory)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("non-finite JSON number")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def _read_saved_record(path: Path, kind: str):
    """Read a bounded opened snapshot; kind is an internal constant, never input."""
    try:
        fd = _open_receipt(path)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise KitError(f"unsafe_{kind}", f"{kind.capitalize()} must be a regular file without hard links")
            if before.st_size > MAX_RECEIPT_BYTES:
                raise KitError(f"{kind}_too_large", f"Saved {kind} exceeds the 8 MiB limit")
            raw = handle.read(MAX_RECEIPT_BYTES + 1)
            after = os.fstat(handle.fileno())
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                      value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
            if identity(before) != identity(after) or len(raw) != after.st_size:
                raise KitError(f"{kind}_changed", f"Saved {kind} changed while being read")
            if len(raw) > MAX_RECEIPT_BYTES:
                raise KitError(f"{kind}_too_large", f"Saved {kind} exceeds the 8 MiB limit")
        record = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                            parse_constant=_nonfinite, parse_float=_finite_float)
        # Kept internal. Comparing bytes as well as file identity detects a
        # replacement between status samples even when selected fields agree.
        return record, (*identity(after), hashlib.sha256(raw).digest())
    except KitError:
        raise
    except FileNotFoundError as exc:
        raise KitError(f"{kind}_not_found", f"No saved {kind} for this request ID") from exc
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise KitError(f"{kind}_unreadable", f"Saved {kind} is unavailable or malformed") from exc


def _validate_receipt(receipt, rid):
    if (not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int or
            receipt.get("schema_version") != 1 or receipt.get("request_id") != rid or
            not isinstance(receipt.get("status"), str) or receipt.get("status") not in _RECEIPT_STATUSES):
        raise KitError("invalid_receipt", "Saved receipt identity or status does not match")


class ReadOnlyOperator:
    def __init__(self, config: dict, state: Path):
        if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
            raise KitError("invalid_config", "Config schema_version must be 1")
        self._state = Path(os.path.abspath(Path(state).expanduser()))
        try:
            _unlinked(self._state)
        except OSError as exc:
            raise KitError("unsafe_state", "Cannot inspect the configured state path") from exc
        def configured_argv(value):
            return isinstance(value, list) and bool(value) and all(
                isinstance(item, str) and bool(item) and "\0" not in item for item in value)
        route = config.get("omp")
        self._configured = {
            "terminal": configured_argv(config.get("smartcli")),
            "desktop": configured_argv(config.get("winapp")),
            "omp_preview": isinstance(route, dict) and isinstance(route.get("wrapper"), str)
                           and bool(route["wrapper"]) and "\0" not in route["wrapper"],
        }

    @staticmethod
    def validate_arguments(name: str, arguments: dict) -> None:
        if name not in TOOL_FIELDS:
            raise KitError("unsupported_tool", "This server exposes only the read-only tools")
        if not isinstance(arguments, dict) or set(arguments) != TOOL_FIELDS[name]:
            raise KitError("invalid_arguments", "Unexpected or missing tool arguments")
        if "request_id" in TOOL_FIELDS[name]:
            rid = arguments["request_id"]
            if not isinstance(rid, str) or not _REQUEST_ID.fullmatch(rid) or rid.upper() in _RESERVED:
                raise KitError("invalid_request_id", "Use a valid Kit request ID, never a path")

    def call(self, name: str, arguments: dict) -> dict:
        self.validate_arguments(name, arguments)
        if name == "operator_capabilities":
            return {"schema_version": 1, "kit_version": __version__, "transport": "stdio",
                    "sdk_required": SDK_VERSION, "mode": "read_only", "tools": sorted(TOOL_FIELDS),
                    "configured": dict(self._configured), "runtime_probes_performed": False,
                    "actions_exposed": False, "receipt_scope": "saved_results_only"}
        rid = arguments["request_id"]
        if name == "operator_request_status":
            return self._request_status(rid)
        receipt, _ = _read_saved_record(self._state / "requests" / f"{rid}.receipt.json", "receipt")
        _validate_receipt(receipt, rid)
        return {"schema_version": 1, "source": "saved_receipt", "receipt": receipt,
                "live_verification_performed": False, "receipt_authenticity_verified": False}

    def _status_sample(self, rid):
        sample = {}
        for kind in ("intent", "receipt"):
            try:
                record, fingerprint = _read_saved_record(
                    self._state / "requests" / f"{rid}.{kind}.json", kind)
            except KitError as exc:
                if exc.code == f"{kind}_not_found":
                    sample[kind] = None
                    continue
                raise
            digest = record.get("digest") if isinstance(record, dict) else None
            valid_digest = isinstance(digest, str) and _DIGEST.fullmatch(digest) is not None
            if kind == "intent":
                if (not isinstance(record, dict) or type(record.get("schema_version")) is not int or
                        record.get("schema_version") != 1 or record.get("request_id") != rid or
                        record.get("state") != "prepared" or not valid_digest):
                    raise KitError("invalid_intent", "Saved intent identity or preparation state does not match")
            else:
                _validate_receipt(record, rid)
            # Do not retain or expose arbitrary intent arguments, commands,
            # paths, action names, timestamps or receipt output in this summary.
            sample[kind] = (fingerprint, digest if valid_digest else None,
                            record.get("status") if kind == "receipt" else None)
        return sample

    def _request_status(self, rid):
        first, second = self._status_sample(rid), self._status_sample(rid)
        state, reason, saved_status = "inconclusive", "records_changed_during_observation", None
        if first == second:
            intent, receipt = second["intent"], second["receipt"]
            if intent is None and receipt is None:
                state, reason = "no_records_observed", "no_records_observed"
            elif receipt is None:
                state, reason = "intent_without_receipt", "receipt_not_observed"
            elif intent is None:
                reason = "receipt_without_intent"
            elif receipt[1] != intent[1]:
                reason = "record_digest_mismatch"
            else:
                state, reason, saved_status = "receipt_recorded", "matching_saved_records", receipt[2]
        return {"schema_version": 1, "source": "saved_request_records", "request_id": rid,
                "record_state": state, "reason": reason, "saved_receipt_status": saved_status,
                "snapshot_atomic": False, "live_verification_performed": False,
                "record_authenticity_verified": False, "actions_exposed": False}


def build_server(operator: ReadOnlyOperator):
    require_sdk()
    from mcp.server import MCPServer
    from mcp.types import CallToolResult, TextContent, ToolAnnotations
    from pydantic import BeforeValidator, ConfigDict, create_model

    def exact_false(value):
        if value is not False:
            raise ValueError("This field must be the JSON boolean false")
        return value

    def exact_version(value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the JSON integer 1")
        return value

    false_flag = Annotated[Literal[False], BeforeValidator(exact_false)]
    schema_version = Annotated[Literal[1], BeforeValidator(exact_version)]

    def output_model(name, **fields):
        return create_model(name, __config__=ConfigDict(extra="forbid", strict=True),
                            **{key: (value, ...) for key, value in fields.items()})

    configured_model = output_model("OperatorConfigured", terminal=bool, desktop=bool, omp_preview=bool)
    saved_receipt_model = create_model("SavedKitReceipt", __config__=ConfigDict(extra="allow", strict=True),
        schema_version=(schema_version, ...), request_id=(str, ...),
        status=(Literal["observed", "completed", "failed", "outcome_unknown"], ...))
    capabilities_model = output_model("OperatorCapabilities", schema_version=schema_version, kit_version=str,
        transport=Literal["stdio"], sdk_required=Literal["2.3.0"], mode=Literal["read_only"],
        tools=list[Literal["operator_capabilities", "operator_receipt", "operator_request_status"]],
        configured=configured_model, runtime_probes_performed=false_flag,
        actions_exposed=false_flag, receipt_scope=Literal["saved_results_only"])
    receipt_model = output_model("OperatorReceipt", schema_version=schema_version, source=Literal["saved_receipt"],
        receipt=saved_receipt_model, live_verification_performed=false_flag,
        receipt_authenticity_verified=false_flag)
    status_model = output_model("OperatorRequestStatus", schema_version=schema_version,
        source=Literal["saved_request_records"], request_id=str,
        record_state=Literal["no_records_observed", "intent_without_receipt", "receipt_recorded", "inconclusive"],
        reason=Literal["no_records_observed", "receipt_not_observed", "matching_saved_records",
                       "records_changed_during_observation", "receipt_without_intent", "record_digest_mismatch"],
        saved_receipt_status=Literal["observed", "completed", "failed", "outcome_unknown"] | None,
        snapshot_atomic=false_flag, live_verification_performed=false_flag,
        record_authenticity_verified=false_flag, actions_exposed=false_flag)

    def as_result(value=None, error=None):
        payload = {"error": {"code": error.code, "message": error.message}} if error else value
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False,
                                                                                allow_nan=False))],
                              structured_content=payload, is_error=error is not None)

    async def strict_arguments(ctx, call_next):
        # SDK 2.3.0's function argument models ignore extra fields by default.
        # This supported middleware seam keeps our business contract exact.
        if ctx.method == "tools/call" and isinstance(ctx.params, dict):
            name = ctx.params.get("name")
            if isinstance(name, str) and name in TOOL_FIELDS:
                try:
                    operator.validate_arguments(name, ctx.params.get("arguments", {}))
                except KitError as exc:
                    return as_result(error=exc)
        result = await call_next(ctx)
        if ctx.method == "tools/list":
            # The context middleware receives serialized results in the live
            # runner, while direct SDK handlers can return typed results.
            if isinstance(result, dict):
                for tool in result.get("tools", []):
                    if isinstance(tool, dict) and tool.get("name") in TOOL_FIELDS:
                        tool["inputSchema"]["additionalProperties"] = False
            elif hasattr(result, "tools"):
                for tool in result.tools:
                    if tool.name in TOOL_FIELDS:
                        tool.input_schema["additionalProperties"] = False
        return result

    server = MCPServer("RDC Operator Kit Read-only", version=__version__, subscriptions=False,
                       log_level="WARNING", middleware=[strict_arguments],
                       instructions="Only describe configuration or read saved request records. No action execution. "
                                    "Saved records do not establish live progress, cancellation or workflow success.")
    annotations = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                  idempotent_hint=True, open_world_hint=False)

    def operator_capabilities():
        """Describe static configuration. Does not probe programs, devices or model services."""
        return as_result(operator.call("operator_capabilities", {}))

    def operator_receipt(request_id: str):
        """Read one saved Kit receipt by ID. No path input; no replay, actions or live verification."""
        try:
            return as_result(operator.call("operator_receipt", {"request_id": request_id}))
        except KitError as exc:
            return as_result(error=exc)

    def operator_request_status(request_id: str):
        """Summarize saved intent/receipt records only. No live running state, cancellation, replay or success claim."""
        try:
            return as_result(operator.call("operator_request_status", {"request_id": request_id}))
        except KitError as exc:
            return as_result(error=exc)

    for function, model in ((operator_capabilities, capabilities_model), (operator_receipt, receipt_model),
                            (operator_request_status, status_model)):
        # Resolve the local SDK/model types now: future-annotation strings would
        # not be resolvable from these functions' module globals. SDK 2.3 validates
        # successful manual CallToolResult values through this Annotated model.
        function.__annotations__["return"] = Annotated[CallToolResult, model]
        server.tool(annotations=annotations, structured_output=True)(function)

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="RDC Operator Kit optional read-only MCP stdio server")
    parser.add_argument("--config", type=Path, required=True, help="trusted operator config path")
    parser.add_argument("--state", type=Path, required=True, help="fixed local receipt state")
    args = parser.parse_args(argv)
    try:
        require_sdk()
        operator = ReadOnlyOperator(read_json(args.config), args.state)
        build_server(operator).run("stdio")
        return 0
    except KitError as exc:
        print(f"rdc-kit-mcp: {exc.code}: {exc.message}", file=sys.stderr)
        return 2
    except (OSError, ImportError) as exc:
        print(f"rdc-kit-mcp: startup_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

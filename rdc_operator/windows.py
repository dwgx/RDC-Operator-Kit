"""Read-only Windows input-context diagnostics, not an input or elevation broker.

The native snapshot is deliberately separate from its conservative assessment.
No result grants authority, proves that a click will work, or identifies a UAC
prompt from a missing foreground window. DLLs are loaded only on Windows.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import struct
import time

from .common import KitError


def _known_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def assess_windows_context(facts: dict) -> dict:
    """Classify observed facts without native calls or input side effects.

    ``observed`` means the listed checks found no mismatch in this snapshot.
    It is intentionally not named ``ready``: authorization, application state,
    session connection, and subsequent focus changes remain outside this probe.
    """
    risks = []

    def risk(code: str, level: str, message: str) -> None:
        risks.append({"code": code, "level": level, "message": message})

    if facts.get("supported") is not True:
        return {"status": "unsupported", "input_performed": False,
                "permission_granted": False, "uac_state": "not_determined",
                "risks": [{"code": "unsupported_platform", "level": "unknown",
                           "message": "This collector requires Windows"}]}

    collector = facts.get("collector") or {}
    desktop = facts.get("desktop") or {}
    foreground = facts.get("foreground") or {}
    target = facts.get("target")
    own_token = collector.get("token") or {}

    if not _known_integer(collector.get("session_id")):
        risk("collector_session_unknown", "unknown", "Collector session could not be read")
    if not _known_integer(own_token.get("integrity_rid")):
        risk("collector_integrity_unknown", "unknown", "Collector integrity could not be read")
    if type(own_token.get("ui_access")) is not bool:
        risk("collector_uiaccess_unknown", "unknown", "Collector UIAccess flag could not be read")

    station = desktop.get("window_station") or {}
    thread = desktop.get("thread") or {}
    input_desktop = desktop.get("input") or {}
    if station.get("visible") is False:
        risk("noninteractive_window_station", "blocked", "Collector window station is not visible")
    elif station.get("visible") is not True:
        risk("window_station_unknown", "unknown", "Window station visibility is unknown")
    thread_name, input_name = thread.get("name"), input_desktop.get("name")
    if not thread_name or not input_name:
        risk("desktop_unknown", "unknown", "Thread or input desktop could not be read; cause is undetermined")
    elif thread_name.casefold() != input_name.casefold():
        risk("desktop_mismatch", "blocked", "Collector thread is not on the observed input desktop")
    if input_name and input_name.casefold() in {"winlogon", "disconnect"}:
        risk("protected_desktop_observed", "blocked", "Observed desktop is not a supported ordinary input desktop")
    for label, value in (("thread", thread.get("receives_input")),
                         ("input", input_desktop.get("receives_input"))):
        if value is False:
            risk(f"{label}_desktop_not_receiving_input", "blocked", f"Observed {label} desktop is not receiving input")
        elif value is not True:
            risk(f"{label}_desktop_input_unknown", "unknown", f"Whether the {label} desktop receives input is unknown")

    foreground_window = foreground.get("window")
    if not _known_integer(foreground_window) or foreground_window == 0:
        risk("foreground_unknown", "unknown", "No foreground HWND was observed; this alone does not identify UAC or a lock")
    if foreground.get("stable") is not True:
        risk("foreground_changed_or_unknown", "unknown", "Foreground was not stable across the diagnostic sample")

    if target is None:
        risk("target_not_provided", "unknown", "No target HWND was supplied; no target-specific assessment is possible")
    else:
        if target.get("exists") is False:
            risk("window_not_found", "blocked", "The requested HWND was not a current window")
        elif target.get("identity_stable") is False:
            risk("target_identity_changed", "blocked", "Target HWND/process identity changed during the sample")
        elif target.get("identity_stable") is not True:
            risk("target_identity_unknown", "unknown", "Stable target process identity could not be established")
        own_session, target_session = collector.get("session_id"), target.get("session_id")
        if not _known_integer(target_session):
            risk("target_session_unknown", "unknown", "Target session could not be read")
        elif _known_integer(own_session) and own_session != target_session:
            risk("session_mismatch", "blocked", "Collector and target belong to different Windows sessions")
        target_token = target.get("token") or {}
        own_il, target_il = own_token.get("integrity_rid"), target_token.get("integrity_rid")
        if not _known_integer(target_il):
            risk("target_integrity_unknown", "unknown", "Target integrity could not be read")
        elif _known_integer(own_il) and target_il > own_il:
            # UIAccess is a fact, not a blanket cross-IL or secure-desktop permit.
            risk("higher_integrity_target", "blocked", "Target integrity is higher; this probe does not authorize cross-integrity input, even with UIAccess")
        if (_known_integer(foreground_window) and foreground_window != 0 and
                foreground_window != target.get("window")):
            risk("foreground_not_target", "blocked", "The exact target HWND does not own the observed foreground")

    if facts.get("errors"):
        risk("native_queries_incomplete", "unknown", "Some native queries failed; inspect their individual errors")
    status = ("blocked" if any(r["level"] == "blocked" for r in risks) else
              "unknown" if risks else "observed")
    return {"status": status, "input_performed": False, "permission_granted": False,
            "uac_state": "not_determined", "risks": risks,
            "limitations": [
                "This is a non-atomic diagnostic snapshot, not an input-success guarantee",
                "Session connection, application effects and user authorization are not verified",
                "A subsequent action must recheck identity, foreground and desktop state",
                "Same-process HWND replacement between samples may not be detectable",
            ]}


class _WindowsQuery:
    """Only native read APIs; owned handles are closed by their matching API."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.c, self.w = ctypes, wintypes
        # Restrict the DLL search to Windows' system directory.
        self.k = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        self.u = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
        self.a = ctypes.WinDLL("advapi32", use_last_error=True, winmode=0x800)
        self.errors: list[dict] = []
        pointer = ctypes.POINTER
        handle, dword, boolean = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
        void, hwnd = ctypes.c_void_p, wintypes.HWND

        declarations = [
            (self.k, "GetCurrentProcessId", [], dword),
            (self.k, "GetCurrentThreadId", [], dword),
            (self.k, "OpenProcess", [dword, boolean, dword], handle),
            (self.k, "CloseHandle", [handle], boolean),
            (self.k, "GetProcessTimes", [handle] + [pointer(wintypes.FILETIME)] * 4, boolean),
            (self.k, "ProcessIdToSessionId", [dword, pointer(dword)], boolean),
            (self.u, "IsWindow", [hwnd], boolean),
            (self.u, "GetWindowThreadProcessId", [hwnd, pointer(dword)], dword),
            (self.u, "GetForegroundWindow", [], hwnd),
            (self.u, "GetProcessWindowStation", [], handle),
            (self.u, "GetThreadDesktop", [dword], handle),
            (self.u, "OpenInputDesktop", [dword, boolean, dword], handle),
            (self.u, "CloseDesktop", [handle], boolean),
            (self.u, "GetUserObjectInformationW", [handle, ctypes.c_int, void, dword, pointer(dword)], boolean),
            (self.a, "OpenProcessToken", [handle, dword, pointer(handle)], boolean),
            (self.a, "GetTokenInformation", [handle, ctypes.c_int, void, dword, pointer(dword)], boolean),
        ]
        for library, name, args, result in declarations:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result

        class UserObjectFlags(ctypes.Structure):
            _fields_ = [("inherit", boolean), ("reserved", boolean), ("flags", dword)]

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", void), ("attributes", dword)]

        self.UserObjectFlags = UserObjectFlags
        self.SidAndAttributes = SidAndAttributes

    def _error(self, operation: str, reason: str = "native_query_failed", *, native: bool = True) -> None:
        self.errors.append({"operation": operation, "reason": reason,
                            "winerror": self.c.get_last_error() if native else None})

    def _close(self, handle, *, desktop: bool = False) -> None:
        self.c.set_last_error(0)
        name = "CloseDesktop" if desktop else "CloseHandle"
        function = self.u.CloseDesktop if desktop else self.k.CloseHandle
        if not function(handle):
            self._error(name)

    def _creation_time(self, process) -> str | None:
        values = [self.w.FILETIME() for _ in range(4)]
        self.c.set_last_error(0)
        if not self.k.GetProcessTimes(process, *(self.c.byref(v) for v in values)):
            self._error("GetProcessTimes")
            return None
        return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)

    def _session_id(self, pid: int) -> int | None:
        value = self.w.DWORD()
        self.c.set_last_error(0)
        if not self.k.ProcessIdToSessionId(pid, self.c.byref(value)):
            self._error("ProcessIdToSessionId")
            return None
        return int(value.value)

    def _token_information(self, token, information_class: int):
        needed = self.w.DWORD()
        self.c.set_last_error(0)
        self.a.GetTokenInformation(token, information_class, None, 0, self.c.byref(needed))
        if not 0 < needed.value <= 65536:
            self._error(f"GetTokenInformation({information_class})")
            return None
        buffer = self.c.create_string_buffer(needed.value)
        self.c.set_last_error(0)
        if not self.a.GetTokenInformation(token, information_class, buffer, len(buffer), self.c.byref(needed)):
            self._error(f"GetTokenInformation({information_class})")
            return None
        if needed.value > len(buffer):
            self._error(f"GetTokenInformation({information_class})", "invalid_native_result", native=False)
            return None
        return buffer, int(needed.value)

    def _token(self, process) -> dict:
        answer = {"integrity_rid": None, "integrity": None, "elevated": None,
                  "elevation_type": None, "ui_access": None}
        token = self.w.HANDLE()
        self.c.set_last_error(0)
        if not self.a.OpenProcessToken(process, 0x0008, self.c.byref(token)):  # TOKEN_QUERY
            self._error("OpenProcessToken")
            return answer
        try:
            for key, value_class, is_bool in (("elevation_type", 18, False),
                                               ("elevated", 20, True),
                                               ("ui_access", 26, True)):
                data = self._token_information(token, value_class)
                if data is not None:
                    buffer, length = data
                    if length >= self.c.sizeof(self.w.DWORD):
                        value = self.w.DWORD.from_buffer_copy(buffer).value
                        answer[key] = bool(value) if is_bool else int(value)
                    else:
                        self._error(f"GetTokenInformation({value_class})", "short_native_result", native=False)
            data = self._token_information(token, 25)  # TokenIntegrityLevel
            if data is not None:
                buffer, length = data
                base = self.c.addressof(buffer)
                if length < self.c.sizeof(self.SidAndAttributes):
                    self._error("TokenIntegrityLevel", "short_native_result", native=False)
                else:
                    sid = self.SidAndAttributes.from_buffer_copy(buffer).sid or 0
                    # A SID's fixed header is eight bytes followed by DWORD
                    # subauthorities. Bound every read to the API-owned buffer;
                    # no unverified native pointer is dereferenced.
                    offset = sid - base
                    if offset < 0 or offset + 8 > length:
                        self._error("TokenIntegrityLevel", "invalid_sid_pointer", native=False)
                    else:
                        raw = buffer.raw
                        revision, count = raw[offset], raw[offset + 1]
                        end = offset + 8 + 4 * count
                        if revision != 1 or not 1 <= count <= 15 or end > length:
                            self._error("TokenIntegrityLevel", "invalid_sid_layout", native=False)
                        else:
                            rid = int.from_bytes(raw[end - 4:end], "little")
                            answer["integrity_rid"] = rid
                            answer["integrity"] = {
                                0x0000: "untrusted", 0x1000: "low", 0x2000: "medium",
                                0x2100: "medium_plus", 0x3000: "high", 0x4000: "system",
                                0x5000: "protected_process",
                            }.get(rid, "other")
        finally:
            self._close(token)
        return answer

    def _process(self, pid: int, *, token: bool = True) -> dict:
        answer = {"pid": pid, "session_id": self._session_id(pid), "process_started": None}
        if token:
            answer["token"] = {"integrity_rid": None, "integrity": None,
                               "elevated": None, "elevation_type": None, "ui_access": None}
        self.c.set_last_error(0)
        process = self.k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            self._error("OpenProcess")
            return answer
        try:
            answer["process_started"] = self._creation_time(process)
            if token:
                answer["token"] = self._token(process)
        finally:
            self._close(process)
        return answer

    def _window(self, window: int, *, token: bool) -> dict:
        answer = {"window": window, "exists": bool(self.u.IsWindow(window)),
                  "pid": None, "thread_id": None, "process_started": None,
                  "session_id": None}
        if not answer["exists"]:
            return answer
        pid = self.w.DWORD()
        self.c.set_last_error(0)
        thread = self.u.GetWindowThreadProcessId(window, self.c.byref(pid))
        if not thread or not pid.value:
            self._error("GetWindowThreadProcessId")
            return answer
        answer["thread_id"] = int(thread)
        answer.update(self._process(int(pid.value), token=token))
        return answer

    def _object_name(self, handle) -> str | None:
        needed = self.w.DWORD()
        self.c.set_last_error(0)
        self.u.GetUserObjectInformationW(handle, 2, None, 0, self.c.byref(needed))
        if not 0 < needed.value <= 65536:
            self._error("GetUserObjectInformationW(UOI_NAME)")
            return None
        chars = (needed.value + self.c.sizeof(self.c.c_wchar) - 1) // self.c.sizeof(self.c.c_wchar)
        buffer = self.c.create_unicode_buffer(chars + 1)
        self.c.set_last_error(0)
        if not self.u.GetUserObjectInformationW(handle, 2, buffer, self.c.sizeof(buffer), self.c.byref(needed)):
            self._error("GetUserObjectInformationW(UOI_NAME)")
            return None
        return buffer.value

    def _desktop(self, handle) -> dict:
        answer = {"name": None, "receives_input": None}
        if handle:
            answer["name"] = self._object_name(handle)
            receiving, needed = self.w.BOOL(), self.w.DWORD()
            self.c.set_last_error(0)
            if self.u.GetUserObjectInformationW(handle, 6, self.c.byref(receiving), self.c.sizeof(receiving), self.c.byref(needed)):
                answer["receives_input"] = bool(receiving.value)
            else:
                self._error("GetUserObjectInformationW(UOI_IO)")
        return answer

    def _desktop_context(self) -> dict:
        self.c.set_last_error(0)
        station = self.u.GetProcessWindowStation()  # borrowed; do not close
        station_facts = {"name": None, "visible": None}
        if station:
            station_facts["name"] = self._object_name(station)
            flags, needed = self.UserObjectFlags(), self.w.DWORD()
            self.c.set_last_error(0)
            if self.u.GetUserObjectInformationW(station, 1, self.c.byref(flags), self.c.sizeof(flags), self.c.byref(needed)):
                station_facts["visible"] = bool(flags.flags & 1)  # WSF_VISIBLE
            else:
                self._error("GetUserObjectInformationW(UOI_FLAGS)")
        else:
            self._error("GetProcessWindowStation")
        thread_id = self.k.GetCurrentThreadId()
        self.c.set_last_error(0)
        thread = self.u.GetThreadDesktop(thread_id)  # borrowed; do not close
        if not thread:
            self._error("GetThreadDesktop")
        thread_facts = self._desktop(thread)
        self.c.set_last_error(0)
        input_handle = self.u.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS only
        if input_handle:
            try:
                input_facts = self._desktop(input_handle)
            finally:
                self._close(input_handle, desktop=True)
        else:
            self._error("OpenInputDesktop")
            input_facts = {"name": None, "receives_input": None}
        return {"window_station": station_facts, "thread": thread_facts, "input": input_facts}

    def collect(self, window: int | None) -> dict:
        foreground_before = int(self.u.GetForegroundWindow() or 0)
        collector = self._process(int(self.k.GetCurrentProcessId()))
        target = self._window(window, token=True) if window is not None else None
        desktop = self._desktop_context()
        if target is not None:
            after = self._window(window, token=False)
            target["identity_after"] = {key: after.get(key) for key in
                                         ("window", "exists", "pid", "thread_id", "process_started")}
            keys = ("pid", "thread_id", "process_started")
            if target["exists"] is False or after["exists"] is False:
                target["identity_stable"] = False
            elif any(target.get(k) is None or after.get(k) is None for k in keys):
                target["identity_stable"] = None
            else:
                target["identity_stable"] = all(target[k] == after[k] for k in keys)
        foreground_after = int(self.u.GetForegroundWindow() or 0)
        return {"supported": True, "collector": collector, "desktop": desktop,
                "foreground": {"window": foreground_before, "window_after": foreground_after,
                               "stable": foreground_before == foreground_after},
                "target": target, "errors": self.errors}


def _collect_windows_facts(window: int | None) -> dict:
    return _WindowsQuery().collect(window)


def inspect_windows_context(window: int | None = None) -> dict:
    """Return a read-only snapshot; the optional window must be an exact HWND.

    A positive integer is syntax, not proof that a window exists. Invalid HWNDs
    return a diagnostic with ``window_not_found`` rather than selecting another
    window. ``None`` samples the collector only and cannot assess a target.
    """
    if window is not None and (type(window) is not int or
                               not 1 <= window < 1 << (struct.calcsize("P") * 8)):
        raise KitError("invalid_arguments", "window must be a positive pointer-sized integer HWND, or null")
    started = time.monotonic()
    observed_at = datetime.now(timezone.utc).isoformat()
    if os.name != "nt":
        facts = {"supported": False, "collector": None, "target": None,
                 "desktop": None, "foreground": None, "errors": []}
    else:
        try:
            facts = _collect_windows_facts(window)
        except OSError as exc:
            target = None if window is None else {"window": window, "exists": None,
                                                  "identity_stable": None}
            facts = {"supported": True, "collector": None, "target": target,
                     "desktop": None, "foreground": None,
                     "errors": [{"operation": "load_windows_query_api", "reason": "native_api_unavailable",
                                 "winerror": getattr(exc, "winerror", None)}]}
    return {"schema_version": 1, "platform": "windows" if os.name == "nt" else os.name,
            "observed_at": observed_at, "requested_window": window,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "read_only": True, "atomic_snapshot": False, **facts,
            "assessment": assess_windows_context(facts)}

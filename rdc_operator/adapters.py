"""Pinned command adapters; no network listener or replacement dispatcher.

SmartCLI 0.3.5 and WinApp CLI 0.8.0 contracts are documented in docs.
Transport acknowledgement and application-effect verification stay separate.
"""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import math
import ntpath
import os
from pathlib import Path
import re
import time
import uuid

from .common import KitError, allowed_path, atomic_json, read_json, run_command
from .frames import verify_capture


SUPPORTED_ACTIONS = {
    "terminal.start", "terminal.snapshot", "terminal.wait", "terminal.send_text",
    "terminal.send_key", "terminal.close", "desktop.observe", "desktop.invoke",
    "desktop.set_value", "desktop.click", "desktop.screenshot", "desktop.focus",
}
MUTATING_ACTIONS = SUPPORTED_ACTIONS - {
    "terminal.snapshot", "terminal.wait", "desktop.observe",
}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_KEYS = {"Enter", "Tab", "Escape", "Esc", "Backspace", "Space", "Up", "Down",
         "Left", "Right", "Home", "End", "PageUp", "PageDown", "Delete", "Insert"}
_KEYS.update(f"F{i}" for i in range(1, 13))
_KEYS.update(f"C-{c}" for c in "abcdefghijklmnopqrstuvwxyz")
_BROWSERS = {"msedge", "microsoftedge", "microsoftedgecp", "chrome", "chromium",
             "firefox", "brave", "opera", "opera_gx", "operagx", "vivaldi",
             "arc", "zen", "librewolf", "waterfox", "thorium", "duckduckgo"}
_PRE_EFFECT_ERRORS = {"element_not_found", "ambiguous_selector",
                      "target_moved", "foreground_not_target", "no_interactive_desktop",
                      "no_target", "invalid_arguments", "invalid_ui_workflow_id",
                      "desktop_coordination_unavailable", "queue_capacity_exceeded"}


def _fields(args: dict, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(args, dict):
        raise KitError("invalid_arguments", "args must be an object")
    missing, extra = required - args.keys(), args.keys() - required - (optional or set())
    if missing or extra:
        raise KitError("invalid_arguments", f"missing fields: {sorted(missing)}; unknown fields: {sorted(extra)}")


def _string(value: object, name: str, *, empty: bool = False, limit: int = 65536) -> str:
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value or len(value) > limit:
        raise KitError("invalid_arguments", f"{name} must be valid text of at most {limit} characters")
    return value


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise KitError("invalid_arguments", f"{name} must be an integer from {low} to {high}")
    return value


def _prefix(config: dict, key: str) -> list[str]:
    prefix = config.get(key)
    if not isinstance(prefix, list) or not prefix or any(not isinstance(s, str) or not s or "\x00" in s for s in prefix):
        raise KitError("dependency_unconfigured", f"Configure an explicit {key} argv prefix")
    return list(prefix)


def _session_path(state: Path, session: str) -> Path:
    return _state_directory(state, "sessions") / (session + ".json")


def _state_directory(state: Path, name: str) -> Path:
    directory = state / name
    if directory.is_symlink() or (hasattr(directory, "is_junction") and directory.is_junction()):
        raise KitError("unsafe_state", f"{name} cannot be a symlink or junction")
    return directory


def _session(state: Path, session: str) -> dict:
    path = _session_path(state, session)
    if not path.is_file():
        raise KitError("session_not_owned", "This kit has no ownership record for that session")
    data = read_json(path)
    if data.get("session") != session or not isinstance(data.get("upstream_session"), str):
        raise KitError("invalid_session_record", "Session ownership record is malformed")
    return data


def _observation_path(state: Path, oid: str) -> Path:
    return _state_directory(state, "observations") / (oid + ".json")


def _observation(state: Path, oid: str, config: dict) -> dict:
    path = _observation_path(state, oid)
    if not path.is_file():
        raise KitError("observation_not_found", "Observe the exact target window first")
    record = read_json(path)
    at, ttl = record.get("observed_at"), config.get("observation_ttl_seconds", 120)
    if isinstance(at, bool) or not isinstance(at, (float, int)) or not math.isfinite(at):
        raise KitError("invalid_observation", "Observation timestamp is invalid")
    if isinstance(ttl, bool) or not isinstance(ttl, (float, int)) or not math.isfinite(ttl) or not 0 < ttl <= 300:
        raise KitError("invalid_config", "observation_ttl_seconds must be finite and in (0, 300]")
    age = time.time() - at
    if not math.isfinite(age) or age < 0 or age > ttl:
        raise KitError("stale_observation", "Observation expired or clock moved backwards; observe again")
    if record.get("observation_id") != oid or not isinstance(record.get("identity"), dict) or not isinstance(record.get("selectors"), dict):
        raise KitError("invalid_observation", "Observation identity or selectors are malformed")
    return record


def validate(action: str, args: dict, config: dict, state: Path) -> None:
    if action not in SUPPORTED_ACTIONS:
        raise KitError("unsupported_action", "Unknown action")
    if action.startswith("terminal."):
        _prefix(config, "smartcli")
        schemas = {
            "terminal.start": ({"session", "command", "cwd"}, {"cols", "rows"}),
            "terminal.snapshot": ({"session"}, set()),
            "terminal.wait": ({"session"}, {"pattern", "timeout_ms"}),
            "terminal.send_text": ({"session", "text"}, {"newline"}),
            "terminal.send_key": ({"session", "key"}, set()),
            "terminal.close": ({"session"}, set()),
        }
        _fields(args, *schemas[action])
        sid = _string(args["session"], "session", limit=64)
        if not _ID.fullmatch(sid):
            raise KitError("invalid_arguments", "session must be a simple identifier")
        if sid.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise KitError("invalid_arguments", "session cannot be a reserved Windows device name")
        if action == "terminal.start":
            _string(args["command"], "command", limit=8192)
            # PyWinPTY 3.1.2 keeps the first token's quotes when splitting a
            # command string, then looks up that quoted token as a filename.
            # Refuse this known failure before starting a daemon. A relative
            # executable under cwd avoids quoting the executable pathname.
            if os.name == "nt" and args["command"].lstrip().startswith(('"', "'")):
                raise KitError("unsupported_command_quoting", "Windows terminal command must start with an unquoted executable; use an allowed cwd and a relative executable path without spaces")
            cwd = allowed_path(_string(args["cwd"], "cwd"), config)
            if not cwd.is_dir():
                raise KitError("invalid_arguments", "cwd must be an existing allowed directory")
            cols = _integer(args.get("cols", 100), "cols", 10, 1000)
            rows = _integer(args.get("rows", 30), "rows", 2, 500)
            if cols * rows > 100000:
                raise KitError("invalid_arguments", "terminal size exceeds 100000 cells")
            if _session_path(state, sid).exists():
                raise KitError("session_exists", "Session identifiers are never reused; choose a fresh identifier")
        else:
            record = _session(state, sid)
            if record.get("smartcli") != _prefix(config, "smartcli"):
                raise KitError("session_route_changed", "Use the SmartCLI configuration that created this session")
            if action in {"terminal.send_text", "terminal.send_key"} and record.get("phase") != "active":
                raise KitError("session_not_active", "Observe an alive owned session before sending input")
        if action == "terminal.wait":
            _integer(args.get("timeout_ms", 10000), "timeout_ms", 1, 30000)
            if "pattern" in args:
                pattern = _string(args["pattern"], "pattern", limit=2048)
                if pattern.startswith("-"):
                    raise KitError("invalid_arguments", "A leading-dash regex is not supported by this CLI adapter; wrap it in a noncapturing group")
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise KitError("invalid_arguments", "pattern is not a valid regular expression") from exc
        elif action == "terminal.send_text":
            text = _string(args["text"], "text", empty=True)
            if type(args.get("newline", False)) is not bool:
                raise KitError("invalid_arguments", "newline must be a boolean")
            if text.endswith(("\r", "\n")):
                raise KitError("unsupported_text", "SmartCLI stdin strips trailing CR/LF; use newline=true for one Enter")
        elif action == "terminal.send_key":
            if _string(args["key"], "key", limit=32) not in _KEYS:
                raise KitError("invalid_arguments", "key is outside this adapter's explicit key allowlist")
        return
    _prefix(config, "winapp")
    if action in {"desktop.observe", "desktop.screenshot"}:
        _fields(args, {"window"} | ({"output"} if action.endswith("screenshot") else set()),
                {"observation_id"} if action == "desktop.screenshot" else set())
        _integer(args["window"], "window", 1, (1 << 63) - 1)
        if action == "desktop.screenshot":
            output = allowed_path(_string(args["output"], "output"), config, must_exist=False)
            if output.exists() or output.suffix.lower() != ".png":
                raise KitError("invalid_arguments", "Screenshot needs a new .png output path")
            if not output.parent.is_dir():
                raise KitError("invalid_arguments", "Screenshot parent directory must already exist")
            if "observation_id" in args:
                oid = _string(args["observation_id"], "observation_id", limit=64)
                if not _ID.fullmatch(oid):
                    raise KitError("invalid_arguments", "observation_id must be a simple identifier")
                record = _observation(state, oid, config)
                if record.get("window") != args["window"]:
                    raise KitError("target_mismatch", "Screenshot HWND differs from its observation")
    elif action == "desktop.focus":
        # Focus is an explicit mutation of a previously observed window. It is
        # never an automatic click fallback and does not accept raw coordinates.
        _fields(args, {"observation_id"})
        oid = _string(args["observation_id"], "observation_id", limit=64)
        if not _ID.fullmatch(oid):
            raise KitError("invalid_arguments", "observation_id must be a simple identifier")
        _observation(state, oid, config)
    else:
        _fields(args, {"observation_id", "selector"} | ({"value"} if action == "desktop.set_value" else set()))
        oid = _string(args["observation_id"], "observation_id", limit=64)
        if not _ID.fullmatch(oid):
            raise KitError("invalid_arguments", "observation_id must be a simple identifier")
        selector = _string(args["selector"], "selector", limit=512)
        # Leading flags would be interpreted by the upstream command parser.
        if selector.startswith("-") or "\r" in selector or "\n" in selector:
            raise KitError("invalid_arguments", "selector must be the exact observed element handle")
        record = _observation(state, oid, config)
        if selector not in record["selectors"]:
            raise KitError("unobserved_selector", "Selector did not occur in this observation")
        if action == "desktop.set_value":
            value = _string(args["value"], "value", empty=True)
            if value.startswith("-"):
                raise KitError("unsupported_text", "Leading-dash values are not yet verified with the upstream parser")


def _failed(run: dict, *, effectful: bool) -> dict | None:
    if run.get("timed_out") or run.get("output_truncated"):
        return {"status": "outcome_unknown" if effectful else "failed", "code": "upstream_incomplete", "upstream": run}
    if run.get("exit_code") != 0:
        error = run.get("stderr_json")
        code = error.get("error", {}).get("code") if isinstance(error, dict) and isinstance(error.get("error"), dict) else None
        uncertain = effectful and code not in _PRE_EFFECT_ERRORS
        return {"status": "outcome_unknown" if uncertain else "failed", "code": code or "upstream_failed", "upstream": run}
    return None


def _json(run: dict, effectful: bool = False) -> dict:
    result = run.get("stdout_json")
    if not isinstance(result, dict):
        raise KitError("invalid_upstream_result", "Upstream returned no JSON object", uncertain=effectful)
    return result


def _terminal_flags(run: dict) -> dict:
    flags = {}
    for key in ("alive", "matched", "exited", "changed"):
        match = re.search(r"(?:^|\s)" + key + r"=(True|False|None)(?:\s|$)", run.get("stderr", ""))
        if match:
            flags[key] = {"True": True, "False": False, "None": None}[match.group(1)]
    match = re.search(r"(?:^|\s)reason=([A-Z_]+)(?:\s|$)", run.get("stderr", ""))
    if match:
        flags["reason"] = match.group(1)
    return flags


def _terminal_snapshot(prefix: list[str], sid: str, *, timeout: float = 20) -> dict:
    run = run_command(prefix + ["snapshot", "--id", sid, "--json"], timeout=timeout)
    failure = _failed(run, effectful=False)
    if failure:
        return failure
    snapshot = _json(run)
    _check_snapshot(snapshot)
    return {"status": "observed", "snapshot": snapshot, "signals": _terminal_flags(run), "upstream": run}


def _check_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot.get("size"), dict) or not isinstance(snapshot.get("lines"), list):
        raise KitError("invalid_upstream_result", "SmartCLI snapshot lacks size or lines")


def _terminal(action: str, args: dict, config: dict, state: Path) -> dict:
    prefix, logical = _prefix(config, "smartcli"), args["session"]
    path = _session_path(state, logical)
    if action == "terminal.start":
        sid = "rdck-" + uuid.uuid4().hex
        record = {"schema_version": 1, "session": logical, "upstream_session": sid,
                  "created_at": time.time(), "phase": "starting", "smartcli": prefix,
                  "command": args["command"], "cwd": str(allowed_path(args["cwd"], config))}
        atomic_json(path, record)  # Custody exists even if spawning times out.
        run = run_command(prefix + ["start", "--cmd", args["command"], "--id", sid,
                          "--cwd", record["cwd"], "--cols", str(args.get("cols", 100)),
                          "--rows", str(args.get("rows", 30)), "--detect-child-exit", "--json"], timeout=20)
        failure = _failed(run, effectful=True)
        if failure:
            record["phase"] = "outcome_unknown"
            atomic_json(path, record)
            return {**failure, "session": logical, "upstream_session": sid}
        response = _json(run, True)
        if response.get("ok") is not True or response.get("sid") != sid:
            raise KitError("invalid_upstream_result", "SmartCLI did not acknowledge this session", uncertain=True)
        record["phase"] = "started"
        atomic_json(path, record)
        try:
            observed = _terminal_snapshot(prefix, sid)
        except KitError as exc:
            return {"status": "outcome_unknown", "session": logical, "upstream_session": sid,
                    "upstream": run, "code": "post_observation_failed", "message": str(exc)}
        if observed.get("signals", {}).get("alive") is True:
            record["phase"] = "active"
            atomic_json(path, record)
        return {"status": "completed" if record["phase"] == "active" else "outcome_unknown",
                "session": logical, "upstream_session": sid, "upstream": run, "observation": observed,
                "verification": {"session_alive": record["phase"] == "active", "program_ready": False}}
    record = _session(state, logical)
    sid = record["upstream_session"]
    if action == "terminal.snapshot":
        observed = _terminal_snapshot(prefix, sid)
        if observed.get("signals", {}).get("alive") is True and record.get("phase") != "close_requested":
            record["phase"] = "active"
            atomic_json(path, record)
        return {**observed, "session": logical}
    if action == "terminal.wait":
        timeout = args.get("timeout_ms", 10000)
        verb = ["wait-regex", "--id", sid, args["pattern"]] if "pattern" in args else ["wait", "--id", sid]
        run = run_command(prefix + verb + ["--timeout-ms", str(timeout), "--json"], timeout=timeout / 1000 + 18)
        failure = _failed(run, effectful=False)
        if failure:
            return {**failure, "session": logical}
        snapshot, flags = _json(run), _terminal_flags(run)
        _check_snapshot(snapshot)
        matched = flags.get("matched") is True if "pattern" in args else flags.get("reason") in {"STABLE", "MARKER"}
        if "pattern" not in args and flags.get("reason") == "STABLE":
            io = snapshot.get("io", {})
            matched = isinstance(io, dict) and io.get("local_cut") == "drained"
        if flags.get("exited") is True or flags.get("alive") is False:
            matched = False
        if flags.get("alive") is True and record.get("phase") != "close_requested":
            record["phase"] = "active"
            atomic_json(path, record)
        return {"status": "observed" if matched else "failed", "condition_met": matched,
                "session": logical, "snapshot": snapshot, "signals": flags, "upstream": run}
    if action == "terminal.close":
        run = run_command(prefix + ["close", "--id", sid, "--json"], timeout=20)
        record["phase"] = "close_requested"
        atomic_json(path, record)
        failure = _failed(run, effectful=True)
        if failure:
            return {**failure, "session": logical, "ownership_retained": True}
        response = _json(run, True)
        acknowledged = response.get("ok") is True and response.get("closed") is True and response.get("sid") == sid
        # The pinned CLI drops the daemon's `close` receipt, including
        # close_unconfirmed. Do not turn its unconditional `closed:true` into
        # independent evidence of child exit, and never delete our custody.
        return {"status": "outcome_unknown", "session": logical, "upstream": run,
                "close_acknowledged": acknowledged, "ownership_retained": True,
                "code": "close_receipt_not_exposed",
                "verification": {"child_exit_confirmed": False,
                    "reason": "SmartCLI 0.3.5 CLI does not expose the daemon's close receipt"}}
    if action == "terminal.send_text":
        verb = "send-line" if args.get("newline", False) else "send-text"
        run = run_command(prefix + [verb, "--id", sid, "--stdin"], text=args["text"], timeout=20)
    else:
        run = run_command(prefix + ["keys", "--id", sid, args["key"]], timeout=20)
    failure = _failed(run, effectful=True)
    if failure:
        return {**failure, "session": logical}
    try:
        observed = _terminal_snapshot(prefix, sid)
    except KitError as exc:
        return {"status": "outcome_unknown", "session": logical, "upstream": run,
                "code": "post_observation_failed", "message": str(exc), "input_acknowledged": True}
    return {"status": "completed" if observed["status"] == "observed" else "outcome_unknown",
            "session": logical, "upstream": run, "observation": observed,
            "verification": {"input_acknowledged": True, "application_effect_verified": False}}


def _window_identity(window: int) -> dict:
    """Ask the Windows kernel, including creation time to resist PID reuse."""
    if os.name != "nt":
        raise KitError("unsupported_platform", "Desktop actions currently require Windows")
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.IsWindow.argtypes, user32.IsWindow.restype = [wintypes.HWND], wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes, kernel32.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    if not user32.IsWindow(window):
        raise KitError("window_not_found", "Target HWND no longer exists")
    pid = wintypes.DWORD()
    thread = user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    if not thread or not pid.value:
        raise KitError("identity_unavailable", "Cannot resolve target window process")
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        raise KitError("identity_unavailable", "Cannot read target process identity")
    try:
        creation, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            raise KitError("identity_unavailable", "Cannot read process creation time")
        image = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(image))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            raise KitError("identity_unavailable", "Cannot read target executable identity")
        identity = {"window": window, "pid": pid.value, "thread_id": thread,
                    "process_started": str((creation.dwHighDateTime << 32) | creation.dwLowDateTime),
                    "executable": image.value.casefold()}
    finally:
        kernel32.CloseHandle(handle)
    _reject_browser(identity["executable"])
    return identity


def _reject_browser(executable: str) -> None:
    name = ntpath.splitext(ntpath.basename(executable))[0].casefold()
    if name in _BROWSERS:
        raise KitError("browser_surface_required", "Use the connected official Browser plugin for browser targets; no desktop fallback")


def _foreground_window() -> int:
    """Read the current foreground HWND; zero is unknown, not proof of UAC."""
    if os.name != "nt":
        raise KitError("unsupported_platform", "Desktop actions currently require Windows")
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    return int(user32.GetForegroundWindow() or 0)


def _root_window(window: int) -> int:
    """Read GA_ROOT only; never substitute an unobserved parent target."""
    if os.name != "nt":
        raise KitError("unsupported_platform", "Desktop actions currently require Windows")
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    return int(user32.GetAncestor(window, 2) or 0)


def _selectors(tree: dict, window: int) -> dict:
    windows = tree.get("windows")
    if not isinstance(windows, list):
        raise KitError("invalid_upstream_result", "WinApp inspect lacks windows[]")
    targets = [w for w in windows if isinstance(w, dict) and w.get("hwnd") == window]
    if len(targets) != 1 or not isinstance(targets[0].get("elements"), list):
        raise KitError("target_mismatch", "WinApp inspect did not resolve exactly the requested HWND")
    selected, stack, count = {}, list(targets[0]["elements"]), 0
    while stack:
        item = stack.pop()
        count += 1
        if count > 20000 or not isinstance(item, dict):
            raise KitError("invalid_upstream_result", "UI tree is malformed or too large")
        selector = item.get("selector")
        if isinstance(selector, str) and selector and not selector.startswith("-"):
            if selector in selected:
                raise KitError("ambiguous_selector", "Inspect returned a duplicated selector")
            selected[selector] = {k: item[k] for k in ("name", "type", "isEnabled", "isOffscreen", "isInvokable", "x", "y", "width", "height") if k in item}
        children = item.get("children", [])
        if not isinstance(children, list):
            raise KitError("invalid_upstream_result", "UI children must be a list")
        stack.extend(children)
    return selected


def _winapp(prefix: list[str], argv: list[str], *, timeout: float = 30) -> dict:
    # No workflow ID: the upstream releases its one-shot turn immediately.
    # The kit's outer OS lock serializes cooperating kit writers. The desktop
    # remains shared with the user and actors that do not use this state.
    return run_command(prefix + ["ui"] + argv + ["--json"], timeout=timeout,
                       env={"WINAPP_UI_WORKFLOW_ID": None})


def _capture_observation(window: int, config: dict, state: Path) -> dict:
    identity = _window_identity(window)
    prefix = _prefix(config, "winapp")
    status = _winapp(prefix, ["status", "-w", str(window)], timeout=15)
    failure = _failed(status, effectful=False)
    if failure:
        return failure
    info = _json(status)
    if info.get("hwnd") != window or info.get("processId") != identity["pid"]:
        raise KitError("target_mismatch", "WinApp status disagrees with kernel window identity")
    if isinstance(info.get("processName"), str):
        _reject_browser(info["processName"])
    inspected = _winapp(prefix, ["inspect", "-w", str(window)], timeout=30)
    failure = _failed(inspected, effectful=False)
    if failure:
        return failure
    tree = _json(inspected)
    selectors = _selectors(tree, window)
    if _window_identity(window) != identity:
        raise KitError("target_changed", "Target changed while being observed")
    oid = "obs-" + uuid.uuid4().hex
    record = {"schema_version": 1, "observation_id": oid, "observed_at": time.time(),
              "window": window, "identity": identity, "selectors": selectors,
              "tree": tree, "winapp": prefix}
    atomic_json(_observation_path(state, oid), record)
    return {"status": "observed", "observation_id": oid, "identity": identity,
            "observed_at": record["observed_at"], "tree": tree,
            "verification": {"window_identity_checked": True, "semantic_effect_verified": False},
            "upstream": {"status": status, "inspect": inspected}}


def _desktop(action: str, args: dict, config: dict, state: Path) -> dict:
    if action == "desktop.observe":
        return _capture_observation(args["window"], config, state)
    prefix = _prefix(config, "winapp")
    if action == "desktop.screenshot":
        window = args["window"]
        identity = _window_identity(window)
        if "observation_id" in args:
            record = _observation(state, args["observation_id"], config)
            if record.get("winapp") != prefix:
                raise KitError("observation_route_changed", "Observe again using this WinApp configuration")
            if record.get("window") != window or record["identity"] != identity:
                raise KitError("target_changed", "Screenshot target no longer matches its observation")
        output = allowed_path(args["output"], config, must_exist=False)
        started_utc = datetime.now(timezone.utc).isoformat()
        started_mono = time.monotonic()
        run = _winapp(prefix, ["screenshot", "-w", str(window), "--output", str(output)])
        elapsed_ms = round((time.monotonic() - started_mono) * 1000, 3)
        finished_utc = datetime.now(timezone.utc).isoformat()
        failure = _failed(run, effectful=True)
        if failure:
            return failure
        try:
            current = _window_identity(window)
        except KitError as exc:
            return {"status": "outcome_unknown", "upstream": run, "message": str(exc)}
        if current != identity or not output.is_file():
            return {"status": "outcome_unknown", "upstream": run, "code": "capture_unverified"}
        try:
            frame = verify_capture(output, _json(run), identity)
        except KitError as exc:
            return {"status": "outcome_unknown", "upstream": run, "code": exc.code,
                    "message": exc.message}
        # These are command timings, not the source frame's rendering time.
        frame["capture_call"] = {"started_utc": started_utc, "finished_utc": finished_utc,
                                 "elapsed_ms": elapsed_ms,
                                 "wall_clock_ordered": finished_utc >= started_utc}
        frame["observation_id"] = args.get("observation_id")
        return {"status": "completed", "output": str(output),
                "width": frame["artifact"]["width"], "height": frame["artifact"]["height"],
                "identity": identity, "upstream": run, "frame": frame,
                "verification": frame["verification"]}
    record = _observation(state, args["observation_id"], config)
    if record.get("winapp") != prefix:
        raise KitError("observation_route_changed", "Observe again using this WinApp configuration")
    window = record["window"]
    current = _window_identity(window)
    if current != record["identity"]:
        raise KitError("target_changed", "The HWND/process identity no longer matches the observation")
    if action == "desktop.focus":
        return _focus_window(window, record["identity"], prefix, config, state)
    selector = args["selector"]
    element = record["selectors"][selector]
    if element.get("isEnabled") is False or element.get("isOffscreen") is True:
        raise KitError("target_unavailable", "Observe a visible enabled target before acting")
    # Inspect can expose an AutomationId while a resolved command returns a
    # generated selector. Resolve that mapping with a read, scoped to the same
    # HWND, instead of treating an arbitrary successful action receipt as proof.
    resolved = _winapp(prefix, ["get-property", selector, "-w", str(window)], timeout=15)
    failure = _failed(resolved, effectful=False)
    if failure:
        return {**failure, "code": "target_resolution_failed"}
    binding = _json(resolved)
    canonical, typed = binding.get("elementId"), binding.get("element")
    if (not isinstance(canonical, str) or not canonical or len(canonical) > 512
            or canonical.startswith("-") or any(c in canonical for c in "\x00\r\n")
            or not isinstance(typed, dict) or typed.get("selector") != canonical
            or not isinstance(binding.get("properties"), dict)):
        raise KitError("invalid_upstream_result", "WinApp did not return a typed canonical element binding")
    if any(key in element and typed.get(key) != element[key] for key in ("type", "name")):
        raise KitError("target_changed", "Resolved element no longer matches the observed type and name")
    if typed.get("isEnabled") is not True or typed.get("isOffscreen") is not False:
        raise KitError("target_unavailable", "Resolved target is not confirmed visible and enabled")
    if _window_identity(window) != record["identity"]:
        raise KitError("target_changed", "Target changed while resolving the element")
    verb = {"desktop.invoke": "invoke", "desktop.set_value": "set-value", "desktop.click": "click"}[action]
    argv = [verb, canonical]
    if action == "desktop.set_value":
        argv.append(args["value"])
    elif action == "desktop.invoke":
        # The upstream automatic mode may fall back to an invokable ancestor.
        # This action is restricted to the exact observed element.
        argv += ["--action", "invoke"]
    argv += ["-w", str(window)]
    run = _winapp(prefix, argv)
    failure = _failed(run, effectful=True)
    if failure:
        return failure
    response = _json(run, True)
    ack_valid = response.get("elementId") == canonical and type(response.get("hwnd")) is int and response["hwnd"] == window
    if action == "desktop.invoke":
        ack_valid = ack_valid and response.get("pattern") == "InvokePattern" and response.get("requestedAction") == "invoke" and response.get("performedAction") == "invoke"
    elif action == "desktop.click":
        ack_valid = ack_valid and response.get("clickType") == "click" and type(response.get("x")) is int and type(response.get("y")) is int
    if not ack_valid or isinstance(response.get("error"), dict):
        return {"status": "outcome_unknown", "upstream": run, "code": "invalid_action_acknowledgement",
                "verification": {"action_acknowledged": False, "application_effect_verified": False}}
    verification = {"action_acknowledged": True, "application_effect_verified": False}
    extra = {"target_binding": {"requested_selector": selector, "canonical_selector": canonical,
                                "window": window, "upstream": resolved}}
    try:
        if _window_identity(window) != record["identity"]:
            return {"status": "outcome_unknown", "upstream": run, "code": "target_changed_after_action"}
        if action == "desktop.set_value":
            value_run = _winapp(prefix, ["get-value", canonical, "-w", str(window)], timeout=15)
            extra["value_verification"] = value_run
            value = value_run.get("stdout_json")
            verification["application_effect_verified"] = bool(not _failed(value_run, effectful=False) and isinstance(value, dict) and value.get("elementId") == canonical and value.get("text") == args["value"])
        observed = _capture_observation(window, config, state)
    except KitError as exc:
        return {"status": "outcome_unknown", "upstream": run, "code": "post_observation_failed", "message": str(exc), "verification": verification, **extra}
    identity_confirmed = observed.get("identity") == record["identity"]
    verification["window_identity_checked_after_action"] = identity_confirmed
    if not identity_confirmed:
        verification["application_effect_verified"] = False
    confirmed = observed.get("status") == "observed" and identity_confirmed
    if action == "desktop.set_value":
        confirmed = confirmed and verification["application_effect_verified"]
    return {"status": "completed" if confirmed else "outcome_unknown", "upstream": run,
            "observation": observed, "verification": verification, **extra}


def _focus_window(window: int, identity: dict, prefix: list[str], config: dict, state: Path) -> dict:
    """Ask the pinned backend once, then independently verify focus and identity.

    A failed focus can already have restored a minimized window. Even a known
    click pre-effect error therefore remains uncertain here; never auto-replay.
    """
    # A window can be reparented without changing HWND/PID/creation time.
    # The backend focuses GA_ROOT; reject that changed hierarchy before asking
    # it to restore or activate a different, unobserved parent window.
    if _root_window(window) != window:
        raise KitError("top_level_target_required", "Observe a current top-level window; focus will not adopt its parent")
    if _window_identity(window) != identity:
        raise KitError("target_changed", "Target identity changed before focus")
    run = _winapp(prefix, ["focus", "-w", str(window)])
    failure = _failed(run, effectful=True)
    if failure:
        return {**failure, "status": "outcome_unknown",
                "verification": {"action_acknowledged": False, "focus_effect_verified": False,
                                 "application_effect_verified": False}}
    response = _json(run, True)
    ack = (response.get("elementId") == "" and type(response.get("hwnd")) is int
           and response["hwnd"] == window and "error" not in response)
    if not ack:
        return {"status": "outcome_unknown", "code": "invalid_action_acknowledgement", "upstream": run,
                "verification": {"action_acknowledged": False, "focus_effect_verified": False,
                                 "application_effect_verified": False}}
    try:
        if _window_identity(window) != identity:
            return {"status": "outcome_unknown", "code": "target_changed_after_action", "upstream": run}
        observed = _capture_observation(window, config, state)
        # Read after inspection as the user or another actor can change focus.
        foreground = _foreground_window()
        identity_confirmed = observed.get("identity") == identity and _window_identity(window) == identity
    except KitError as exc:
        return {"status": "outcome_unknown", "code": "post_observation_failed", "upstream": run,
                "message": exc.message,
                "verification": {"action_acknowledged": True, "focus_effect_verified": False,
                                 "application_effect_verified": False}}
    confirmed = observed.get("status") == "observed" and identity_confirmed and foreground == window
    return {"status": "completed" if confirmed else "outcome_unknown",
            "code": "focus_verified" if confirmed else "focus_unverified",
            "upstream": run, "observation": observed, "foreground_window": foreground,
            "verification": {"action_acknowledged": True, "focus_effect_verified": confirmed,
                             "window_identity_checked_after_action": identity_confirmed,
                             "application_effect_verified": False}}


def execute(action: str, args: dict, config: dict, state: Path) -> dict:
    """Execute under the engine's state lock and recorded intent."""
    validate(action, args, config, state)
    if action.startswith("terminal."):
        return _terminal(action, args, config, state)
    return _desktop(action, args, config, state)

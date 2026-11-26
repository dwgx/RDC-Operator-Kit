"""Real SmartCLI terminal smoke with independent, synthetic file witnesses.

Run from an installed checkout, using its private Python environment. This
script creates only fresh owned sessions and a fresh evidence/terminal-state-*
directory. It never calls a model, touches an existing session, or kills a PID.
Windows process handles independently verify exit; close receipts stay unknown
when the pinned upstream CLI cannot prove child exit.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import traceback
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from rdc_operator.common import atomic_json, read_json  # noqa: E402
from rdc_operator.core import execute_request  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def wait_json(path: Path, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.1)
    raise AssertionError(f"No complete independent witness: {path.name}")


def command(argv):
    if os.name == "nt":
        # This fixture runs with PROJECT as cwd. Relative owned paths avoid
        # PyWinPTY's quoted-executable lookup bug when PROJECT has spaces.
        # This is not a general command-string quoting implementation.
        relative = []
        for item in argv:
            try:
                relative.append(str(Path(item).relative_to(PROJECT)))
            except ValueError:
                relative.append(item)
        return subprocess.list2cmdline(relative)
    return shlex.join(argv)


class ProcessWitness:
    """Observe only the freshly bootstrapped fixture's OS process handle."""

    def __init__(self, startup: dict, token: str):
        if startup.get("token") != token or type(startup.get("pid")) is not int:
            raise AssertionError("Startup witness did not identify this fixture")
        if os.name != "nt":
            raise RuntimeError("This smoke's independent exit witness requires Windows")
        from ctypes import wintypes
        self.pid = startup["pid"]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x100000 | 0x1000, False, self.pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if self.kernel.WaitForSingleObject(self.handle, 0) != 0x102:
                raise AssertionError("Fixture exited before an independent handle was acquired")
            created, ended, kernel, user = (wintypes.FILETIME() for _ in range(4))
            if not self.kernel.GetProcessTimes(self.handle, ctypes.byref(created), ctypes.byref(ended), ctypes.byref(kernel), ctypes.byref(user)):
                raise ctypes.WinError(ctypes.get_last_error())
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if not self.kernel.QueryFullProcessImageNameW(self.handle, 0, buf, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.identity = {"pid": self.pid, "image_basename": Path(buf.value).name,
                             "creation_filetime": (created.dwHighDateTime << 32) | created.dwLowDateTime,
                             "handle_acquired_while_running": True}
        except BaseException:
            self.release()
            raise

    def wait_exit(self, timeout_ms=10000):
        from ctypes import wintypes
        result = self.kernel.WaitForSingleObject(self.handle, timeout_ms)
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {**self.identity, "method": "held Windows process handle",
                "wait_result": result, "exited": result == 0,
                "exit_code": code.value, "observed_utc": now()}

    def release(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def snapshot(receipt):
    result = receipt.get("result", {})
    return result.get("snapshot", result.get("observation", {}).get("snapshot", {}))


def screen_text(receipt):
    lines = snapshot(receipt).get("lines", [])
    text = []
    for line in lines:
        value = line if isinstance(line, str) else line.get("text") if isinstance(line, dict) else None
        if not isinstance(value, str):
            raise AssertionError("Snapshot line has no text field")
        text.append(value)
    return "\n".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT / "config.local.json")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run this witness on Windows; it does not simulate process exit")
    token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    state = PROJECT / "evidence" / ("terminal-state-" + token)
    state.mkdir(parents=True, exist_ok=False)
    config = read_json(args.config.resolve())
    summary = {"schema_version": 1, "run_id": token, "started_utc": now(),
               "platform": sys.platform, "python": sys.version.split()[0],
               "smartcli": version("smartcli-toolkit"), "state": str(state),
               "tests": {}, "calls": [], "source_sha256": {}}
    for relative in ("rdc_operator/core.py", "rdc_operator/common.py", "rdc_operator/adapters.py", "examples/terminal-fixture.py", "scripts/smoke_terminal.py"):
        summary["source_sha256"][relative] = hashlib.sha256((PROJECT / relative).read_bytes()).hexdigest()
    counter = 0

    def call(label, action, arguments, apply=False):
        nonlocal counter
        counter += 1
        request = {"request_id": f"{counter:02d}-{label}", "action": action, "args": arguments}
        atomic_json(state / (request["request_id"] + ".request.json"), request)
        receipt = execute_request(request, config, state, apply=apply)
        summary["calls"].append({"request_id": request["request_id"], "action": action,
                                 "status": receipt["status"], "replayed": receipt.get("replayed")})
        atomic_json(state / "summary.json", summary)
        return receipt

    def require(receipt, statuses=("observed", "completed")):
        if receipt["status"] not in statuses:
            raise AssertionError(f"{receipt['request_id']} returned {receipt['status']}; inspect its receipt")
        return receipt

    def run_case(name, body):
        logical = f"smoke-{name}-{uuid.uuid4().hex[:10]}"
        case = {"session": logical, "started_utc": now(), "status": "RUNNING"}
        summary["tests"][name] = case
        handle = None
        try:
            handle = body(logical, case)
            case["status"] = "PASS"
        except Exception as exc:
            case["status"] = "FAIL"
            case["error"] = f"{type(exc).__name__}: {exc}"
            case["traceback"] = traceback.format_exc()
        finally:
            session_file = state / "sessions" / (logical + ".json")
            if session_file.exists():
                try:
                    close = call(name + "-close", "terminal.close", {"session": logical}, apply=True)
                    case["close_status"] = close["status"]
                    case["close_code"] = close.get("result", {}).get("code")
                    case["ownership_retained"] = close.get("result", {}).get("ownership_retained")
                    case["close_is_independent_exit_proof"] = False
                except Exception as exc:
                    case["close_error"] = f"{type(exc).__name__}: {exc}"
                    case["status"] = "FAIL"
            if handle:
                try:
                    case["exit_after_cleanup"] = handle.wait_exit(10000)
                    if not case["exit_after_cleanup"]["exited"]:
                        case["status"] = "FAIL"
                finally:
                    handle.release()
            case["finished_utc"] = now()
            atomic_json(state / "summary.json", summary)

    def repl_case(logical, case):
        startup, witness = state / "repl-startup.json", state / "repl-witness.json"
        bootstrap = state / "repl-bootstrap.py"
        bootstrap.write_text("import json, os\nfrom pathlib import Path\n" +
            f"_startup = {{'pid': os.getpid(), 'token': {token!r}}}\n" +
            f"Path({str(startup)!r}).write_text(json.dumps(_startup), encoding='utf-8')\n",
            encoding="utf-8")
        require(call("repl-start", "terminal.start", {"session": logical,
            "command": command([sys.executable, "-u", "-i", "-q", str(bootstrap)]),
            "cwd": str(PROJECT), "cols": 140, "rows": 35}, apply=True))
        ready = require(call("repl-ready", "terminal.wait", {"session": logical, "pattern": r">>>\s*$", "timeout_ms": 12000}))
        case["prompt_observed_before_input"] = ready["result"].get("condition_met") is True
        handle = ProcessWitness(wait_json(startup), token)
        # Keep the handle reachable even when a later assertion fails.
        active_handles[logical] = handle
        text = '中文："双引号" 与 \'单引号\'，空格 $HOME `literal` \\ path'
        source = (f"_result = 6*7; _text = {text!r}; "
                  f"_witness = {{'value': _result, 'text': _text, 'pid': os.getpid(), 'token': {token!r}}}; "
                  f"Path({str(witness)!r}).write_text(json.dumps(_witness, ensure_ascii=False), encoding='utf-8'); print(_result)")
        require(call("repl-input", "terminal.send_text", {"session": logical, "text": source, "newline": True}, apply=True))
        observed = require(call("repl-result", "terminal.wait", {"session": logical, "pattern": r"(?m)^42\s*$", "timeout_ms": 12000}))
        value = wait_json(witness)
        if value != {"value": 42, "text": text, "pid": handle.pid, "token": token}:
            raise AssertionError("REPL file witness did not match computed result and Unicode text")
        if not re.search(r"(?m)^42\s*$", screen_text(observed)):
            raise AssertionError("No standalone 42 output line; echoed source cannot pass")
        case["witness"] = {"file": str(witness), "computed_value": value["value"],
                           "unicode_and_quotes_exact": True, "pid_matches_held_handle": True}
        require(call("repl-exit", "terminal.send_text", {"session": logical, "text": "exit()", "newline": True}, apply=True))
        case["independent_exit"] = handle.wait_exit()
        if not case["independent_exit"]["exited"] or case["independent_exit"]["exit_code"] != 0:
            raise AssertionError("Python REPL process did not independently exit with code 0")
        end = call("repl-exit-snapshot", "terminal.snapshot", {"session": logical})
        case["exit_snapshot_status"] = end["status"]
        case["exit_snapshot_signals"] = end.get("result", {}).get("signals", {})
        return handle

    def tui_case(logical, case):
        startup, witness = state / "tui-startup.json", state / "tui-witness.json"
        runner = state / "tui-bootstrap.py"
        fixture = PROJECT / "examples" / "terminal-fixture.py"
        runner.write_text("import json, os, runpy, sys\nfrom pathlib import Path\n" +
            f"Path({str(startup)!r}).write_text(json.dumps({{'pid': os.getpid(), 'token': {token!r}}}), encoding='utf-8')\n" +
            f"sys.argv = [{str(fixture)!r}, '--witness', {str(witness)!r}]\n" +
            f"runpy.run_path({str(fixture)!r}, run_name='__main__')\n", encoding="utf-8")
        require(call("tui-start", "terminal.start", {"session": logical,
            "command": command([sys.executable, "-u", str(runner)]),
            "cwd": str(PROJECT), "cols": 100, "rows": 25}, apply=True))
        ready = require(call("tui-ready", "terminal.wait", {"session": logical, "pattern": "RDC_KIT_MENU", "timeout_ms": 12000}))
        case["menu_ready"] = ready["result"].get("condition_met") is True
        case["terminal_representation"] = snapshot(ready).get("io", {}).get("representation")
        case["alternate_screen_observed"] = snapshot(ready).get("hints", {}).get("alt_screen")
        handle = ProcessWitness(wait_json(startup), token)
        active_handles[logical] = handle
        require(call("tui-down", "terminal.send_key", {"session": logical, "key": "Down"}, apply=True))
        selected = require(call("tui-beta", "terminal.wait", {"session": logical, "pattern": r">\s*Beta", "timeout_ms": 12000}))
        case["beta_observed_before_enter"] = bool(re.search(r">\s*Beta", screen_text(selected)))
        require(call("tui-enter", "terminal.send_key", {"session": logical, "key": "Enter"}, apply=True))
        value = wait_json(witness)
        if value != {"choice": "Beta", "index": 1, "pid": handle.pid}:
            raise AssertionError("Raw TUI independent witness was not choice=Beta,index=1 with the owned PID")
        case["witness"] = {"file": str(witness), **value}
        case["independent_exit"] = handle.wait_exit()
        if not case["independent_exit"]["exited"] or case["independent_exit"]["exit_code"] != 0:
            raise AssertionError("Raw TUI process did not independently exit with code 0")
        end = call("tui-exit-snapshot", "terminal.snapshot", {"session": logical})
        case["exit_snapshot_status"] = end["status"]
        case["exit_snapshot_signals"] = end.get("result", {}).get("signals", {})
        case["exit_marker_visible"] = "RDC_KIT_EXIT" in screen_text(end)
        return handle

    active_handles = {}
    try:
        run_case("repl", repl_case)
        run_case("tui", tui_case)
    finally:
        # If a case failed after acquiring a handle, retain independent cleanup
        # evidence without ever issuing a PID kill or touching another session.
        for logical, handle in active_handles.items():
            if handle.handle:
                case = next(item for item in summary["tests"].values() if item["session"] == logical)
                try:
                    case["exit_after_cleanup"] = handle.wait_exit(10000)
                    if not case["exit_after_cleanup"]["exited"]:
                        case["status"] = "FAIL"
                finally:
                    handle.release()
        summary["finished_utc"] = now()
        summary["status"] = "PASS" if len(summary["tests"]) == 2 and all(item["status"] == "PASS" for item in summary["tests"].values()) else "FAIL"
        atomic_json(state / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "tests": {key: value["status"] for key, value in summary["tests"].items()}, "summary": str(state / "summary.json")}, ensure_ascii=False))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

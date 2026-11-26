"""Run the Kit's finite Windows fixture suite, sequentially, with durable progress.

Use an actual CPython base executable for --python, an absolute PowerShell 7
pwsh.exe for --powershell, the SmartCLI environment for --terminal-python, and
the separate MCP environment for --mcp-python. Nothing is installed. No browser
is operated and no model is called. Existing scripts retain their own fixture
states; the suite never uses a second state to bypass a busy writer.

Exit 0: every case passed. Exit 1: failure/uncertain cleanup. Exit 2: incomplete
coverage (skipped/not-run/unsupported). A single JSON summary is not proof of
all application behavior; the linked raw fixture reports remain authoritative.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from rdc_operator import __version__
from rdc_operator.adapters import _window_identity
from rdc_operator.common import KitError, allowed_path, atomic_json, read_json, strict_json

CASE_ORDER = ("core", "doctor", "liveness", "terminal", "mcp", "browser_offline",
              "omp_preview", "desktop", "observation")
CASE_KINDS = {"core": "offline_and_mocked_core", "doctor": "executable_discovery",
              "liveness": "real_synthetic_pipe_children", "terminal": "real_terminal_fixtures",
              "mcp": "real_sdk_stdio_with_synthetic_state", "browser_offline": "offline_fixture_consistency",
              "omp_preview": "real_dispatcher_dry_run", "desktop": "real_owned_windows_fixture",
              "observation": "real_owned_windows_fixture"}
FIXTURES = {
    "desktop": ("desktop-fixture.ps1", "RDC Operator Kit — Desktop Test Fixture"),
    "observation": ("observation-fixture.ps1", "RDC Operator Kit — Observation Fixture"),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def unittest_counts(text):
    """Preserve unittest's run/skip/failure accounting; don't count assertions."""
    run = re.search(r"Ran (\d+) tests? in", text)
    if not run:
        return {"run": None, "passed": None, "skipped": None, "failures": None, "errors": None}
    tail = text[run.end():]
    counts = {key: int(match.group(1)) if (match := re.search(key + r"=(\d+)", tail)) else 0
              for key in ("skipped", "failures", "errors")}
    count = int(run.group(1))
    passed = max(0, count - sum(counts.values())) if re.search(r"(?:^|\n)(?:OK|FAILED)", tail) else None
    return {"run": count, "passed": passed, **counts}


def aggregate(cases):
    statuses = [item["status"] for item in cases]
    if any(status in {"failed", "outcome_unknown", "interrupted", "running"} for status in statuses):
        return "failed", 1
    if not statuses or any(status != "passed" for status in statuses):
        return "incomplete", 2
    return "passed", 0


def _window_title(window):
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(window, buffer, len(buffer))
    return buffer.value


def _close_window(window):
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.PostMessageW.restype = wintypes.BOOL
    return bool(user32.PostMessageW(window, 0x10, 0, 0))  # WM_CLOSE, never arbitrary input


def _new_output(path):
    absolute = Path(os.path.abspath(path))
    for parent in (absolute, *absolute.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Output cannot use linked paths")
    absolute.mkdir(parents=True, exist_ok=False)
    return absolute


class WindowsSmoke:
    def __init__(self, options, *, clock=time.monotonic):
        self.options, self.clock = options, clock
        self.output = _new_output(options.output)
        self.started = clock()
        self.deadline = self.started + options.deadline_seconds
        self.cleanup_reserve = min(3.0, options.deadline_seconds / 10)
        self.halt_reason = None
        self.active = None
        self.report = {"schema_version": 1, "kit_source_version": __version__,
                       "started_utc": now(), "status": "running", "platform": sys.platform,
                       "deadline_seconds": options.deadline_seconds,
                       "cleanup_reserve_seconds": self.cleanup_reserve,
                       "source_execution": True, "installed_package_validation": False,
                       "real_model_call": False, "live_browser_execution": False,
                       "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "scope": "sequential owned Windows fixtures; independent per-script states",
                       "limits": ["Shared state is not a desktop-wide lock",
                                  "Only directly held child processes may be terminated",
                                  "Timeout cleanup cannot prove all descendants have exited",
                                  "Native OS queries and disk writes are not hard real-time operations"],
                       "cases": []}
        self.persist()

    def remaining(self, *, work=False):
        reserve = self.cleanup_reserve if work else 0
        return max(0.0, self.deadline - self.clock() - reserve)

    def persist(self):
        self.report["elapsed_seconds"] = round(self.clock() - self.started, 3)
        atomic_json(self.output / "summary.json", self.report)

    def terminate_direct(self, process):
        """Use the held Popen object, never a discovered PID or process name."""
        result = {"pid": process.pid, "direct_child_only": True, "forced": False,
                  "possible_descendants": "not_established"}
        if process.poll() is None:
            result["forced"] = True
            result["possible_descendants"] = "unknown"
            try:
                process.kill()
                if self.remaining() > 0:
                    process.wait(timeout=min(2.0, self.remaining()))
            except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, KeyboardInterrupt):
                    result["interrupted"] = True
                    self.halt_reason = "operator_interrupt_during_cleanup"
        result.update(exited=process.poll() is not None, exit_code=process.poll())
        return result

    def command(self, label, argv, *, timeout=120, expected_exit=0):
        if self.remaining(work=True) <= 0:
            return {"status": "not_run", "reason": "suite_deadline", "label": label}
        logs = self.output / "logs"
        logs.mkdir(exist_ok=True)
        stdout_path, stderr_path = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
        row = {"label": label, "argv": [str(x) for x in argv], "stdout": str(stdout_path),
               "stderr": str(stderr_path), "status": "running", "started_utc": now()}
        if self.active is not None:
            self.active.setdefault("commands", []).append(row)
        self.persist()
        process = None
        stop_reason = None
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        try:
            with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                process = subprocess.Popen(row["argv"], cwd=PROJECT, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=err, shell=False, env=env)
                row["pid"] = process.pid
                self.persist()
                end = min(self.deadline - self.cleanup_reserve, self.clock() + timeout)
                while process.poll() is None:
                    if self.clock() >= end:
                        stop_reason = "deadline"
                        break
                    if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > 8 * 1024 * 1024:
                        stop_reason = "output_limit"
                        break
                    time.sleep(min(.05, max(0, end - self.clock())))
                if stop_reason:
                    row["cleanup"] = self.terminate_direct(process)
                    self.halt_reason = "command_ended_uncertainly:" + label
                row["exit_code"] = process.poll()
        finally:
            if process is not None and process.poll() is None:
                row["cleanup"] = self.terminate_direct(process)
                self.halt_reason = "direct_child_cleanup_uncertain:" + label
            row["finished_utc"] = now()
            row["stop_reason"] = stop_reason
            if stop_reason or row.get("cleanup", {}).get("forced"):
                row["status"] = "outcome_unknown"
            elif "exit_code" in row:
                row["status"] = "passed" if row["exit_code"] == expected_exit else "failed"
            else:
                row["status"] = "failed"
            self.persist()
        return row

    def stdout_json(self, result):
        path = Path(result["stdout"])
        # Each script prints a final JSON object; terminal additionally prints JSONL.
        text = path.read_bytes()[-1024 * 1024:].decode("utf-8-sig", errors="replace")
        try:
            value = strict_json(text)
            if isinstance(value, dict):
                return value
        except (ValueError, RecursionError):
            pass
        for line in reversed(text.splitlines()):
            try:
                value = strict_json(line)
                if isinstance(value, dict):
                    return value
            except (ValueError, RecursionError):
                continue
        raise ValueError("Script did not provide a JSON result")

    def child_report(self, result, path, parent):
        # Failed child reports are especially useful; retain their pointer and
        # verdict even when the subprocess already returned nonzero.
        try:
            resolved = Path(path).resolve(strict=True)
            resolved.relative_to(Path(parent).resolve(strict=True))
            value = read_json(Path(path))
        except (OSError, ValueError, KitError) as exc:
            return {**result, "status": "failed" if result["status"] == "passed" else result["status"],
                    "child_summary_available": False, "child_report_error": f"{type(exc).__name__}: {exc}"}
        status = result["status"]
        if status == "passed" and value.get("status") not in {"PASS", "passed"}:
            status = "failed"
        return {**result, "status": status,
                "child_summary_available": True,
                "child_summary": str(resolved), "child_status": value.get("status"),
                "child_summary_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()}

    def announced_report(self, result, parent):
        try:
            path = self.stdout_json(result)["summary"]
        except (OSError, ValueError, KeyError) as exc:
            return {**result, "status": "failed" if result["status"] == "passed" else result["status"],
                    "child_summary_available": False, "child_report_error": f"{type(exc).__name__}: {exc}"}
        return self.child_report(result, path, parent)

    def core(self):
        result = self.command("core", [self.options.python, "-m", "unittest", "discover", "-s", "tests", "-v"])
        if "stderr" in result:
            result["unittest"] = unittest_counts(Path(result["stderr"]).read_bytes()[-262144:].decode("utf-8", errors="replace"))
            if result["status"] == "passed" and not (result["unittest"]["run"] and
                    result["unittest"]["passed"] is not None and not result["unittest"]["failures"] and not result["unittest"]["errors"]):
                result["status"] = "failed"
        return result

    def doctor(self):
        result = self.command("doctor", [self.options.python, "-m", "rdc_operator", "--config", self.options.config, "doctor"], timeout=45)
        if result["status"] == "passed":
            value = self.stdout_json(result)
            result["adapter_statuses"] = {k: v.get("status") for k, v in value.get("adapters", {}).items()}
            if value.get("kit") != __version__ or value.get("platform") != "Windows" or "probe_failed" in result["adapter_statuses"].values():
                result["status"] = "failed"
            result["scope"] = "executable discovery, not functional readiness"
        return result

    def liveness(self):
        result = self.command("liveness", [self.options.python, "scripts/probe_terminal_liveness.py", "--output-dir", self.output / "liveness"], timeout=45)
        return self.announced_report(result, self.output)

    def terminal(self):
        result = self.command("terminal", [self.options.terminal_python or self.options.python, "scripts/smoke_terminal.py", "--config", self.options.config], timeout=180)
        return self.announced_report(result, PROJECT / "evidence")

    def mcp(self):
        if not self.options.mcp_python:
            return {"status": "skipped", "reason": "separate_mcp_python_not_supplied"}
        destination = self.output / "mcp"
        result = self.command("mcp", [self.options.mcp_python, "scripts/smoke_mcp.py", "--output-dir", destination], timeout=90)
        return self.child_report(result, destination / "summary.json", self.output)

    def browser_offline(self):
        cases = {"counter-success": (0, "verified_fixture"), "lost-response": (1, "outcome_unknown"),
                 **{name: (1, "unverified") for name in ("ack-without-effect", "echo-is-not-effect", "reused-tab", "stale-screenshot")}}
        results = []
        for name, (code, expected) in cases.items():
            if self.halt_reason or self.remaining(work=True) <= 0:
                results.append({"name": name, "status": "not_run", "reason": self.halt_reason or "suite_deadline"})
                continue
            result = self.command("browser-" + name, [self.options.python, "scripts/verify_browser_evidence.py", "examples/browser-evidence/" + name + ".json"], timeout=10, expected_exit=code)
            if result["status"] == "passed":
                verdict = self.stdout_json(result)
                result["status"] = "passed" if verdict.get("status") == expected and verdict.get("live_execution_verified") is False else "failed"
                result["verdict"] = verdict.get("status")
            results.append({"name": name, **result})
        status, _ = aggregate(results)
        return {"status": status, "fixtures": results, "live_browser_execution": False}

    def omp_preview(self):
        if not isinstance(self.config.get("omp"), dict):
            return {"status": "skipped", "reason": "omp_route_not_configured", "real_model_call": False}
        brief = self.output / "omp-preview-brief.md"
        brief.write_text("# Synthetic preview only\n\nGoal: validate frozen dry-run receipt.\nRetry-Safe: read-only\nNo real worker may be started.\n", encoding="utf-8")
        request = {"request_id": "preview-once", "action": "omp.preview", "args": {
            "job": "smoke-preview-" + uuid.uuid4().hex[:12], "brief": str(brief), "cwd": str(PROJECT),
            "model": "lunaroute/glm-5.3-flash", "effort": "max", "max_attempts": 1,
            "attempt_timeout": 30, "total_timeout": 30}}
        request_path = self.output / "omp-preview-request.json"
        atomic_json(request_path, request)
        result = self.command("omp-preview", [self.options.python, "-m", "rdc_operator", "--config", self.options.config,
            "--state", self.output / "state", "call", request_path, "--apply"], timeout=40)
        if result["status"] == "passed":
            receipt = self.stdout_json(result)
            payload = receipt.get("result", {})
            result["status"] = "passed" if (receipt.get("status") == "completed" and payload.get("native_status") == "DRY_RUN" and payload.get("real_model_call") is False) else "failed"
            result["native_receipt"] = payload.get("native_receipt")
        result["real_model_call"] = False
        return result

    def wait_fixture(self, process, witness_path, fixture, timeout=20):
        end = min(self.deadline - self.cleanup_reserve, self.clock() + timeout)
        while self.clock() < end and process.poll() is None:
            try:
                witness = read_json(witness_path)
            except KitError:
                time.sleep(min(.05, max(0, end - self.clock())))
                continue
            if type(witness.get("pid")) is not int or witness["pid"] != process.pid:
                raise RuntimeError("Fixture witness PID differs from the held launcher; no child adoption is allowed")
            window = witness.get("hwnd")
            if type(window) is not int or window <= 0 or witness.get("last_event") != "ready":
                raise RuntimeError("Fixture did not expose a fresh ready HWND")
            identity = _window_identity(window)
            if identity["pid"] != process.pid or _window_title(window) != FIXTURES[fixture][1]:
                raise RuntimeError("Fixture HWND/PID/title did not identify the owned process")
            if os.path.normcase(os.path.normpath(identity["executable"])) != os.path.normcase(str(Path(self.options.powershell).resolve())):
                raise RuntimeError("Fixture executable differs from the explicitly selected PowerShell")
            if fixture == "desktop" and witness.get("count") != 0:
                raise RuntimeError("Desktop fixture was already changed")
            if fixture == "observation" and (not re.fullmatch(r"[0-9a-f]{12}", witness.get("nonce", "")) or witness.get("action_count") != 0 or witness.get("frame_seq") != 0):
                raise RuntimeError("Observation fixture nonce or initial state is invalid")
            if process.poll() is not None or _window_identity(window) != identity:
                raise RuntimeError("Fixture identity changed during readiness validation")
            return witness, identity
        raise TimeoutError("Owned fixture did not become ready within the remaining budget")

    def cleanup_fixture(self, process, identity, witness_path):
        cleanup = {"pid": process.pid, "normal_close_sent": False, "identity_rechecked": False,
                   "forced": False, "possible_descendants": "not_established"}
        if process.poll() is None and identity is not None:
            try:
                if _window_identity(identity["window"]) == identity:
                    cleanup["identity_rechecked"] = True
                    cleanup["normal_close_sent"] = _close_window(identity["window"])
            except (KitError, OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                cleanup["normal_close_error"] = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, KitError) and exc.code == "window_not_found":
                    cleanup["window_already_closed"] = True
                if isinstance(exc, KeyboardInterrupt):
                    cleanup["interrupted"] = True
                    self.halt_reason = "operator_interrupt_during_cleanup"
        # A nested smoke may have closed its own HWND already. Destruction of
        # that window precedes PowerShell's process exit; wait on the original
        # held handle before concluding cleanup needs force. Never adopt a PID.
        if process.poll() is None and self.remaining() > 0:
            try:
                process.wait(timeout=min(2.0, self.remaining()))
            except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                cleanup["exit_wait_error"] = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, KeyboardInterrupt):
                    cleanup["interrupted"] = True
                    self.halt_reason = "operator_interrupt_during_cleanup"
        if process.poll() is None:
            cleanup.update(self.terminate_direct(process))
            self.halt_reason = "fixture_cleanup_forced_or_uncertain"
        cleanup.update(exited=process.poll() is not None, exit_code=process.poll())
        try:
            cleanup["witness_closed"] = read_json(witness_path).get("last_event") == "closed"
        except KitError:
            cleanup["witness_closed"] = False
        cleanup["verified"] = (cleanup["exited"] and cleanup["exit_code"] == 0 and
                               cleanup["witness_closed"] and not cleanup["forced"] and
                               not cleanup.get("interrupted"))
        return cleanup

    def gui(self, fixture):
        folder = self.output / (fixture + "-fixture")
        folder.mkdir()
        witness_path = folder / ("witness-" + uuid.uuid4().hex + ".json")
        script, title = FIXTURES[fixture]
        argv = [str(self.options.powershell), "-NoProfile", "-STA", "-File", str(PROJECT / "examples" / script), "-EvidencePath", str(witness_path)]
        process, identity = None, None
        result = {"status": "failed", "fixture": fixture, "witness": str(witness_path)}
        try:
            with (folder / "fixture.stdout.log").open("wb") as out, (folder / "fixture.stderr.log").open("wb") as err:
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=PROJECT, shell=False)
                result["fixture_pid"] = process.pid
                self.active["fixture"] = result
                self.persist()
                witness, identity = self.wait_fixture(process, witness_path, fixture)
                result.update(identity=identity, title_verified=True, nonce=witness.get("nonce"))
                from rdc_operator.windows import inspect_windows_context
                atomic_json(folder / "preflight.json", inspect_windows_context(witness["hwnd"]))
                self.persist()
                destination = folder / "desktop.json" if fixture == "desktop" else folder / "observation"
                command = self.command(fixture, [self.options.python, "scripts/smoke_" + fixture + ".py", "--config", self.options.config,
                    "--witness", witness_path, "--output", destination], timeout=90)
                result.update(self.child_report(command, destination if fixture == "desktop" else destination / "summary.json", folder))
        finally:
            if process is not None:
                result["cleanup"] = self.cleanup_fixture(process, identity, witness_path)
                if not result["cleanup"]["verified"]:
                    result["status"] = "failed"
                self.persist()
        return result

    def run(self, plan=None):
        """The optional plan is a test seam; production always uses CASE_ORDER."""
        if plan is None:
            plan = [(name, CASE_KINDS[name],
                     (lambda name=name: self.gui(name)) if name in FIXTURES else getattr(self, name)) for name in CASE_ORDER]
        try:
            for name, kind, body in plan:
                row = {"name": name, "kind": kind, "status": "running", "started_utc": now()}
                self.report["cases"].append(row)
                self.active = row
                if self.halt_reason or self.remaining(work=True) <= 0:
                    row.update(status="not_run", reason=self.halt_reason or "suite_deadline")
                else:
                    self.persist()
                    try:
                        result = body()
                        row.update(result)
                        if row["status"] not in {"passed", "failed", "outcome_unknown", "skipped", "not_run", "incomplete"}:
                            raise ValueError("Case returned no final status")
                    except KeyboardInterrupt:
                        row.update(status="interrupted", reason="operator_interrupt")
                        self.halt_reason = "operator_interrupt"
                    except Exception as exc:
                        row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                row["finished_utc"] = now()
                self.persist()
                print(json.dumps({"case": name, "status": row["status"], "summary": str(self.output / "summary.json")}), flush=True)
        finally:
            self.active = None
            self.report["status"], code = aggregate(self.report["cases"])
            self.report.update(finished_utc=now(), exit_code=code, halt_reason=self.halt_reason)
            self.persist()
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new, nonexistent evidence directory")
    parser.add_argument("--python", type=Path, required=True, help="absolute actual CPython base executable")
    parser.add_argument("--powershell", type=Path, required=True, help="absolute actual PowerShell 7 pwsh.exe, not a PATH redirector")
    parser.add_argument("--terminal-python", type=Path, help="SmartCLI environment Python; defaults to --python")
    parser.add_argument("--mcp-python", type=Path, help="separate MCP SDK environment Python; otherwise MCP is skipped")
    parser.add_argument("--deadline-seconds", type=float, default=600)
    args = parser.parse_args(argv)
    if not math.isfinite(args.deadline_seconds) or not 1 <= args.deadline_seconds <= 3600:
        parser.error("deadline must be finite and between 1 and 3600 seconds")
    runner = None
    try:
        runner = WindowsSmoke(args)
        if os.name != "nt":
            runner.halt_reason = "unsupported_platform"
        else:
            for key in ("python", "powershell", "terminal_python", "mcp_python"):
                path = getattr(args, key)
                if path is not None and (not path.is_absolute() or not path.is_file()):
                    raise ValueError(f"{key} must be an existing absolute executable")
            if args.powershell.name.casefold() != "pwsh.exe":
                raise ValueError("Use the actual absolute PowerShell 7 pwsh.exe, not powershell.exe or a PATH shim")
            args.config = args.config.resolve(strict=True)
            runner.config = read_json(args.config)
            allowed_path(str(runner.output), runner.config)
            runner.report["config_sha256_before"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
        code = runner.run()
        if hasattr(runner, "config"):
            digest = hashlib.sha256(args.config.read_bytes()).hexdigest()
            runner.report["config_sha256_after"] = digest
            runner.report["config_unchanged"] = digest == runner.report["config_sha256_before"]
            if not runner.report["config_unchanged"]:
                runner.report.update(status="failed", exit_code=1)
                code = 1
            runner.persist()
        return code
    except Exception as exc:
        if runner is not None:
            runner.report.update(status="failed", exit_code=1, finished_utc=now(), error=f"{type(exc).__name__}: {exc}")
            runner.persist()
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

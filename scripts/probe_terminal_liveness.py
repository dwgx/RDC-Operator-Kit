"""Bounded liveness experiments on freshly owned synthetic pipe children only.

This is a diagnostic fixture, not a new terminal adapter or universal hang
detector. It does not attach to arbitrary commands, PIDs, sessions or a daemon.
It does not use a PTY: ConPTY/TUI coverage remains in smoke_terminal.py.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from rdc_operator.common import atomic_json

FIXTURE = PROJECT / "examples" / "liveness-fixture.py"
CASES = ("silent", "silent-input", "waiting-input", "flood", "timeout",
         "exit-no-marker", "ready-only", "marker-no-witness", "wrong-token")
PREFIX = b"RDC_LIVENESS "
EVENTS = {"waiting_input", "ready", "business_done", "flood_started"}


def _fixture_interpreter():
    """Select the actual CPython executable for this stdlib-only fixture.

    Windows venv python.exe can be a redirector which creates another process.
    Its Popen PID is then not the fixture PID. Do not relax identity matching or
    adopt the PID found in a witness to compensate for this distinction.
    """
    requested = sys.executable
    if sys.platform == "win32":
        selected = getattr(sys, "_base_executable", None)
        reason = "windows_cpython_base_executable_for_stdlib_fixture"
        if not isinstance(selected, str) or not selected:
            raise RuntimeError("Windows fixture requires an explicit CPython base executable")
    else:
        selected = requested
        reason = "current_interpreter_on_non_windows"
    candidate = Path(selected)
    if not candidate.is_absolute() or not candidate.is_file():
        raise RuntimeError("Fixture interpreter must be an existing absolute executable path")
    return {"requested_executable": requested,
            "selected_executable": str(candidate.resolve(strict=True)),
            "selection_reason": reason}


class _Drain:
    """One reader per output channel; retained output and parser state are bounded."""

    def __init__(self, pipe, token: str, capture_limit: int, protocol: bool):
        self.pipe, self.token = pipe, token
        self.capture_limit, self.protocol = capture_limit, protocol
        self.total = 0
        self.retained = bytearray()
        self.events = set()
        self.eof = False
        self.error = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        partial = bytearray()
        discard_line = False
        try:
            while True:
                chunk = self.pipe.read(4096)
                if not chunk:
                    break
                found = set()
                if self.protocol:
                    # Overlong lines are discarded through their newline. A marker
                    # in the middle of a flood/echo line is never a new record.
                    for piece in chunk.splitlines(keepends=True):
                        terminated = piece.endswith(b"\n")
                        if not discard_line:
                            partial.extend(piece)
                            if len(partial) > 1024:
                                discard_line = True
                                partial.clear()
                        if terminated:
                            if not discard_line and partial.startswith(PREFIX):
                                try:
                                    value = json.loads(partial[len(PREFIX):])
                                    if (isinstance(value, dict) and
                                            value.get("token") == self.token and
                                            value.get("event") in EVENTS):
                                        found.add(value["event"])
                                except (ValueError, TypeError):
                                    pass
                            partial.clear()
                            discard_line = False
                with self.lock:
                    self.total += len(chunk)
                    self.retained.extend(chunk[:max(0, self.capture_limit - len(self.retained))])
                    self.events.update(found)
        except (OSError, ValueError) as exc:
            with self.lock:
                self.error = type(exc).__name__
        finally:
            with self.lock:
                self.eof = True

    def snapshot(self):
        with self.lock:
            return {"bytes_read": self.total, "bytes_retained": len(self.retained),
                    "truncated": self.total > len(self.retained),
                    "events": sorted(self.events), "eof": self.eof, "error": self.error}


class OwnedFixture:
    """Holds exactly the Popen created here; accepts no PID or command string."""

    def __init__(self, case: str, directory: Path, *, capture_limit: int = 4096):
        if case not in CASES:
            raise ValueError("Only the listed synthetic fixture cases are allowed")
        if not 128 <= capture_limit <= 65536:
            raise ValueError("capture_limit must be 128..65536 bytes per stream")
        self.case, self.token = case, uuid.uuid4().hex
        self.witness = Path(directory) / ("witness-" + self.token + ".json")
        self.cleanup = None
        self.started = time.monotonic()
        self.launch_identity = _fixture_interpreter()
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        self.child = subprocess.Popen(
            [self.launch_identity["selected_executable"], "-u", str(FIXTURE), "--case", case,
             "--token", self.token, "--witness", str(self.witness)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, shell=False, env=env)
        self.launch_identity["held_process_pid"] = self.child.pid
        try:
            self.stdout = _Drain(self.child.stdout, self.token, capture_limit, True)
            self.stderr = _Drain(self.child.stderr, self.token, capture_limit, False)
        except BaseException:
            self.child.kill()
            self.child.wait(timeout=2)
            raise
        self.input_sent = False

    def observe(self):
        started = time.perf_counter()
        code = self.child.poll()
        out, err = self.stdout.snapshot(), self.stderr.snapshot()
        result = {"alive": code is None, "exit_code": code,
                  "elapsed_ms": round((time.monotonic() - self.started) * 1000, 3),
                  "stdout": out, "stderr": err,
                  "waiting_input_declared": "waiting_input" in out["events"],
                  "ready_marker_seen": "ready" in out["events"],
                  "completion_marker_seen": "business_done" in out["events"]}
        result["return_latency_ms"] = round((time.perf_counter() - started) * 1000, 6)
        return result

    def continue_input(self):
        # This tiny known input fits a fresh owned fixture's stdin pipe. It is
        # not a generic promise that writing arbitrary bytes cannot block.
        if self.case != "waiting-input" or self.input_sent:
            raise ValueError("Only one declared waiting-input continuation is allowed")
        if not self.observe()["waiting_input_declared"]:
            raise ValueError("No fixture input request has been observed")
        started = time.perf_counter()
        payload = ("continue " + self.token + "\n").encode("ascii")
        written = self.child.stdin.write(payload)
        self.child.stdin.flush()
        self.input_sent = True
        if written != len(payload):
            raise RuntimeError("Incomplete fixture input; do not replay")
        return {"bytes_written": written,
                "return_latency_ms": round((time.perf_counter() - started) * 1000, 6)}

    def finish(self, reason: str):
        if self.cleanup is not None:
            return self.cleanup
        started = time.perf_counter()
        was_alive = self.child.poll() is None
        action = "already_exited"
        if was_alive:
            action = "terminate"
            self.child.terminate()
            try:
                self.child.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                action = "terminate_then_kill"
                self.child.kill()
                try:
                    self.child.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    action = "kill_unconfirmed"
        # Continue draining while waiting for exit; do not block a close on a
        # reader which itself needs the child to exit. The fixture source does
        # not spawn, but that fact alone says nothing about a launcher's process
        # topology. Only this held direct child is controlled or confirmed here.
        # The deadline is shared by both joins.
        join_deadline = time.monotonic() + 0.5
        for drain in (self.stdout, self.stderr):
            drain.thread.join(max(0, join_deadline - time.monotonic()))
            if not drain.thread.is_alive():
                drain.pipe.close()
        self.child.stdin.close()
        self.cleanup = {"reason": reason, "action": action, "was_alive": was_alive,
                        "direct_child_exit_confirmed": self.child.poll() is not None,
                        "exit_code": self.child.returncode,
                        "readers_joined": not self.stdout.thread.is_alive() and not self.stderr.thread.is_alive(),
                        "scope": "held Popen direct child only; no descendant exit claim",
                        "arbitrary_pid_selection": False,
                        "return_latency_ms": round((time.perf_counter() - started) * 1000, 3)}
        return self.cleanup


def _witness_evidence(child: OwnedFixture):
    result = {"present": False, "valid": False, "held_process_pid": child.child.pid,
              "fixture_pid": None, "pid_matches_held_child": False}
    try:
        if child.witness.stat().st_size > 2048:
            return {**result, "present": True, "reason": "witness_too_large"}
        value = json.loads(child.witness.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {**result, "reason": "missing_witness"}
    except (OSError, ValueError):
        return {**result, "reason": "unreadable_witness"}
    result["present"] = True
    if not isinstance(value, dict) or type(value.get("pid")) is not int:
        return {**result, "reason": "invalid_witness_shape"}
    result["fixture_pid"] = value["pid"]
    result["pid_matches_held_child"] = value["pid"] == child.child.pid
    if not result["pid_matches_held_child"]:
        return {**result, "reason": "pid_mismatch"}
    valid = value == {"token": child.token, "case": "waiting-input", "value": 42,
                      "input_accepted": True, "pid": child.child.pid}
    return {**result, "valid": valid, "reason": "matched" if valid else "payload_mismatch"}


def _witness_valid(child: OwnedFixture):
    return _witness_evidence(child)["valid"]


def run_case(case: str, *, deadline_ms: int = 1200, sample_ms: int = 150,
             capture_limit: int = 4096, output_limit: int = 131072):
    if not 400 <= deadline_ms <= 3000 or not 20 <= sample_ms < deadline_ms:
        raise ValueError("Use deadline_ms 400..3000 and sample_ms 20..deadline_ms-1")
    if not 16384 <= output_limit <= 1048576:
        raise ValueError("output_limit must be 16 KiB..1 MiB")
    with tempfile.TemporaryDirectory(prefix="rdck-liveness-") as directory:
        child = OwnedFixture(case, Path(directory), capture_limit=capture_limit)
        initial = child.observe()
        deadline = child.started + deadline_ms / 1000
        decision, before_input, input_receipt = None, None, None
        observations = 0
        maximum_latency = 0.0
        try:
            while True:
                state = child.observe()
                observations += 1
                maximum_latency = max(maximum_latency, state["return_latency_ms"])
                total = state["stdout"]["bytes_read"] + state["stderr"]["bytes_read"]
                if total >= output_limit:
                    decision = "output_limit_reached"
                    break
                if not state["alive"] and state["stdout"]["eof"] and state["stderr"]["eof"]:
                    decision = "process_exited"
                    break
                if case == "waiting-input" and state["waiting_input_declared"] and not child.input_sent:
                    before_input = state
                    input_receipt = child.continue_input()
                if state["elapsed_ms"] >= sample_ms:
                    if case in ("silent", "silent-input"):
                        decision = "sample_returned_while_running"
                        break
                    if case == "ready-only" and state["ready_marker_seen"]:
                        decision = "ready_observed_without_completion"
                        break
                if time.monotonic() >= deadline:
                    decision = "deadline_exceeded"
                    break
                time.sleep(0.005)
        finally:
            cleanup = child.finish(decision or "probe_interrupted")
        final = child.observe()
        witness = _witness_evidence(child)
        verified = (final["completion_marker_seen"] and witness["valid"]
                    and final["exit_code"] == 0 and cleanup["readers_joined"])
        if verified:
            classification = "business_completed"
        elif decision == "deadline_exceeded":
            classification = "deadline_exceeded"
        elif decision == "output_limit_reached":
            classification = "output_limit_reached"
        elif case in ("silent", "silent-input") and state["alive"]:
            classification = "running_silent" if total == 0 else "running_with_output"
        elif final["ready_marker_seen"]:
            classification = "ready_without_completion"
        elif final["completion_marker_seen"]:
            classification = "completion_marker_without_witness"
        else:
            classification = "exited_without_completion"
        return {"case": case, "transport": "subprocess pipes; not a PTY",
                "classification": classification, "decision": decision,
                "initial_observation": initial, "decision_observation": state,
                "before_input": before_input, "input_receipt": input_receipt,
                "final_observation": final, "semantic_verified": verified,
                "independent_witness_valid": witness["valid"],
                "witness_verification": witness, "launch_identity": child.launch_identity,
                "deadline_ms": deadline_ms, "sample_ms": sample_ms,
                "output_limit_bytes": output_limit, "capture_limit_per_stream": capture_limit,
                "observation_count": observations,
                "max_observation_return_latency_ms": maximum_latency,
                "wall_time_ms": round((time.monotonic() - child.started) * 1000, 3),
                "cleanup": cleanup}


def expectations(result):
    expected = {"silent": "running_silent", "silent-input": "running_silent",
                "waiting-input": "business_completed", "flood": "output_limit_reached",
                "timeout": "deadline_exceeded", "exit-no-marker": "exited_without_completion",
                "ready-only": "ready_without_completion",
                "marker-no-witness": "completion_marker_without_witness",
                "wrong-token": "exited_without_completion"}
    return (result["classification"] == expected[result["case"]]
            and result["cleanup"]["direct_child_exit_confirmed"]
            and result["cleanup"]["readers_joined"]
            and not result["final_observation"]["stdout"]["error"]
            and not result["final_observation"]["stderr"]["error"])


class _ArchiveFailure(Exception):
    """A checkpoint did not return successfully; it may have replaced the file."""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *CASES), default="all")
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "evidence")
    args = parser.parse_args(argv)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.output_dir / ("liveness-" + timestamp + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / "summary.json"
    planned = list(CASES if args.case == "all" else (args.case,))
    report = {"schema_version": 1, "status": "RUNNING", "phase": "initializing",
              "scope": "fresh synthetic direct children; pipe transport only",
              "started_utc": timestamp, "platform": platform.platform(),
              "python": sys.version.split()[0], "planned_cases": planned,
              "active_case": None, "cases": [], "interrupted": False,
              "error": None, "archive_error": None, "source_sha256": {}}
    started = time.monotonic()
    summary_current = False
    exit_code = 1

    def checkpoint():
        nonlocal summary_current
        summary_current = False
        try:
            atomic_json(output, report)
        except KeyboardInterrupt as exc:
            report.update(interrupted=True,
                          error={"type": "KeyboardInterrupt", "message": "Interrupted while archiving probe evidence"})
            raise _ArchiveFailure("KeyboardInterrupt: checkpoint interrupted") from exc
        except Exception as exc:
            raise _ArchiveFailure(f"{type(exc).__name__}: {exc}") from exc
        summary_current = True

    def archive_failed(exc):
        nonlocal exit_code
        exit_code = 130 if report["interrupted"] else 3
        report.update(status="FAIL", phase="archive_failed", archive_error=str(exc), exit_code=exit_code)

    try:
        # Do not launch a child if its initial intent cannot be archived.
        checkpoint()
        report["source_sha256"] = {
            str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(), FIXTURE)}
        for case in planned:
            report.update(phase="case_running", active_case=case)
            checkpoint()
            result = run_case(case)
            report["cases"].append(result)
            report.update(phase="case_complete", active_case=None)
            checkpoint()
        passed = all(expectations(result) for result in report["cases"])
        report.update(status="PASS" if passed else "FAIL", phase="finished")
        exit_code = 0 if passed else 1
    except KeyboardInterrupt:
        report.update(status="FAIL", phase="interrupted", interrupted=True,
                      error={"type": "KeyboardInterrupt", "message": "Probe interrupted; no later case started"})
        exit_code = 130
    except _ArchiveFailure as exc:
        archive_failed(exc)
    except Exception as exc:
        report.update(status="FAIL", phase="failed",
                      error={"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1
    finally:
        report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                      exit_code=exit_code)
        if report["active_case"] is not None:
            # run_case did not return: never infer its cleanup from an exception.
            report["incomplete_case"] = {"case": report["active_case"],
                                         "result_returned": False, "cleanup_verified": None}
        already_failed_to_archive = report["archive_error"] is not None
        try:
            checkpoint()
        except _ArchiveFailure as exc:
            archive_failed(exc)
            if not already_failed_to_archive:
                # A failing replace/fsync can leave a prior PASS on disk. Make
                # one bounded attempt to archive the conservative failure state.
                try:
                    checkpoint()
                except _ArchiveFailure as final_exc:
                    archive_failed(final_exc)
    print(json.dumps({"status": report["status"],
                      "summary": str(output) if output.is_file() else None,
                      "summary_current": summary_current, "exit_code": exit_code,
                      "error": report["error"], "archive_error": report["archive_error"],
                      "cases": [{"case": r.get("case"), "classification": r.get("classification"),
                                 "semantic_verified": r.get("semantic_verified"),
                                 "wall_time_ms": r.get("wall_time_ms")} for r in report["cases"]]}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

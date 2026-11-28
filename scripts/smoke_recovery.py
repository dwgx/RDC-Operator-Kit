"""Bounded local recovery acceptance with a real deliberately interrupted child.

The child writes a synthetic effect and exits before its receipt is committed.
No RDC login, account change, GUI, model or actual terminal adapter is involved.
Use --installed with an installed interpreter and -I to check site-packages.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import time
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]


def load_kit(installed, worker_package_root=None):
    if not installed:
        sys.path.insert(0, str(PROJECT))
    elif worker_package_root is not None:
        sys.path.insert(0, str(worker_package_root))
    import rdc_operator
    from rdc_operator import recovery
    if installed:
        purelib = (worker_package_root or Path(sysconfig.get_path("purelib"))).resolve()
        for module in (rdc_operator, recovery):
            Path(module.__file__).resolve().relative_to(purelib)
    return rdc_operator, recovery


def utc():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        result[path.relative_to(root).as_posix()] = {
            "mode": info.st_mode, "mtime_ns": info.st_mtime_ns,
            "identity": [info.st_dev, info.st_ino],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}
    return result


class ReadOnlyGuard:
    """Detect Python-level effects during assessment; not an OS sandbox."""
    def __init__(self):
        self.active = False
        self.attempts = []
        self.calls = 0
        sys.addaudithook(self.audit)

    def deny(self, name):
        self.attempts.append(name)
        raise RuntimeError("read-only assessment attempted " + name)

    def audit(self, event, args):
        if not self.active:
            return
        if event == "open":
            mode, flags = args[1], args[2]
            if ((isinstance(mode, str) and any(char in mode for char in "wax+")) or
                    (isinstance(flags, int) and flags &
                     (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))):
                self.deny("open_write")
        if event in {"os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.truncate",
                     "os.link", "os.symlink", "os.chmod", "os.chown", "os.utime",
                     "os.system", "os.posix_spawn", "os.spawn", "subprocess.Popen"} or event.startswith("socket."):
            self.deny(event)

    def assess(self, function, *args, **kwargs):
        # Import before enabling audit so imports are not mistaken for recovery I/O.
        from rdc_operator import adapters, omp
        self.calls += 1
        before = len(self.attempts)
        with patch.object(adapters, "execute", side_effect=lambda *_a, **_k: self.deny("adapter.execute")), \
                patch.object(omp, "execute", side_effect=lambda *_a, **_k: self.deny("omp.execute")), \
                patch.object(os, "write", side_effect=lambda *_a, **_k: self.deny("os.write")):
            self.active = True
            try:
                return function(*args, **kwargs)
            finally:
                self.active = False
                if len(self.attempts) != before:
                    # An implementation catching the deny exception cannot hide an attempt.
                    raise RuntimeError("read-only assessment attempted a forbidden effect")


def launch_worker(command, output):
    """Hold a direct interpreter and use files so inherited PIPEs cannot stall exit."""
    child = None
    outcome = {"exit_code": None, "held_pid": None, "forced_cleanup": False,
               "cleanup_complete": False, "worker_prefix_may_differ": True}
    try:
        with (output / "child.stdout.log").open("wb") as stdout, \
                (output / "child.stderr.log").open("wb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     stdin=subprocess.DEVNULL, cwd=output, shell=False)
            outcome["held_pid"] = child.pid
            deadline = time.monotonic() + 45
            while child.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("owned recovery fixture exceeded 45 seconds")
                if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > 2 * 1024 * 1024:
                    raise RuntimeError("owned recovery fixture exceeded its output guard")
                time.sleep(0.02)
            outcome["exit_code"] = child.returncode
    finally:
        try:
            if child is not None:
                if child.poll() is None:
                    outcome["forced_cleanup"] = True
                    child.kill()
                outcome["exit_code"] = child.wait(timeout=5)
                outcome["cleanup_complete"] = True
        finally:
            dump(output / "child.json", outcome)
    return outcome


def dump(path, value):
    from rdc_operator.common import atomic_json
    atomic_json(path, value)


def fixture(root):
    workspace = root / "owned workspace"
    workspace.mkdir()
    config = {"schema_version": 1, "allowed_roots": [str(root)],
              "smartcli": [sys.executable], "winapp": [sys.executable],
              "observation_ttl_seconds": 120}
    request = {"request_id": "lost-reply", "action": "terminal.start",
               "args": {"session": "owned-fixture", "command": "fixture-never-launched",
                        "cwd": str(workspace)}}
    return config, request


def checkpoint(task_id, requests):
    return {"schema_version": 1, "task_id": task_id,
            "scope_sha256": hashlib.sha256(b"owned recovery smoke scope").hexdigest(),
            "route": {"link_id": "synthetic-old-link", "device_id": "synthetic-device",
                      "observed_utc": utc()},
            "event": "same_connection", "request_ids": requests,
            "handles": [{"kind": "rdc_call", "id": "synthetic-pending-call"},
                        {"kind": "process", "id": "424242"}],
            "stop_reason": "none"}


def context(document, changed=True):
    value = {key: copy.deepcopy(document[key]) for key in
             ("schema_version", "scope_sha256", "route", "event", "stop_reason")}
    value["route"]["observed_utc"] = utc()
    if changed:
        value["route"]["link_id"] = "synthetic-new-link"
        value["event"] = "user_reconnected"
    return value


def worker(root, installed, worker_package_root=None):
    kit, recovery = load_kit(installed, worker_package_root)
    from rdc_operator.common import read_json
    from rdc_operator.core import execute_request
    config, request = read_json(root / "config.json"), read_json(root / "request.json")
    dump(root / "worker-import.json", {
        "pid": os.getpid(), "executable": sys.executable, "prefix": sys.prefix,
        "module_file": str(Path(recovery.__file__).resolve()),
        "module_sha256": hashlib.sha256(Path(recovery.__file__).read_bytes()).hexdigest(),
        "kit_version": kit.__version__, "installed_package_requested": installed,
        "import_mode": "explicit_verified_purelib" if worker_package_root else "source"})

    def effect_then_exit(*_args):
        dump(root / "effect.json", {"effect_count": 1, "fixture": True})
        # Deliberate process exit, not an exception converted into a receipt.
        os._exit(73)

    execute_request(request, config, root / "state", apply=True, operation=effect_then_exit)
    raise RuntimeError("interrupted child unexpectedly returned")


def run(args):
    kit, recovery = load_kit(args.installed)
    from rdc_operator.common import KitError
    from rdc_operator.core import execute_request
    from rdc_operator.mcp_server import _unlinked

    output = Path(os.path.abspath(args.output_dir))
    _unlinked(output)
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    report = {"schema_version": 1, "started_utc": utc(), "kit_version": kit.__version__,
              "platform": platform.platform(), "python": platform.python_version(),
              "module_file": str(Path(recovery.__file__).resolve()),
              "module_sha256": hashlib.sha256(Path(recovery.__file__).read_bytes()).hexdigest(),
              "source_execution": not args.installed,
              "installed_package_validation": args.installed,
              "real_rdc_reauthentication": False, "fixture_uses_injected_operation": True,
              "resume_guard_scope": "Python audit events and adapter entry points, not OS containment",
              "cases": {}, "status": "running"}
    if args.installed:
        report["installed_distribution_version"] = importlib.metadata.version("rdc-operator-kit")
        if report["installed_distribution_version"] != kit.__version__:
            raise RuntimeError("installed metadata and imported package versions differ")
    dump(output / "summary.json", report)
    guard = ReadOnlyGuard()

    def check(name, condition):
        report["cases"][name] = {"passed": condition is True}
        dump(output / "summary.json", report)
        if condition is not True:
            raise AssertionError(name)

    try:
        config, request = fixture(output)
        state = output / "state"
        document = checkpoint("lost-reply-task", ["lost-reply"])
        initial = recovery.save_checkpoint(document, config, state, expected_revision=0)
        dump(output / "checkpoint-save.json", initial)
        dump(output / "config.json", config)
        dump(output / "request.json", request)
        # A Windows venv python.exe can be a redirector. Launch its actual base
        # interpreter directly and bind the worker to the parent's verified package.
        worker_python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        command = [worker_python, "-I", str(Path(__file__).resolve()),
                   "--worker", str(output)]
        if args.installed:
            command.extend(["--installed", "--worker-package-root",
                            str(Path(sysconfig.get_path("purelib")).resolve())])
        child = launch_worker(command, output)
        witness = json.loads((output / "worker-import.json").read_text(encoding="utf-8"))
        check("worker_matches_held_process_and_import",
              type(witness.get("pid")) is int and witness["pid"] == child["held_pid"] and
              witness["module_file"] == report["module_file"] and
              witness["module_sha256"] == report["module_sha256"] and
              witness["kit_version"] == report["kit_version"])
        check("real_child_exited_after_effect", child["exit_code"] == 73 and
              child["cleanup_complete"] is True and child["forced_cleanup"] is False and
              json.loads((output / "effect.json").read_text())["effect_count"] == 1)
        check("intent_survives_without_receipt",
              (state / "requests/lost-reply.intent.json").is_file() and
              not (state / "requests/lost-reply.receipt.json").exists())

        before = fingerprint(state)
        effect_before = (output / "effect.json").read_bytes()
        plan = guard.assess(recovery.assess_resume, document["task_id"], context(document), config, state)
        dump(output / "resume-lost-reply.json", plan)
        check("unknown_effect_blocks_plan", plan["status"] == "blocked")
        check("lost_request_details_and_reasons_are_preserved",
              len(plan["requests"]) == 1 and plan["requests"][0]["request_id"] == "lost-reply" and
              plan["requests"][0]["record_state"] == "intent_without_receipt" and
              plan["requests"][0]["saved_receipt_status"] is None and
              plan["requests"][0]["reconciliation_required"] is True and
              "request_reconciliation_required" in plan["blocking_reasons"])
        handles = {item["kind"]: item for item in plan["handles"]}
        check("route_and_typed_handles_require_new_observation",
              plan["route_comparison"] == "changed" and
              plan["route_handles_invalidated_for_plan"] is True and
              plan["fresh_observation_required"] is True and
              "route_changed" in plan["review_reasons"] and
              len(plan["handles"]) == 2 and set(handles) == {"rdc_call", "process"} and
              all(item["live_verification_performed"] is False and item["count"] == 1
                  for item in plan["handles"]) and
              handles["rdc_call"]["assessment"] == "invalidated_for_plan" and
              handles["rdc_call"]["requirement"] == "rediscover_on_current_route" and
              handles["process"]["assessment"] == "reidentification_required" and
              handles["process"]["requirement"] == "verify_pid_creation_time_executable_and_task_ownership")
        check("plan_does_not_authorize_execution", all(plan[key] is False for key in
              ("actions_exposed", "automatic_replay_allowed", "execution_authorized",
               "physical_device_verified", "request_config_binding_verified")))
        check("resume_preserves_every_saved_byte", fingerprint(state) == before and
              (output / "effect.json").read_bytes() == effect_before)
        called = []
        try:
            execute_request(request, config, state, apply=True,
                            operation=lambda *_: called.append("unexpected"))
        except KitError as exc:
            replay_code = exc.code
        else:
            replay_code = "unexpected_success"
        check("original_request_cannot_repeat_effect",
              replay_code == "outcome_unknown" and called == [] and
              (output / "effect.json").read_bytes() == effect_before)

        wrong_state = output / "wrong-new-state"
        try:
            guard.assess(recovery.assess_resume, document["task_id"], context(document), config, wrong_state)
        except KitError as exc:
            wrong_result = {"error": exc.code}
        else:
            wrong_result = {"unexpected_success": True}
        dump(output / "wrong-state.json", wrong_result)
        check("wrong_state_refused_without_creation",
              "error" in wrong_result and not wrong_state.exists())
        try:
            recovery.save_checkpoint(document, config, state, expected_revision=0)
        except KitError as exc:
            cas_error = exc.code
        else:
            cas_error = None
        check("stale_writer_cannot_overwrite_checkpoint",
              cas_error is not None and fingerprint(state) == before)

        # Independent positive task: its only operation has an actual receipt.
        positive = output / "positive"
        positive.mkdir()
        positive_config, completed = fixture(positive)
        completed["request_id"] = "completed-step"
        positive_state = positive / "state"
        saved = execute_request(completed, positive_config, positive_state, apply=True,
                                operation=lambda *_: {"status": "completed", "fixture": True})
        positive_doc = checkpoint("completed-task", ["completed-step"])
        recovery.save_checkpoint(positive_doc, positive_config, positive_state, expected_revision=0)
        positive_before = fingerprint(positive_state)
        positive_plan = guard.assess(recovery.assess_resume, "completed-task", context(positive_doc),
                                     positive_config, positive_state)
        dump(output / "resume-completed.json", positive_plan)
        check("completed_receipt_is_reviewable_after_route_change",
              saved["status"] == "completed" and positive_plan["status"] == "review_required" and
              positive_plan["execution_authorized"] is False and
              positive_before == fingerprint(positive_state))
        check("completed_request_details_are_preserved",
              len(positive_plan["requests"]) == 1 and
              positive_plan["requests"][0]["request_id"] == "completed-step" and
              positive_plan["requests"][0]["record_state"] == "receipt_recorded" and
              positive_plan["requests"][0]["saved_receipt_status"] == "completed" and
              positive_plan["requests"][0]["reconciliation_required"] is False)
        mismatched = context(positive_doc)
        mismatched["scope_sha256"] = "f" * 64
        mismatch_plan = guard.assess(recovery.assess_resume, "completed-task", mismatched,
                                     positive_config, positive_state)
        check("changed_scope_blocks_resume", mismatch_plan["status"] == "blocked")
        expired = context(positive_doc)
        expired["route"]["observed_utc"] = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()
        expired_plan = guard.assess(recovery.assess_resume, "completed-task", expired,
                                   positive_config, positive_state)
        check("expired_route_sample_blocks_resume", expired_plan["status"] == "blocked")
        positive_doc["stop_reason"] = "quota"
        positive_doc["route"]["observed_utc"] = utc()
        recovery.save_checkpoint(positive_doc, positive_config, positive_state, expected_revision=1)
        fresh = context(positive_doc)
        fresh["stop_reason"] = "none"
        quota_plan = guard.assess(recovery.assess_resume, "completed-task", fresh, positive_config, positive_state)
        check("new_route_does_not_erase_saved_stop", quota_plan["status"] == "blocked")
        check("all_assessments_attempted_no_python_level_effects", guard.calls == 6 and guard.attempts == [])
        report["status"] = "passed"
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["finished_utc"] = utc()
        report["resume_calls_guarded"] = guard.calls
        report["resume_side_effect_attempts"] = guard.attempts
        dump(output / "summary.json", report)
        print(json.dumps({"status": report["status"], "cases": report["cases"],
                          "source_execution": report["source_execution"],
                          "installed_package_validation": report["installed_package_validation"],
                          "real_rdc_reauthentication": False}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-package-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        worker(args.worker, args.installed, args.worker_package_root)
    elif args.worker_package_root is not None:
        parser.error("--worker-package-root is internal to the owned worker")
    elif args.output_dir is None:
        parser.error("--output-dir is required")
    else:
        run(args)


if __name__ == "__main__":
    main()

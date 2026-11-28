from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys

from . import __version__
from .common import KitError, read_json, run_command, strict_json
from .core import execute_request


def doctor(config):
    result = {"kit": __version__, "platform": platform.system(), "python": platform.python_version(),
              "browser": {"status": "external_connector_required", "availability": "not_probed"},
              "scope": "Discovery is not an end-to-end functional test", "adapters": {}}
    for name, flags in (("smartcli", ["doctor"]), ("winapp", ["--version"])):
        prefix = config.get(name)
        if not isinstance(prefix, list) or not prefix:
            result["adapters"][name] = {"status": "not_configured"}
            continue
        try:
            probe = run_command(prefix + flags, timeout=12)
            result["adapters"][name] = {"status": "available" if probe["exit_code"] == 0 and not probe["timed_out"] else "probe_failed", "probe": probe}
        except KitError as exc:
            result["adapters"][name] = {"status": "probe_failed", "code": exc.code, "message": exc.message}
    route = config.get("omp", {})
    result["adapters"]["omp"] = {"status": "wrapper_found" if isinstance(route, dict) and
        isinstance(route.get("wrapper"), str) and Path(route["wrapper"]).is_file() else "not_configured",
        "real_model_call": False}
    result["paths"] = {name: shutil.which(name) for name in ("node", "git", "omp", "codex")}
    return result


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="RDC Operator Kit — local adapters with durable receipts")
    parser.add_argument("--config", type=Path, default=Path("config.local.json"))
    parser.add_argument("--state", type=Path, help="state directory; recovery commands require an explicit original path")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="probe executable availability without changing desktop or starting models")
    preflight = commands.add_parser("windows-preflight", help="read Windows token/session/desktop context; does not grant access or send input")
    preflight.add_argument("--window", type=lambda value: int(value, 0), help="optional current HWND, decimal or 0x hex")
    call = commands.add_parser("call", help="execute or retrieve one uniquely identified request")
    call.add_argument("request", help="JSON request path or - for stdin")
    call.add_argument("--apply", action="store_true", help="apply already authorized state-changing action")
    receipt = commands.add_parser("receipt", help="read one saved receipt")
    receipt.add_argument("request_id")
    checkpoint = commands.add_parser("checkpoint", help="save a local recovery checkpoint with compare-and-swap")
    checkpoint.add_argument("document", type=Path, help="private checkpoint JSON document")
    checkpoint.add_argument("--expected-revision", type=int, required=True)
    resume = commands.add_parser("resume", help="read a recovery plan without creating state, executing or authorizing actions")
    resume.add_argument("task_id")
    resume.add_argument("--context", type=Path, required=True, help="fresh caller-observed route and recovery context")
    args = parser.parse_args(argv)
    try:
        if args.command == "windows-preflight":
            from .windows import inspect_windows_context
            result = inspect_windows_context(args.window)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if result["assessment"]["status"] == "observed" else 1
        if args.command in {"checkpoint", "resume"}:
            from .recovery import assess_resume, read_recovery_document, save_checkpoint
            if args.state is None:
                raise KitError("explicit_state_required", "Recovery requires the explicit original --state path")
            config = read_recovery_document(args.config)
            if args.command == "checkpoint":
                result = save_checkpoint(read_recovery_document(args.document), config, args.state,
                                         expected_revision=args.expected_revision)
            else:
                result = assess_resume(args.task_id, read_recovery_document(args.context), config, args.state)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
            return 1 if result["status"] == "blocked" else 0
        args.state = args.state if args.state is not None else Path(".rdc-state")
        config = read_json(args.config)
        if args.command == "doctor":
            result = doctor(config)
        elif args.command == "call":
            if args.request == "-":
                raw = sys.stdin.read(262145)
                if len(raw.encode("utf-8")) > 262144:
                    raise KitError("invalid_request", "stdin request exceeds 256 KiB")
                try:
                    request = strict_json(raw)
                except (ValueError, RecursionError) as exc:
                    raise KitError("invalid_json", str(exc)) from exc
            else:
                request = read_json(Path(args.request))
            result = execute_request(request, config, args.state, apply=args.apply)
        else:
            import re
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.request_id):
                raise KitError("invalid_request_id", "Invalid receipt ID")
            result = read_json(args.state / "requests" / f"{args.request_id}.receipt.json")
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("status") in {"failed", "outcome_unknown"} else 0
    except KitError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": exc.message,
                                   "uncertain": exc.uncertain}}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps({"error": {"code": "io_error", "message": str(exc), "uncertain": True}}), file=sys.stderr)
        return 2

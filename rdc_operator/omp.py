"""Preview the existing OMP dispatcher; do not create another job broker."""
from pathlib import Path
import re

from .common import KitError, allowed_path, read_json, run_command

SUPPORTED_ACTIONS = {"omp.preview"}
MUTATING_ACTIONS = {"omp.preview"}  # writes wrapper-owned dry-run evidence


def validate(action, args, config, state):
    required = {"job", "brief", "cwd", "model", "effort"}
    if set(args) - (required | {"max_attempts", "attempt_timeout", "total_timeout"}) or not required <= set(args):
        raise KitError("invalid_args", "OMP preview requires job, brief, cwd, model and effort")
    if not isinstance(args["job"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args["job"]):
        raise KitError("invalid_job", "Invalid OMP job ID")
    for field in ("model", "effort"):
        if not isinstance(args[field], str) or not args[field] or args[field].startswith("-") or "\x00" in args[field]:
            raise KitError("invalid_args", f"Invalid {field}")
    if args["effort"] not in {"minimal", "low", "medium", "high", "xhigh", "max"}:
        raise KitError("invalid_args", "Use an explicit known effort")
    if not allowed_path(args["brief"], config).is_file() or not allowed_path(args["cwd"], config).is_dir():
        raise KitError("invalid_path", "OMP brief must be a file and cwd a directory")
    route = config.get("omp", {})
    if not all(isinstance(route.get(k), str) and Path(route[k]).is_file() for k in ("python", "wrapper")):
        raise KitError("missing_omp", "Configure the existing Python and origin-dispatch wrapper paths")
    for key, default, lo, hi in (("max_attempts", 1, 1, 3), ("attempt_timeout", 120, 5, 1800),
                                  ("total_timeout", 120, 5, 3600)):
        value = args.get(key, default)
        if type(value) is not int or not lo <= value <= hi:
            raise KitError("invalid_args", f"{key} must be an integer in [{lo}, {hi}]")


def execute(action, args, config, state):
    route = config["omp"]
    jobs = state / "omp-preview-jobs"
    argv = [route["python"], route["wrapper"], "run", "--job", args["job"],
            "--jobs-root", str(jobs), "--brief", args["brief"], "--cwd", args["cwd"],
            "--model", args["model"], "--effort", args["effort"],
            "--max-attempts", str(args.get("max_attempts", 1)),
            "--attempt-timeout", str(args.get("attempt_timeout", 120)),
            "--total-timeout", str(args.get("total_timeout", 120)), "--dry-run"]
    result = run_command(argv, timeout=30)
    if result["timed_out"] or result["output_truncated"]:
        return {"status": "outcome_unknown", "transport": result, "real_model_call": False}
    receipt = jobs / args["job"] / "receipt.json"
    if result["exit_code"] != 0 or not receipt.exists():
        return {"status": "failed", "transport": result, "real_model_call": False}
    native = read_json(receipt)
    return {"status": "completed" if native.get("status") == "DRY_RUN" else "failed",
            "native_status": native.get("status"), "native_receipt": str(receipt),
            "real_model_call": False, "semantic_verified": native.get("status") == "DRY_RUN",
            "transport": result}

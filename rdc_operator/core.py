from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from . import __version__
from .common import KitError, atomic_json, read_json


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise KitError("invalid_request", "Request and config must be finite JSON values") from exc
    if len(payload) > 256 * 1024:
        raise KitError("invalid_request", "Request and config exceed 256 KiB")
    return hashlib.sha256(payload).hexdigest()


@contextmanager
def state_lock(state: Path):
    absolute = Path(os.path.abspath(state))
    # Reject all existing symlink ancestors. Resolve junction aliases on Windows
    # as well: different names must not pretend to be independent state.
    for path in (absolute, *absolute.parents):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise KitError("unsafe_state", "State cannot use symlink or junction paths")
    absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
    canonical = absolute.resolve(strict=True)
    lock = canonical / ".lock"
    if lock.is_symlink():
        raise KitError("unsafe_state", "Lock cannot be a symlink")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    acquired = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise KitError("busy", "Another operation owns this state; inspect its receipt") from exc
        yield canonical
    finally:
        if acquired:
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def execute_request(request: dict, config: dict, state: Path, apply: bool = False,
                    operation=None) -> dict:
    from . import adapters
    from . import omp

    if not isinstance(request, dict) or set(request) != {"request_id", "action", "args"}:
        raise KitError("invalid_request", "Expected exactly request_id, action, args")
    rid, action, args = request["request_id"], request["action"], request["args"]
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", rid):
        raise KitError("invalid_request_id", "Use 1-64 ASCII letters, digits, underscore or hyphen")
    if rid.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise KitError("invalid_request_id", "Request ID cannot be a reserved Windows device name")
    if not isinstance(action, str) or not isinstance(args, dict):
        raise KitError("invalid_request", "action must be a string and args an object")
    if (not isinstance(config, dict) or type(config.get("schema_version")) is not int
            or config["schema_version"] != 1):
        raise KitError("invalid_config", "config schema_version must be 1")
    adapter = omp if action.startswith("omp.") else adapters
    if action not in adapter.SUPPORTED_ACTIONS:
        raise KitError("unsupported_action", f"Unsupported action: {action}")
    digest = _digest({"request": request, "config": config})

    with state_lock(Path(state)) as root:
        records = root / "requests"
        if records.is_symlink():
            raise KitError("unsafe_state", "requests directory cannot be a symlink")
        records.mkdir(exist_ok=True, mode=0o700)
        intent_path, result_path = records / f"{rid}.intent.json", records / f"{rid}.receipt.json"
        if intent_path.exists() or intent_path.is_symlink() or result_path.exists() or result_path.is_symlink():
            if not intent_path.exists():
                raise KitError("outcome_unknown", "Orphan receipt; original intent is missing", uncertain=True)
            try:
                intent = read_json(intent_path)
            except KitError as exc:
                raise KitError("outcome_unknown", "Existing intent is unreadable; reconcile local evidence", uncertain=True) from exc
            if intent.get("digest") != digest:
                raise KitError("request_conflict", "Request ID already belongs to different request or config")
            if not result_path.exists():
                raise KitError("outcome_unknown", "Intent exists without a final receipt; reconcile before any new action", uncertain=True)
            try:
                result = read_json(result_path)
            except KitError as exc:
                raise KitError("outcome_unknown", "Existing receipt is unreadable; reconcile local evidence", uncertain=True) from exc
            if (result.get("digest") != digest or result.get("request_id") != rid or
                    result.get("status") not in {"observed", "completed", "failed", "outcome_unknown"}):
                raise KitError("outcome_unknown", "Receipt does not match its intent", uncertain=True)
            return {**result, "replayed": True}

        if action in adapter.MUTATING_ACTIONS and not apply:
            raise KitError("apply_required", "This operation requires --apply after scope authorization")
        adapter.validate(action, args, config, root)
        started = _now()
        intent = {"schema_version": 1, "request_id": rid, "action": action,
                  "digest": digest, "kit_version": __version__, "state": "prepared", "started_utc": started}
        atomic_json(intent_path, intent)
        # Do not catch BaseException. Interruption after intent is deliberately
        # recoverable only as an unknown outcome, never a replayable operation.
        try:
            payload = (operation or adapter.execute)(action, args, config, root)
            if not isinstance(payload, dict) or payload.get("status") not in {
                    "observed", "completed", "failed", "outcome_unknown"}:
                raise KitError("invalid_adapter_result", "Adapter returned no explicit outcome", uncertain=True)
        except KitError as exc:
            payload = {"status": "outcome_unknown" if exc.uncertain else "failed",
                       "error": {"code": exc.code, "message": exc.message}, "semantic_verified": False}
        except Exception as exc:
            payload = {"status": "outcome_unknown", "error": {"code": "adapter_exception",
                       "message": f"{type(exc).__name__}: {exc}"}, "semantic_verified": False}
        result = {"schema_version": 1, "request_id": rid, "action": action,
                  "digest": digest, "kit_version": __version__, "started_utc": started,
                  "finished_utc": _now(), "status": payload["status"],
                  "result": payload, "replayed": False}
        # A failed commit leaves the durable intent. It must not be converted to
        # a fabricated success, deleted, or reused by a subsequent request.
        atomic_json(result_path, result)
        return result

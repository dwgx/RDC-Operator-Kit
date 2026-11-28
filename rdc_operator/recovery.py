"""Durable local checkpoints and a read-only, non-authorizing recovery plan.

The internal mcp_server reader is deliberately shared: it imports without the
optional SDK and retains bounded reads, hard-link checks, POSIX directory-fd
walking, and Windows opened-HANDLE path verification. Do not replace it with a
weaker Path.read_text/read_json call. This module never authenticates a route.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata
import uuid

from .common import KitError, atomic_json
from .core import _digest, state_lock
from .mcp_server import ReadOnlyOperator, _read_saved_record, _unlinked


MARKER_NAME = ".recovery-marker.json"
CHECKPOINT_DIRECTORY = "checkpoints"
MAX_ROUTE_AGE_SECONDS = 300
MAX_HANDLE_HISTORY = 4096
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_EVENTS = {"same_connection", "user_reconnected"}
_STOPS = {"none", "disconnected", "auth_required", "quota", "policy_refused", "cancelled"}
_HARD_STOPS = {"quota", "policy_refused", "cancelled"}
_KINDS = {"rdc_call", "process", "search", "terminal", "browser_tab", "desktop_observation"}
_DOCUMENT_FIELDS = {"schema_version", "task_id", "scope_sha256", "route", "event",
                    "request_ids", "handles", "stop_reason"}
_SAVED_FIELDS = _DOCUMENT_FIELDS | {"state_id", "state_path_sha256", "config_sha256",
                                    "revision", "route_generation", "handle_history"}


def _object(value, fields, code):
    if not isinstance(value, dict) or set(value) != fields:
        raise KitError(code, "Unexpected or missing recovery document fields")


def _version(value, code):
    if type(value) is not int or value != 1:
        raise KitError(code, "Recovery schema_version must be the integer 1")


def _identifier(value, kind):
    try:
        ReadOnlyOperator.validate_arguments("operator_request_status", {"request_id": value})
    except KitError as exc:
        raise KitError(f"invalid_{kind}_id", "Use a valid Kit ID, never a path or Windows reserved name") from exc


def _opaque_id(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip() or
            any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)):
        raise KitError("invalid_recovery_id", "Route and handle IDs must be bounded strings without controls")


def _sha(value, code):
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise KitError(code, "Expected a lowercase SHA-256 digest")


def _timestamp(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise KitError("invalid_route_time", "Route observation must contain a timezone-aware timestamp")
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timezone required")
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise KitError("invalid_route_time", "Route observation must contain a timezone-aware timestamp") from exc


def _clock(now):
    value = datetime.now(timezone.utc) if now is None else now
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise KitError("invalid_clock", "Recovery clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _route(value):
    _object(value, {"link_id", "device_id", "observed_utc"}, "invalid_route")
    _opaque_id(value["link_id"])
    _opaque_id(value["device_id"])
    _timestamp(value["observed_utc"])
    return dict(value)


def _enum(value, allowed, code):
    if not isinstance(value, str) or value not in allowed:
        raise KitError(code, "Unsupported recovery classification")


def _document(value):
    _object(value, _DOCUMENT_FIELDS, "invalid_checkpoint")
    _version(value["schema_version"], "invalid_checkpoint")
    _identifier(value["task_id"], "task")
    _sha(value["scope_sha256"], "invalid_scope")
    route = _route(value["route"])
    _enum(value["event"], _EVENTS, "invalid_event")
    _enum(value["stop_reason"], _STOPS, "invalid_stop_reason")
    requests, handles = value["request_ids"], value["handles"]
    if not isinstance(requests, list) or len(requests) > 128:
        raise KitError("invalid_request_ids", "Checkpoint accepts at most 128 request IDs")
    for rid in requests:
        _identifier(rid, "request")
    if len(set(requests)) != len(requests):
        raise KitError("invalid_request_ids", "Checkpoint request IDs must be unique")
    if not isinstance(handles, list) or len(handles) > 128:
        raise KitError("invalid_handles", "Checkpoint accepts at most 128 handles")
    seen = set()
    for handle in handles:
        _object(handle, {"kind", "id"}, "invalid_handles")
        _enum(handle["kind"], _KINDS, "invalid_handle_kind")
        _opaque_id(handle["id"])
        key = (handle["kind"], handle["id"])
        if key in seen:
            raise KitError("invalid_handles", "Checkpoint handles must be unique")
        seen.add(key)
    return {**value, "route": route, "request_ids": list(requests),
            "handles": [dict(handle) for handle in handles]}


def _context(value):
    _object(value, {"schema_version", "scope_sha256", "route", "event", "stop_reason"},
            "invalid_resume_context")
    _version(value["schema_version"], "invalid_resume_context")
    _sha(value["scope_sha256"], "invalid_scope")
    route = _route(value["route"])
    _enum(value["event"], _EVENTS, "invalid_event")
    _enum(value["stop_reason"], _STOPS, "invalid_stop_reason")
    return {**value, "route": route}


def read_recovery_document(path: Path) -> dict:
    """Read an explicit private input without links, unbounded reads or raw errors."""
    absolute = Path(os.path.abspath(Path(path).expanduser()))
    value, _ = _read_saved_record(absolute, "document")
    if not isinstance(value, dict):
        raise KitError("invalid_document", "Recovery input must be a JSON object")
    return value


def _state_path(state, *, must_exist):
    try:
        absolute = Path(os.path.abspath(Path(state).expanduser()))
        _unlinked(absolute)
        if not absolute.exists():
            if must_exist:
                raise KitError("state_not_found", "Original recovery state is required; no substitute was created")
            return absolute
        if not absolute.is_dir():
            raise KitError("unsafe_state", "Recovery state must be an ordinary directory")
        return absolute.resolve(strict=True)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise KitError("unsafe_state", "Cannot verify the original recovery state") from exc


def _path_digest(root):
    return hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()


def _config_digest(config):
    if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise KitError("invalid_config", "Config schema_version must be the integer 1")
    try:
        return _digest(config)
    except KitError as exc:
        raise KitError("invalid_config", "Config must contain bounded finite JSON values") from exc


def _optional_record(path, kind):
    try:
        return _read_saved_record(path, kind)
    except KitError as exc:
        if exc.code == f"{kind}_not_found":
            return None
        raise


def _marker(value, root):
    _object(value, {"schema_version", "state_id", "state_path_sha256"}, "invalid_marker")
    _version(value["schema_version"], "invalid_marker")
    try:
        identifier = uuid.UUID(value["state_id"])
        if identifier.version != 4 or str(identifier) != value["state_id"]:
            raise ValueError("not a canonical random UUID")
    except (ValueError, TypeError, AttributeError) as exc:
        raise KitError("invalid_marker", "Recovery marker identity is invalid") from exc
    _sha(value["state_path_sha256"], "invalid_marker")
    if value["state_path_sha256"] != _path_digest(root):
        raise KitError("state_path_mismatch", "Recovery marker belongs to a different state directory")


def _positive(value, code):
    if type(value) is not int or not 1 <= value < 2 ** 63:
        raise KitError(code, "Recovery revision and generation must be positive bounded integers")


def _saved(value, task_id, marker, root):
    _object(value, _SAVED_FIELDS, "invalid_checkpoint")
    _document({key: value[key] for key in _DOCUMENT_FIELDS})
    if value["task_id"] != task_id:
        raise KitError("checkpoint_identity_mismatch", "Checkpoint belongs to a different task")
    if value["state_id"] != marker["state_id"] or value["state_path_sha256"] != _path_digest(root):
        raise KitError("checkpoint_state_mismatch", "Checkpoint does not match the original state marker and path")
    _sha(value["config_sha256"], "invalid_checkpoint")
    _positive(value["revision"], "invalid_checkpoint")
    _positive(value["route_generation"], "invalid_checkpoint")
    if value["route_generation"] > value["revision"]:
        raise KitError("invalid_checkpoint", "Checkpoint generation exceeds its revision")
    history = value["handle_history"]
    if not isinstance(history, dict) or len(history) > MAX_HANDLE_HISTORY:
        raise KitError("invalid_checkpoint", "Handle ownership history is unavailable or exceeds its bound")
    for fingerprint, generation in history.items():
        _sha(fingerprint, "invalid_checkpoint")
        _positive(generation, "invalid_checkpoint")
        if generation > value["route_generation"]:
            raise KitError("invalid_checkpoint", "Handle ownership references a future generation")
    for handle in value["handles"]:
        if history.get(_digest(handle)) != value["route_generation"]:
            raise KitError("invalid_checkpoint", "A handle is not bound to the checkpoint generation")


def _bundle(root, task_id):
    marker, marker_fp = _read_saved_record(root / MARKER_NAME, "marker")
    _marker(marker, root)
    checkpoint, checkpoint_fp = _read_saved_record(root / CHECKPOINT_DIRECTORY / f"{task_id}.json", "checkpoint")
    _saved(checkpoint, task_id, marker, root)
    return marker, checkpoint, (marker_fp, checkpoint_fp)


def _write_preflight(root):
    # state_lock remains the single coordinating lock. Reject unsafe existing
    # lock objects before it opens them, including hard links and reparse points.
    for path, directory in ((root / ".lock", False), (root / CHECKPOINT_DIRECTORY, True)):
        _unlinked(path)
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if (directory and not stat.S_ISDIR(info.st_mode)) or (
                not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
            raise KitError("unsafe_state", "Recovery directory or lock has an unsafe file type or hard link")


def save_checkpoint(document: dict, config: dict, state: Path, *, expected_revision: int,
                    now: datetime | None = None) -> dict:
    """Explicit local write, under the existing lock, with compare-and-swap."""
    value, clock = _document(document), _clock(now)
    if type(expected_revision) is not int or not 0 <= expected_revision < 2 ** 63 - 1:
        raise KitError("invalid_revision", "expected_revision must be a nonnegative bounded integer")
    age = (clock - _timestamp(value["route"]["observed_utc"])).total_seconds()
    if age < 0 or age > MAX_ROUTE_AGE_SECONDS:
        raise KitError("route_sample_in_future" if age < 0 else "route_sample_stale",
                       "Checkpoint requires a fresh caller-observed route sample")
    config_sha = _config_digest(config)
    root = _state_path(state, must_exist=False)
    try:
        _write_preflight(root)
        with state_lock(root) as locked:
            root = _state_path(locked, must_exist=True)
            _write_preflight(root)
            marker_sample = _optional_record(root / MARKER_NAME, "marker")
            target = root / CHECKPOINT_DIRECTORY / f"{value['task_id']}.json"
            previous_sample = _optional_record(target, "checkpoint")
            if marker_sample is None:
                folder = root / CHECKPOINT_DIRECTORY
                if previous_sample is not None or (folder.exists() and any(folder.iterdir())):
                    raise KitError("marker_not_found", "Existing checkpoints require their original state marker")
                marker = {"schema_version": 1, "state_id": str(uuid.uuid4()),
                          "state_path_sha256": _path_digest(root)}
            else:
                marker = marker_sample[0]
                _marker(marker, root)
            previous = previous_sample[0] if previous_sample is not None else None
            if previous_sample is not None:
                _saved(previous, value["task_id"], marker, root)
            actual_revision = previous["revision"] if previous_sample is not None else 0
            if expected_revision != actual_revision:
                raise KitError("checkpoint_conflict", "Checkpoint revision changed; inspect the saved revision")
            history, generation = {}, 1
            if previous:
                if previous["scope_sha256"] != value["scope_sha256"] or previous["config_sha256"] != config_sha:
                    raise KitError("checkpoint_identity_mismatch", "Checkpoint scope and configuration cannot change")
                if not set(previous["request_ids"]).issubset(value["request_ids"]):
                    raise KitError("request_ids_retained", "Checkpoint updates cannot discard earlier request IDs")
                if previous["stop_reason"] in _HARD_STOPS and value["stop_reason"] != previous["stop_reason"]:
                    raise KitError("stop_reason_retained", "Quota, policy refusal and cancellation cannot be cleared or replaced")
                if previous["stop_reason"] in {"disconnected", "auth_required"} and value["stop_reason"] == "none" and value["event"] != "user_reconnected":
                    raise KitError("reconnection_required", "A connection pause requires an explicit fresh reconnection event")
                if _timestamp(value["route"]["observed_utc"]) < _timestamp(previous["route"]["observed_utc"]):
                    raise KitError("route_sample_regressed", "New route evidence predates the checkpoint")
                changed = any(value["route"][key] != previous["route"][key] for key in ("link_id", "device_id"))
                generation = previous["route_generation"] + int(changed or value["event"] == "user_reconnected")
                history = dict(previous["handle_history"])
            for handle in value["handles"]:
                fingerprint = _digest(handle)
                if fingerprint in history and history[fingerprint] != generation:
                    raise KitError("stale_handle_reuse", "An earlier handle cannot be relabelled under a new route generation")
                history[fingerprint] = generation
            if len(history) > MAX_HANDLE_HISTORY:
                raise KitError("handle_history_full", "Retained handle ownership history reached its bound")
            saved = {**value, "state_id": marker["state_id"], "state_path_sha256": _path_digest(root),
                     "config_sha256": config_sha, "revision": actual_revision + 1,
                     "route_generation": generation, "handle_history": history}
            if marker_sample is None:
                atomic_json(root / MARKER_NAME, marker)
            _unlinked(target)
            atomic_json(target, saved)
            try:
                reread_marker, reread, _ = _bundle(root, value["task_id"])
            except KitError as exc:
                # Safe readers translate I/O and validation failures into
                # KitError. The new revision may already be durable here.
                raise KitError("checkpoint_commit_unconfirmed",
                               "Checkpoint was written but confirmation failed; inspect the saved revision before updating",
                               uncertain=True) from exc
            if reread_marker != marker or reread != saved:
                raise KitError("checkpoint_commit_unconfirmed", "Saved checkpoint changed before confirmation", uncertain=True)
    except OSError as exc:
        raise KitError("checkpoint_persistence_failed", "Checkpoint persistence failed; inspect the saved revision before updating",
                       uncertain=True) from exc
    return {"schema_version": 1, "source": "saved_checkpoint", "task_id": value["task_id"],
            "revision": saved["revision"], "route_generation": generation, "status": "checkpoint_saved",
            "request_count": len(value["request_ids"]), "handle_count": len(value["handles"]),
            "stop_reason": value["stop_reason"], "actions_exposed": False,
            "automatic_replay_allowed": False, "execution_authorized": False,
            "physical_device_verified": False}


def _handle_assessments(handles, invalidated):
    assessments = []
    for kind in sorted({handle["kind"] for handle in handles}):
        if kind == "process":
            requirement = "verify_pid_creation_time_executable_and_task_ownership"
        elif kind == "desktop_observation":
            requirement = "obtain_fresh_desktop_observation"
        elif kind == "browser_tab":
            requirement = "rediscover_tab_and_obtain_fresh_browser_observation" if invalidated else "obtain_fresh_browser_observation"
        else:
            requirement = "rediscover_on_current_route" if invalidated else "revalidate_on_current_route"
        assessments.append({"kind": kind, "count": sum(handle["kind"] == kind for handle in handles),
                            "assessment": "reidentification_required" if kind == "process" else
                                          "invalidated_for_plan" if invalidated or kind == "desktop_observation" else "revalidation_required",
                            "requirement": requirement, "live_verification_performed": False})
    return assessments


def assess_resume(task_id: str, context: dict, config: dict, state: Path, *,
                  now: datetime | None = None) -> dict:
    """Only read saved evidence. No lock, directory creation, adapter or probe."""
    _identifier(task_id, "task")
    current, clock, config_sha = _context(context), _clock(now), _config_digest(config)
    root = _state_path(state, must_exist=True)
    _, checkpoint, fingerprints = _bundle(root, task_id)
    reasons = []
    age = (clock - _timestamp(current["route"]["observed_utc"])).total_seconds()
    if age < 0:
        reasons.append("route_sample_in_future")
    elif age > MAX_ROUTE_AGE_SECONDS:
        reasons.append("route_sample_stale")
    if _timestamp(current["route"]["observed_utc"]) < _timestamp(checkpoint["route"]["observed_utc"]):
        reasons.append("context_predates_checkpoint")
    if checkpoint["config_sha256"] != config_sha:
        reasons.append("config_mismatch")
    if checkpoint["scope_sha256"] != current["scope_sha256"]:
        reasons.append("scope_mismatch")
    previous_stop = checkpoint["stop_reason"]
    if (previous_stop in {"disconnected", "auth_required"} and current["stop_reason"] == "none" and
            current["event"] == "user_reconnected" and 0 <= age <= MAX_ROUTE_AGE_SECONDS):
        previous_stop = "none"
    stops = sorted({value for value in (previous_stop, current["stop_reason"]) if value != "none"})
    reasons.extend(f"stop_{stop}" for stop in stops)
    changed = any(current["route"][key] != checkpoint["route"][key] for key in ("link_id", "device_id"))
    invalidated = changed or current["event"] == "user_reconnected"
    operator, requests = ReadOnlyOperator(config, root), []
    for rid in checkpoint["request_ids"]:
        try:
            status = operator.call("operator_request_status", {"request_id": rid})
        except KitError as exc:
            status = {"request_id": rid, "record_state": "unavailable", "reason": exc.code,
                      "saved_receipt_status": None, "snapshot_atomic": False,
                      "live_verification_performed": False, "record_authenticity_verified": False,
                      "actions_exposed": False}
        unresolved = status["record_state"] != "receipt_recorded" or status["saved_receipt_status"] not in {"completed", "observed"}
        requests.append({**status, "reconciliation_required": unresolved,
                         "request_config_binding_verified": False, "automatic_replay_allowed": False})
    if any(item["reconciliation_required"] for item in requests):
        reasons.append("request_reconciliation_required")
    try:
        _state_path(root, must_exist=True)
        _, _, after = _bundle(root, task_id)
        if fingerprints != after:
            reasons.append("recovery_records_changed_during_observation")
    except KitError:
        reasons.append("recovery_records_unavailable_after_sampling")
    return {"schema_version": 1, "source": "saved_checkpoint_and_request_records", "task_id": task_id,
            "checkpoint_revision": checkpoint["revision"], "route_generation": checkpoint["route_generation"],
            "status": "blocked" if reasons else "review_required", "blocking_reasons": reasons,
            "review_reasons": ["saved_results_require_review", "fresh_visual_observations_required"] +
                              (["route_changed"] if changed else []) +
                              (["user_reconnected"] if current["event"] == "user_reconnected" else []),
            "stop_reasons": stops, "route_comparison": "changed" if changed else "same",
            "event": current["event"], "route_source": "caller_attested",
            "route_authenticity_verified": False, "route_handles_invalidated_for_plan": invalidated,
            "scope_source": "caller_attested", "scope_content_verified": False,
            "handles": _handle_assessments(checkpoint["handles"], invalidated), "requests": requests,
            "fresh_observation_required": True, "snapshot_atomic": False,
            "live_verification_performed": False, "record_authenticity_verified": False,
            "request_config_binding_verified": False, "actions_exposed": False,
            "automatic_replay_allowed": False, "execution_authorized": False,
            "physical_device_verified": False}

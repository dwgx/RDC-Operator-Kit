"""Offline consistency checks for a declared synthetic browser counter fixture.

No browser, network, filesystem writes, authorization or authenticated provenance
are provided here. A coherent caller-supplied bundle can still be fabricated.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit


MAX_BUNDLE_BYTES = 1024 * 1024
_PAGE_KEYS = {"browser_id", "context_id", "tab_id", "target_id", "document_epoch", "fixture_nonce", "origin"}
_REQUEST_KEYS = {"request_id", "operation", "token", "before_count", "expected_count"}


class InvalidEvidence(ValueError):
    pass


def _object(value, keys, name):
    if not isinstance(value, dict) or set(value) != keys:
        raise InvalidEvidence(f"{name} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _text(value, name, maximum=256):
    if not isinstance(value, str) or not value or len(value) > maximum or "\0" in value:
        raise InvalidEvidence(f"{name} must be nonempty text of at most {maximum} characters")
    return value


def _integer(value, name, minimum=0, maximum=10**9):
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidEvidence(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _timestamp(value, name):
    text = _text(value, name, 64)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEvidence(f"{name} must be an ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidEvidence(f"{name} must include its timezone")
    return result.astimezone(timezone.utc)


def _hash(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise InvalidEvidence(f"{name} must be a lowercase SHA-256 hex digest")


def _page(value, name):
    _object(value, _PAGE_KEYS, name)
    for field in _PAGE_KEYS:
        _text(value[field], f"{name}.{field}")
    try:
        origin = urlsplit(value["origin"])
        _ = origin.port
    except ValueError as exc:
        raise InvalidEvidence(f"{name}.origin is malformed") from exc
    if (origin.scheme not in {"http", "https"} or not origin.hostname or origin.username is not None or
            origin.password is not None or origin.path or origin.query or origin.fragment):
        raise InvalidEvidence(f"{name}.origin must be an HTTP(S) origin without a path or credentials")


def request_digest(request):
    """Checksum the five counter-intent fields; this is not a signature."""
    payload = {field: request[field] for field in _REQUEST_KEYS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _base_result(status, reasons, next_action):
    return {"schema_version": 1, "status": status, "reasons": reasons, "next_action": next_action,
            "verification_scope": "offline_fixture_consistency_only", "authorization_verified": False,
            "live_execution_verified": False, "authenticity_verified": False,
            "automatic_replay_permitted": False, "business_condition_consistent": False,
            "pixel_freshness": "unproven", "pixel_semantics_verified": False,
            "limits": ["All supplied identities and timestamps are caller claims.",
                       "A matching hash binds bytes, not a browser, machine, or capture source.",
                       "DOM and screenshot are separate observations, not an atomic snapshot.",
                       "No result grants access, resumes a stopped task, or triggers an action."]}


def validate_bundle(bundle, *, host_refused=False, operator_stopped=False):
    """Return a verdict without executing anything.

    The keyword flags are separate caller context and can only tighten a verdict.
    False means no stop was supplied; it never means permission was established.
    """
    if type(host_refused) is not bool or type(operator_stopped) is not bool:
        return _base_result("invalid", ["stop_flags_must_be_booleans"], "stop")
    if host_refused or operator_stopped:
        return _base_result("blocked", ["host_refused" if host_refused else "operator_stopped"], "stop")
    try:
        # The pure API is bounded too; reject NaN and deeply recursive JSON.
        encoded = json.dumps(bundle, allow_nan=False, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_BUNDLE_BYTES:
            raise InvalidEvidence("bundle exceeds 1 MiB")
        return _validate(bundle)
    except (InvalidEvidence, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        return _base_result("invalid", [str(exc)], "stop")


def _validate(bundle):
    _object(bundle, {"schema_version", "evidence_kind", "executor", "page", "request",
                     "observation", "screenshot", "action", "witness"}, "bundle")
    if type(bundle["schema_version"]) is not int or bundle["schema_version"] != 1:
        raise InvalidEvidence("schema_version must be 1")
    if bundle["evidence_kind"] not in {"synthetic_fixture", "imported"}:
        raise InvalidEvidence("evidence_kind must be synthetic_fixture or imported")
    executor = _object(bundle["executor"], {"name", "version", "session_id"}, "executor")
    for field in executor:
        _text(executor[field], f"executor.{field}")
    page = bundle["page"]
    _page(page, "page")
    request = _object(bundle["request"], _REQUEST_KEYS | {"digest"}, "request")
    _text(request["request_id"], "request.request_id")
    _text(request["token"], "request.token")
    _integer(request["before_count"], "request.before_count")
    _integer(request["expected_count"], "request.expected_count", minimum=1)
    if request["operation"] != "increment_once" or request["expected_count"] != request["before_count"] + 1:
        raise InvalidEvidence("v0 accepts only a counter increment of exactly one")
    _hash(request["digest"], "request.digest")
    observation = _object(bundle["observation"], {"observation_id", "page", "sequence", "observed_at", "counter"}, "observation")
    screenshot = _object(bundle["screenshot"], {"frame_id", "page", "observation_id", "sequence",
        "capture_started_at", "capture_completed_at", "captured_at", "png_base64", "sha256", "width", "height"}, "screenshot")
    action = _object(bundle["action"], {"request_id", "request_digest", "page", "observation_id", "sequence",
        "occurred_at", "dispatched", "acknowledged", "response"}, "action")
    witness = bundle["witness"]
    if witness is not None:
        _object(witness, {"page", "sequence", "observed_at", "source", "counter", "request_id", "token"}, "witness")
        if witness["source"] not in {"fixture_dom_readback", "command_echo", "agent_report"}:
            raise InvalidEvidence("unsupported witness source")
        _integer(witness["counter"], "witness.counter")
        for key in ("request_id", "token"):
            _text(witness[key], f"witness.{key}")
    for name, record in (("observation", observation), ("screenshot", screenshot), ("action", action), ("witness", witness)):
        if record is not None:
            _page(record["page"], name + ".page")
            _integer(record["sequence"], name + ".sequence", minimum=1)
    for name, value in (("observation_id", observation["observation_id"]), ("frame_id", screenshot["frame_id"]),
                        ("screenshot.observation_id", screenshot["observation_id"]), ("action.request_id", action["request_id"]),
                        ("action.observation_id", action["observation_id"])):
        _text(value, name)
    _integer(observation["counter"], "observation.counter")
    _hash(action["request_digest"], "action.request_digest")
    _hash(screenshot["sha256"], "screenshot.sha256")
    _integer(screenshot["width"], "screenshot.width", minimum=1, maximum=32768)
    _integer(screenshot["height"], "screenshot.height", minimum=1, maximum=32768)
    for field in ("dispatched", "acknowledged"):
        if action[field] is not None and type(action[field]) is not bool:
            raise InvalidEvidence(f"action.{field} must be boolean or null")
    if action["response"] not in {"received", "lost", "not_sent"}:
        raise InvalidEvidence("action.response must be received, lost, or not_sent")
    observed_at = _timestamp(observation["observed_at"], "observation.observed_at")
    screen_started = _timestamp(screenshot["capture_started_at"], "screenshot.capture_started_at")
    screen_completed = _timestamp(screenshot["capture_completed_at"], "screenshot.capture_completed_at")
    action_at = _timestamp(action["occurred_at"], "action.occurred_at")
    witness_at = _timestamp(witness["observed_at"], "witness.observed_at") if witness is not None else None
    captured_at = _timestamp(screenshot["captured_at"], "screenshot.captured_at") if screenshot["captured_at"] is not None else None
    _text(screenshot["png_base64"], "screenshot.png_base64", MAX_BUNDLE_BYTES)
    try:
        pixels = base64.b64decode(screenshot["png_base64"], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InvalidEvidence("screenshot.png_base64 must be valid base64") from exc
    if len(pixels) < 24 or pixels[:8] != b"\x89PNG\r\n\x1a\n" or pixels[8:16] != b"\0\0\0\rIHDR":
        raise InvalidEvidence("screenshot needs a PNG signature and IHDR header")

    reasons = []
    if request_digest(request) != request["digest"] or action["request_digest"] != request["digest"]:
        reasons.append("request_digest_mismatch")
    if action["request_id"] != request["request_id"]:
        reasons.append("request_id_mismatch")
    for name, record in (("observation", observation), ("screenshot", screenshot), ("action", action), ("witness", witness)):
        if record is not None and record["page"] != page:
            reasons.append(name + "_page_identity_mismatch")
    if screenshot["observation_id"] != observation["observation_id"] or action["observation_id"] != observation["observation_id"]:
        reasons.append("observation_reference_mismatch")
    if not observation["sequence"] < screenshot["sequence"] < action["sequence"]:
        reasons.append("observation_sequence_not_increasing")
    if witness is not None and witness["sequence"] <= action["sequence"]:
        reasons.append("witness_sequence_not_after_action")
    if not observed_at <= screen_started <= screen_completed <= action_at or (witness_at is not None and witness_at < action_at):
        reasons.append("observation_time_order_mismatch")
    if captured_at is not None and not observed_at <= captured_at <= screen_completed:
        reasons.append("reported_pixel_time_outside_observation_interval")
    if hashlib.sha256(pixels).hexdigest() != screenshot["sha256"]:
        reasons.append("screenshot_hash_mismatch")
    if (int.from_bytes(pixels[16:20], "big"), int.from_bytes(pixels[20:24], "big")) != (screenshot["width"], screenshot["height"]):
        reasons.append("screenshot_dimensions_mismatch")
    if observation["counter"] != request["before_count"]:
        reasons.append("precondition_counter_mismatch")
    if witness is None:
        reasons.append("business_witness_missing")
    elif (witness["source"] != "fixture_dom_readback" or witness["counter"] != request["expected_count"] or
          witness["request_id"] != request["request_id"] or witness["token"] != request["token"]):
        reasons.append("business_witness_not_matching")
    fixture_match = not reasons
    if bundle["evidence_kind"] != "synthetic_fixture":
        reasons.append("imported_evidence_has_no_authenticated_collector")
    uncertain_action = (action["response"] == "lost" or action["dispatched"] is None or
                        action["acknowledged"] is None or
                        (action["dispatched"] is False and action["acknowledged"] is True) or
                        (action["response"] == "not_sent" and action["dispatched"] is not False))
    if uncertain_action:
        reasons.append("action_outcome_unknown_do_not_replay")
        result = _base_result("outcome_unknown", reasons, "reconcile")
    elif action["dispatched"] is not True or action["acknowledged"] is not True:
        reasons.append("action_not_acknowledged_as_dispatched")
        result = _base_result("unverified", reasons, "reconcile")
    elif reasons:
        result = _base_result("unverified", reasons, "reobserve")
    else:
        result = _base_result("verified_fixture", ["synthetic_counter_condition_consistent"], "stop")
    result["business_condition_consistent"] = fixture_match
    result["artifact_checks"] = {"sha256_matches_supplied_bytes": "screenshot_hash_mismatch" not in reasons,
        "png_dimensions_match": "screenshot_dimensions_mismatch" not in reasons, "full_image_decode_verified": False}
    result["pixel_freshness"] = "source_time_claimed_but_unproven" if captured_at is not None else "unproven"
    result["request_id"] = request["request_id"]
    return result


def exit_code(result):
    return 0 if result["status"] == "verified_fixture" else 2 if result["status"] == "invalid" else 1

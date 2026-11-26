"""Finite screenshot samples with incremental receipts, never a background service.

Captures may restore or foreground the target. Source frame time is unavailable.
The start deadline stops admitting new frames; an admitted call can take up to
the adapter's 30-second timeout plus direct-child cleanup and OS overhead.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rdc_operator.adapters import _window_identity
from rdc_operator.common import KitError, allowed_path, atomic_json, read_json
from rdc_operator.core import execute_request


def sample(config, state, window, output, *, count=3, interval_ms=500, start_deadline_seconds=30, emit=None):
    if type(window) is not int or not 1 <= window < (1 << 63):
        raise KitError("invalid_arguments", "window must be a positive HWND integer")
    if type(count) is not int or not 1 <= count <= 12:
        raise KitError("invalid_arguments", "frame count must be an integer from 1 to 12")
    if type(interval_ms) is not int or not 0 <= interval_ms <= 5000:
        raise KitError("invalid_arguments", "interval_ms must be an integer from 0 to 5000")
    if type(start_deadline_seconds) not in (int, float) or not 0 < start_deadline_seconds <= 60:
        raise KitError("invalid_arguments", "start deadline must be finite and in (0, 60]")
    output = allowed_path(str(output), config, must_exist=False)
    if output.exists():
        raise KitError("output_exists", "Use a new sample directory; existing evidence is never resumed or overwritten")
    target = _window_identity(window)
    output.mkdir(parents=True, exist_ok=False)
    run_id = "sample-" + uuid.uuid4().hex[:16]
    started = time.monotonic()
    deadline = started + start_deadline_seconds
    manifest = {"schema_version": 1, "run_id": run_id, "status": "running", "target": target,
                "requested_frames": count, "frames": [], "stopped_reason": None,
                "scope": "finite native-window screenshot samples; not continuous video",
                "pixel_freshness": "unproven", "may_restore_or_foreground_window": True,
                "deadline_semantics": "admission only; each admitted call has its own bounded timeout"}
    atomic_json(output / "manifest.json", manifest)
    try:
        observed = execute_request({"request_id": run_id + "-observe", "action": "desktop.observe",
                                    "args": {"window": window}}, config, state)
        if observed["status"] != "observed" or observed["result"].get("identity") != target:
            manifest["status"] = "partial"
            manifest["stopped_reason"] = "initial_observation_unverified"
            return manifest
        observation_id = observed["result"]["observation_id"]
        manifest["observation_request_id"] = observed["request_id"]
        manifest["observation_id"] = observation_id
        atomic_json(output / "manifest.json", manifest)
        for index in range(count):
            if time.monotonic() >= deadline:
                manifest["stopped_reason"] = "start_deadline_reached"
                break
            if _window_identity(window) != target:
                manifest["stopped_reason"] = "target_identity_changed"
                break
            request = {"request_id": f"{run_id}-{index:03d}", "action": "desktop.screenshot",
                       "args": {"window": window, "observation_id": observation_id,
                                "output": str(output / f"frame-{index:03d}.png")}}
            receipt = execute_request(request, config, state, apply=True)
            frame = receipt["result"].get("frame")
            row = {"index": index, "request_id": receipt["request_id"], "status": receipt["status"],
                   "replayed": receipt["replayed"], "frame": frame}
            if not frame or frame.get("target") != target or receipt["replayed"]:
                row["accepted"] = False
                row["code"] = receipt["result"].get("code") or receipt["result"].get("error", {}).get("code", "frame_or_target_unverified")
                manifest["stopped_reason"] = row["code"]
            else:
                row["accepted"] = receipt["status"] == "completed"
            previous = manifest["frames"][-1].get("frame") if manifest["frames"] else None
            row["same_bytes_as_previous"] = (frame["artifact"]["sha256"] == previous["artifact"]["sha256"]
                                             if frame and previous else None)
            manifest["frames"].append(row)
            atomic_json(output / "manifest.json", manifest)
            if emit:
                emit(row)
            if not row["accepted"]:
                break
            if index + 1 < count:
                time.sleep(max(0, min(interval_ms / 1000, deadline - time.monotonic())))
        if len(manifest["frames"]) == count and all(r["accepted"] for r in manifest["frames"]):
            manifest["status"] = "completed"
            manifest["stopped_reason"] = "frame_limit_reached"
        else:
            manifest["status"] = "partial"
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed"
        manifest["stopped_reason"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        atomic_json(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True, help="same cooperating Kit state as your other operations")
    parser.add_argument("--window", type=int, required=True, help="fresh HWND of the authorized native window")
    parser.add_argument("--output", type=Path, required=True, help="new absolute directory under allowed_roots")
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--start-deadline-seconds", type=float, default=30)
    parser.add_argument("--apply", action="store_true", help="execute already-authorized captures that may change focus")
    args = parser.parse_args()
    if not args.apply:
        parser.error("--apply is required: captures may restore or foreground the window")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        manifest = sample(read_json(args.config), args.state, args.window, args.output,
                          count=args.frames, interval_ms=args.interval_ms,
                          start_deadline_seconds=args.start_deadline_seconds,
                          emit=lambda row: print(json.dumps({"event": "frame", **row}, ensure_ascii=False), flush=True))
        print(json.dumps({"event": "finished", "status": manifest["status"],
                          "manifest": str(args.output / "manifest.json"),
                          "elapsed_ms": manifest["elapsed_ms"]}), flush=True)
        return 0 if manifest["status"] == "completed" else 1
    except (KitError, OSError) as exc:
        print(json.dumps({"event": "failed", "message": str(exc)}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Decisive Windows test for examples/observation-fixture.ps1 only.

This closes its own verified fixture with WM_CLOSE. Never pass an arbitrary app's
witness file. Saved pictures still require separate transfer and human/model view.
"""
from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rdc_operator.adapters import _window_identity
from rdc_operator.common import atomic_json, read_json
from rdc_operator.core import execute_request
from scripts.sample_desktop import sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists")
    args.output.mkdir(parents=True)
    config, witness = read_json(args.config), read_json(args.witness)
    state = args.output / "state"
    sequence = 0
    report = {"status": "running", "checks": [], "pictures_visually_reviewed": False,
              "scope": "one owned Observation Fixture and its explicitly opened owned dialog"}
    target = None

    def check(name, condition, details=None):
        row = {"name": name, "pass": bool(condition), "details": details}
        report["checks"].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if not condition:
            raise AssertionError(name)

    def call(action, values, apply=False, rid=None):
        nonlocal sequence
        sequence += 1
        return execute_request({"request_id": rid or f"step-{sequence}", "action": action, "args": values},
                               config, state, apply=apply)

    def observe():
        reply = call("desktop.observe", {"window": witness["hwnd"]})
        check("observation", reply["status"] == "observed", reply["result"].get("code"))
        return reply["result"]

    def invoke(observation, selector, rid=None):
        reply = call("desktop.invoke", {"observation_id": observation["observation_id"], "selector": selector}, True, rid)
        check("invoke-" + selector, reply["status"] == "completed", reply["result"].get("code"))
        return reply

    def capture(observation, name):
        values = {"window": witness["hwnd"], "observation_id": observation["observation_id"],
                  "output": str((args.output / (name + ".png")).resolve())}
        return call("desktop.screenshot", values, True, name), values

    try:
        observation = observe()
        observed_identity = observation["identity"]
        windows = observation["tree"]["windows"]
        check("owned-target", observed_identity["pid"] == witness["pid"] and any(
            w.get("hwnd") == witness["hwnd"] and w.get("title") == "RDC Operator Kit — Observation Fixture"
            for w in windows))
        target = observed_identity
        check("fresh-fixture", witness["action_count"] == 0 and witness["frame_seq"] == 0 and not witness["pulsing"])
        first, first_values = capture(observation, "before")
        check("first-single-window-frame", first["status"] == "completed", first["result"].get("code"))
        advance_args = {"observation_id": observation["observation_id"], "selector": "NextFrameButton"}
        advanced = invoke(observation, "NextFrameButton", "advance-once")
        changed = read_json(args.witness)
        check("independent-action-witness", changed["nonce"] == witness["nonce"] and changed["action_count"] == 1 and changed["frame_seq"] == 1)
        second, _ = capture(advanced["result"]["observation"], "after")
        check("second-single-window-frame", second["status"] == "completed", second["result"].get("code"))
        frame_a, frame_b = first["result"]["frame"], second["result"]["frame"]
        check("changed-artifact-bytes", frame_a["artifact"]["sha256"] != frame_b["artifact"]["sha256"])
        check("unknown-pixel-time-preserved", frame_b["captured_at"] is None and frame_b["pixel_freshness"] == "unproven")
        replay = call("desktop.invoke", advance_args, rid="advance-once")
        check("action-replay-no-second-change", replay["replayed"] and read_json(args.witness)["action_count"] == 1)
        replay_capture = call("desktop.screenshot", first_values, rid="before")
        check("frame-replay-keeps-identity-and-time", replay_capture["replayed"] and replay_capture["result"]["frame"] == frame_a)
        invoke(observe(), "PulseButton")
        start_seq = read_json(args.witness)["frame_seq"]
        sampled = sample(config, state, witness["hwnd"], (args.output / "samples").resolve(), count=3, interval_ms=500,
                         start_deadline_seconds=45,
                         emit=lambda row: print(json.dumps({"sample_index": row["index"], "accepted": row["accepted"]}), flush=True))
        invoke(observe(), "PulseButton")
        end_seq = read_json(args.witness)["frame_seq"]
        check("finite-sampler", sampled["status"] == "completed" and len(sampled["frames"]) == 3,
              {"status": sampled["status"], "elapsed_ms": sampled["elapsed_ms"]})
        check("fixture-animation-progressed", end_seq > start_seq, {"before": start_seq, "after": end_seq})
        hashes = {r["frame"]["artifact"]["sha256"] for r in sampled["frames"]}
        check("sampled-bytes-changed", len(hashes) > 1, {"distinct": len(hashes), "samples": 3})
        owned = invoke(observe(), "OwnedDialogButton")
        check("owned-dialog-witness", read_json(args.witness)["owned_hwnd"] > 0)
        composite, _ = capture(owned["result"]["observation"], "composite-rejected")
        check("composite-rejected", composite["status"] == "outcome_unknown" and
              composite["result"].get("code") == "composite_capture_rejected", composite["result"].get("code"))
        report.update(status="passed", frame_a=frame_a, frame_b=frame_b,
                      sample_manifest=str(args.output / "samples" / "manifest.json"),
                      fixture_nonce=witness["nonce"], final_witness=read_json(args.witness))
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        cleanup = {"normal_close_sent": False, "window_closed": False}
        if target is not None:
            try:
                if _window_identity(witness["hwnd"]) == target:
                    user32 = ctypes.WinDLL("user32", use_last_error=True)
                    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
                    user32.PostMessageW.restype = ctypes.c_int
                    user32.IsWindow.argtypes = [ctypes.c_void_p]
                    user32.IsWindow.restype = ctypes.c_int
                    cleanup["normal_close_sent"] = bool(user32.PostMessageW(witness["hwnd"], 0x10, 0, 0))
                    until = time.monotonic() + 3
                    while user32.IsWindow(witness["hwnd"]) and time.monotonic() < until:
                        time.sleep(.05)
                    cleanup["window_closed"] = not bool(user32.IsWindow(witness["hwnd"]))
                    cleanup["witness_closed"] = read_json(args.witness).get("last_event") == "closed"
            except Exception as exc:
                cleanup["error"] = f"{type(exc).__name__}: {exc}"
        report["cleanup"] = cleanup
        if not cleanup.get("window_closed") or not cleanup.get("witness_closed"):
            report["status"] = "failed"
        atomic_json(args.output / "summary.json", report)
    print(json.dumps({"status": report["status"], "summary": str(args.output / "summary.json"), "cleanup": report["cleanup"]}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

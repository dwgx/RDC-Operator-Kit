"""Run only against examples/desktop-fixture.ps1, never an arbitrary app."""
from pathlib import Path
import argparse
import json
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rdc_operator.common import read_json, atomic_json, KitError
from rdc_operator.core import execute_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = read_json(args.config)
    witness = read_json(args.witness)
    state = args.output.parent / ("desktop-state-" + uuid.uuid4().hex[:10])
    sequence = 0
    checks = []

    def call(action, values, apply=False, rid=None):
        nonlocal sequence
        sequence += 1
        return execute_request({"request_id": rid or f"step-{sequence}", "action": action, "args": values},
                               config, state, apply=apply)

    def check(name, condition, details=None):
        checks.append({"name": name, "pass": bool(condition), "details": details})
        print(json.dumps(checks[-1], ensure_ascii=False), flush=True)
        if not condition:
            raise AssertionError(name)

    def observed():
        result = call("desktop.observe", {"window": witness["hwnd"]})
        check("observe", result["status"] == "observed")
        observation = result["result"]
        check("owned-fixture-identity", observation["identity"]["pid"] == witness["pid"] and
              observation["tree"]["windows"][0]["title"] == "RDC Operator Kit — Desktop Test Fixture")
        return observation

    try:
        observation = observed()
        required = {"FixtureInput", "ApplyValueButton", "IncrementButton", "CloseFixtureButton"}
        def walk(items):
            for item in items:
                yield item.get("selector")
                yield from walk(item.get("children", []))
        check("fixture-selectors", required <= set(walk(observation["tree"]["windows"][0]["elements"])))
        value = "RDC 测试 · 日本語 | 'quotes' & $()"
        set_result = call("desktop.set_value", {"observation_id": observation["observation_id"],
            "selector": "FixtureInput", "value": value}, apply=True)
        check("unicode-value-readback", set_result["status"] == "completed", set_result["result"].get("verification"))
        observation = set_result["result"]["observation"]
        applied = call("desktop.invoke", {"observation_id": observation["observation_id"],
            "selector": "ApplyValueButton"}, apply=True)
        check("invoke-acknowledged", applied["status"] == "completed")
        current = read_json(args.witness)
        check("independent-file-witness", current["applied"] == value)
        before = current["count"]
        observation = applied["result"]["observation"]
        screenshot = args.output.with_suffix(".png")
        capture = call("desktop.screenshot", {"window": witness["hwnd"], "output": str(screenshot.resolve())}, apply=True)
        check("window-screenshot", capture["status"] == "completed", {k:capture["result"].get(k) for k in ("width", "height", "output")})
        focused = call("desktop.focus", {"observation_id": observation["observation_id"]}, apply=True)
        check("explicit-window-focus", focused["status"] == "completed", focused["result"].get("code"))
        check("foreground-readback", focused["result"].get("foreground_window") == witness["hwnd"])
        observation = focused["result"]["observation"]
        increment_args = {"observation_id": observation["observation_id"], "selector": "IncrementButton"}
        clicked = call("desktop.click", increment_args, apply=True, rid="increment-once")
        check("selector-click", clicked["status"] == "completed", clicked["result"].get("code"))
        current = read_json(args.witness)
        check("click-file-witness", current["count"] == before + 1)
        replayed = call("desktop.click", increment_args, apply=False, rid="increment-once")
        current = read_json(args.witness)
        check("duplicate-request-no-second-click", replayed["replayed"] is True and current["count"] == before + 1)
        final_capture = call("desktop.screenshot", {"window": witness["hwnd"],
            "observation_id": clicked["result"]["observation"]["observation_id"],
            "output": str(args.output.with_name(args.output.stem + "-after.png").resolve())}, apply=True)
        check("after-click-window-screenshot", final_capture["status"] == "completed")
        try:
            call("desktop.invoke", {"observation_id": clicked["result"]["observation"]["observation_id"],
                                     "selector": "UnobservedFakeControl"}, apply=True)
        except KitError as exc:
            check("unobserved-target-refused", exc.code == "unobserved_selector")
        else:
            check("unobserved-target-refused", False)
        report = {"status":"passed", "checks":checks, "state":str(state), "witness":current,
                  "scope":"one owned WinForms fixture; no other desktop applications"}
    except Exception as exc:
        report = {"status":"failed", "checks":checks, "state":str(state), "error":f"{type(exc).__name__}: {exc}"}
    atomic_json(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

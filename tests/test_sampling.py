"""Finite sampler regressions with real Kit receipts and a mocked Windows backend."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from rdc_operator import adapters
from rdc_operator.common import KitError, read_json


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rdck_sample_desktop_tests", PROJECT / "scripts/sample_desktop.py")
sampler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampler)

IDENTITY_A = {"window": 123, "pid": 7, "thread_id": 8,
              "process_started": "111", "executable": "fixture-a.exe"}
IDENTITY_B = {**IDENTITY_A, "pid": 9, "process_started": "222", "executable": "fixture-b.exe"}


def png_bytes():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\0\xff\0" * 2)) + chunk(b"IEND", b""))


class FakeWinapp:
    """Only the three fixed calls made by this fixture are supported."""
    def __init__(self, *, screenshot_hook=None, composite=False):
        self.calls = []
        self.screenshot_hook = screenshot_hook
        self.composite = composite

    def __call__(self, prefix, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[0] == "status":
            report = {"hwnd": 123, "processId": 7, "processName": "fixture"}
        elif argv[0] == "inspect":
            report = {"windows": [{"hwnd": 123, "elements": []}]}
        elif argv[0] == "screenshot":
            if self.screenshot_hook:
                self.screenshot_hook()
            output = Path(argv[argv.index("--output") + 1])
            output.write_bytes(png_bytes())
            report = {"hwnd": 123, "processId": 7, "filePath": str(output), "width": 2, "height": 2}
            if self.composite:
                report["windows"] = [{"hwnd": 123, "captured": True}, {"hwnd": 124, "captured": True}]
        else:
            raise AssertionError(f"Unexpected backend call: {argv}")
        return {"exit_code": 0, "timed_out": False, "output_truncated": False,
                "stdout": json.dumps(report), "stdout_json": report, "stderr": "", "stderr_json": None}

    def count(self, name):
        return sum(call[0] == name for call in self.calls)


class SamplingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.output = self.root / "samples"
        self.config = {"schema_version": 1, "allowed_roots": [str(self.root)],
                       "winapp": [sys.executable], "observation_ttl_seconds": 120}

    def run_sample(self, backend, *, adapter_identities=None, sample_identities=None, **kwargs):
        with patch.object(sampler, "_window_identity", side_effect=sample_identities,
                          return_value=IDENTITY_A), \
                patch.object(adapters, "_window_identity", side_effect=adapter_identities,
                             return_value=IDENTITY_A), \
                patch.object(adapters, "_winapp", side_effect=backend):
            return sampler.sample(self.config, self.state, 123, self.output,
                                  interval_ms=0, **kwargs)

    def test_reused_target_between_outer_check_and_adapter_is_not_captured(self):
        backend = FakeWinapp()
        # Observe completes on A. The outer sampler still sees A; the adapter's
        # own first query now sees B and must reject before it asks for pixels.
        result = self.run_sample(backend, count=2,
                                 adapter_identities=[IDENTITY_A, IDENTITY_A, IDENTITY_B])
        self.assertEqual(backend.count("screenshot"), 0)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stopped_reason"], "target_changed")
        self.assertFalse(any(self.output.glob("*.png")))
        self.assertEqual(backend.count("inspect"), 1)

    def test_all_frames_keep_one_observation_and_emit_after_persisting(self):
        backend = FakeWinapp()
        emitted = []
        def emit(row):
            saved = read_json(self.output / "manifest.json")
            self.assertEqual(saved["frames"][-1], row)
            emitted.append(row)
        result = self.run_sample(backend, count=2, emit=emit)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(backend.count("inspect"), 1)
        self.assertEqual(backend.count("screenshot"), 2)
        self.assertEqual(len(emitted), 2)
        self.assertEqual({row["frame"]["observation_id"] for row in emitted}, {result["observation_id"]})
        self.assertNotEqual(emitted[0]["frame"]["frame_id"], emitted[1]["frame"]["frame_id"])
        self.assertTrue(emitted[1]["same_bytes_as_previous"])
        self.assertTrue(all(row["frame"]["pixel_freshness"] == "unproven" for row in emitted))

    def test_composite_stops_sampling_and_preserves_the_refused_artifact(self):
        backend = FakeWinapp(composite=True)
        result = self.run_sample(backend, count=3)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stopped_reason"], "composite_capture_rejected")
        self.assertEqual(backend.count("screenshot"), 1)
        self.assertTrue((self.output / "frame-000.png").is_file())
        self.assertFalse((self.output / "frame-001.png").exists())

    def test_expired_observation_stops_without_refresh_or_second_capture(self):
        clock = [100.0]
        def advance_clock():
            clock[0] = 500.0
        backend = FakeWinapp(screenshot_hook=advance_clock)
        with patch.object(adapters, "time", SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)):
            with self.assertRaises(KitError) as error:
                self.run_sample(backend, count=3)
        self.assertEqual(error.exception.code, "stale_observation")
        self.assertEqual(backend.count("inspect"), 1)
        self.assertEqual(backend.count("screenshot"), 1)
        saved = read_json(self.output / "manifest.json")
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(len(saved["frames"]), 1)

    def test_admission_deadline_does_not_start_another_capture(self):
        clock = [0.0]
        def finish_after_deadline():
            clock[0] = 2.0
        backend = FakeWinapp(screenshot_hook=finish_after_deadline)
        fake_time = SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda _: None)
        with patch.object(sampler, "time", fake_time):
            result = self.run_sample(backend, count=3, start_deadline_seconds=1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stopped_reason"], "start_deadline_reached")
        self.assertEqual(backend.count("screenshot"), 1)

    def test_interrupt_keeps_uncertain_intent_and_never_starts_next_frame(self):
        def stop():
            raise KeyboardInterrupt("synthetic stop")
        backend = FakeWinapp(screenshot_hook=stop)
        with self.assertRaises(KeyboardInterrupt):
            self.run_sample(backend, count=3)
        self.assertEqual(backend.count("screenshot"), 1)
        saved = read_json(self.output / "manifest.json")
        self.assertEqual(saved["status"], "interrupted")
        intents = list((self.state / "requests").glob("*.intent.json"))
        receipts = list((self.state / "requests").glob("*.receipt.json"))
        self.assertEqual(len(intents), 2)  # one observation and one uncertain capture
        self.assertEqual(len(receipts), 1)  # the completed observation only
        self.assertEqual(read_json(receipts[0])["action"], "desktop.observe")


if __name__ == "__main__":
    unittest.main()

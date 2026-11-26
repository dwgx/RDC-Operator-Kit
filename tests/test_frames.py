"""Negative controls for screenshot provenance, not desktop integration tests."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from rdc_operator import adapters
from rdc_operator.core import execute_request
from rdc_operator.common import atomic_json
import time


def png_bytes():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\0\xff\0" * 2)) + chunk(b"IEND", b""))


class CaptureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # Match the canonical --output path passed to the WinApp adapter, even
        # when Windows TEMP uses an 8.3 directory alias.
        self.root = Path(tmp.name).resolve(strict=True)
        self.config = {"schema_version": 1, "allowed_roots": [str(self.root)], "winapp": [sys.executable]}
        self.identity = {"window": 123, "pid": 7, "thread_id": 8,
                         "process_started": "111", "executable": "fixture.exe"}
        self.state = self.root / "state"

    def capture(self, report_changes=None, *, rid="capture", image=None, identity_after=None):
        output = self.root / (rid + ".png")
        report = {"filePath": str(output), "width": 2, "height": 2, "processId": 7, "hwnd": 123}
        report.update(report_changes or {})
        def upstream(*_args, **_kwargs):
            output.write_bytes(image if image is not None else png_bytes())
            return {"exit_code": 0, "timed_out": False, "output_truncated": False,
                    "stdout": json.dumps(report), "stdout_json": report, "stderr": "", "stderr_json": None}
        request = {"request_id": rid, "action": "desktop.screenshot", "args": {"window": 123, "output": str(output)}}
        with patch.object(adapters, "_window_identity", side_effect=[self.identity, identity_after or self.identity]), \
                patch.object(adapters, "_winapp", side_effect=upstream):
            result = execute_request(request, self.config, self.state, apply=True)
        return result, request

    def test_composite_report_is_not_accepted_as_single_window(self):
        result, _ = self.capture({"windows": [{"hwnd": 123, "captured": True}, {"hwnd": 124, "captured": True}]})
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertNotIn("frame", result["result"])
        # Rejection is after capture: retain the evidence, do not claim no image was written.
        self.assertTrue((self.root / "capture.png").is_file())

    def test_wrong_identity_path_dimensions_and_element_crop_are_not_accepted(self):
        cases = [{"processId": 9}, {"hwnd": 124}, {"hwnd": True}, {"processId": True},
                 {"filePath": str(self.root / "other.png")}, {"width": 3}, {"height": True},
                 {"elementId": "cropped-element"}, {"coordinates": {}}, {"windows": []}, {"executionTarget": {}}]
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                result, _ = self.capture(changes, rid=f"mismatch-{index}")
                self.assertEqual(result["status"], "outcome_unknown")
                self.assertNotIn("frame", result["result"])

    def test_replay_preserves_frame_identity_and_time_without_recapture(self):
        result, request = self.capture()
        self.assertEqual(result["status"], "completed")
        frame = result["result"]["frame"]
        self.assertEqual(frame["artifact"]["sha256"], hashlib.sha256(png_bytes()).hexdigest())
        self.assertEqual(frame["artifact"]["bytes"], len(png_bytes()))
        self.assertIsNone(frame["captured_at"])
        self.assertEqual(frame["pixel_freshness"], "unproven")
        self.assertTrue(frame["capture_behavior"]["may_restore_or_foreground_window"])
        with patch.object(adapters, "_winapp") as upstream:
            replay = execute_request(request, self.config, self.state)
        upstream.assert_not_called()
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["result"]["frame"], frame)

    def test_two_calls_with_identical_pixels_do_not_claim_new_rendered_content(self):
        first, _ = self.capture(rid="one")
        second, _ = self.capture(rid="two")
        a, b = first["result"]["frame"], second["result"]["frame"]
        self.assertNotEqual(a["frame_id"], b["frame_id"])
        self.assertEqual(a["artifact"]["sha256"], b["artifact"]["sha256"])
        self.assertEqual(b["pixel_freshness"], "unproven")

    def test_target_replacement_or_invalid_png_remains_unknown(self):
        result, _ = self.capture(identity_after={**self.identity, "process_started": "222"})
        self.assertEqual(result["status"], "outcome_unknown")

    def test_bound_observation_prevents_capture_after_detectable_target_reuse(self):
        atomic_json(self.state / "observations" / "obs-bound.json", {
            "observation_id": "obs-bound", "observed_at": time.time(), "window": 123,
            "identity": self.identity, "selectors": {}, "winapp": [sys.executable]})
        request = {"request_id": "bound", "action": "desktop.screenshot", "args": {
            "window": 123, "output": str(self.root / "bound.png"), "observation_id": "obs-bound"}}
        changed = {**self.identity, "process_started": "222", "pid": 9}
        with patch.object(adapters, "_window_identity", return_value=changed), \
                patch.object(adapters, "_winapp") as upstream:
            result = execute_request(request, self.config, self.state, apply=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["result"]["error"]["code"], "target_changed")
        upstream.assert_not_called()
        self.assertFalse((self.root / "bound.png").exists())
        result, _ = self.capture(rid="invalid", image=b"not an image")
        self.assertEqual(result["status"], "outcome_unknown")


if __name__ == "__main__":
    unittest.main()

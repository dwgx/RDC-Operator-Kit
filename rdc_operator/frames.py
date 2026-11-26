"""Evidence for one screenshot call; no rendering-time or focus guarantees."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import uuid

from .common import KitError


MAX_CAPTURE_BYTES = 64 * 1024 * 1024


def _unknown(code: str, message: str):
    # These checks run after a capture, which may already have changed focus or
    # written a composite. Refusal cannot undo those effects.
    raise KitError(code, message, uncertain=True)


def verify_capture(output: Path, report: dict, identity: dict) -> dict:
    """Bind a new PNG artifact to a strictly single-window upstream report.

    The hash identifies file bytes, not a compositor frame. The caller supplies
    independently checked kernel identity before and after the capture command.
    """
    if not isinstance(report, dict):
        _unknown("capture_provenance_missing", "Screenshot JSON object is missing")
    if (type(report.get("hwnd")) is not int or type(report.get("processId")) is not int or
            report["hwnd"] != identity["window"] or report["processId"] != identity["pid"]):
        _unknown("capture_target_mismatch", "Screenshot report disagrees with kernel target identity")
    # Winapp omits null values. Even [] signals a multi-window result shape;
    # accepting it would silently depend on undocumented composite semantics.
    if report.get("windows") is not None:
        _unknown("composite_capture_rejected", "Multi-window capture cannot serve as single-window evidence")
    if (report.get("elementId") is not None or report.get("coordinates") is not None or
            report.get("executionTarget") is not None):
        _unknown("capture_scope_mismatch", "Element or coordinate capture is not the requested whole window")
    returned = report.get("filePath")
    if (not isinstance(returned, str) or not returned or "\0" in returned or
            not os.path.isabs(returned) or
            os.path.normcase(os.path.normpath(returned)) != os.path.normcase(str(output))):
        _unknown("capture_path_mismatch", "Screenshot report does not identify the requested output path")
    if any(type(report.get(k)) is not int or report[k] <= 0 for k in ("width", "height")):
        _unknown("capture_dimensions_mismatch", "Screenshot dimensions must be positive integers")
    if output.is_symlink() or (hasattr(output, "is_junction") and output.is_junction()):
        _unknown("capture_file_changed", "Screenshot output became a link")
    try:
        before = output.stat()
        if not stat.S_ISREG(before.st_mode) or not 24 <= before.st_size <= MAX_CAPTURE_BYTES:
            _unknown("invalid_capture", "Screenshot is not a bounded regular PNG file")
        digest, size = hashlib.sha256(), 0
        with output.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _unknown("capture_file_changed", "Screenshot file was replaced before hashing")
            header = stream.read(24)
            digest.update(header)
            size = len(header)
            while True:
                block = stream.read(min(65536, MAX_CAPTURE_BYTES + 1 - size))
                if not block:
                    break
                size += len(block)
                digest.update(block)
                if size > MAX_CAPTURE_BYTES:
                    _unknown("invalid_capture", "Screenshot exceeds the artifact byte limit")
            after_opened = os.fstat(stream.fileno())
        after = output.stat()
        signatures = [(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns) for s in (before, opened, after_opened, after)]
        if len(set(signatures)) != 1 or size != before.st_size or output.is_symlink():
            _unknown("capture_file_changed", "Screenshot file changed during verification")
    except OSError as exc:
        _unknown("capture_unreadable", f"Cannot verify screenshot artifact: {exc}")
    if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or
            header[8:12] != b"\0\0\0\r" or header[12:16] != b"IHDR"):
        _unknown("invalid_capture", "Screenshot PNG header is invalid")
    width, height = int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    if width != report["width"] or height != report["height"]:
        _unknown("capture_dimensions_mismatch", "PNG dimensions disagree with screenshot JSON")
    return {
        "schema_version": 1, "frame_id": "frame-" + uuid.uuid4().hex,
        "target": dict(identity), "captured_at": None,
        "pixel_freshness": "unproven", "backend": "not_reported",
        "artifact": {"path": str(output), "sha256": digest.hexdigest(), "bytes": size,
                     "width": width, "height": height},
        "capture_behavior": {"contract": "winapp-0.8.0", "surface": "single_window_report",
                             "may_restore_or_foreground_window": True},
        "verification": {"upstream_provenance_checked": True, "png_header_verified": True,
                         "full_image_decode_verified": False, "pixels_visually_reviewed": False,
                         "semantic_effect_verified": False},
    }

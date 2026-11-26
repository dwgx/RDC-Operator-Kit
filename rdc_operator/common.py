from __future__ import annotations

import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time


class KitError(Exception):
    def __init__(self, code: str, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.code, self.message, self.uncertain = code, message, uncertain


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("non-finite JSON number")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def strict_json(text):
    """Reject ambiguous keys and non-finite numbers at ingress."""
    return json.loads(text, object_pairs_hook=_unique_object,
                      parse_constant=_nonfinite, parse_float=_finite_float)


def read_json(path: Path) -> dict:
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            raise KitError("unsafe_path", "JSON state must not be a link or reparse point")
        if not stat.S_ISREG(info.st_mode):
            raise KitError("unsafe_path", "JSON state must be a regular file")
        limit = 8 * 1024 * 1024
        if info.st_size > limit:
            raise KitError("invalid_json", "JSON file exceeds the 8 MiB limit")
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise KitError("invalid_json", "JSON file exceeds the 8 MiB limit")
        value = strict_json(raw.decode("utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except KitError:
        raise
    except (OSError, ValueError, RecursionError) as exc:
        raise KitError("invalid_json", f"Cannot read JSON object: {path.name}: {exc}") from exc


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=".rdc-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        # Directory fsync is unavailable on Windows. File data is flushed above.
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def allowed_path(value: str, config: dict, *, must_exist: bool = True) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise KitError("invalid_path", "An explicit nonempty path is required")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise KitError("invalid_path", "Paths must be absolute")
    try:
        resolved = candidate.resolve(strict=must_exist)
        roots = [Path(root).resolve(strict=True) for root in config.get("allowed_roots", [])]
    except (OSError, RuntimeError) as exc:
        raise KitError("invalid_path", str(exc)) from exc
    for root in roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise KitError("outside_workspace", "Resolved path is outside configured allowed_roots")


def _json_or_none(text: str):
    try:
        return strict_json(text)
    except (ValueError, TypeError, RecursionError):
        return None


def run_command(argv: list[str], *, cwd: str | None = None, text: str | None = None,
                timeout: float = 30, env: dict | None = None) -> dict:
    """Own one direct child; never claim process-tree containment.

    Temporary files avoid deadlock on large simultaneous stdout/stderr or stdin.
    Output is monitored every 50 ms, bounded in returned memory, and truncated
    explicitly. A sufficiently fast child can exceed the on-disk threshold before
    the next sample: this is an output guard, not a disk quota or OS sandbox.
    """
    if (not isinstance(argv, list) or not argv or
            any(not isinstance(x, str) or "\x00" in x for x in argv)):
        raise KitError("invalid_argv", "argv must be a nonempty string list")
    if not 0 < timeout <= 3600:
        raise KitError("invalid_timeout", "Command timeout must be in (0, 3600]")
    input_bytes = (text or "").encode("utf-8")
    if len(input_bytes) > 65536:
        raise KitError("input_too_large", "stdin exceeds 64 KiB")
    command_env = os.environ.copy()
    command_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    if env:
        for key, value in env.items():
            if value is None:
                command_env.pop(key, None)
            else:
                command_env[key] = value
    limit = 1024 * 1024
    timed_out, truncated = False, False
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as incoming:
        incoming.write(input_bytes)
        incoming.seek(0)
        try:
            child = subprocess.Popen(argv, cwd=cwd, stdin=incoming, stdout=out, stderr=err,
                                     shell=False, env=command_env)
        except OSError as exc:
            raise KitError("launch_failed", str(exc)) from exc
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                truncated = os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > 2 * limit
                timed_out = time.monotonic() >= deadline
                if timed_out or truncated:
                    child.kill()  # verified child handle only; never an arbitrary PID
                    child.wait(timeout=5)
                    break
                time.sleep(0.05)
        finally:
            # An interrupt must not release our state lock while the direct
            # child is still executing. Detached grandchildren remain outside
            # this guarantee and are handled by the owning upstream adapter.
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
        out.seek(0)
        err.seek(0)
        stdout_bytes, stderr_bytes = out.read(limit + 1), err.read(limit + 1)
        truncated = truncated or len(stdout_bytes) > limit or len(stderr_bytes) > limit
        stdout = stdout_bytes[:limit].decode("utf-8-sig", errors="replace")
        stderr = stderr_bytes[:limit].decode("utf-8-sig", errors="replace")
        return {"argv": argv, "exit_code": child.returncode,
                "stdout": stdout, "stderr": stderr,
                "stdout_json": _json_or_none(stdout), "stderr_json": _json_or_none(stderr),
                "timed_out": timed_out, "output_truncated": truncated}

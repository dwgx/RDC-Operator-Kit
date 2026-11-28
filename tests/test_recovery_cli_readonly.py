"""Observe a fresh-source -B resume CLI without claiming an OS sandbox."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from rdc_operator.common import atomic_json
from rdc_operator.core import execute_request
from rdc_operator.recovery import save_checkpoint


def _snapshot(root):
    """Include directories and file identities/content, deliberately not atime."""
    snapshot = {}
    for path in (root, *sorted(root.rglob("*"))):
        info = path.lstat()
        snapshot[path.relative_to(root).as_posix()] = (
            info.st_mode, info.st_size, info.st_dev, info.st_ino, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest()
            if stat.S_ISREG(info.st_mode) else None,
        )
    return snapshot


class RecoveryCliReadOnlyTests(unittest.TestCase):
    def test_fresh_source_resume_with_B_creates_no_files_or_directories(self):
        with tempfile.TemporaryDirectory(prefix="rdc-cli-readonly-") as temporary:
            root = Path(temporary).resolve()
            state = root / "owned state"
            inputs = root / "owned inputs"
            inputs.mkdir()
            runner = root / "neutral cwd"
            runner.mkdir()
            config = {"schema_version": 1, "allowed_roots": [str(root)],
                      "smartcli": [sys.executable]}
            request = {"request_id": "completed-fixture", "action": "terminal.start",
                       "args": {"session": "owned-fixture", "command": "fixture-never-executed",
                                "cwd": str(runner)}}
            # All preparation happens before the fresh package copy and snapshot.
            # The injected operation never starts a terminal or another adapter.
            execute_request(request, config, state, apply=True,
                            operation=lambda *_: {"status": "completed", "fixture": True})
            document = {
                "schema_version": 1, "task_id": "cli-readonly-task", "scope_sha256": "a" * 64,
                "route": {"link_id": "synthetic-link", "device_id": "synthetic-device",
                          "observed_utc": datetime.now(timezone.utc).isoformat()},
                "event": "same_connection", "request_ids": [request["request_id"]],
                "handles": [], "stop_reason": "none",
            }
            save_checkpoint(document, config, state, expected_revision=0)
            context = {key: deepcopy(document[key]) for key in
                       ("schema_version", "scope_sha256", "route", "event", "stop_reason")}
            context["event"] = "user_reconnected"
            config_path, context_path = inputs / "config.json", inputs / "context.json"
            atomic_json(config_path, config)
            atomic_json(context_path, context)

            source = root / "fresh source"
            package = Path(__file__).resolve().parents[1] / "rdc_operator"
            shutil.copytree(package, source / "rdc_operator",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            self.assertTrue((source / "rdc_operator/__main__.py").is_file())
            self.assertFalse(any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                                 for path in source.rglob("*")))

            env = os.environ.copy()
            # Replacing PYTHONPATH and using a neutral cwd selects the fresh copy.
            # -B itself must prevent cache writes, not an inherited environment setting.
            for name in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTHONHOME"):
                env.pop(name, None)
            env.update({"PYTHONPATH": str(source), "PYTHONNOUSERSITE": "1",
                        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
            command = [sys.executable, "-B", "-m", "rdc_operator",
                       "--config", str(config_path), "--state", str(state),
                       "resume", document["task_id"], "--context", str(context_path)]
            watched = {"source": source, "state": state, "inputs": inputs}
            before = {name: _snapshot(path) for name, path in watched.items()}
            stdout_path, stderr_path = root / "cli.stdout.log", root / "cli.stderr.log"
            # Files avoid a Windows venv redirector retaining captured PIPE handles.
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                result = subprocess.run(command, cwd=runner, env=env, stdin=subprocess.DEVNULL,
                                        stdout=stdout, stderr=stderr, shell=False, timeout=30)
            after = {name: _snapshot(path) for name, path in watched.items()}
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, stderr)
            self.assertEqual(stderr, "")
            plan = json.loads(stdout_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["status"], "review_required")
            self.assertIs(plan["execution_authorized"], False)
            self.assertEqual(plan["requests"][0]["request_id"], request["request_id"])
            self.assertEqual(plan["requests"][0]["saved_receipt_status"], "completed")
            for name in watched:
                with self.subTest(directory=name):
                    self.assertEqual(after[name], before[name],
                                     "The -B resume CLI changed its " + name + " directory")


if __name__ == "__main__":
    unittest.main()

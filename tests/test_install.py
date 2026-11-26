import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("verify_winapp", Path(__file__).parents[1] / "scripts/verify_winapp.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class InstallerContentTests(unittest.TestCase):
    def package(self, root, files=None):
        archive = root / "tool.zip"
        with zipfile.ZipFile(archive, "w") as package:
            for name, data in (files or {"winapp.exe": b"fixture - never executed", "engine.dll": b"fixture"}).items():
                package.writestr(name, data)
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_existing_binary_tampering_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, sha = self.package(root)
            dest = root / "installed"
            self.assertEqual(verify.verify_install(archive, sha, dest)["verified_files"], 2)
            verify.verify_install(archive, sha, dest)
            (dest / "winapp.exe").write_bytes(b"unexpected executable")
            with self.assertRaisesRegex(ValueError, "differs"):
                verify.verify_install(archive, sha, dest)
            self.assertEqual((dest / "winapp.exe").read_bytes(), b"unexpected executable")

    def test_unexpected_dll_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, sha = self.package(root)
            dest = root / "installed"
            verify.verify_install(archive, sha, dest)
            (dest / "extra.dll").write_bytes(b"unexpected")
            with self.assertRaises(ValueError):
                verify.verify_install(archive, sha, dest)

    def test_bad_archive_hash_never_extracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, sha = self.package(root)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify.verify_install(archive, "0" * 64, root / "installed")
            self.assertFalse((root / "installed").exists())

    def test_zip_traversal_never_extracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, sha = self.package(root, {"winapp.exe": b"fixture", "../outside": b"bad"})
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                verify.verify_install(archive, sha, root / "installed")
            self.assertFalse((root / "outside").exists())


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux installer needs bash")
class LinuxInterpreterDirectoryTests(unittest.TestCase):
    def fixture(self, base):
        root = base / "source with spaces 中文"
        (root / "scripts").mkdir(parents=True)
        shutil.copyfile(Path(__file__).parents[1] / "scripts/install.sh", root / "scripts/install.sh")
        (root / ".rdc-install.json").write_text(json.dumps({
            "project": "rdc-operator-kit", "install_root": str(root), "schema_version": 1}))
        return root

    def run_installer(self, root):
        env = dict(os.environ)
        env["RDC_PYTHON"] = sys.executable
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        return subprocess.run([shutil.which("bash"), str(root / "scripts/install.sh")],
                              env=env, capture_output=True, text=True, timeout=15)

    def test_linked_bin_directory_never_executes_external_fixture_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = self.fixture(base)
            (root / ".venv").mkdir()
            foreign = base / "separate-fixture-bin"
            foreign.mkdir()
            sentinel = base / "foreign-executed"
            binary = foreign / "python"
            binary.write_text("#!/bin/sh\nprintf executed > " + shlex.quote(str(sentinel)) + "\nexit 91\n")
            binary.chmod(0o700)
            (root / ".venv/bin").symlink_to(foreign, target_is_directory=True)
            marker_before = (root / ".rdc-install.json").read_bytes()
            result = self.run_installer(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Linked installation path refused: bin", result.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual((root / ".rdc-install.json").read_bytes(), marker_before)

    def test_normal_venv_python_symlink_remains_usable_without_installing_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(Path(temporary).resolve())
            created = subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", "--symlinks",
                                      str(root / ".venv")], capture_output=True, text=True, timeout=15)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue((root / ".venv/bin/python").is_symlink())
            result = self.run_installer(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no module named pip", result.stderr.lower())
            self.assertNotIn("Linked installation path refused", result.stderr)


@unittest.skipUnless(os.name == "nt", "Windows installer junction test requires Windows")
class WindowsInterpreterDirectoryTests(unittest.TestCase):
    def test_linked_scripts_directory_is_refused_before_interpreter_invocation(self):
        powershell = shutil.which("pwsh")
        command = shutil.which("cmd.exe")
        if not powershell or not command:
            self.skipTest("pwsh and cmd.exe are required for the Windows junction fixture")
        with tempfile.TemporaryDirectory(prefix="rdck-install-junction-") as temporary:
            base = Path(temporary).resolve()
            root = base / "source with spaces 中文"
            (root / "scripts").mkdir(parents=True)
            shutil.copyfile(Path(__file__).parents[1] / "scripts/install.ps1", root / "scripts/install.ps1")
            (root / "pyproject.toml").write_text("# owned fixture; never installed\n", encoding="utf-8")
            (root / ".venv").mkdir()
            marker = root / ".rdc-install.json"
            marker.write_text(json.dumps({"project": "rdc-operator-kit", "install_root": str(root),
                                          "schema_version": 1}), encoding="utf-8")
            marker_before = marker.read_bytes()
            foreign = base / "separate owned empty directory"
            foreign.mkdir()
            linked = root / ".venv" / "Scripts"
            junction = subprocess.run([command, "/d", "/c", "mklink", "/J", str(linked), str(foreign)],
                                      capture_output=True, timeout=10)
            if junction.returncode != 0:
                self.skipTest("directory junction creation is unavailable for this user or filesystem")
            try:
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)
                result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-File",
                                         str(root / "scripts/install.ps1"), "-Python", sys.executable],
                                        env=env, capture_output=True, text=True, encoding="utf-8",
                                        errors="replace", timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Linked installation path refused", result.stdout + result.stderr)
                self.assertFalse((root / "config.local.json").exists())
                self.assertEqual(marker.read_bytes(), marker_before)
                self.assertEqual(list(foreign.iterdir()), [])
            finally:
                # Remove only the junction itself; its target is separately owned.
                os.rmdir(linked)

"""Source bundle privacy checks using isolated files, never real local config."""
import html
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import build_release


class ReleasePrivacyTests(unittest.TestCase):
    def make_build_fixture(self, root, references):
        links = "".join('<a href="./docs/' + html.escape(name, quote=True) + '">document</a>'
                        for name in references)
        files = {
            "rdc_operator/__init__.py": '__version__ = "0.0.0-review"\n',
            "site/index.html": ('<!doctype html><html><head>'
                                '<link rel="stylesheet" href="./styles.css">'
                                '<script src="./app.js" defer></script>'
                                '<link rel="icon" href="./icon.svg">'
                                '</head><body><main>' + links + '</main></body></html>'),
            "site/styles.css": "body { color: black; }",
            "site/app.js": "void 0;",
            "site/icon.svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
            "site/docs/guide.md": "SYNTHETIC_PUBLIC_GUIDE",
            "site/docs/research/data.json": '{"research":"SYNTHETIC_PUBLIC_JSON"}',
            "examples/config.example.json": '{"schema_version":1}',
            "examples/recovery-checkpoint.example.json": '{"example":"SYNTHETIC_PUBLIC_CHECKPOINT"}',
            "site/docs/recovery-context.example.json": '{"example":"SYNTHETIC_PUBLIC_CONTEXT"}',
        }
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_nested_runtime_files_are_excluded_without_reading_their_bytes(self):
        private_names = {
            "config.local.json", ".rdc-install.json", ".rdc-delivery.json",
            "delivery-payload.json", "receive-source.py",
            ".recovery-marker.json", "recovery-checkpoint.local.json",
            "recovery-context.local.json", "recovery-handoff.local.md",
        }
        allowed = {
            "README.md": "source readme",
            "examples/config.example.json": '{"schema_version": 1}',
            "examples/recovery-checkpoint.example.json": '{"example": true}',
            "site/docs/recovery-context.example.json": '{"example": true}',
            "examples/browser-evidence/counter-success.json": '{"synthetic": true}',
            "docs/research-wave2/OBSERVATION.sources.json": '{"research": true}',
            "docs/research-wave2/MCP-SKILL.sources.json": '{"research": true}',
            "docs/research-wave2/sources-browser.json": '{"research": true}',
            "site/docs/research-wave2/OBSERVATION.sources.json": '{"research": true}',
            "site/.nojekyll": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, content in allowed.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            for parent in (root, root / "docs/copied-runtime", root / "site/nested/runtime"):
                parent.mkdir(parents=True, exist_ok=True)
                for name in private_names:
                    (parent / name).write_text("SYNTHETIC_PRIVATE", encoding="utf-8")
            # Keep separate directories so the fixture also works on Windows.
            mixed = root / "site/mixed-case"
            mixed.mkdir()
            for name in private_names:
                path = Path(name)
                (mixed / (path.stem.swapcase() + path.suffix)).write_text(
                    "SYNTHETIC_PRIVATE", encoding="utf-8")

            original_read = Path.read_bytes

            def guarded_read(path):
                if path.name.casefold() in private_names:
                    self.fail(f"Private runtime bytes were read: {path.relative_to(root)}")
                return original_read(path)

            with patch.object(build_release, "ROOT", root), \
                    patch.object(Path, "read_bytes", guarded_read):
                actual = dict(build_release.source_files())
            self.assertEqual(actual, {name: content.encode("utf-8") for name, content in allowed.items()})

    def test_private_directories_are_pruned_before_listing_case_insensitively(self):
        private_directories = {
            "__pycache__", ".git", ".venv", ".venv-mcp", "evidence", "tools",
            "dist", "build", ".rdc-state", ".pytest_cache", "sample.egg-info",
            "checkpoints",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, name in enumerate(sorted(private_directories)):
                for branch, spelling in (("docs", name), ("site", name.swapcase())):
                    private = root / branch / f"nested-{index}" / spelling
                    private.mkdir(parents=True)
                    (private / "private.json").write_text("SYNTHETIC_PRIVATE", encoding="utf-8")
            retained = root / "docs/research.json"
            retained.write_text('{"research": true}', encoding="utf-8")
            original_iterdir = Path.iterdir

            def guarded_iterdir(path):
                if any(part.casefold() in private_directories for part in path.relative_to(root).parts):
                    self.fail(f"Private directory was traversed: {path.relative_to(root)}")
                return original_iterdir(path)

            with patch.object(build_release, "ROOT", root), \
                    patch.object(Path, "iterdir", guarded_iterdir):
                self.assertEqual(dict(build_release.source_files()),
                                 {"docs/research.json": b'{"research": true}'})

    def test_build_rejects_private_preview_references_without_reading_them(self):
        references = (
            "config.local.json", ".rdc-install.json", ".rdc-delivery.json",
            "delivery-payload.json", "receive-source.py", "nested/CONFIG.LOCAL.json",
            ".pytest_cache/private.json", "nested/EVIDENCE/private.json",
            "nested/Sample.EGG-INFO/private.json",
            ".recovery-marker.json", "recovery-checkpoint.local.json",
            "nested/RECOVERY-CONTEXT.LOCAL.json", "recovery-handoff.local.md",
            "state/checkpoints/private-task.json", "state/CHECKPOINTS/private-task.json",
        )
        for reference in references:
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as tmp:
                root, output = Path(tmp) / "source", Path(tmp) / "output"
                self.make_build_fixture(root, [reference])
                private = root / "site/docs" / reference
                private.parent.mkdir(parents=True, exist_ok=True)
                private.write_text("SYNTHETIC_PRIVATE_PREVIEW_SENTINEL", encoding="utf-8")
                original_open = Path.open

                def guarded_open(path, *args, **kwargs):
                    if path == private:
                        self.fail(f"Private preview content was opened: {reference}")
                    return original_open(path, *args, **kwargs)

                with patch.object(build_release, "ROOT", root), \
                        patch.object(Path, "open", guarded_open):
                    with self.assertRaises(ValueError):
                        build_release.build(output)
                self.assertEqual(list(output.iterdir()), [])

    def test_build_rejects_noncanonical_or_unlisted_preview_references(self):
        for reference in ("../styles.css", "../../unlisted.json", "../../../outside.json",
                          "not-in-source.txt", "..\\outside.json", "absolute"):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as tmp:
                root, output = Path(tmp) / "source", Path(tmp) / "output"
                actual_reference = str(Path(tmp) / "absolute.json") if reference == "absolute" else reference
                self.make_build_fixture(root, [actual_reference])
                target = root / "site/docs" / actual_reference
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("SYNTHETIC_OUTSIDE_DOC_SCOPE", encoding="utf-8")
                with patch.object(build_release, "ROOT", root):
                    with self.assertRaises(ValueError):
                        build_release.build(output)
                self.assertEqual(list(output.iterdir()), [])

    def test_build_artifacts_exclude_private_data_and_preserve_public_documents(self):
        sentinel = b"SYNTHETIC_PRIVATE_ARTIFACT_SENTINEL"
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / "source", Path(tmp) / "output"
            self.make_build_fixture(root, ["guide.md", "research/data.json", "recovery-context.example.json"])
            for relative in ("site/docs/config.local.json", "docs/nested/.rdc-delivery.json",
                             "site/docs/.pytest_cache/private.json",
                             "docs/copied-state/.recovery-marker.json",
                             "site/docs/copied-state/checkpoints/private-task.json",
                             "docs/copied-state/CHECKPOINTS/private-task.json",
                             "site/docs/recovery-checkpoint.local.json",
                             "docs/nested/RECOVERY-CONTEXT.LOCAL.json",
                             "site/docs/recovery-handoff.local.md"):
                private = root / relative
                private.parent.mkdir(parents=True, exist_ok=True)
                private.write_bytes(sentinel)
            with patch.object(build_release, "ROOT", root):
                result = build_release.build(output)
            contents = {path.name: path.read_bytes() for path in output.iterdir()}
            with zipfile.ZipFile(output / "RDC-Operator-Kit-0.0.0-review.zip") as archive:
                contents.update({"zip/" + name: archive.read(name) for name in archive.namelist()})
            with tarfile.open(output / "RDC-Operator-Kit-0.0.0-review.tar.gz", "r:gz") as archive:
                for member in archive.getmembers():
                    contents["tar/" + member.name] = archive.extractfile(member).read()
            for name, content in contents.items():
                with self.subTest(artifact=name):
                    self.assertNotIn(sentinel, content)
            preview = contents["RDC-Operator-Kit-preview.html"]
            self.assertIn(b"SYNTHETIC_PUBLIC_GUIDE", preview)
            self.assertIn(b"SYNTHETIC_PUBLIC_JSON", preview)
            self.assertIn(b"SYNTHETIC_PUBLIC_CONTEXT", preview)
            manifest_names = {entry["path"] for entry in json.loads(contents["SOURCE-MANIFEST.json"])["files"]}
            self.assertIn("site/docs/research/data.json", manifest_names)
            self.assertIn("examples/config.example.json", manifest_names)
            self.assertIn("examples/recovery-checkpoint.example.json", manifest_names)
            self.assertIn("site/docs/recovery-context.example.json", manifest_names)
            self.assertEqual(result["source_files"], len(manifest_names))

    def test_standalone_preview_uses_the_same_private_reference_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_build_fixture(root, ["config.local.json"])
            (root / "site/docs/config.local.json").write_text(
                "SYNTHETIC_PRIVATE_STANDALONE_SENTINEL", encoding="utf-8")
            with patch.object(build_release, "ROOT", root):
                with self.assertRaises(ValueError):
                    build_release.standalone_page()

    def test_standalone_preview_refuses_recovery_runtime_even_in_supplied_snapshot(self):
        references = (
            ".recovery-marker.json", "recovery-checkpoint.local.json",
            "nested/RECOVERY-CONTEXT.LOCAL.json", "recovery-handoff.local.md",
            "state/checkpoints/private-task.json", "state/CHECKPOINTS/private-task.json",
        )
        for reference in references:
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make_build_fixture(root, [reference])
                with patch.object(build_release, "ROOT", root):
                    sources = dict(build_release.source_files())
                # Even a caller-supplied snapshot must not make a private
                # recovery record available to the standalone HTML renderer.
                sources["site/docs/" + reference] = b"SYNTHETIC_PRIVATE_RECOVERY_SNAPSHOT"
                with self.assertRaisesRegex(ValueError, "Private source reference refused"):
                    build_release.standalone_page(sources)


if __name__ == "__main__":
    unittest.main()

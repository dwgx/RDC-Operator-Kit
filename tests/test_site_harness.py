"""Lifecycle regressions only: no Playwright import, browser launch, or UI access."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import smoke_site


class FakePage:
    def __init__(self, rig, index):
        self.rig, self.index = rig, index

    def set_default_timeout(self, timeout):
        self.rig.event("timeout:" + str(self.index))

    def on(self, name, callback):
        self.rig.event("listen:" + str(self.index))

    def goto(self, url):
        self.rig.event("goto:" + str(self.index))

    def screenshot(self, *, path):
        self.rig.event("screenshot:" + str(self.index))
        Path(path).write_bytes(b"synthetic artifact, not a browser image")


class FakeContext:
    def __init__(self, rig, index):
        self.rig, self.index = rig, index

    def route(self, pattern, callback):
        self.rig.event("route:" + str(self.index))

    def new_page(self):
        self.rig.event("page:" + str(self.index))
        return FakePage(self.rig, self.index)

    def close(self):
        self.rig.event("close_context:" + str(self.index))


class FakeBrowser:
    version = "lifecycle-stub-not-a-browser"

    def __init__(self, rig):
        self.rig, self.context_count = rig, 0

    def new_context(self, **options):
        self.context_count += 1
        self.rig.event("context:" + str(self.context_count))
        return FakeContext(self.rig, self.context_count)

    def close(self):
        self.rig.event("close_browser")


class FakeRuntime:
    def __init__(self, errors=None, observer=None):
        self.errors = errors or {}
        self.observer = observer
        self.events = []
        self.browser = FakeBrowser(self)
        self.chromium = SimpleNamespace(launch=self.launch)

    def event(self, name):
        self.events.append(name)
        if self.observer:
            self.observer(name)
        if name in self.errors:
            raise self.errors[name]

    def factory(self):
        return SimpleNamespace(start=self.start)

    def start(self):
        self.event("start_runtime")
        return self

    def launch(self, **options):
        self.event("launch")
        return self.browser

    def stop(self):
        self.event("stop_runtime")


class SiteHarnessLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "new-run"

    def execute(self, *, rig=None, dependency_error=None, actions=None, page_error=None):
        rig = rig or FakeRuntime()
        if actions is None:
            actions = [lambda page: page.goto("file:///owned-fixture.html")] * 2
        cases = [smoke_site.SiteCase("case-" + str(i), action)
                 for i, action in enumerate(actions, 1)]

        def load():
            if dependency_error:
                raise dependency_error
            return rig.factory, None

        stdout = io.StringIO()
        with (patch.object(smoke_site, "_load_playwright", side_effect=load),
              patch.object(smoke_site, "_site_cases", return_value=cases),
              patch.object(smoke_site, "standalone_page",
                           side_effect=page_error, return_value=b"<title>owned fixture</title>"),
              redirect_stdout(stdout)):
            code = smoke_site.main(["--output", str(self.output)])
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, result["exit_code"])
        if self.output.is_dir():
            saved = json.loads((self.output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, result)
        return code, result, rig

    def test_success_archives_before_launch_and_closes_only_owned_handles(self):
        phases = []
        def observe(event):
            if event == "launch":
                phases.append(json.loads((self.output / "summary.json").read_text())["phase"])
        code, result, rig = self.execute(rig=FakeRuntime(observer=observe))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(phases, ["launch_browser"])
        self.assertEqual((result["passed"], result["failed"], result["not_run"]), (2, 0, 0))
        self.assertTrue(all(item["status"] == "pass" for item in result["screenshots"]))
        self.assertEqual(rig.events[-2:], ["close_browser", "stop_runtime"])
        self.assertEqual(sum(event.startswith("close_context:") for event in rig.events), 4)
        self.assertEqual(list(self.output.glob(".rdc-*.tmp")), [])

    def test_missing_dependency_writes_unavailable_without_any_browser_work(self):
        code, result, rig = self.execute(dependency_error=ModuleNotFoundError("No module named playwright"))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["not_run"], 2)
        self.assertEqual(rig.events, [])
        self.assertTrue(all(not item["executed"] for item in result["checks"]))

    def test_page_preparation_failure_has_summary_and_no_optional_import(self):
        code, result, rig = self.execute(page_error=RuntimeError("page build failed"))
        self.assertEqual(code, 1)
        self.assertEqual(result["errors"][0]["stage"], "prepare_pages")
        self.assertEqual(result["passed"], 0)
        self.assertEqual(rig.events, [])

    def test_runtime_start_failure_is_reported_without_claiming_cleanup(self):
        code, result, rig = self.execute(rig=FakeRuntime({"start_runtime": RuntimeError("driver start failed")}))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cleanup"], [])
        self.assertEqual(rig.events, ["start_runtime"])

    def test_launch_failure_still_stops_started_runtime(self):
        code, result, rig = self.execute(rig=FakeRuntime({"launch": RuntimeError("binary unavailable")}))
        self.assertEqual(code, 1)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["not_run"], 2)
        self.assertEqual(rig.events, ["start_runtime", "launch", "stop_runtime"])
        self.assertEqual(result["cleanup"], [{"name": "playwright", "status": "pass"}])

    def test_context_creation_failure_cannot_pass_unexecuted_case(self):
        rig = FakeRuntime({"context:1": RuntimeError("context creation failed")})
        code, result, rig = self.execute(rig=rig)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"][0]["status"], "fail")
        self.assertFalse(result["checks"][0]["executed"])
        self.assertEqual(result["checks"][0]["stage"], "context_create")
        self.assertEqual(result["checks"][1]["status"], "pass")
        self.assertNotIn("close_context:1", rig.events)

    def test_partial_context_initialization_is_cleaned(self):
        for stage in ["route:1", "page:1", "listen:1"]:
            with self.subTest(stage=stage):
                self.output = Path(self.temp.name) / stage.replace(":", "-")
                code, result, rig = self.execute(rig=FakeRuntime({stage: RuntimeError("setup failed")}))
                self.assertEqual(code, 1)
                self.assertFalse(result["checks"][0]["executed"])
                self.assertIn("close_context:1", rig.events)
                self.assertNotIn("goto:1", rig.events)

    def test_policy_refusal_stops_all_later_tests_and_screenshots(self):
        rig = FakeRuntime({"goto:1": RuntimeError("net::ERR_BLOCKED_BY_ADMINISTRATOR")})
        code, result, rig = self.execute(rig=rig)
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["checks"][0]["status"], "blocked")
        self.assertEqual(result["checks"][1]["status"], "not_run_after_refusal")
        self.assertEqual(result["passed"], 0)
        self.assertTrue(all(item["status"] == "not_run_after_refusal" for item in result["screenshots"]))
        self.assertNotIn("context:2", rig.events)
        self.assertEqual(rig.events[-3:], ["close_context:1", "close_browser", "stop_runtime"])

    def test_test_failure_is_retained_while_independent_tests_continue(self):
        def fail(page):
            page.goto("file:///owned-fixture.html")
            raise AssertionError("expected state was not observed")
        code, result, rig = self.execute(actions=[fail, lambda page: page.goto("file:///owned-fixture.html")])
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual((result["passed"], result["failed"]), (1, 1))
        self.assertEqual(result["checks"][1]["status"], "pass")
        self.assertIn("goto:2", rig.events)

    def test_final_screenshot_failure_is_archived_and_resources_close(self):
        rig = FakeRuntime({"screenshot:3": RuntimeError("capture failed")})
        code, result, rig = self.execute(rig=rig)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["screenshot_failed"], 1)
        self.assertEqual(result["screenshots"][0]["status"], "fail")
        self.assertIn("close_context:3", rig.events)
        self.assertEqual(rig.events[-2:], ["close_browser", "stop_runtime"])

    def test_refusal_in_final_capture_stops_following_capture(self):
        rig = FakeRuntime({"goto:3": RuntimeError("net::ERR_BLOCKED_BY_ADMINISTRATOR")})
        code, result, rig = self.execute(rig=rig)
        self.assertEqual(code, 3)
        self.assertEqual(result["screenshots"][0]["status"], "blocked")
        self.assertEqual(result["screenshots"][1]["status"], "not_run_after_refusal")
        self.assertNotIn("context:4", rig.events)
        self.assertNotIn("screenshot:3", rig.events)

    def test_context_cleanup_failure_stops_new_work_and_keeps_effect_result(self):
        rig = FakeRuntime({"close_context:1": RuntimeError("context close failed")})
        code, result, rig = self.execute(rig=rig)
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"][0]["status"], "pass")
        self.assertEqual(result["checks"][1]["status"], "not_run_after_failure")
        self.assertEqual(result["cleanup_failed"], 1)
        self.assertNotIn("context:2", rig.events)
        self.assertEqual(rig.events[-2:], ["close_browser", "stop_runtime"])

    def test_browser_cleanup_failure_does_not_skip_runtime_cleanup(self):
        code, result, rig = self.execute(rig=FakeRuntime({"close_browser": RuntimeError("close failed")}))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cleanup_failed"], 1)
        self.assertEqual(rig.events[-1], "stop_runtime")

    def test_runtime_cleanup_failure_cannot_report_pass(self):
        code, result, rig = self.execute(rig=FakeRuntime({"stop_runtime": RuntimeError("stop failed")}))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cleanup_failed"], 1)

    def test_keyboard_interrupt_saves_partial_summary_and_closes_resources(self):
        code, result, rig = self.execute(rig=FakeRuntime({"goto:1": KeyboardInterrupt()}))
        self.assertEqual(code, 130)
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["checks"][1]["status"], "not_run_after_interruption")
        self.assertEqual(rig.events[-3:], ["close_context:1", "close_browser", "stop_runtime"])

    def test_summary_write_failure_stops_before_more_ui_and_still_cleans(self):
        original = smoke_site.atomic_json
        failed = False
        def archive(path, value):
            nonlocal failed
            if value["phase"] == "tests" and not failed:
                failed = True
                raise OSError("simulated disk error")
            original(path, value)
        with patch.object(smoke_site, "atomic_json", side_effect=archive):
            code, result, rig = self.execute()
        self.assertEqual(code, 4)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed"], 0)
        self.assertFalse(any(event.startswith("context:") for event in rig.events))
        self.assertEqual(rig.events[-2:], ["close_browser", "stop_runtime"])

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        marker = self.output / "summary.json"
        original = '{"keep":"prior evidence"}'
        marker.write_text(original)
        stdout = io.StringIO()
        with patch.object(smoke_site, "_load_playwright") as load, redirect_stdout(stdout):
            code = smoke_site.main(["--output", str(self.output)])
        self.assertEqual(code, 4)
        self.assertEqual(marker.read_text(), original)
        load.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")


if __name__ == "__main__":
    unittest.main()

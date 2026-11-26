"""Optional Chromium smoke for this project's own local static pages.

No alternate transport is attempted after a policy refusal. Playwright is an
optional dependency loaded only after the initial summary is archived. The
summary describes this runner, not permission to run it in a restricted host.

Exit codes: 0 passed, 1 failed/incomplete, 2 dependency unavailable,
3 policy blocked, 4 evidence output unavailable, 130 interrupted.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rdc_operator.common import atomic_json
from scripts.build_release import standalone_page


@dataclass
class SiteCase:
    name: str
    run: Callable
    options: dict = field(default_factory=dict)


class SummaryWriteError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _error(exc):
    return {"type": type(exc).__name__, "message": str(exc)[:1000]}


def _policy_refusal(exc):
    message = str(exc).casefold()
    return any(marker in message for marker in (
        "err_blocked_by_administrator", "err_blocked_by_policy",
        "host restrictions gate", "not permitted by policy",
    ))


def _load_playwright():
    # Import failures must be represented in summary.json, not a bare traceback.
    from playwright.sync_api import expect, sync_playwright
    return sync_playwright, expect


class _Run:
    def __init__(self, output):
        self.output = output
        self.created = False
        self.archive_failed = False
        self.interrupted = False
        self.unavailable = False
        self.result = {
            "schema_version": 1,
            "scope": "own static files only; Chromium, mock clipboard, no external site",
            "status": "running", "phase": "output", "browser": None,
            "checks": [], "screenshots": [], "cleanup": [], "errors": [],
            "passed": 0, "failed": 0, "blocked": False, "not_run": 0,
            "started_at": _now(), "finished_at": None, "exit_code": None,
        }

    def error(self, stage, exc):
        item = {"stage": stage, **_error(exc)}
        self.result["errors"].append(item)
        self.result["blocked"] |= _policy_refusal(exc)
        self.interrupted |= isinstance(exc, KeyboardInterrupt)
        return item

    def checkpoint(self, *, required=True):
        result = self.result
        result["passed"] = sum(c["status"] == "pass" for c in result["checks"])
        result["failed"] = sum(c["status"] == "fail" for c in result["checks"])
        result["not_run"] = sum(c["status"].startswith("not_run") for c in result["checks"])
        result["screenshot_failed"] = sum(c["status"] == "fail" for c in result["screenshots"])
        result["cleanup_failed"] = sum(c["status"] == "fail" for c in result["cleanup"])
        result["updated_at"] = _now()
        try:
            atomic_json(self.output / "summary.json", result)
            return True
        except (Exception, KeyboardInterrupt) as exc:
            if not self.archive_failed:
                self.error("summary_write", exc)
            self.archive_failed = True
            if required:
                raise SummaryWriteError("Cannot durably update summary.json") from exc
            return False

    def close_owned(self, name, close):
        record = {"name": name, "status": "running"}
        self.result["cleanup"].append(record)
        # Even if recording fails, attempt to release every handle we own.
        self.checkpoint(required=False)
        try:
            close()
            record["status"] = "pass"
        except (Exception, KeyboardInterrupt) as exc:
            record.update(status="fail", error=self.error("cleanup:" + name, exc))
        self.checkpoint(required=False)

    def should_stop(self):
        return (self.result["blocked"] or self.interrupted or self.archive_failed
                or any(c["status"] == "fail" for c in self.result["cleanup"]))

    def finish(self):
        result = self.result
        if self.archive_failed or not self.created:
            status, code, suffix = "failed", 4, "after_failure"
        elif self.interrupted:
            status, code, suffix = "interrupted", 130, "after_interruption"
        elif result["blocked"]:
            status, code, suffix = "blocked", 3, "after_refusal"
        elif self.unavailable:
            status, code, suffix = "unavailable", 2, "dependency_unavailable"
        elif result["errors"] or any(c["status"] != "pass"
                                    for c in result["checks"] + result["screenshots"]):
            status, code, suffix = "failed", 1, "after_failure"
        else:
            status, code, suffix = "passed", 0, ""
        for item in result["checks"] + result["screenshots"]:
            if item["status"] == "not_run":
                item["status"] = "not_run_" + suffix
            elif item["status"] == "running":
                item["status"] = "not_completed"
        result.update(status=status, phase="complete", exit_code=code, finished_at=_now())
        if self.created and not self.checkpoint(required=False):
            result.update(status="failed", exit_code=4)
            # A prior replace may have succeeded before fsync failed. Try once to
            # leave the conservative final state; stdout remains the fallback.
            self.checkpoint(required=False)
        return result, result["exit_code"]


def _run_page(run, browser, record, action, options):
    context = None
    record.update(status="running", stage="context_create", executed=False)
    run.checkpoint()
    try:
        context = browser.new_context(**options)
        record["stage"] = "context_setup"
        context.route("**/*", lambda route:
                      route.continue_() if route.request.url.startswith(("file:", "data:"))
                      else route.abort())
        record["stage"] = "page_create"
        page = context.new_page()
        page.set_default_timeout(2500)
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        record["stage"] = "action"
        run.checkpoint()
        record["executed"] = True
        action(page)
        if page_errors:
            raise AssertionError("Page errors: " + "; ".join(page_errors)[:1000])
        record.update(status="pass", stage="complete")
    except SummaryWriteError:
        raise
    except (Exception, KeyboardInterrupt) as exc:
        error = run.error(record["name"] + ":" + record["stage"], exc)
        record.update(status="blocked" if _policy_refusal(exc) else "fail", error=error)
    finally:
        if context is not None:
            run.close_owned("context:" + record["name"], context.close)
        run.checkpoint()


def _site_cases(page_url, lab_url, offline, expect):
    def tabs(page):
        page.goto(page_url)
        for name in ["terminal", "desktop", "browser", "omp", "windows", "agent", "linux"]:
            tab = page.locator("#tab-" + name)
            tab.click()
            expect(tab).to_have_attribute("aria-selected", "true")
            expect(page.locator("#panel-" + name)).to_be_visible()
        page.locator("#tab-terminal").click()
        page.locator("#tab-terminal").press("ArrowRight")
        expect(page.locator("#tab-desktop")).to_be_focused()
        page.locator("#tab-desktop").press("End")
        expect(page.locator("#tab-omp")).to_be_focused()
        page.locator("#tab-omp").press("Home")
        expect(page.locator("#tab-terminal")).to_be_focused()

    def theme(page):
        page.goto(page_url)
        before = page.locator("html").get_attribute("data-theme")
        page.locator("#theme-toggle").click()
        after = page.locator("html").get_attribute("data-theme")
        assert before != after
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", after)

    def filters(page):
        page.goto(page_url)
        for kind in ["source", "contract", "blocked", "all"]:
            control = page.locator('[data-filter="' + kind + '"]')
            control.click()
            expect(control).to_have_attribute("aria-pressed", "true")
            for card in page.locator(".evidence-card").all():
                assert card.is_visible() == (kind == "all" or card.get_attribute("data-kind") == kind)
        page.locator("#show-browser").click()
        expect(page.locator("#panel-browser")).to_be_visible()

    def copy_branch(page, fail):
        body = ("return Promise.reject(new Error('test'))" if fail
                else "window.__copied=v;return Promise.resolve()")
        page.add_init_script("Object.defineProperty(navigator,'clipboard',"
                             "{value:{writeText:(v)=>{" + body + "}}})")
        page.goto(page_url)
        control = page.locator('[data-copy="code-windows"]')
        control.click()
        expect(control).to_have_text("已选中" if fail else "已复制")
        copied = page.evaluate("String(window.getSelection())" if fail else "window.__copied")
        assert copied == page.locator("#code-windows").inner_text()

    def links(page):
        page.goto(page_url)
        ids = page.locator("[id]").evaluate_all("(els)=>els.map(e=>e.id)")
        assert len(ids) == len(set(ids))
        for link in page.locator("a[href]").all():
            href = link.get_attribute("href")
            if href.startswith("#") and len(href) > 1:
                assert page.locator("[id=" + json.dumps(href[1:]) + "]").count() == 1, href
            if href.startswith("./"):
                assert (ROOT / "site" / href[2:]).is_file(), href

    def responsive(page):
        page.goto(page_url)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "viewport overflow"
        expect(page.locator("#validation-title")).to_be_visible()

    def nojs(page):
        page.goto(page_url)
        expect(page.locator("#panel-omp")).to_be_visible()
        expect(page.locator("#panel-linux")).to_be_visible()

    def lab(page):
        page.goto(lab_url)
        get = lambda: json.loads(page.locator("#witness").inner_text())
        first = get()
        assert first["counter"] == 0
        page.locator("#request-id").fill("test-id")
        page.locator("#request-token").fill("test-token")
        page.locator("#increment").click()
        assert get()["counter"] == 1 and get()["last_completed"]["token"] == "test-token"
        page.locator("#echo").click()
        assert get()["counter"] == 1
        expect(page.locator("#activity-log")).to_contain_text("NO business effect")
        page.locator("#new-request").click()
        request = page.locator("#request-id").input_value()
        assert request != "test-id"
        page.locator("#delayed").click()
        assert get()["counter"] == 1 and get()["pending_request"]["request_id"] == request
        expect(page.locator("#counter")).to_have_text("2", timeout=3500)
        assert get()["last_completed"]["request_id"] == request
        page.locator("#delayed").click()
        page.locator("#reset").click()
        assert get()["document_epoch"] != first["document_epoch"]
        page.wait_for_timeout(1350)
        assert get()["counter"] == 0 and get()["pending_request"] is None
        old = get()["fixture_nonce"]
        page.locator("#reload").click()
        expect(page.locator("#counter")).to_have_text("0")
        assert get()["fixture_nonce"] != old
        page.locator("#request-id").fill("")
        page.locator("#increment").click()
        expect(page.locator("#status")).to_contain_text("Enter both")
        assert get()["counter"] == 0

    def offline_links(page):
        page.goto(offline.as_uri())
        link = page.locator('a[href^="#reference-"]').first
        href = link.get_attribute("href")
        link.click()
        expect(page.locator(href + " details")).to_have_attribute("open", "")

    cases = [
        SiteCase("all tabs + keyboard", tabs),
        SiteCase("theme persistence", theme),
        SiteCase("evidence filter and jump", filters),
        SiteCase("copy success (mock clipboard)", lambda page: copy_branch(page, False)),
        SiteCase("copy failure fallback (mock clipboard)", lambda page: copy_branch(page, True)),
        SiteCase("internal links and unique IDs", links),
        SiteCase("JS disabled", nojs, {"java_script_enabled": False}),
    ]
    cases += [SiteCase("responsive " + str(width), responsive,
                      {"viewport": {"width": width, "height": 900}})
              for width in [320, 375, 768, 1280]]
    cases += [
        SiteCase("lab controls and independent DOM readback", lab),
        SiteCase("offline reference disclosure", offline_links),
    ]
    return cases


def run_smoke(output, chromium=None):
    run = _Run(Path(output))
    playwright = browser = None
    phase = "output"
    try:
        run.output = run.output.resolve()
        run.output.mkdir(parents=True, exist_ok=False)
        run.created = True
        # Archive before optional dependencies, page preparation, or browser launch.
        run.checkpoint()
        page_url = (ROOT / "site/index.html").as_uri()
        lab_url = (ROOT / "site/lab.html").as_uri()
        offline = run.output / "offline.html"
        expect = None
        cases = _site_cases(page_url, lab_url, offline, lambda *args, **kw: expect(*args, **kw))
        run.result["checks"] = [{"name": case.name, "status": "not_run", "executed": False}
                                for case in cases]
        run.result["screenshots"] = [
            {"name": "validation-" + str(width), "width": width,
             "path": "validation-" + str(width) + ".png", "status": "not_run", "executed": False}
            for width in [375, 1280]
        ]
        phase = run.result["phase"] = "prepare_pages"
        run.checkpoint()
        offline.write_bytes(standalone_page())
        phase = run.result["phase"] = "load_dependency"
        run.checkpoint()
        try:
            factory, expect = _load_playwright()
        except ImportError:
            run.unavailable = True
            raise
        phase = run.result["phase"] = "start_runtime"
        run.checkpoint()
        playwright = factory().start()
        phase = run.result["phase"] = "launch_browser"
        run.checkpoint()
        browser = playwright.chromium.launch(executable_path=chromium, headless=True, timeout=15000)
        run.result["browser"] = browser.version
        phase = run.result["phase"] = "tests"
        run.checkpoint()
        for case, record in zip(cases, run.result["checks"]):
            _run_page(run, browser, record, case.run, case.options)
            if run.should_stop():
                break
        if not run.should_stop():
            phase = run.result["phase"] = "screenshots"
            run.checkpoint()
            for record in run.result["screenshots"]:
                def capture(page, record=record):
                    page.goto(page_url + "#validation")
                    page.screenshot(path=str(run.output / record["path"]))
                _run_page(run, browser, record, capture,
                          {"viewport": {"width": record["width"], "height": 900}})
                if run.should_stop():
                    break
    except (Exception, KeyboardInterrupt) as exc:
        # Individual test failures are recorded in _run_page and may allow the
        # next independent test. Initialization/reporting failures end the run.
        if not isinstance(exc, SummaryWriteError):
            run.error(phase, exc)
    finally:
        if run.created:
            run.result["phase"] = "cleanup"
            run.checkpoint(required=False)
            if browser is not None:
                run.close_owned("browser", browser.close)
            if playwright is not None:
                run.close_owned("playwright", playwright.stop)
    return run.finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new evidence directory")
    parser.add_argument("--chromium", default=None, help="Optional Chromium executable path")
    args = parser.parse_args(argv)
    result, code = run_smoke(args.output, args.chromium)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

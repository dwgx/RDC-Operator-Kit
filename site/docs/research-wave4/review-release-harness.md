# Independent release and site-harness review

Review date: 2026-11-26 UTC. Repository: `<project>`.

## Conclusion

**Final reviewed state: no remaining confirmed P1/P2 finding in this scope.** This reviewer found two P2 defects: a pre-existing standalone-preview privacy path left outside the first exclusion repair, and a new Windows GUI cleanup interruption gap. Both were corrected by their owners and independently reverified with this reviewer's original counterexamples. The owner subsequently reported a real Windows integration race between inner window closure and outer process cleanup; its r2 correction was also independently reviewed and exercised against eight local synthetic scenarios. The revised site smoke harness had no confirmed new P1/P2 defect.

The recursive exclusion removes the named private files/directories from `source_files()`, including nested and mixed-case spellings. The final preview implementation uses the same approved source snapshot and rejects private/noncanonical references before opening private bytes. The site smoke harness preserves initialization, screenshot, refusal, interruption, and cleanup failures in its report and exit status in the exercised local stub cases. The Windows runner's corrected cleanup preserves an interruption, collects the held child, marks verification false, and stops later cases.

When the preview gap was reproduced, the real `site/index.html` had five document references and none used excluded private names. The historical finding does **not** establish that the candidate ever contained private bytes.

This is a read-only code review plus local synthetic verification. No Playwright import, browser launch, live UI, remote device action, new transport, public push, publication, or deployment was performed. The historical administrator refusal of the a3 `file://` run was not retried.

## Scope and fixed point

- Fixed point verified: `baseline-0.1.0a3` = `4930cd026f29ac61da88992712f002fc4b6943a4`.
- Compared the working tree with `git diff baseline-0.1.0a3 -- scripts/build_release.py scripts/smoke_site.py`. There are no commits between the baseline and HEAD; the reviewed implementation is working-tree content.
- Explicitly read untracked `tests/test_site_harness.py` and `tests/test_release_privacy.py`.
- Standards: `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.zh-CN.md`, `docs/RELEASE.zh-CN.md`, `.gitignore`, and `site/README.md`. No `CODING_STANDARDS.md` or `CONTRIBUTING.md` was present.
- Spec: `docs/WINDOWS-CONTROL.zh-CN.md`, especially section 5, plus the requested release privacy and failure-reporting repair.
- `scripts/smoke_windows.py` and its tests were deliberately not read while another agent was writing them. After the owner reported that implementation complete, they were independently reviewed; the addendum below records that second scope and its separate finding/fix verification.

Final reverified source SHA-256 (historical finding locations below refer to the pre-fix version where stated):

| File | SHA-256 |
|---|---|
| `scripts/build_release.py` | `3ad3d5e4be6f3c7aa5db70a7a7898036ac1d7c5ce153f8f5f146df83cfefbcff` |
| `scripts/smoke_site.py` | `5099d3405dd9df82ac4bda499d6692f7d41769fa93d74e44dc033781bb1f55f6` |
| `scripts/smoke_windows.py` | `73fa5f555e17ba51f6971f51d7978a80480be78eab3b13e200a705b7dd698f92` |
| `tests/test_release_privacy.py` | `c7d7557afd635af94bbc360143649e547aee6e37cd743726350d597b03b68619` |
| `tests/test_site_harness.py` | `ffb3dfc5e6906d4868da830443f3b2c289fe8f35b0b320b0849871c2cf8e7082` |
| `tests/test_windows_smoke_runner.py` | `97b6d5f4dc8e3737f7ede132ffde1840f377506b2576d3e814120256ee97e0f5` |

## Standards

### P2 residual, now fixed — private document bytes could enter the standalone release preview

Pre-fix location: `scripts/build_release.py:88`, `scripts/build_release.py:94`, and the preview output assignment at `scripts/build_release.py:137`.

`AGENTS.md`, “Local scope and publication”, requires `config.local.json`, runtime evidence and other private material to stay out of release bundles. `docs/RELEASE.zh-CN.md`, “本地候选”, applies this boundary to the release package. The new filter at `scripts/build_release.py:51` applies only to `source_files()`. `standalone_page()` separately follows every `href="./docs/..."` from the page and reads its bytes without applying the private-name/directory exclusion.

**Concrete reproduction:** in an isolated synthetic root, add `site/docs/config.local.json` containing a synthetic token marker and reference it from `site/index.html` as `./docs/config.local.json`. `build()` succeeds. The source manifest and ZIP omit the private file, but `RDC-Operator-Kit-preview.html` includes its marker. A document under an excluded `evidence/` subtree can use the same route.

**Impact:** an accidentally retained private-document link makes a release artifact contain the very bytes the source filter promises to exclude. Current source has no such link, and the vulnerable preview implementation predates this diff. Treat this as a residual repair gap, not evidence of an actual disclosure.

**Correction and verification:** the owner changed both `build()` and independent `standalone_page()` calls to use an approved source-bytes snapshot. Reference validation rejects private components, noncanonical paths, and files outside that snapshot. Actual build/preview-level regressions were added. This reviewer reran the original private-file counterexample: it now fails with `Private source reference refused`, no private file is opened, and no artifact is emitted. A separate public-reference fixture successfully built; unpacked ZIP/TAR and preview contained no synthetic private marker and retained the public document. **Fixed and independently reverified.**

No separate hard standards violation or actionable Fowler smell was confirmed in the revised lifecycle code. Cleanup stays attached to returned owned handles, and UI success is kept separate from cleanup failure.

## Spec

The Windows guide states: “无依赖、启动失败和环境策略拒绝都保存 summary，不算功能通过.” The reviewed harness meets that requirement in the tested conditions where the evidence directory is writable. It also retains final screenshot failures, stops new work after a recognized refusal or cleanup failure, and returns a nonzero exit code for incomplete runs. When the evidence store itself is unavailable, exit 4 and the returned/stdout result explicitly report failure instead of claiming an archived report.

The source-bundle portion of the nested private-file repair is complete for the documented private names: exact and mixed-case nested files are skipped before any `read_bytes`, and private directories are pruned before traversal. The broader release-artifact privacy promise initially remained partial because of the independent preview path described in the Standards finding. The final snapshot-based correction closes that same residual P2; it is not a second independent defect.

No new missing/incorrect site lifecycle requirement or scope expansion was confirmed. The tests prove Python control flow and persistence only. They do not prove the actual page's tab behavior, clipboard behavior, rendering, native browser launch, or the separately authorized official Edge interaction.

## Verification performed

Environment: Linux 6.18.57 x86_64 with glibc 2.41; CPython 3.12.14. Every fixture used its own temporary directory.

Executed commands:

```bash
python -m unittest discover -s tests -p 'test_site_harness.py' -v
python -m unittest discover -s tests -p 'test_release_privacy.py' -v
python -m unittest discover -s tests -p 'test_wave3_review.py' -v
```

Initial results: 17/17 site lifecycle tests passed; 2/2 private-release enumeration tests passed; 5/5 existing wave3 JSON/traversal tests passed. After the preview correction, this reviewer reran all three commands: 17/17 site, 6/6 release privacy and 5/5 wave3 passed. No skipped tests in these runs. The full unrelated core suite was not rerun by this reviewer.

An independently written local stub, rather than the new test module's fake runtime, exercised another 25 scenarios:

| Scenarios | Observed result |
|---|---|
| Factory, runtime start, browser launch, browser version access | Failure code 1, final failure summary; all handles which had been returned were closed |
| Context creation, route registration, page creation, timeout setup, event registration | Failed case was not reported as executed; owned contexts were closed when available; independent cases could continue |
| Action exception and emitted uncaught page error | Failed case retained, later independent case allowed, final code 1 |
| Final screenshot failure | Passed action cases retained; screenshot failure recorded; contexts, browser and runtime cleanup attempted |
| Context, browser and runtime close errors | Final code 1; context cleanup failure stopped later work; outer cleanup still attempted |
| Refusal at runtime start, browser launch/version, context creation, navigation, screenshot and context close | Final code 3; later cases/captures did not start after the recognized refusal |
| Persistent failure of the first summary write | Final code 4; no runtime/browser calls; no false claim that a summary exists |
| Final summary error after a successful replace, once or repeatedly | Final code 4; conservative final summary retried; owned handles closed; saved and returned final result agreed |

For writable evidence storage, the independent probe checked that the archived JSON equalled the returned result. For a deliberately unwritable first checkpoint, it checked that no summary was claimed and no browser work began. These are lifecycle checks, not browser passes.

## Quality of the new tests

The new lifecycle tests check consequential behavior rather than merely the implementation's branch shape: no work after refusal, no pass for an unexecuted case, cleanup of partial initialization, cleanup continuation after a close error, nonzero screenshot failure, preserved existing output, and agreement of saved/stdout status and exit code. They also check interrupted and unavailable outcomes. The independent probe covered additional `version`, timeout setup, `pageerror`, and final replacement/fsync-style failure boundaries without finding a new defect.

The initial release tests were useful: guards failed if private bytes were read or excluded directories were listed, and allowed JSON research/sample content had to remain present. Their original limitation was the call boundary: both stopped at `source_files()`, while `build()` also emitted a preview through a different reader. The correction added build-level private-reference rejection with `Path.open` guards, noncanonical-reference rejection, actual archive extraction/byte checks, and direct standalone-preview coverage. These cover the important missing behavior demonstrated by the residual P2.

## Historical minimal reproduction of the preview gap

This is the original pre-fix counterexample, run from the repository root. All data is synthetic and temporary; no real config is read. On the final reviewed implementation, `build()` raises `ValueError` at the private reference instead; the two post-build assertions are intentionally no longer reachable. The independent recheck additionally guarded the private file's `Path.open` and verified an empty artifact directory.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts import build_release

with TemporaryDirectory() as folder:
    root = Path(folder)
    files = {
        'rdc_operator/__init__.py': '__version__ = "0.0.0-review"',
        'site/index.html': (
            '<html><head><link rel="stylesheet" href="./styles.css">'
            '<script src="./app.js" defer></script></head><body><main>'
            '<a href="./docs/config.local.json">Config</a>'
            '</main></body></html>'
        ),
        'site/styles.css': '',
        'site/app.js': '',
        'site/icon.svg': '<svg/>',
        'site/docs/config.local.json': '{"token":"SYNTHETIC_PRIVATE_MARKER"}',
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding='utf-8')
    with patch.object(build_release, 'ROOT', root):
        build_release.build(root / 'dist')
    manifest = json.loads((root / 'dist/SOURCE-MANIFEST.json').read_text())
    preview = (root / 'dist/RDC-Operator-Kit-preview.html').read_text()
    assert not any(item['path'].endswith('/config.local.json')
                   for item in manifest['files'])
    assert 'SYNTHETIC_PRIVATE_MARKER' in preview
```

Release/site axis totals after recheck: Standards — 1 historical residual P2, fixed; 0 remaining. Spec — 0 new lifecycle findings; the same release privacy gap is fixed. No publication decision is made by this review.

## Addendum: Windows runner independent review

The owner explicitly released `scripts/smoke_windows.py` and `tests/test_windows_smoke_runner.py` for review after their writer finished. I then read both files, their called smoke-script entry points, the two WinForms fixtures, and `_window_identity()` in `rdc_operator/adapters.py`.

### Standards: P2 found and independently verified fixed

The initial `cleanup_fixture()` caught `KitError`, `OSError` and `subprocess.TimeoutExpired` around exact-HWND closure and `process.wait()`, but did not catch `KeyboardInterrupt`. An interrupt during normal-close waiting therefore unwound `gui()`'s `finally` before fallback cleanup and before assigning its cleanup receipt. `run()` correctly marked the case interrupted, but that did not collect the still-owned child.

The independent reproduction exercised the real `runner.run()` → `gui()` → `cleanup_fixture()` path using an entirely synthetic Popen and patched native queries. Before the correction, `process.wait()` raising `KeyboardInterrupt` produced:

```json
{
  "exit_code": 1,
  "case_status": "interrupted",
  "child_still_alive": true,
  "kill_calls": 0,
  "fixture_has_cleanup_report": false
}
```

This violated the scoped process-cleanup and retained-evidence requirements in `AGENTS.md` and the Windows guide's promise to record cleanup separately. The original interruption unit test only threw from a plain case body, so it did not cover interruption inside cleanup.

The owner corrected `cleanup_fixture()` and `terminate_direct()` to retain the interruption, continue cleanup against the held child object, and keep the verification false. The added regression exercises the actual `run()` → `gui()` cleanup route. I reran my own unchanged fault trigger independently; it now observed one kill of the same held child, exited=true, `interrupted=true`, `direct_child_only=true`, `verified=false`, a failed case and exit 1, a retained cleanup receipt, and no later case execution. My fake also interrupted the post-kill wait, so preservation did not depend on that second wait returning normally.

**Status: fixed and independently reverified.** No other actionable standards finding was confirmed in the runner scope.

### Spec: result and limits

The runner uses the explicit PowerShell executable as a `shell=False` argv, a new fixture directory and random witness path, and verifies fresh ready state against both the held Popen PID and a stable kernel window identity before passing the fixture onward. It rejects a witness whose PID differs from the launcher instead of adopting that child. Normal cleanup rechecks the entire saved window identity before `WM_CLOSE`; forced cleanup acts only on the held Popen object and records descendant uncertainty.

The overall deadline is applied to child command polling and fixture readiness, while cleanup uses the remaining total budget. A failed/unknown command stops later work, and its output logs and per-command row remain referenced. Core unittest counts retain skip/failure/error counts. Missing optional MCP is skipped and makes aggregate coverage incomplete. Nonzero subprocess exit cannot be repaired into success by a passing-looking child report. GUI cleanup failure prevents a pass.

A documentation integration note was sent to the owner: the guide's initial example used a base `--python` without showing `--terminal-python`, although the normal installer keeps SmartCLI in a separate `.venv`. The runner supports the separate interpreter correctly; the sample needs that parameter when the base interpreter lacks `smartcli-toolkit`. This was not treated as a runtime safety blocker.

No additional incorrect or missing requirement was confirmed. These findings do not establish actual Windows GUI execution or interpreter/package behavior on the remote machine; that acceptance remains the owner's separate work.

### Windows runner verification

```bash
python -m unittest discover -s tests -p 'test_windows_smoke_runner.py' -v
```

Initial result: 10/10 passed, despite the independently reproduced cleanup gap. After the correction: 11/11 passed, including the new cleanup-interruption regression. Both runs were local on Linux; one existing test owns and terminates an ordinary stdlib child process, and native/UI calls are mocked.

Additional independent local checks:

- A nonexistent executable produced a failed per-command receipt; a later successful child could not hide the earlier failure.
- A real local Python child received argv containing spaces, quotes, `$()`, Chinese/Japanese text and a Windows-style path verbatim. The intended `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` environment reached it. This is Linux subprocess evidence, not a Windows quoting test.
- The actual CLI entry point on Linux returned exit 2, marked all nine planned cases `not_run` with `unsupported_platform`, and created no child-command log directory. No Windows or browser action was attempted.

Windows addendum totals: Standards — 1 P2 found, fixed and independently verified; 0 remaining. Spec — the same cleanup requirement gap is fixed; no remaining confirmed defect. Actual Windows acceptance is outside this review.

## Final scope summary

Latest targeted results for the reviewed files: site lifecycle 17/17, release privacy 6/6, existing wave3 5/5, Windows runner 12/12, with no skips in those targeted runs. These 40 local test methods are not a browser or Windows GUI acceptance count. The reviewer's 25 separate lifecycle fault probes, the two original P2 counterexamples, and the eight r2 cleanup probes provide additional independent control-flow evidence.

Standards: two reviewer-identified P2 findings and one subsequent owner-reported integration race are fixed and independently reverified; zero remaining confirmed findings. Spec: the corresponding requirements gaps are closed; zero remaining confirmed findings. No publication, deployment, or live-browser approval is implied.

## r2 addendum: a closed window may precede its process exit

### Evidence provenance and pre-fix behavior

After the first review completed, the owner reported an actual Windows run in which eight of nine outer cases passed. The observation subprocess reportedly completed its 22 checks and its own window/witness cleanup with exit 0, but the outer runner immediately observed the PowerShell Popen as still alive. Its HWND was already destroyed, so `_window_identity()` raised `window_not_found`. The pre-r2 code waited only inside the successful `WM_CLOSE` branch and therefore fell directly into forced process termination, making the overall run fail.

That Windows execution summary was supplied by the owner. This reviewer did not reopen the remote report or perform RDC/Windows actions, and does not independently attest the numerical Windows results. The reviewed pre-r2 control flow is consistent with the reported race. Its source hash was `7c668506dad4bdb929c41c61d145f002171c01d095e75fcf637d213d9dee7a73`.

### Standards and spec review of the correction

The r2 correction separates the optional exact-HWND `WM_CLOSE` attempt from waiting for the original held process. A missing window is recorded as `window_already_closed`. The runner then gives the held Popen at most `min(2 seconds, remaining suite budget)` to exit before deciding force is necessary. It does not discover or adopt another PID and does not post a close message when the saved window identity no longer matches.

A pass still requires the original process to have exited with code 0, the witness to report `closed`, and no forced or interrupted cleanup. Timeout and interruption remain visible in the cleanup record; forced cleanup remains restricted to the held Popen. The patch therefore addresses the false failure without relaxing ownership or cleanup verification. No new standards or spec defect was confirmed.

### Independent r2 verification

The new `test_nested_smoke_closed_window_gets_grace_for_held_process_exit` regression and all prior runner tests passed: **12/12**, local Linux only.

An independently constructed stub exercised the actual `runner.run()` → `gui()` → real `child_report()` → `cleanup_fixture()` route. It wrote an inner summary and witness to isolated temporary paths, and patched all native/UI calls. Results:

| Scenario | Result |
|---|---|
| HWND already missing; held process naturally exits 0; witness closed | Case passed, `verified=true`, zero kills; inner report retained |
| HWND now belongs to a different identity; original process naturally exits 0 | No `WM_CLOSE` sent to the replacement; zero kills; original child exit/witness verified |
| Missing HWND; original child wait times out | Only the held child killed once, `verified=false`, failed exit status and halt reason; inner report retained |
| Missing HWND; wait raises `KeyboardInterrupt` | Interruption retained, only held child killed once, `verified=false`, failed exit status and halt reason |
| Natural exit 0 without a closed witness | Failed, no fabricated cleanup verification |
| Closed witness but natural process exit 7 | Failed, no fabricated cleanup verification |
| Only 0.125 seconds remain | Wait timeout exactly 0.125 seconds; no extra two-second grace granted |
| Deadline already expired | No wait; conservative forced cleanup of held child, failed verification |

All eight independent scenarios passed their expected assertions; every scenario retained the inner child-summary reference. The new code is thus independently reverified for the reported integration race and its relevant failure boundaries. This remains synthetic control-flow evidence; the owner's fresh Windows r2 run is separate acceptance evidence.

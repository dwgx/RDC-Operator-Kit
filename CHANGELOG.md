# 0.1.0a5 — public source, Release pending, 2026-11-26

### Added

- Modern light/dark layouts for the static project guide and Browser Evidence Lab,
  with local evidence search, combined category filters, empty-state recovery and
  clearer copy feedback. Lab business/witness JavaScript retains the a4 bytes.
- Discoverable, validated output schemas for all three read-only MCP tools, with
  JSON text and structured results kept together. Added operator_request_status
  for minimal saved-record summaries; it does not expose original arguments or
  infer live progress, cancellation, retry permission or business success.
- Current capability, architecture, installation and evidence documentation;
  see [Wave 05](docs/REVIEW-WAVE5.zh-CN.md) for the exact snapshot and scope.

### Fixed

- Reject linked Linux .venv/bin and Windows .venv/Scripts directories before
  interpreter invocation; retain normal interpreter links/redirectors. The
  Windows junction regression ran once and passed without invoking pip.
- Preserve partial liveness results through incremental atomic checkpoints;
  stop after launch, interruption or archive failures and report stale summaries.
- Keep IME composition Escape events from clearing the evidence query. The
  independent source-event regression passed three targeted branches.
- Harden MCP smoke verdicts with JSON-type-sensitive equality and complete
  successful text/structured-channel comparisons. Independent mutations now
  produce the expected two control passes and ten rejected bad responses.
- Handle Windows 8.3 state-directory names in MCP by expanding the expected
  name before opening, while retaining the exact opened-HANDLE path comparison
  and reparse rejection. Add real short-name and transient-junction regressions.
- Align screenshot fixtures and child-report path expectations with existing
  canonical-path contracts; preserve the production identity and negative checks.
- Pin GitHub Actions to the verified commit SHAs recorded in the workflows.

### Validation and publication status

- An initial a5 Linux core run passed 177/177 with no skips. One owned Windows
  source run passed all nine top-level cases; its core had 177 run, 166 passed and
  11 skipped. These results precede the final MCP smoke hardening and remain
  labelled as that snapshot, not an installed-package or universal-control result.
- Initial Windows SDK 2.3.0 modern/legacy sessions each passed 30 checks. The
  strengthened smoke subsequently passed 36 checks in each real Windows session.
  At the pre-push checkpoint, Linux core ran 182 tests (181 passed, one
  Windows-only skip); Windows core ran 181 (170 passed, 11 skipped), plus one
  separate junction test.
  These separate commands do not form a new nine-case integration run.
- The public [dwgx/RDC-Operator-Kit repository](https://github.com/dwgx/RDC-Operator-Kit)
  received its first `main` commit, `5952a45f03549de17cdc3d92ff6d7a1f91b3e0ad`.
  Its [first CI run](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079)
  failed both Windows core jobs: each ran 182 tests with 11 failures, 10 errors
  and seven skips. The other four jobs passed; the original failures remain recorded.
- The correction was pushed as `a880144d07d8599c6e5232a34bcef1e1cac54bc1`.
  [CI run 45780615916](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916)
  passed all six jobs. Windows Python 3.10/3.13 core each had 184 run, 177 passed
  and seven skipped; Ubuntu core each had 184 run, 179 passed and five skipped.
  Optional Pydantic model checks remain explicit skips in the core jobs.
  Both independent MCP jobs passed modern/legacy sessions with unchanged records;
  no detailed CI check count is claimed from the separate owned-Windows result.
- After the CI fixes, Linux core ran 184 tests (181 passed, three Windows-only
  skips) in 2.677 s; owned Windows core ran 184 (173 passed, 11 skipped) in
  7.673 s. The new short-name and junction regressions passed on Windows.
  Real Windows MCP again passed 72/72 checks, still executing the source tree.
- Preserve the pre-CI installation checkpoint: both owned Windows environments
  had upgraded from a4 to a5, with 11 modules matching that earlier wheel.
- Reinstalled the final CI-corrected wheel into both environments as a5 to a5,
  updating only the Kit. Isolated imports verified all 11 installed modules
  against corrected source; other distribution versions and config hashes stayed
  unchanged, and backups were retained. The final wheel is 44,645 bytes; its
  SHA-256 is recorded in [Wave 05](docs/REVIEW-WAVE5.zh-CN.md).
- Both installed `rdc-kit.exe --version` entry points returned 0.1.0a5 with exit 0.
  One real modern MCP session launched with `-I` from installed site-packages
  passed all 17 recorded assertions, retaining unknown outcomes and unchanged
  records. This is separate from source checks and CI; legacy and GUI were not rerun.
- Pages is configured to use GitHub Actions and its URL was read back from the
  API, but deployment remains unverified. The a5 tag/Release is still pending.
- Modern UI validation remains static/synthetic because browser access was
  denied. HMC environment probing was quota-blocked. Actual GLM/DeepSeek OMP
  reviews returned deadline/provider-balance failures with no final review.
- Preserve all historical a4 focus failures, browser refusals, generic close
  uncertainty and normal UAC confirmation requirements.

# 0.1.0a4 — Windows control candidate, 2026-11-26

- Added a read-only native Windows context probe for process tokens, sessions,
  desktop/input state and foreground identity. Unknown remains unknown; the
  probe neither elevates nor grants permission.
- Added explicit observation-bound desktop.focus, exact top-level-window checks,
  independent foreground verification and conservative replay semantics.
- Added a finite nine-case Windows source acceptance runner with separate Python
  environments, durable partial reports, owned-child cleanup and overall failure
  propagation. Fixed interrupted cleanup and the window-destroyed/process-exiting
  race discovered by review and the first live Windows run.
- Hardened the optional site smoke lifecycle and release privacy across source
  archives and standalone HTML; preview references use the same filtered snapshot.
- Updated Windows guidance, native/bundled Skill, project page, upstream research
  and independent reviews. See docs/REVIEW-WAVE4.zh-CN.md for exact evidence.
- Live native mouse click succeeded in the first owned fixture. A later run caught
  a changed foreground after focus and withheld the click; its suite remains failed.
  Official Edge localhost semantic/pointer interactions succeeded separately.
- A bounded GLM review returned BLOCKED / Deadline exceeded with no final review.
  Normal UAC confirmation and previously denied browser targets remain outside
  automatic control. No public repository/Release/Pages deployment is implied.

# 0.1.0a3 — review candidate, 2026-11-26

Strict JSON ingress, typed schema, pruned release traversal and static QA matrix; see docs/REVIEW-WAVE3.zh-CN.md. Not installed on Windows or publicly released.

# Changelog

## 0.1.0a2 — 2026-11-26 — Unreleased alpha candidate

### Added

- Immutable screenshot frame metadata, hashes and upstream single-window
  provenance validation; optional observation binding before capture.
- Finite native-window sampling with per-frame JSON output and a durable manifest.
- Owned Windows observation fixture and live smoke covering one effect, replay,
  changing image samples, composite rejection and normal window cleanup.
- Synthetic terminal liveness diagnostics for silence, input requests, output
  flood, deadlines and independent completion evidence on Windows and Linux.
- Offline browser-evidence validation, negative examples and an account-free lab page.
- Current browser/Relay, Windows observation, terminal and MCP/Skill research with
  fixed source references and independently reviewed implementation slices.
- Optional official-SDK stdio MCP entry for read-only capability/receipt access.

### Fixed and retained limits

- Reject composite screenshot reports rather than presenting them as one window.
- Bind the sampler's original observation inside the capture adapter before effects.
- Launch Windows stdlib liveness fixtures with the real base interpreter, retaining
  strict PID equality instead of adopting a venv redirector's child PID.
- Preserve unknown rendering time, header-only PNG validation, capture focus side
  effects, generic terminal close uncertainty and historical failed GUI readbacks.
- Real model calls, provider failures and browser fixture results are recorded
  separately in the second-wave report; no public publication is implied.

## 0.1.0a1 — 2026-11-26 — Unreleased alpha candidate

### Added

- Python standard-library CLI with per-state OS locking, durable intents and
  receipts, request/configuration conflict detection, and conservative recovery.
- SmartCLI 0.3.5 adapters for owned terminal start, snapshot, wait, text/key input
  and close requests.
- Microsoft winapp 0.8.0 adapters for observed Windows targets, scoped UIA element
  binding, explicit invoke, value setting, selector clicks and window screenshots.
- Existing origin-dispatch dry-run integration; no replacement model dispatcher.
- Windows and Linux installers using a project-local environment; verified WinApp
  archives and installed-file manifests on Windows.
- Synthetic terminal and desktop fixtures, independent engine/installer regression
  tests, portable routing Skill, Chinese documentation and a static project site.
- Prepared Windows/Linux core CI and manually triggered GitHub Pages workflow.

### Reliability decisions

- Ambiguous interruptions remain `outcome_unknown`; duplicate requests never
  automatically repeat an effect. Full configuration participates in identity.
- Interrupted direct child commands are cleaned up before releasing the state lock.
- Malformed or mismatched action acknowledgements do not become success.
- Installer ownership does not authorize linked environments or mismatched cached
  executables. User configuration is preserved on repeat installation.

### Known limits

- Windows GUI coverage is limited to the behavior actually recorded in
  [VERIFICATION](docs/VERIFICATION.zh-CN.md); it is not arbitrary-application proof.
- SmartCLI's CLI omits its full close receipt, so generic close remains uncertain.
- The Windows PyWinPTY route cannot resolve a quoted first executable token; the
  kit refuses this known form before daemon launch. Owned smoke uses relative paths.
- Desktop smoke02 passed, while smoke03/04 observed mismatched text after an ack.
  Later isolated upstream writes passed; the source of extra changes is unproven.
- Linux does not implement Windows UIA. Browser control requires the official host
  connector and follows its policy. OMP integration currently previews only.
- Dependencies are not fully hermetically locked. No public repository, GitHub
  Release, CI run or Pages deployment is implied by this prepared candidate.

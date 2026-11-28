# 0.1.0a6 — released alpha, 2026-11-28

### Added

- Durable task checkpoints with compare-and-swap revisions, exact original-state
  marker/path binding, frozen scope/config fingerprints and append-only request IDs.
- Read-only resumption plans after user-managed reconnection, including same-ID
  reconnect generations, typed-handle provenance, retained stop reasons and
  before/after checkpoint sampling. Plans never authorize execution or replay;
  this is not a global interceptor for every call or control tool.
- A real owned child-exit fixture for an effect before its receipt, plus an
  installed-package mode that verifies actual isolated site-packages imports.
- Task-first Skill routing, a private agent handoff guide and version-scoped
  recovery research. Browser-only and saved-record tasks need no RDC discovery.

### Fixed

- Treat a JSON null checkpoint as corruption, not absence; normalize NUL state
  paths into structured errors without overwriting existing records.
- Preserve uncertain commit semantics when atomic replacement succeeds but
  checkpoint readback fails. Keep the committed revision and reject stale writers.
- Guard smoke assessments against Python-level side-effect attempts; verify full
  request/handle evidence and use held-worker cleanup with bounded file logging.
  Independent mutations now reject swallowed effects and empty evidence.
- Exclude private recovery checkpoints, markers, local contexts and handoff files
  before release traversal and standalone preview generation; retain public examples.
- Document and test the -B CLI boundary: normal Python imports may create bytecode
  even when the assessment function itself performs no writes.

### Verification and delivery status

- Final Linux Python 3.12.14 core: 225 run, 221 passed, four Windows-only skips.
  Windows 11 build 26300 / Python 3.14.7 core: 225 run, 212 passed, 13 skipped.
  Both exited zero. The earlier Linux 223/219/4 result remains a separate checkpoint.
- Linux and Windows source recovery smoke each passed 17 checks. These use owned
  synthetic effects, not real RDC reauthentication, Browser or GUI operations.
- Three independent runtime regressions passed after their original failures;
  release privacy passed seven test methods after 26 failure entries including
  subtests. Fresh-copy -B CLI passed; removing -B created seven pyc files and the
  negative control failed as expected. Targeted counts are not added to core totals.
- Both owned Windows environments upgraded offline/no-deps from a5 to a6 with
  backups, 12 installed modules matching the wheel, and unchanged other dependency
  versions and config hashes. Both actual CLI entry points returned a6; isolated
  installed recovery smoke passed 17/17 in each, and in one fresh Linux environment.
- A separate real installed SDK 2.3.0 MCP session negotiated 2026-07-28 and passed
  17 assertions for three tools, strict text/structured equality, retained unknown
  outcome, unchanged records and normal worker exit. It is not the recovery suite.
- The installed wheel is 51,757 bytes; its SHA-256 is recorded in
  [Wave 06](docs/REVIEW-WAVE6.zh-CN.md). The Windows source tree separately
  verified all 156 public source files; its rollback copy remains available.
- Canonical Skill resources were saved and read back. Four native-agent scenario
  responses exercised the handoff guidance without performing live task actions.
- a6 was published at 18:07:02 JST from `edf4aa52e11d1f326cee93a538b8dfa7422a055f`.
  All six [CI jobs](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/46128657762)
  passed; all nine release assets were downloaded and hash-verified before publication.
  [Pages build/deploy](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/46129018315)
  succeeded for the same release source. These main-branch notes do not rewrite the tag.
  Previous Browser refusals, HMC quota block and OMP failures were not rerun or bypassed.
  Previous release evidence remains below and is not inherited by a6.

# 0.1.0a5 — released alpha, 2026-11-26

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
- Published [v0.1.0a5](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5)
  at 2026-11-26 08:31:53 UTC (17:31:53 JST), fixed to
  `27d367a9698c381d90986c8640d506b24d84ddd9`. All nine uploaded assets were
  downloaded again and matched their SHA-256 values.
- The [release-commit CI](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45782996129)
  passed all six jobs: each Windows core job had 184 run, 177 passed and seven
  skips; each Ubuntu core job had 184 run, 179 passed and five skips. Both
  independent MCP jobs passed the modern and legacy protocols.
- [Pages build/deploy](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45783289213)
  succeeded at the same release commit. The project site is
  [https://dwgx.github.io/RDC-Operator-Kit/](https://dwgx.github.io/RDC-Operator-Kit/).
  Deployment does not add live acceptance of the refreshed UI.
- Release archives remain fixed to that commit. Subsequent main changes only
  synchronize publication receipts in docs/pages; the tag and assets are unchanged.
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

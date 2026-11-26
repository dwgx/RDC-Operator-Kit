# Working on RDC Operator Kit

This is a Windows-first, local CLI companion for existing RDC, SmartCLI, winapp,
Browser, and origin-dispatch capabilities. Read README.md and
docs/ARCHITECTURE.zh-CN.md before changing behavior. Current release state and
executed evidence belong in docs/VERIFICATION.zh-CN.md and CHANGELOG.md.

## Preserve the contract

- Keep request identity bound to the full request and the actual configuration.
  Persist intent before effects. Return existing receipts for duplicate requests;
  never automatically execute an intent with an uncertain outcome again.
- Hold the state lock across preparation, execution and receipt commit. State
  coordinates cooperating Kit callers only; do not claim a global desktop lock.
- Keep operation acknowledgement, observed application state, and independent
  business-result verification separate.
- Use shell=False argv for adapter commands. SmartCLI's command string is an
  explicitly authorized program-execution surface, not a sandboxed language.
- Keep Windows targets bound to fresh observations, HWND/process identity and
  scoped element selection. Do not add blind coordinate fallback or suppress
  upstream ambiguity to make a test pass.
- Browser work uses the host's official Browser capability. A refusal must not
  cause fallback through desktop, CDP, PowerShell or a new remote-debugging route.
- OMP preview reuses an existing origin-dispatch wrapper. Do not create a second
  broker, queue, model router or credential store to solve a local adapter issue.

## Work and verify

Use isolated fixture directories and one writer per file when collaborating.
Read current source before acting on another agent's historical report. Do not
edit runtime receipts, screenshots or independent witnesses to manufacture a pass.

Run relevant tests, then the core suite when a cross-cutting change warrants it:

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic input and mocked adapters unless explicitly described as live
smoke tests. Windows GUI and terminal smoke scripts operate on their own fixtures;
they are not routine CI steps. Report the OS, source revision, actual command,
passes, failures, skips and limits. Do not relabel unavailable capabilities as tested.

Changes to request recovery, target binding, process cleanup or installer ownership
need a concrete failing example and a regression check. Avoid tests that merely
repeat the implementation's structure or count assertions as quality.

## Local scope and publication

Preserve existing user configuration and unrelated environments. Never stop RDC,
global SmartCLI sessions, user browsers or unrelated agents for cleanup. Only act
on processes and files whose ownership has been established for this task.

Keep config.local.json, .rdc-state/, .venv/, tools/, evidence/, device/account IDs,
credentials and raw private UI/terminal content out of commits and release bundles.
Use redacted summaries rather than raw execution traces in public documentation.

Preparing changes, tests and release material is separate from publishing. Public
repository creation, remote pushes, Releases and Pages deployment require explicit
authorization for that action. Do not claim CI or deployment ran from the mere
presence of a workflow file. See docs/RELEASE.zh-CN.md for the prepared process.

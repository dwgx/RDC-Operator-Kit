> **0.1.0a6 Windows-first alpha — 2026-11-28.** Durable task checkpoints and read-only resumption plans after user-managed reconnection. Preserve the original state, scope and uncertain effects. Read the [Agent guide](docs/AGENT-GUIDE.zh-CN.md) and [recovery specification](docs/RESUME-SPEC.zh-CN.md). The [Wave 06 report](docs/REVIEW-WAVE6.zh-CN.md) records recovery review, real failure injections and source/installed acceptance separately.

# RDC Operator Kit

**Let an authorized agent observe, operate, and verify real computer work.**

Windows-first companion tooling for Remote Desktop Commander (RDC), SmartCLI,
Microsoft winapp, the official ChatGPT Browser connector, and an existing OMP
dispatcher. Independent community project; not affiliated with these vendors.

**Status: 0.1.0a6 Windows-first alpha; validation and publication are recorded separately.**

[GitHub repository](https://github.com/dwgx/RDC-Operator-Kit) · [Releases](https://github.com/dwgx/RDC-Operator-Kit/releases) · [中文说明](docs/README.zh-CN.md)

The [Wave 06 report](docs/REVIEW-WAVE6.zh-CN.md) separates source tests, installed-package validation and publication receipts. Previous [Wave 05 evidence](docs/REVIEW-WAVE5.zh-CN.md) remains historical.

See [中文说明](docs/README.zh-CN.md), [capability map](docs/CAPABILITIES.zh-CN.md),
[research and sources](docs/RESEARCH.zh-CN.md), and [verification](docs/VERIFICATION.zh-CN.md).

The [second research and validation wave](docs/research-wave2/REPORT.zh-CN.md)
covers browser/MCP projects, OMP Relay, finite window samples, and terminal liveness.

## What it provides

- A Python CLI with durable request intents and receipts. Duplicate requests retrieve
  their original outcome. Ambiguous interruptions are never automatically replayed.
- Durable task checkpoints with revision checks, original-state identity, frozen
  scope/config fingerprints, typed handles and persistent stop reasons. The read-only
  `resume` command checks saved results and fresh caller-supplied route observations;
  it does not log in, authenticate a physical device, replay actions or authorize execution.
- Real terminal sessions through pinned SmartCLI: start, snapshot, wait, input, keys,
  and conservative close acknowledgement.
- Windows UIA through pinned winapp: inspect a specific window, select an observed
  element, invoke, set a value, explicitly focus the observed window, click, and
  capture a window screenshot. Focus is a separate mutation with kernel readback;
  clicks never force focus or silently retry an uncertain result.
- A read-only `windows-preflight` command reports token integrity, elevation,
  UIAccess, session, desktop and foreground context. Unknown observations remain
  unknown. This does not click UAC, request elevation, or change Windows policy.
- Screenshot provenance checks, immutable frame metadata, and a finite sampler
  that emits each captured frame receipt as it becomes available. Composite
  captures are rejected as single-window evidence; true rendering time is unknown.
- Windows/Linux synthetic liveness probes and an offline browser-evidence
  validator with an account-free test page. Neither is a universal task-success detector.
- An optional official-SDK MCP stdio server with three read-only tools and typed
  output schemas: describe configuration, read a saved receipt, or summarize a
  request's saved records without returning its arguments, command or paths.
  Saved-record status is not live progress or permission to retry. Use its own
  `.venv-mcp`; SmartCLI's MCP 1.x dependency cannot share the SDK 2.3.0 environment.
  See [MCP installation and protocol checks](docs/MCP.zh-CN.md).
- A modern static guide and Browser Evidence Lab with light/dark styling, local
  evidence search, category filters and explicit copy feedback. The a5 UI has
  static and synthetic-event checks; live browser acceptance remains blocked.
- A compact routing Skill: use RDC for files/processes, SmartCLI for TUI, winapp for
  native Windows UI, and the official Browser plugin for signed-in web UI.
- Preview integration with an existing origin-dispatch wrapper. It does not create a
  competing queue, daemon, model router, or store credentials.

## Install from this source directory

Python 3.10+ is required. The installers use a local `.venv`, preserve existing config,
and do not change your global PATH or start a public network listener.

Windows (PowerShell):

```powershell
.\scripts\install.ps1 -WithTerminal -WithDesktop
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json doctor
```

Linux (CLI and terminal layer; Windows UIA is unavailable):

```bash
bash scripts/install.sh --with-terminal
.venv/bin/python -m rdc_operator --config config.local.json doctor
```

The installers reject linked `.venv/bin` (Linux) and `.venv/Scripts` (Windows)
directories before executing their interpreter, while retaining normal
virtual-environment interpreter links and redirectors.
Local Linux fixture checks do not constitute validation on the separately
requested HMC device; that device's first environment probe was quota-blocked.

The desktop installer verifies the official winapp 0.8.0 archive SHA-256 before
extraction. SmartCLI is pinned to 0.3.5; its transitive dependencies are resolved by
pip, so this is not a fully hermetic dependency lock. Install and pair RDC through
its official setup instructions. Existing installations are reused; the kit does not
read RDC login tokens or replace its running agent.

## Make one request

Create an UTF-8 JSON request with a unique ID:

```json
{"request_id":"inspect-001","action":"desktop.observe","args":{"window":123456}}
```

Use an HWND obtained from a fresh `winapp ui list-windows --json`, never the example
number. The observation returns a short-lived ID and the actual selectors.

```powershell
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json --state .rdc-state call request.json
```

An authorized state-changing request requires `--apply`. This is an execution switch,
not a replacement for user authorization. Read [the workflow](docs/README.zh-CN.md)
before driving a terminal or desktop.

## Continue after a manual reconnect

Read the [Agent guide](docs/AGENT-GUIDE.zh-CN.md) before constructing the private
checkpoint and context JSON. Use the original absolute state path; both recovery
commands require an explicit `--state`. Preserve the frozen task brief and request
files alongside the private handoff: a scope hash cannot reconstruct their contents.

```text
python -B -m rdc_operator --config CONFIG --state ORIGINAL_STATE checkpoint recovery-checkpoint.local.json --expected-revision 0
python -B -m rdc_operator --config CONFIG --state ORIGINAL_STATE resume TASK_ID --context recovery-context.local.json
```

`-B` suppresses Python startup bytecode-cache writes. The read-only guarantee
for recovery assessment does not cover OS access timestamps, host logs or
caller-selected stdout redirection.

Revision 0 creates a checkpoint. Updates require its current revision and cannot
drop known requests or clear a quota, policy-refusal or cancellation stop. A plan
is always read-only: `review_required` is not permission to act, while `blocked`
preserves missing evidence or a stop. Even unchanged route IDs require fresh UI
observations after a human handoff. This is an agent workflow, not global
enforcement over other tools or calls made without the checkpoint.

## Boundaries that matter

- A Skill supplies procedures; it cannot grant tools, bypass Browser policy, or pair
  a computer on its own. ChatGPT availability depends on the current environment.
- `allowed_roots` restricts the kit's own path handling. It is not an OS sandbox for
  terminal children. Use an isolated machine/account when execution requires one.
- A shared state lock coordinates this kit's callers, not all human and software
  desktop activity. Observe again before acting after a delay or focus change.
- UI action acknowledgement is separate from the intended result. Check the
  resulting control state, file, or other independent witness.
- SmartCLI 0.3.5's CLI can hide its lower-level close result. The adapter preserves
  uncertainty rather than claiming every child has exited.
- Runtime receipts, screenshots, terminal content and local configuration are private
  by default and excluded from source bundles. Review before sharing evidence.

## Development and publication

```bash
python -m unittest discover -s tests -v
python scripts/build_release.py
```

Read Windows context without configuration or state files:

```powershell
python -m rdc_operator windows-preflight
python -m rdc_operator windows-preflight --window 123456
```

Replace the example HWND with a currently observed owned target. Exit 0 only
means the collected conditions did not reveal a conflict; it is not permission
or a guarantee of a successful action. Exit 1 includes unsupported, blocked and
unknown assessments. Use the Windows guide for the bounded smoke runner.

The first public `main` commit is [5952a45](https://github.com/dwgx/RDC-Operator-Kit/commit/5952a45f03549de17cdc3d92ff6d7a1f91b3e0ad).
Its [first CI run](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079)
had two failed Windows core jobs and four successful jobs. Those failures remain
recorded. After the path fixes, Linux source core ran 184 tests (181 passed,
three Windows-only skips); owned Windows source core ran 184 (173 passed,
11 skipped), and real SDK 2.3.0 MCP sessions passed 72 checks in total.

The correction was published as [a880144](https://github.com/dwgx/RDC-Operator-Kit/commit/a880144d07d8599c6e5232a34bcef1e1cac54bc1),
and [its CI run](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916)
passed all six jobs. Each Windows core job ran 184 tests with 177 passes and
seven skips; each Ubuntu core job had 179 passes and five skips. Core CI omits
optional Pydantic 2, so its two model checks are explicit skips. Both independent
MCP jobs passed modern and legacy sessions with unchanged records; their CI logs
do not provide a detailed check count, so the separate owned-Windows 72 is not
attributed to those jobs.

Installed-package acceptance is recorded separately from source smoke. It checks
the actual site-packages module bytes, the CLI entry points, a real stdio session,
and preservation of unrelated dependencies and configuration. See the
[versioned installation record](docs/REVIEW-WAVE5.zh-CN.md); a version string or
source-tree pass alone does not establish that the corrected package is installed.

Static GitHub Pages source lives in `site/`. CI and manual Pages workflows use
pinned action revisions under `.github/workflows`. Use the repository Releases
and deployment records to verify a fixed tag and site publication. The dated
[Wave 05 report](docs/REVIEW-WAVE5.zh-CN.md) preserves the publication checkpoints.
[Release instructions](docs/RELEASE.zh-CN.md) describe the publication process.

MIT for original kit code. Upstream components retain their own licenses; see
[UPSTREAMS](docs/UPSTREAMS.md). RDC's hosted service is not bundled or reimplemented.

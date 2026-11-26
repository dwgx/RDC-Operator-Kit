> **0.1.0a5 integration candidate — 2026-11-26.** This update adds typed, read-only MCP results and saved-request summaries, strengthens Linux installation and liveness reporting, and refreshes both static web pages. Read the [Wave 05 report](docs/REVIEW-WAVE5.zh-CN.md) for completed checks and pending gates. Earlier Windows evidence remains in the [Wave 04 report](docs/REVIEW-WAVE4.zh-CN.md).

# RDC Operator Kit

**Let an authorized agent observe, operate, and verify real computer work.**

Windows-first companion tooling for Remote Desktop Commander (RDC), SmartCLI,
Microsoft winapp, the official ChatGPT Browser connector, and an existing OMP
dispatcher. Independent community project; not affiliated with these vendors.

**Status: 0.1.0a5 Windows-first alpha with documented limitations.**

[GitHub repository](https://github.com/dwgx/RDC-Operator-Kit) · [Releases](https://github.com/dwgx/RDC-Operator-Kit/releases) · [中文说明](docs/README.zh-CN.md)

The [Wave 05 report](docs/REVIEW-WAVE5.zh-CN.md) separates source tests, installed-package validation and publication receipts.

See [中文说明](docs/README.zh-CN.md), [capability map](docs/CAPABILITIES.zh-CN.md),
[research and sources](docs/RESEARCH.zh-CN.md), and [verification](docs/VERIFICATION.zh-CN.md).

The [second research and validation wave](docs/research-wave2/REPORT.zh-CN.md)
covers browser/MCP projects, OMP Relay, finite window samples, and terminal liveness.

## What it provides

- A Python CLI with durable request intents and receipts. Duplicate requests retrieve
  their original outcome. Ambiguous interruptions are never automatically replayed.
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

The Linux installer rejects a linked `.venv/bin` directory before executing its
interpreter, while retaining normal virtual-environment interpreter symlinks.
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

Static GitHub Pages source lives in `site/`. CI and manual Pages workflows are
prepared under `.github/workflows`, with action revisions pinned to commit SHAs.
Workflow files are not execution evidence: actual CI, publication and deployment
results are tracked in the [Wave 05 report](docs/REVIEW-WAVE5.zh-CN.md).
[Release instructions](docs/RELEASE.zh-CN.md) describe the publication process.

MIT for original kit code. Upstream components retain their own licenses; see
[UPSTREAMS](docs/UPSTREAMS.md). RDC's hosted service is not bundled or reimplemented.

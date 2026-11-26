---
name: rdc-operator-kit
description: "Operate an authorized computer through RDC Operator Kit: route files and processes to RDC, persistent terminal UIs to SmartCLI, native Windows UI and finite image samples to winapp, and web UI to permitted browser capabilities. Use for computer-work setup, Windows input/focus diagnosis, terminal liveness diagnosis, controlled execution, read-only MCP saved-record queries, receipt inspection and result verification."
---

# RDC Operator Kit

Choose an available control surface, perform the authorized operation, and inspect
the actual outcome. This skill does not grant tools, install a connector, or create
permission. The kit is an independent local adapter package, not an RDC service.

## Resolve the live route

For saved-record queries through an already configured local MCP host, first read
[read-only MCP queries](references/mcp.md). Do not run `doctor` or discover live
devices merely to read saved records. Use the steps below for live computer work
or requested setup.

1. Discover current RDC tools and list connected devices. Select the requested
   computer; pass its exact current account and device identifiers on every call.
   A machine name in an old note is a hint, not live connectivity.
2. Read relevant project instructions and current ownership before writes. Locate
   the existing `RDC-Operator-Kit` installation or the user-specified checkout.
   Read its README and local config without copying credentials or unrelated
   environment variables into prompts, receipts or reports.
3. Run its `doctor`. Executable detection, launch success and a tested workflow
   are separate facts. A WindowsApps alias may exist but fail to launch.
4. If installation is requested and missing, use the reviewed local installer;
   see [installation](references/installation.md). Reuse a working RDC agent.
   Do not change global PATH or create another broker merely to invoke a CLI.

## Choose the surface

| Work | Route |
|---|---|
| Local files, search, one-shot command or line-oriented REPL | RDC file/search/process tools |
| Interactive TUI, raw keys, current terminal screen | Kit `terminal.*` through pinned SmartCLI |
| Native Windows app | Kit `desktop.*` through pinned winapp, exact observed HWND |
| Finite native-window image samples | Kit `scripts/sample_desktop.py`, shared state and bounded frame count |
| Saved Kit request summary or receipt | Optional local read-only MCP; check the advertised tools and [MCP version/privacy contract](references/mcp.md) |
| Signed-in website, tabs, ChatGPT page or browser UI | Official Browser skill and its own tools |
| Bounded OMP worker | Existing `dispatch-local-omp` / `origin-dispatch` route |
| Codex CLI | Existing authorized CLI/session; verify ownership before input |

Explicit browser choice wins. Read the Browser skill and verify the selected
browser family. A browser security-policy refusal stops that action: never
replace it with RDC, desktop input, raw CDP, cookies or hidden network requests.
The kit intentionally rejects known browser process targets. A Skill cannot
make every website or browser feature available.

When the user explicitly requests an existing local OMP Relay for a separately
permitted fixture, use its installed guide and the existing dispatcher. Freeze
the exact origin and owned-tab scope, create a new named tab without borrowing a
user tab, and stop if the backend is unavailable. This does not permit accessing
a target already refused by the current host. Never change global browser routes
or run extension install/sync as a read-only diagnostic.

## Execute and recover

Use `python -m rdc_operator --config <config> --state <shared-state> call <request.json>`.
Add `--apply` only for an already-authorized state-changing action. Use the exact
installed Python path and JSON files or stdin; avoid improvised shell quoting.
See [requests and receipts](references/requests.md) for supported actions.

- Give each new action a fresh request ID. Retrieve a prior request with its same
  ID and identical payload/config. Do not change the ID merely to retry an
  unknown effect. Changed payload/config with an old ID is a conflict.
- If an intent has no final receipt, or a result is `outcome_unknown`, reconcile
  existing artifacts and live state first. Do not delete locks/intents or
  automatically repeat input. A new action needs a concrete reason and continued
  authority after that reconciliation.
- Use one shared state directory for cooperating writers. Its OS lock does not
  control the human desktop, other tools or separate state directories.
- Distinguish RDC `call_id` (poll `get_tool_result`), process `pid` (read process
  output) and search `sessionId` (search pagination). Pending is not failure and
  does not authorize duplicate execution.
- Cancel only the verified process/session owned by this task. RDC `shutdown`
  disconnects remote access; never use it to cancel ordinary work.

## Verify terminal work

Start an owned session in an allowed workspace. Wait for a real prompt or screen
condition, send input, then inspect the fresh snapshot and `io` fields. RDC pipes
are not a PTY. SmartCLI's `--cmd` is a string interface. The pinned Windows
PyWinPTY route cannot resolve a quoted first executable token. Use an allowed cwd
and an unquoted relative executable path; the kit refuses known unsupported
quoting before daemon launch. A working fixture does not prove general argv portability.

Do not accept echoed input as computed output. Prefer a separate output line or
an independent artifact. `matched:false`, undrained observations and an exited
child are not readiness. Preserve SmartCLI 0.3.5 close uncertainty: its CLI hides
the lower-level close receipt. Confirm child exit separately when required.

Use short bounded waits when observation responsiveness matters: Kit holds its
state lock during a wait, so another call to that state can return `busy`. Do not
make a second state to evade coordination. Treat alive plus silence as unknown
work state, not proof of computation or an input request. For synthetic liveness
diagnosis, use `scripts/probe_terminal_liveness.py`; it operates on its own fixed
fixtures and is not an arbitrary-process attachment tool. On Windows a venv
Python redirector can have a different PID from the interpreter; retain strict
process identity checks and inspect the selected base executable.

## Verify desktop work

Observe a specific current HWND. Select only an element actually returned in
that observation. Observe again after expiry, target replacement or an
intervening desktop change. The kit checks PID/creation-time identity and binds
the upstream canonical element ID; those checks are not an OS sandbox.

For an a4-compatible checkout, read [Windows preflight and focus](references/requests.md#windows-preflight-and-focus)
before diagnosing input conditions or changing focus. Keep the read-only probe
separate from permission. Request focus explicitly for the observed top-level
window; never force focus inside a click or adopt an unobserved parent.

For UAC or elevation, name the specific program, action and reason, then hand
the normal Windows confirmation to the user. After the user returns, collect
fresh window, token, session, desktop and foreground evidence. Do not click the
secure desktop or change UAC policy; never use this handoff to bypass a host
refusal. Use [bounded source acceptance](references/installation.md#bounded-windows-source-acceptance)
only for separately authorized owned fixtures.

Prefer `invoke` and `set_value`; use selector-based clicks where necessary.
Read the post-action state and independently verify the intended effect. Capture
only the relevant window when visual evidence helps. A valid PNG proves capture
bytes, not that its pixels have been reviewed. Keep private UI and receipts out
of public reports by default.

For screenshots, pass the same fresh `observation_id` when a prior target binding
exists. Reject mismatched path/PID/HWND/dimensions and multi-window `windows[]`
results as single-window evidence. Capture can restore or foreground a window.
Read [observation evidence](references/observation.md) before finite sampling or
using browser-evidence validation. A frame hash identifies bytes; a new filename,
new frame ID or completed screenshot command does not prove new rendered pixels.

## Finish at a concrete acceptance boundary

Report what ran, the observed result, evidence location and remaining limits.
Separate source claims, mocked tests, real fixture tests and real model calls.
OMP transport `DONE` is not artifact acceptance. Do not promise background work
or future monitoring without a real running process or scheduling receipt.

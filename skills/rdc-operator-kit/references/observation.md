# Image, browser and receipt evidence

Use the installed version's README and scripts. These procedures require Kit
0.1.0a2 or a later compatible version; do not assume an old installation has them.

## Finite native-window samples

Pass a current authorized HWND, the same state directory used for other Kit
operations, and a new output directory under configured allowed_roots:

```text
python scripts/sample_desktop.py --config <config> --state <shared-state> --window <HWND> --output <new-absolute-dir> --frames 3 --interval-ms 500 --start-deadline-seconds 30 --apply
```

The sampler emits one JSON line per completed frame and updates manifest.json
before emitting it. RDC may return a running PID before it finishes; read that
process's output instead of starting it again. The count is bounded to 1–12 and
the admission deadline to 60 seconds. An already admitted capture still has its
own timeout; this is not continuous video or a hard real-time deadline.

The sampler obtains one short-lived observation and uses it for every frame.
Target replacement, expiry, an uncertain capture or a composite stops sampling.
Do not refresh a stale observation automatically inside the run. If the user
still needs samples, reconcile the stopped run and reobserve explicitly.

Read frame_id, artifact SHA-256, target identity, capture_call timestamps,
observation_id, and replay status together. captured_at is null because the
upstream does not expose actual rendering time. Identical hashes may be a static
scene or repeated cached pixels. Different hashes do not prove which action
caused a change. PNG header checks are not full decoding or visual review.

Read the actual image with the available image tool before claiming to have seen
it. Use a corresponding control-state or independent file witness for the
business effect. Preserve a separate visual-review record; do not rewrite a
script's old evidence flags to pretend that the script viewed the picture.

## Browser evidence

For requested page interaction or visual acceptance, use the current official
Browser skill proactively. Follow its connector preference, selected-browser
scope and advertised API. Reacquire tab/origin/document and current semantic
targets after navigation, reload, worker recovery or a manual handoff. When a
permitted CUA action needs coordinates, inspect a fresh screenshot first and
capture/read the result afterward; never reuse old coordinates across a change.

Keep action readiness, accepted input and business effect separate. A visible
enabled control can still lack its application's event handler during hydration.
Wait for the relevant application condition and verify the intended effect;
do not repeat a click to compensate for an uncertain response. See [recovery](recovery.md)
for preserved request identities and typed handles after a connection change.

`scripts/verify_browser_evidence.py` checks a small fixture bundle offline. It
does not operate a browser, authenticate evidence, or grant website access.
`verified_fixture` means the supplied synthetic evidence is internally
consistent. It never establishes authorization or a real browser run.

Use `--host-refused` / `--operator-stopped` to preserve known stop context when
analyzing a bundle. Missing flags are not permission. A lost response remains
unknown even if the DOM witness changed: reconcile, do not automatically click
again. Navigation or worker recovery invalidates old document/element evidence.

The account-free `site/lab.html` provides a counter, ACK-only button, delayed
effect, epoch reset and reload. It deliberately allows repeated clicks to repeat
the effect, so an executor must preserve its own request identity. Prefer this
fixture for independently authorized browser route tests; never substitute it
as evidence that a denied or untested website works.

## Optional MCP

Read [read-only MCP queries](mcp.md) before choosing capabilities, raw receipt or
saved-record status lookup. The three-tool/schema/status contract requires
0.1.0a5 or a later compatible version; do not infer it from older two-tool tests.
Keep successful reads, stored Kit status and independently verified business
completion separate. Raw receipts remain private, unsanitized evidence.

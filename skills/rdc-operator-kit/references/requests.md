# Requests and receipts

```json
{"request_id":"unique-id","action":"desktop.observe","args":{"window":123456}}
```

Replace the illustrative HWND with a current observed handle. IDs use 1–64 ASCII
letters, digits, `_` or `-`, excluding Windows device names. Read the installed
source/help if its contract differs. Unknown fields are rejected.

| Action | Arguments |
|---|---|
| `terminal.start` | `session`, `command`, `cwd`; optional `cols`, `rows` |
| `terminal.snapshot` | `session` |
| `terminal.wait` | `session`; optional `pattern`, `timeout_ms` |
| `terminal.send_text` | `session`, `text`; optional `newline` |
| `terminal.send_key` | `session`, `key` |
| `terminal.close` | `session` |
| `desktop.observe` | `window` |
| `desktop.focus` (0.1.0a4+) | fresh `observation_id`; exact observed top-level HWND only |
| `desktop.set_value` | `observation_id`, `selector`, `value` |
| `desktop.invoke`, `desktop.click` | `observation_id`, `selector` |
| `desktop.screenshot` | `window`, new absolute `.png` `output`; optional fresh `observation_id` |
| `omp.preview` | `job`, absolute `brief`, absolute `cwd`, explicit `model`, `effort`; optional bounded attempt/time limits |

For call requests, all except snapshots, waits and desktop observation require `--apply`. OMP preview
writes a dry-run receipt without calling a model; it cannot resume into execution.
Real OMP dispatch still uses the existing native wrapper.

Terminal text ending in CR/LF is refused because the pinned stdin path trims it;
use `newline:true` for one Enter. Leading-dash desktop values and regex patterns
are refused where the upstream parser is ambiguous.

Receipts live in `<state>/requests/<id>.receipt.json`. Intent, receipts, session
ownership and observations are runtime evidence: preserve them during recovery
and exclude them from source/publication. `allowed_roots` constrains kit path
arguments, not the OS access of a terminal child.

`observed` is a read; `completed` is an acknowledged adapter operation; `failed`
is a known failure; `outcome_unknown` requires reconciliation. Read result
`verification` fields and independent application evidence before claiming the
user's goal succeeded. `replayed:true` retrieves a prior result without execution.
An existing complete receipt can be retrieved without `--apply`. An intent with
no final receipt returns uncertainty and never executes again, with or without
that flag.

## Windows preflight and focus

Confirm that the selected source/installation supports 0.1.0a4 interfaces.
Set $kitPython to its actual absolute Python executable. Set $targetHwnd from a
fresh observation of the authorized target; do not substitute an example number.

~~~powershell
& $kitPython -m rdc_operator windows-preflight
& $kitPython -m rdc_operator windows-preflight --window $targetHwnd
~~~

Read the probe without config or state: it sends no input, changes no foreground,
and requests no elevation. Interpret assessment.status and exit code together:

| Assessment | Exit | Interpretation |
|---|---|---|
| observed | 0 | Listed checks found no conflict in this sample |
| blocked | 1 | A concrete mismatch was observed |
| unknown | 1 | Required evidence is missing, unstable, or no target was supplied |
| unsupported | 1 | The platform is not Windows |

Expect unknown / target_not_provided without --window on an otherwise ordinary
Windows desktop; an observed desktop conflict still takes precedence as blocked.
Treat invalid arguments as exit 2. Never interpret exit 0 as authorization or a
future input guarantee. Preserve uac_state=not_determined: null foreground and
access denied alone do not identify UAC, and UIAccess grants no blanket permission.

After separate authority to change focus, write a new call request using the
current observation ID:

~~~json
{"request_id":"focus-001","action":"desktop.focus","args":{"observation_id":"obs-REPLACE-WITH-FRESH-ID"}}
~~~

Run it with the same config/state and --apply. Supply only observation_id; do
not add window, selector, coordinates or force. Require the observed HWND to
remain its own GA_ROOT: reparented targets are refused before the backend call,
and their parent is never adopted. Preserve uncertainty if the normal activation
request fails: the backend may already have restored a minimized window.

Retrieve the same ID with identical payload/config to read its stored outcome;
this does not focus again. Reconcile outcome_unknown instead of changing IDs to
retry. After verified focus, use result.observation.observation_id from that
receipt and an actual selector in its returned tree for the next authorized
click. Reobserve if that observation is missing or stale. Keep the upstream
click foreground guard; focus verification does not prove the click's business
effect or prevent another actor from changing the desktop.

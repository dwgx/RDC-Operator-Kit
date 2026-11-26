# Read saved records through optional MCP

## Select a compatible local entry

Require Kit 0.1.0a5 or a later compatible version for the three-tool contract,
declared output schemas and `operator_request_status`. Check the actual installed
version and advertised tools. Older entries may offer capabilities and receipt
reads only; do not infer the new contract from earlier two-tool smoke results.
Keep the existing desktop focus/preflight and source runner minimum at 0.1.0a4.

Use a local MCP host that can launch a stdio subprocess. This entry is not an
HTTPS endpoint and does not make a local process reachable by cloud ChatGPT.
Do not run `doctor`, query live devices or install dependencies merely to inspect
saved records. If the required entry is absent, report that specific limitation.

For authorized setup, follow the selected checkout's `docs/MCP.zh-CN.md`. Use a
new dedicated `.venv-mcp` with official `mcp==2.3.0`; SmartCLI 0.3.5 needs MCP 1.x.
Never combine terminal/MCP extras or upgrade SmartCLI's environment for this.
Pass the actual interpreter with separate arguments: `-m`,
`rdc_operator.mcp_server`, `--config`, the absolute config path, `--state`, and the
absolute state path. Config/state are fixed, trusted startup choices, not tool
parameters. Do not invent a remote URL or replace the configured state.

## Choose the smallest sufficient read

| Tool | Exact arguments | Meaning |
|---|---|---|
| `operator_capabilities` | `{}` | Describe static configuration shape and tool/version metadata; do not infer executable availability, connectivity or readiness. |
| `operator_request_status` | `{"request_id":"example-001"}` | Summarize saved intent/receipt records with `record_state`, `reason` and `saved_receipt_status`; prefer this when raw contents are unnecessary. |
| `operator_receipt` | `{"request_id":"example-001"}` | Read the original saved receipt with its original status and fields; treat paths, commands, outputs and other contained data as private. |

Use a Kit ID of 1–64 ASCII letters, digits, `_` or `-`, excluding Windows device
names. Never pass a path, command, config override, action arguments or extra
fields. Keep the MCP JSON-RPC envelope `id` separate from this durable
`request_id`; repeated reads do not create or replay a Kit request.

The status summary omits stored args, commands, paths, action names, timestamps,
digests and receipt output. It does not enumerate other request IDs. This privacy
property does not apply to raw `operator_receipt`: read it only within the task's
authorized scope, and review/redact its contents before any separately authorized
external sharing. Neither tool executes actions or refreshes application state.

## Interpret saved-record status conservatively

The status tool makes two bounded rounds, reading intent and receipt in each.
Always retain `snapshot_atomic: false`; matching samples are not a global lock or
a live view.

| `record_state` | `reason` | `saved_receipt_status` and interpretation |
|---|---|---|
| `no_records_observed` | `no_records_observed` | `null`; no records were observed in the configured state, not proof that no external action occurred. |
| `intent_without_receipt` | `receipt_not_observed` | `null`; execution may not have started, may have occurred or may have been interrupted. Do not call it running or retryable. |
| `receipt_recorded` | `matching_saved_records` | Preserve `observed`, `completed`, `failed` or `outcome_unknown`; this is stored status, not independent business verification. |
| `inconclusive` | `records_changed_during_observation`, `receipt_without_intent` or `record_digest_mismatch` | `null`; reconcile existing evidence. Do not cancel, change IDs or replay an uncertain effect. |

Preserve `live_verification_performed: false`,
`record_authenticity_verified: false` and `actions_exposed: false`. Do not infer
live running, cancellation, replay permission or task success from any state.
Treat unreadable, invalid or unsafe records as the returned error, not as absent
records or a new lifecycle state. Only explicit not-found reads count as missing.

## Read the output contract without widening its guarantees

The three tools publish object-root output schemas. Their outer successful
results are closed to undeclared fields; `operator_receipt.receipt` deliberately
allows additional original fields beyond schema version, request ID and status.
It is not a sanitized receipt or proof of authenticity. Keep its
`live_verification_performed` and `receipt_authenticity_verified` flags false.

JSON text and `structuredContent` express the same result. Handle `isError: true`
and its stable `error.code` separately from successful output schemas. A
successful read can return an original `outcome_unknown` receipt; MCP read
success, stored Kit completion and verified business completion are distinct.
Do not turn annotations or schema validation into authorization. This entry
exposes no process probing, cancellation, replay, desktop or model action tools.

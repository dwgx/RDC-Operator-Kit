# Static site · 0.1.0a6 Alpha

This directory contains a self-contained static project guide and Browser Evidence
Lab. It needs no build step, package install, remote font, analytics service or
live device connection. The page is documentation, not a remote-control console.

## a6 recovery guide

The homepage adds a manual-reconnection workflow, original-state reconciliation,
fresh observation guidance and a separately labelled Wave 06 acceptance section.
The established CSS/JavaScript and Lab witness logic remain unchanged. New content
and relative links receive static validation; no blocked browser target was retried.
See [Wave 06](../docs/REVIEW-WAVE6.zh-CN.md) for exact installed/source evidence.

## Modern interface

The a5 homepage adds local evidence search, category/query combinations, empty
result recovery and more explicit copy feedback to the light/dark visual refresh.
Tabs and keyboard navigation remain. Queries are normalized locally, matched as
AND terms against public card text, and never sent to a service or saved as query
history. Copy controls guard pending writes, recover busy state after rejection,
and explain text-selection failure. Escape leaves an active IME composition alone.

Lab styling follows the same visual direction. Its counter, delayed-action and
witness JavaScript retains the a4 bytes; a visual change does not authorize reuse
of old screenshot coordinates or establish new browser acceptance.

## What has actually been checked

The modern UI has static structure and source checks, synthetic Node DOM/event
checks, independent search/filter and keyboard cases, and copy failure cases.
Review found an IME Escape bug; the fix passed three targeted independent event
branches. These results do not claim live rendering, Windows IME behavior, real
clipboard permissions, mobile layout or full accessibility acceptance.

Historical a4 official Edge Lab interaction and a4 homepage checks remain labelled
as a4. The homepage Markdown guide returned `ERR_BLOCKED_BY_CLIENT`; subsequent
same-origin access was denied by automatic approval review. Responsive checks and
the final homepage screenshot were not executed. The ChatGPT-origin and local
file transport refusals remain separate boundaries. Do not change browser,
transport, desktop, shell or OMP routes to complete denied browser validation.

The initial a5 local core passed 177/177 with no skips. One Windows source snapshot
passed all nine top-level cases; its core had 177 run, 166 pass and 11 skips. The
initial real MCP 2.3.0 sessions each passed 30 checks. Review then found and fixed
smoke verdict gaps; stronger final core and affected wire results are recorded
separately in [Wave 05](../docs/REVIEW-WAVE5.zh-CN.md). None of these source tests
is proof of modern homepage browser execution or installed-package validation.
HMC was quota-blocked and both real OMP reviews ended without a final response.

## Historical repository preparation and deployment

The public [dwgx/RDC-Operator-Kit repository](https://github.com/dwgx/RDC-Operator-Kit)
has been created. At this documentation checkpoint, source push, CI, Release and
Pages deployment have not yet been recorded complete. Update the current page
labels and real download/deployment links from actual receipts before declaring
the site live; preserve the separately labelled historical evidence. Repository
creation alone does not make an empty repository installable.

The optional MCP environment remains separate from SmartCLI because their fixed
MCP major versions conflict. a5 exposes three read-only tools, including a minimal
saved-record summary; it does not add action tools or a remote network endpoint.
Use the repository's [MCP guide](../docs/MCP.zh-CN.md) for the contract and setup.

Before packaging or deployment, synchronize the public repository `docs/` tree
into `site/docs/`, preserving subdirectories. In the site copies, rewrite relative
links that leave `docs/` to the matching public repository path at the released
tag; only `site/` is deployed, so a link to a sibling source directory would break.
Keep intra-document and intra-`docs/` links relative. The source documents themselves
retain their repository-relative links. This includes every document linked
from the page and its relative dependencies, such as `WINDOWS-CONTROL.zh-CN.md`,
`REVIEW-WAVE5.zh-CN.md`, historical reports and research references. Never copy
runtime `evidence/`, local configuration or private reports into the site.
The release builder embeds directly linked documents from that same filtered
snapshot into the standalone preview. The source bundle retains the full approved
document tree. Recheck final relative links after synchronization.

`lab.html` is an account-free synthetic evidence fixture. Offline evidence
validation proves internal consistency, not browser operation, source authenticity
or website permission. The standalone preview remains a project guide; companion
page links must not become missing local-file references in that single-file output.

[The Pages workflow](../.github/workflows/pages.yml) is manually dispatched on the
default branch, uploads only `site/`, and uses fixed official Actions commits.
Its existence does not prove CI or deployment success. Record the actual run,
commit and returned `page_url`; do not invent a live URL from repository naming.
[Release instructions](../docs/RELEASE.zh-CN.md) cover the authorized process.

## Historical a5 public CI checkpoint

The public source commit `a880144d07d8599c6e5232a34bcef1e1cac54bc1` passed all six
[Core CI jobs](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916).
Each core job ran 184 tests: Windows 3.10 / 3.13 each passed 177 with 7 skips;
Ubuntu 3.10 / 3.13 each passed 179 with 5 skips. Both MCP jobs passed the two
protocol sessions and reported unchanged saved records. The initial failed
[CI run](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079) remains available.
These are core/stdio results, not live modern-UI acceptance.

## Historical a5 release and site

[0.1.0a5](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5)
was published on 2026-11-26 at 17:31:53 JST from commit
`27d367a9698c381d90986c8640d506b24d84ddd9`. All nine uploaded assets were
downloaded from the draft and compared byte-for-byte by SHA-256 before publication.
[CI for that source](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45782996129)
passed all six jobs. [Pages build and deploy](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45783289213)
succeeded for the same source, publishing
<https://dwgx.github.io/RDC-Operator-Kit/>.

Later main-branch documentation records the observed publication and pins its
installation examples to the released tag. It does not rewrite that tag or its
assets. Deployment does not add live-browser UI acceptance to the static checks.

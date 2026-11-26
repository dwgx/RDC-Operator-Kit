# Security and operating boundaries

RDC Operator Kit `0.1.0a1` is an alpha release candidate. It executes authorized
work as the current OS user. It is not an OS sandbox, a credential manager, or a
replacement for the host assistant's permissions.

## What the controls cover

- Durable intents and receipts prevent automatic replay of a known request after
  an ambiguous interruption. They do not provide exactly-once effects or protect
  state from a hostile process running as the same user.
- A per-state OS lock serializes cooperating callers. Other desktop users,
  software, state directories and upstream daemons remain outside that lock.
- UI operations require recent target observations and scoped element binding.
  Business results still need independent verification.
- Installer ownership and archive/content checks protect against accidentally
  adopting unrelated environments or executing mismatched cached WinApp files.
- The kit opens no network listener. RDC and other upstream services keep their
  own authentication, configuration and security responsibilities.

`allowed_roots` applies to paths handled by the kit. A terminal command or an OMP
wrapper can access resources allowed to its OS user; use an appropriate isolated
account or machine when a task requires that boundary. Configured executable
prefixes and source code are trusted operator inputs.

## Private runtime data

Receipts can contain commands, terminal output, UI text, filenames and error
messages. Screenshots can contain personal information. Keep runtime state and
evidence local by default, review before sharing, and never attach credentials,
cookies, API keys or unrelated account/device details to a public report.

Browser policy decisions remain with the official host capability. Do not route a
blocked browser task through another control mechanism. The browser-name checks
in the desktop adapter are an additional routing guard, not a complete security
boundary for every possible web-rendering application.

## Reporting a problem

Before public repository creation, no public vulnerability-reporting endpoint or
response SLA is promised. Coordinate privately with the project maintainer using
an established channel. After publication, use GitHub's private vulnerability
reporting feature if the repository has enabled it; do not assume it is enabled.

Provide the kit version or source commit, platform and Python version, the
smallest synthetic reproduction, expected behavior, actual behavior and relevant
redacted error codes. Avoid publishing an exploitable private configuration or
raw logs. General non-sensitive bugs can use the repository's issue tracker once
it exists. Upstream RDC, SmartCLI and winapp vulnerabilities may also need their
respective maintainers; disclose only the minimum information required.

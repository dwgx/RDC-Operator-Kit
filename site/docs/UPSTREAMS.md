# Upstreams and provenance

Checked: 2026-11-26, Asia/Tokyo. This is a source and dependency ledger, not a claim that every upstream test has been rerun. No hosted RDC implementation, account credential, or browser profile is redistributed by this project.

## Pinned references

| Project | Reference examined | License / role |
|---|---|---|
| [DesktopCommanderMCP](https://github.com/wonderwhy-er/DesktopCommanderMCP) | `0.3.4`; [`9a101b17e44577f0baefa4c7120f087881c5cc56`](https://github.com/wonderwhy-er/DesktopCommanderMCP/commit/9a101b17e44577f0baefa4c7120f087881c5cc56) | [MIT](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/LICENSE). Official local MCP and remote device agent; retain the existing installation. |
| [Remote Desktop Commander](https://github.com/desktop-commander/remote-desktop-commander) | [`71d6444c59c36f2cba2f13e8f72785383a8528b5`](https://github.com/desktop-commander/remote-desktop-commander/commit/71d6444c59c36f2cba2f13e8f72785383a8528b5) | [Restricted documentation/manifests license](https://github.com/desktop-commander/remote-desktop-commander/blob/71d6444c59c36f2cba2f13e8f72785383a8528b5/LICENSE); hosted implementation is proprietary. Link to it; do not copy the repository into this kit. |
| [SmartCLI](https://github.com/dwgx/SmartCLI) | Release `v0.3.5`, peeled commit [`ccf3472dadaae0b5081c8324e2569c25a9174115`](https://github.com/dwgx/SmartCLI/commit/ccf3472dadaae0b5081c8324e2569c25a9174115); research main [`24da9834686e4df7625a0096cb281567c4824042`](https://github.com/dwgx/SmartCLI/commit/24da9834686e4df7625a0096cb281567c4824042) | [MIT](https://github.com/dwgx/SmartCLI/blob/24da9834686e4df7625a0096cb281567c4824042/LICENSE). PTY and terminal screen adapter. |
| [Microsoft WinApp CLI](https://github.com/microsoft/winappCli) | `v0.8.0` annotated tag peels to [`696222f72e80c669671845bd6c7b0286eefab987`](https://github.com/microsoft/winappCli/commit/696222f72e80c669671845bd6c7b0286eefab987); release API `target_commitish` is `e5cedcc04921f6f74535cf45668292203e439d45`; research main [`c9e6a9bdf010add8edaddb790689e3cbaae33cd5`](https://github.com/microsoft/winappCli/commit/c9e6a9bdf010add8edaddb790689e3cbaae33cd5) | [MIT](https://github.com/microsoft/winappCli/blob/c9e6a9bdf010add8edaddb790689e3cbaae33cd5/LICENSE). UIA/window-scoped desktop adapter. The tag identity and release metadata are different fields; do not silently replace one with the other. |
| [Remote Commander Tray](https://github.com/PeterShanxin/Remote-Commander-Tray) | [`70ec27403dfa909534ecc58c67d554855d57c1e2`](https://github.com/PeterShanxin/Remote-Commander-Tray/commit/70ec27403dfa909534ecc58c67d554855d57c1e2) | [MIT](https://github.com/PeterShanxin/Remote-Commander-Tray/blob/70ec27403dfa909534ecc58c67d554855d57c1e2/LICENSE). Research reference for process custody and tray supervision; not bundled or installed automatically. |
| Official Browser plugin | Runtime-provided `control-browser` instructions | Use the installed plugin under its own policies; no copied runtime or unofficial browser session bridge. |
| Existing OMP dispatcher | Operator-configured local `origin-dispatch` wrapper | Reuse the installed route. It is not vendored, replaced, or assigned an invented public license by this kit. |
| [OMP Browser Relay](https://github.com/can1357/oh-my-pi/tree/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/browser-relay) | Existing OMP `19.2.1`, commit `b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac` | MIT. Existing installation used only for an authorized localhost fixture; no extension, native host or profile files redistributed. |
| [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/2118f14f8a19bc158d8a1cf90af58d85d187f849) | Optional `mcp==2.3.0`, commit `2118f14f8a19bc158d8a1cf90af58d85d187f849` | MIT. Implements the optional read-only stdio transport. Install into its own environment, separate from SmartCLI's MCP 1.x requirement. |

## Artifact identity

GitHub's `v0.8.0` release API returned the following digest for the Windows x64 portable archive:

```text
asset: winappcli-x64.zip
sha256: 67a8e1d39421a5ef5309c7017327c6a70ea6215a0e56e47ec22a7e9ec3b914e6
release: https://github.com/microsoft/winappCli/releases/tag/v0.8.0
```

This ledger records upstream metadata. A local download is only verified when its actual bytes have been hashed and compared; see the kit's test evidence for that separate result. A checksum is a content identity check, not a publisher signature. Version tags, source commits and binary bytes must remain distinct fields.

## Requirements and known disagreements

1. **RDC Node requirement:** remote setup prose still says Node 18+. The pinned `0.3.4` package declares Node `>=22.12.0`, and the Windows launcher enforces that threshold. Use the pinned package's engines for installation decisions. [package.json](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/package.json), [launcher](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/scripts/remote/remote-windows.ps1).
2. **RDC pipes versus a terminal:** its `terminal-manager.ts` starts pipes and appends a newline to submitted input. That does not implement raw-key/resize/VT semantics. The kit delegates terminal work to SmartCLI instead of claiming RDC itself gained a PTY. [source](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/terminal-manager.ts).
3. **SmartCLI dependency compatibility:** the examined `0.3.5` metadata requires Python `>=3.10`, `pyte`, `mcp>=1.0,<2`, and Windows-only `pywinpty`. The MCP major cap is deliberate; an upgrade needs a real compatibility check. [pyproject.toml](https://github.com/dwgx/SmartCLI/blob/24da9834686e4df7625a0096cb281567c4824042/pyproject.toml).
4. **winapp main versus a release:** upstream labels its CLI Public Preview and explicitly says main can differ from published builds. A command or flag documented at research main is not proof that the pinned portable release supports it. The adapter must inspect the installed binary and fail closed for missing or malformed results. [README](https://github.com/microsoft/winappCli/blob/c9e6a9bdf010add8edaddb790689e3cbaae33cd5/README.md), [UI documentation](https://github.com/microsoft/winappCli/blob/c9e6a9bdf010add8edaddb790689e3cbaae33cd5/docs/ui-automation.md).
5. **Windows GUI conditions:** UIA pattern actions and OS-level input are different. Mouse/key injection needs an appropriate interactive desktop; screenshots can restore or foreground a window. This is why the kit requests `--apply` for screenshots and uses explicit windows. [UI documentation](https://github.com/microsoft/winappCli/blob/c9e6a9bdf010add8edaddb790689e3cbaae33cd5/docs/ui-automation.md).
6. **Limited history:** RDC local history and process buffers are bounded. Its remote service temporarily holds call data for delivery and cleanup. Do not advertise zero transient retention or durable exactly-once execution. [device documentation](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/remote-device/README.md).
7. **Existing supervision:** Remote Commander Tray owns one process generation and does not coordinate a separate user-created scheduled task. Do not install another supervisor on top of an existing RDC launch route. Its current source includes a Linux Beta, despite older indexed descriptions saying otherwise. [README](https://github.com/PeterShanxin/Remote-Commander-Tray/blob/70ec27403dfa909534ecc58c67d554855d57c1e2/README.md).

## Useful upstream tests, not kit results

- [Process pagination](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/test-process-pagination.js): new-output cursor, explicit offsets, tail reads, truncation.
- [Remote pending recovery](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/test-remote-pending-recovery.js): recover eligible pending calls and atomically claim them.
- [Windows launcher tests](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/remote-launcher-windows.test.ps1): dependency detection, installer integrity, errors, caller settings restoration.

These were inspected as committed source. Their existence does not establish that this kit passed them, that the user's machine has the same version, or that production outages have been reproduced.

## Reuse policy

The second research wave compares ten browser/relay projects in [BROWSER-MCP](research-wave2/BROWSER-MCP.zh-CN.md), records screenshot research in [OBSERVATION](research-wave2/OBSERVATION.zh-CN.md), and records protocol sources in [MCP-SKILL](research-wave2/MCP-SKILL.zh-CN.md). Those are references, not additional bundled dependencies. BrowserOS and Skyvern AGPL code was not copied into this MIT source tree. Source inspection, installed package identity, and executed tests remain separate evidence.

Do not combine the `terminal` and `mcp` extras in one environment: SmartCLI 0.3.5 requires `mcp>=1.0,<2`, while this optional server deliberately pins `mcp==2.3.0`. A resolver conflict is expected for `.[terminal,mcp]`; use the dedicated environment in [MCP installation](MCP.zh-CN.md). A local stdio server does not provide a remotely reachable ChatGPT connector.

Call established tools through documented interfaces. Pin packages and artifact identities in installation code; preserve upstream notices for any redistributed code. Keep credentials, private screenshots, machine IDs and account-specific dispatcher configuration outside public release files. Do not imply endorsement by Desktop Commander, Microsoft, OpenAI or any other upstream publisher.

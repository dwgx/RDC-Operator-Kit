# Local installation

Use a complete known source checkout supplied by the user or a verified published
release. Verify the selected source and version; do not invent a download URL or
claim a release is published without checking its actual publication record.

Windows, from the complete source tree:

```powershell
.\scripts\install.ps1 -WithTerminal -WithDesktop
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json doctor
```

Linux core and terminal:

```bash
bash scripts/install.sh --with-terminal
.venv/bin/python -m rdc_operator --config config.local.json doctor
```

Python 3.10+ is required. Installers use an isolated `.venv`, preserve existing
config and reject links/conflicts. Desktop support pins winapp 0.8.0, verifies
the official archive hash and installed files before execution. Terminal support
pins SmartCLI 0.3.5. These pins are not a full transitive dependency lock.

The RDC device agent must already be installed and paired through its official
device flow. Never read or export its token. Follow current tool instructions
for any requested new pairing or browser login. RDC 0.3.4 package engines require
Node >=22.12.0; older remote prose says >=18. Follow the pinned package metadata.

Find the existing OMP dispatch wrapper when requested; read its live skill and
`--help`. Do not copy a private wrapper into a public release without inspecting
its licensing and contents. Do not change global model routing.

## Bounded Windows source acceptance

Use this 0.1.0a4+ runner only for an authorized fixture run in the selected
complete source checkout. Check its current --help. Reuse provisioned SmartCLI
and separate MCP environments; this command installs nothing. From that checkout,
resolve actual paths before starting. Adapt the example if the environments or
PowerShell installation live elsewhere:

~~~powershell
$kitRoot = (Resolve-Path '.').Path
$terminalPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$mcpPython = (Resolve-Path '.\.venv-mcp\Scripts\python.exe').Path
$basePython = (& $terminalPython -c 'import sys; print(sys._base_executable)').Trim()
$basePython = (Resolve-Path -LiteralPath $basePython).Path
$pwsh = (Resolve-Path 'C:\Program Files\PowerShell\7\pwsh.exe').Path
$configPath = (Resolve-Path '.\config.local.json').Path
$windowsOutput = Join-Path $kitRoot ('evidence\windows-' + [guid]::NewGuid().ToString('N'))
$smokeArgs = @(
  '.\scripts\smoke_windows.py',
  '--config', $configPath, '--output', $windowsOutput,
  '--python', $basePython, '--terminal-python', $terminalPython,
  '--mcp-python', $mcpPython, '--powershell', $pwsh,
  '--deadline-seconds', '600'
)
& $basePython @smokeArgs
~~~

Use a real CPython base executable for --python and the actual absolute
PowerShell 7 pwsh.exe, not WindowsApps/PATH aliases or powershell.exe. Keep
--terminal-python on SmartCLI's environment and --mcp-python on the separate SDK
environment. If MCP is unavailable, omit its variable and argument; record its
skipped case instead of merging dependencies. Keep the new, nonexistent output
directory under configured allowed_roots; never overwrite an earlier run.

Poll the same running process and read summary.json plus its linked fixture
reports. Treat 600 seconds as the suite budget, not a hard real-time guarantee.
Interpret runner exit 0 as all cases passed, 1 as failure or uncertain cleanup,
and 2 as incomplete coverage, including skipped/not-run/unsupported cases.
Preserve case counts, deadlines and cleanup limits; stop only task-owned
processes, never all instances of an executable.

Report this as source execution: source_execution=true and
installed_package_validation=false. OMP preview validates DRY_RUN without a
real model call; browser_offline checks fixture consistency without operating a
browser. Test a live website separately through its permitted official Browser
route. These instructions and synthetic passes are not evidence of a Windows
live run; claim platform coverage only from the reports actually produced.

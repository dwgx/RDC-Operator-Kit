[CmdletBinding()]
param(
    [switch]$WithTerminal,
    [switch]$WithDesktop,
    [string]$Python = 'python',
    [string]$InstallRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Get-RdcSha256([string]$FilePath) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($FilePath)
        return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $hasher.Dispose()
    }
}
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ne $sourceRoot) {
    throw 'Extract or clone this source tree into the desired directory, then run its installer there. InstallRoot must be the source root.'
}
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'pyproject.toml'))) { throw 'Incomplete source tree' }
$versionText = & $Python -c 'import sys; print(sys.version_info.major, sys.version_info.minor); raise SystemExit(sys.version_info < (3,10))'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or newer is required; install from python.org and retry.' }
$venv = Join-Path $InstallRoot '.venv'
$marker = Join-Path $InstallRoot '.rdc-install.json'
foreach ($guarded in @($InstallRoot, $venv, (Join-Path $venv 'Scripts'), $marker, (Join-Path $InstallRoot 'config.local.json'), (Join-Path $InstallRoot 'tools'))) {
    if (Test-Path -LiteralPath $guarded) {
        if ((Get-Item -Force -LiteralPath $guarded).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked installation path refused: $guarded" }
    }
}
if ((Test-Path -LiteralPath $venv) -and -not (Test-Path -LiteralPath $marker)) {
    throw 'An unowned .venv already exists. Use a fresh source directory; the installer will not adopt or overwrite it.'
}
if (Test-Path -LiteralPath $marker) {
    $owner = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($owner.project -ne 'rdc-operator-kit' -or $owner.install_root -ne $InstallRoot) { throw 'Install ownership mismatch' }
}
if (-not (Test-Path -LiteralPath $venv)) {
    @{ project='rdc-operator-kit'; install_root=$InstallRoot; schema_version=1 } | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated Python environment' }
}
$pythonExe = Join-Path $venv 'Scripts/python.exe'
& $pythonExe -m pip install --disable-pip-version-check $InstallRoot
if ($LASTEXITCODE -ne 0) { throw 'Local package installation failed' }
if ($WithTerminal) {
    & $pythonExe -m pip install --disable-pip-version-check 'smartcli-toolkit==0.3.5'
    if ($LASTEXITCODE -ne 0) { throw 'Pinned SmartCLI installation failed' }
}
$winappExe = Join-Path $InstallRoot 'tools/winapp-0.8.0/winapp.exe'
if ($WithDesktop) {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    $hashes = @{ x64='67a8e1d39421a5ef5309c7017327c6a70ea6215a0e56e47ec22a7e9ec3b914e6'; arm64='fbbb2f83228b5130978c17051a9a18e72ea169426cc547de1a17f6cde707561f' }
    if (-not $hashes.ContainsKey($arch)) { throw "Unsupported desktop architecture: $arch" }
    $toolRoot = Join-Path $InstallRoot 'tools'
    New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
    $archive = Join-Path $toolRoot "winappcli-$arch.zip"
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -Uri "https://github.com/microsoft/winappCli/releases/download/v0.8.0/winappcli-$arch.zip" -OutFile "$archive.partial"
        if ((Get-RdcSha256 "$archive.partial") -ne $hashes[$arch]) {
            throw 'WinApp archive checksum mismatch; partial download preserved for inspection, never executed.'
        }
        Move-Item -LiteralPath "$archive.partial" -Destination $archive
    }
    if ((Get-RdcSha256 $archive) -ne $hashes[$arch]) { throw 'Cached WinApp archive checksum mismatch' }
    $toolDir = Join-Path $toolRoot 'winapp-0.8.0'
    & $pythonExe (Join-Path $PSScriptRoot 'verify_winapp.py') $archive $hashes[$arch] $toolDir
    if ($LASTEXITCODE -ne 0) { throw 'Installed WinApp content verification failed; no executable was launched.' }
    & $winappExe --version
    if ($LASTEXITCODE -ne 0) { throw 'WinApp executable probe failed' }
}
$configPath = Join-Path $InstallRoot 'config.local.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $config = @{ schema_version=1; allowed_roots=@($InstallRoot); observation_ttl_seconds=120 }
    $smartcli = Join-Path $venv 'Scripts/smartcli-tui.exe'
    if (Test-Path -LiteralPath $smartcli) { $config.smartcli = @($smartcli) }
    if (Test-Path -LiteralPath $winappExe) { $config.winapp = @($winappExe) }
    $config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding utf8
} else {
    Write-Output 'Existing config.local.json preserved. Add optional adapter paths explicitly if you enabled another component.'
}
& $pythonExe -m rdc_operator --config $configPath --state (Join-Path $InstallRoot '.rdc-state') doctor
if ($LASTEXITCODE -ne 0) { throw 'Doctor failed' }
Write-Output 'Installed locally. No login, public listener, scheduled task, or global PATH change was created.'

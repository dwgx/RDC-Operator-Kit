param([string]$EvidencePath = (Join-Path $PSScriptRoot '../evidence/gui-fixture.json'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'RDC Operator Kit — Desktop Test Fixture'
$form.Name = 'RdcOperatorFixture'
$form.ClientSize = New-Object System.Drawing.Size(680, 360)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 248, 254)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$title = New-Object System.Windows.Forms.Label
$title.Text = 'RDC Operator Kit'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 22, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(28, 24)
$title.Size = New-Object System.Drawing.Size(610, 45)
$form.Controls.Add($title)
$caption = New-Object System.Windows.Forms.Label
$caption.Text = 'Owned test window · observe → act → verify'
$caption.Location = New-Object System.Drawing.Point(30, 77)
$caption.Size = New-Object System.Drawing.Size(610, 30)
$form.Controls.Add($caption)
$fixtureInputBox = New-Object System.Windows.Forms.TextBox
$fixtureInputBox.Name = 'FixtureInput'
$fixtureInputBox.AccessibleName = 'Fixture input'
$fixtureInputBox.Location = New-Object System.Drawing.Point(30, 125)
$fixtureInputBox.Size = New-Object System.Drawing.Size(610, 35)
$form.Controls.Add($fixtureInputBox)
$apply = New-Object System.Windows.Forms.Button
$apply.Name = 'ApplyValueButton'
$apply.Text = 'Apply value'
$apply.Location = New-Object System.Drawing.Point(30, 180)
$apply.Size = New-Object System.Drawing.Size(180, 42)
$form.Controls.Add($apply)
$increment = New-Object System.Windows.Forms.Button
$increment.Name = 'IncrementButton'
$increment.Text = 'Increment'
$increment.Location = New-Object System.Drawing.Point(225, 180)
$increment.Size = New-Object System.Drawing.Size(180, 42)
$form.Controls.Add($increment)
$close = New-Object System.Windows.Forms.Button
$close.Name = 'CloseFixtureButton'
$close.Text = 'Close fixture'
$close.Location = New-Object System.Drawing.Point(420, 180)
$close.Size = New-Object System.Drawing.Size(220, 42)
$form.Controls.Add($close)
$status = New-Object System.Windows.Forms.Label
$status.Name = 'FixtureStatus'
$status.Text = 'Ready · count 0'
$status.Location = New-Object System.Drawing.Point(30, 247)
$status.Size = New-Object System.Drawing.Size(610, 72)
$form.Controls.Add($status)
$script:count = 0
$script:applied = ''
$script:events = @()
function Write-Witness([string]$eventName) {
    $script:events += $eventName
    $record = @{ pid = $PID; hwnd = $form.Handle.ToInt64(); count = $script:count;
        input = $fixtureInputBox.Text; applied = $script:applied; last_event = $eventName;
        events = $script:events; utc = [DateTime]::UtcNow.ToString('o') }
    $parent = Split-Path -Parent $EvidencePath
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $temporary = "$EvidencePath.tmp"
    [IO.File]::WriteAllText($temporary, ($record | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $EvidencePath -Force
}
$apply.Add_Click({ $script:applied = $fixtureInputBox.Text; $status.Text = "Applied: $script:applied · count $script:count"; Write-Witness 'apply' })
$increment.Add_Click({ $script:count++; $status.Text = "Applied: $script:applied · count $script:count"; Write-Witness 'increment' })
$fixtureInputBox.Add_TextChanged({ Write-Witness 'text-changed' })
$close.Add_Click({ $form.Close() })
$form.Add_Shown({ Write-Witness 'ready'; Write-Output "GUI_READY pid=$PID hwnd=$($form.Handle.ToInt64())" })
$form.Add_FormClosed({ Write-Witness 'closed' })
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1800000
$timer.Add_Tick({ $form.Close() })
$timer.Start()
try { [System.Windows.Forms.Application]::Run($form) }
finally { $timer.Dispose(); $form.Dispose() }

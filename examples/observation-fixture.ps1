param([Parameter(Mandatory=$true)][string]$EvidencePath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'RDC Operator Kit — Observation Fixture'
$form.Name = 'RdcObservationFixture'
$form.ClientSize = New-Object System.Drawing.Size(740, 420)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$script:nonce = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$script:actionCount = 0
$script:frameSeq = 0
$script:pulsing = $false
$script:owned = $null
$title = New-Object System.Windows.Forms.Label
$title.Text = 'Observation Lab'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 24, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(28, 24)
$title.Size = New-Object System.Drawing.Size(680, 46)
$form.Controls.Add($title)
$identityLabel = New-Object System.Windows.Forms.Label
$identityLabel.Text = "Fixture nonce: $script:nonce"
$identityLabel.Name = 'FixtureNonce'
$identityLabel.Location = New-Object System.Drawing.Point(30, 85)
$identityLabel.Size = New-Object System.Drawing.Size(680, 32)
$form.Controls.Add($identityLabel)
$stateLabel = New-Object System.Windows.Forms.Label
$stateLabel.Name = 'FrameState'
$stateLabel.Location = New-Object System.Drawing.Point(30, 137)
$stateLabel.Size = New-Object System.Drawing.Size(680, 70)
$stateLabel.Font = New-Object System.Drawing.Font('Segoe UI', 19, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($stateLabel)
function Add-FixtureButton([string]$name, [string]$text, [int]$left, [int]$top) {
    $button = New-Object System.Windows.Forms.Button
    $button.Name = $name
    $button.Text = $text
    $button.Location = New-Object System.Drawing.Point($left, $top)
    $button.Size = New-Object System.Drawing.Size(325, 48)
    $form.Controls.Add($button)
    return $button
}
$next = Add-FixtureButton 'NextFrameButton' 'Advance one frame' 30 230
$pulseButton = Add-FixtureButton 'PulseButton' 'Toggle animation' 385 230
$ownedButton = Add-FixtureButton 'OwnedDialogButton' 'Show owned dialog' 30 300
$close = Add-FixtureButton 'CloseObservationButton' 'Close observation lab' 385 300
function Paint-State {
    $stateLabel.Text = "Action count: $script:actionCount`nFrame sequence: $script:frameSeq"
    if (($script:frameSeq % 2) -eq 0) {
        $form.BackColor = [System.Drawing.Color]::FromArgb(219, 234, 254)
    } else {
        $form.BackColor = [System.Drawing.Color]::FromArgb(254, 215, 170)
    }
    $form.Invalidate()
}
function Write-Witness([string]$eventName) {
    $ownedHandle = 0
    if ($null -ne $script:owned -and !$script:owned.IsDisposed) { $ownedHandle = $script:owned.Handle.ToInt64() }
    $record = @{ pid=$PID; hwnd=$form.Handle.ToInt64(); nonce=$script:nonce;
        action_count=$script:actionCount; frame_seq=$script:frameSeq; pulsing=$script:pulsing;
        owned_hwnd=$ownedHandle; last_event=$eventName; utc=[DateTime]::UtcNow.ToString('o') }
    New-Item -ItemType Directory -Path (Split-Path -Parent $EvidencePath) -Force | Out-Null
    $temporary = "$EvidencePath.tmp"
    [IO.File]::WriteAllText($temporary, ($record | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $EvidencePath -Force
}
$next.Add_Click({ $script:actionCount++; $script:frameSeq++; Paint-State; Write-Witness 'advance' })
$pulseButton.Add_Click({ $script:pulsing = !$script:pulsing; Write-Witness 'toggle-animation' })
$ownedButton.Add_Click({
    if ($null -eq $script:owned -or $script:owned.IsDisposed) {
        $script:owned = New-Object System.Windows.Forms.Form
        $script:owned.Text = 'Observation Lab — Owned Dialog'
        $script:owned.ClientSize = New-Object System.Drawing.Size(340, 150)
        $dialogLabel = New-Object System.Windows.Forms.Label
        $dialogLabel.Text = 'This is a second owned window.'
        $dialogLabel.Dock = [System.Windows.Forms.DockStyle]::Fill
        $dialogLabel.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
        $script:owned.Controls.Add($dialogLabel)
        $script:owned.Show($form)
    }
    Write-Witness 'owned-dialog'
})
$close.Add_Click({ $form.Close() })
$form.Add_Shown({ Paint-State; Write-Witness 'ready'; Write-Output "OBSERVATION_READY pid=$PID hwnd=$($form.Handle.ToInt64())" })
$form.Add_FormClosed({ Write-Witness 'closed' })
$pulseTimer = New-Object System.Windows.Forms.Timer
$pulseTimer.Interval = 250
$pulseTimer.Add_Tick({ if ($script:pulsing) { $script:frameSeq++; Paint-State; Write-Witness 'pulse' } })
$pulseTimer.Start()
$expiryTimer = New-Object System.Windows.Forms.Timer
$expiryTimer.Interval = 900000
$expiryTimer.Add_Tick({ $form.Close() })
$expiryTimer.Start()
try { [System.Windows.Forms.Application]::Run($form) }
finally {
    $pulseTimer.Dispose(); $expiryTimer.Dispose()
    if ($null -ne $script:owned) { $script:owned.Dispose() }
    $form.Dispose()
}

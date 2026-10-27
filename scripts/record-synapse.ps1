# Record Razer Synapse's USB traffic to the Tartarus Pro (1532:0244), one capture per
# Synapse action, for working out the profile-LED and analog commands on the Mac.
# Runs on the Windows PC, in an administrator PowerShell, with Wireshark installed
# (USBPcap ticked in its installer, then a reboot):
#   powershell -ExecutionPolicy Bypass -File .\record-synapse.ps1
# It only listens: nothing is sent to the keypad. Captures, notes.txt and a zip end up
# on the Desktop.
param(
    [string]$WiresharkDir = "$env:ProgramFiles\Wireshark",
    [string]$USBPcapCmd = "$env:ProgramFiles\USBPcap\USBPcapCMD.exe",
    [int]$LeadSeconds = 10,
    [int]$TailSeconds = 10
)

# Native tools write warnings to stderr (e.g. the last packet of a stopped capture is cut
# short); with 'Stop' Windows PowerShell would turn those into errors.
$ErrorActionPreference = 'Continue'
$Tshark = Join-Path $WiresharkDir 'tshark.exe'
$LedPrompt = 'Which profile LEDs are lit? left/middle/right as 1/0, e.g. 100'

function Assert-Setup {
    $identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this from an administrator PowerShell (USBPcap needs it).'
    }
    foreach ($exe in @($Tshark, $USBPcapCmd)) {
        if (-not (Test-Path $exe)) {
            throw "Not found: $exe. Install Wireshark with the USBPcap option ticked, then reboot."
        }
    }
}

function Read-Line($Prompt) {
    # Drop anything typed while the console wasn't asking (e.g. keypad presses).
    try { $Host.UI.RawUI.FlushInputBuffer() } catch {}
    Read-Host $Prompt
}

function Wait-Countdown($Seconds, $Label) {
    for ($i = $Seconds; $i -gt 0; $i--) {
        Write-Host -NoNewline "`r  $Label $i s   "
        Start-Sleep -Seconds 1
    }
    Write-Host "`r  $Label done.          "
}

function Start-Capture($Hub, $OutFile, [string[]]$Filter) {
    # Start-Process joins the arguments without quoting, so quote the path ourselves.
    $cmdArgs = @('-d', $Hub, '-o', "`"$OutFile`"", '--inject-descriptors') + $Filter
    Start-Process -FilePath $USBPcapCmd -ArgumentList $cmdArgs -WindowStyle Hidden -PassThru
}

function Stop-Capture($Process) {
    if ($Process -and -not $Process.HasExited) { Stop-Process -Id $Process.Id -Force }
    Start-Sleep -Milliseconds 500  # let the file handle go
}

function Get-FrameCount($File, $Filter) {
    $tsharkArgs = @('-r', $File, '-T', 'fields', '-e', 'frame.number')
    if ($Filter) { $tsharkArgs += @('-Y', $Filter) }
    @(& $Tshark @tsharkArgs 2>$null | Where-Object { $_ }).Count
}

# Capture a few seconds from each root hub with descriptors injected, and look for the
# keypad's device descriptor to learn its hub and device address.
function Find-Keypad {
    $hubs = @(& $USBPcapCmd --extcap-interfaces 2>$null |
        Select-String -Pattern 'value=(\\\\\.\\USBPcap\d+)' |
        ForEach-Object { $_.Matches[0].Groups[1].Value })
    if ($hubs.Count -eq 0) { $hubs = 1..10 | ForEach-Object { "\\.\USBPcap$_" } }
    $probe = Join-Path $env:TEMP 'tartarus-probe.pcap'
    foreach ($hub in $hubs) {
        Write-Host "  Checking $hub ..."
        Remove-Item $probe -ErrorAction SilentlyContinue
        $p = Start-Capture $hub $probe @('-A')
        Start-Sleep -Seconds 3
        Stop-Capture $p
        if (-not (Test-Path $probe)) { continue }
        $address = & $Tshark -r $probe -Y 'usb.idVendor == 0x1532 && usb.idProduct == 0x0244' `
            -T fields -e usb.device_address 2>$null | Where-Object { $_ } | Select-Object -First 1
        if ($address) { return @{ Hub = $hub; Address = [int]$address } }
    }
    throw 'Tartarus Pro (1532:0244) not found on any USB root hub. Is it plugged into this PC?'
}

function Add-Note($Line) {
    Add-Content -Path (Join-Path $OutDir 'notes.txt') -Value $Line
}

# A step is a hashtable: Name, Action, and optionally Prep (shown before recording),
# Mode ('enter' by default: you press Enter once done; 'timed' and 'idle' run for
# Seconds), Ask (a question for notes.txt) and Optional (a yes/no question to skip it).
function Invoke-Step($Step) {
    Write-Host ''
    Write-Host "=== $($Step.Name) ===" -ForegroundColor Cyan
    if ($Step.Optional -and (Read-Line "  $($Step.Optional) (y/N)") -notmatch '^[yY]') {
        Add-Note "$($Step.Name) | skipped"
        return
    }
    if ($Step.Prep) { Write-Host "  Prepare: $($Step.Prep)" }
    Write-Host "  Then: $($Step.Action)"
    $null = Read-Line '  Press Enter to start recording (then hands off until told)'

    $file = Join-Path $OutDir "$($Step.Name).pcap"
    while ($true) {
        Remove-Item $file -ErrorAction SilentlyContinue
        $p = Start-Capture $Keypad.Hub $file @('--devices', "$($Keypad.Address)")
        try {
            $clock = [Diagnostics.Stopwatch]::StartNew()
            Wait-Countdown $LeadSeconds 'Recording, hands off:'
            $go = $clock.Elapsed.TotalSeconds
            if ($Step.Mode -eq 'idle') {
                Wait-Countdown $Step.Seconds 'Idle, hands off:'
            } else {
                [console]::Beep(880, 200)
                Write-Host "  DO NOW: $($Step.Action)" -ForegroundColor Yellow
                if ($Step.Mode -eq 'timed') {
                    Wait-Countdown $Step.Seconds 'Time left:'
                } else {
                    $null = Read-Line '  Done? Come back here and press Enter'
                }
            }
            $done = $clock.Elapsed.TotalSeconds
            Wait-Countdown $TailSeconds 'Hands off:'
            $exitedEarly = $p.HasExited
        } finally {
            Stop-Capture $p
        }

        $total = if (Test-Path $file) { Get-FrameCount $file $null } else { 0 }
        $hid = if ($total) { Get-FrameCount $file 'usb.bmRequestType == 0x21' } else { 0 }
        Write-Host "  Captured $total packets, $hid host-to-keypad HID requests."
        if ($exitedEarly -or $total -eq 0) {
            Write-Host '  WARNING: the capture stopped early or is empty. Redo it.' -ForegroundColor Red
        }
        if ((Read-Line '  Enter = keep, r = redo') -notmatch '^[rR]') { break }
    }

    $note = if ($Step.Ask) { Read-Line "  $($Step.Ask)" } else { '' }
    Add-Note ('{0}.pcap | {1} | action from +{2:N1}s to +{3:N1}s | {4}' -f
        $Step.Name, $Step.Action, $go, $done, $note)
}

Assert-Setup
Write-Host 'Looking for the Tartarus Pro...'
$Keypad = Find-Keypad
Write-Host "Found it on $($Keypad.Hub), device address $($Keypad.Address)." -ForegroundColor Green
Write-Host 'Do not unplug the keypad until the end: Windows may give it a new address.'

$OutDir = Join-Path ([Environment]::GetFolderPath('Desktop')) ("tartarus-captures-" + (Get-Date -Format 'yyyyMMdd-HHmm'))
New-Item -ItemType Directory -Path $OutDir | Out-Null
$synapse = Read-Line 'Synapse version (Synapse > Settings > About, e.g. "Synapse 4 4.0.xxx")'
Add-Note "Recorded $(Get-Date -Format 's') | $synapse | $(& $Tshark --version | Select-Object -First 1)"
Add-Note "Keypad on $($Keypad.Hub), device address $($Keypad.Address)"
Add-Note "Each capture: $LeadSeconds s idle, the action, $TailSeconds s idle. Times are from capture start."
Add-Note ''

Write-Host ''
Write-Host '--- Calibration ---' -ForegroundColor Magenta
$steps = @(
    @{ Name = '00-baseline-idle'; Mode = 'idle'; Seconds = 60; Action = 'Nothing, Synapse open and idle.'
       Prep = 'Synapse open. Lighting effect Static, Chroma Connect / app integrations off.' }
    @{ Name = '01-lighting-static-red'; Action = 'Set the Static colour to pure red (FF0000).'
       Prep = 'Open the Tartarus Pro lighting page, effect Static, colour anything but red.' }
    @{ Name = '02-lighting-brightness-50'; Action = 'Set the lighting brightness to 50%.'
       Prep = 'Stay on the lighting page, brightness anything but 50%.' }
    @{ Name = '03-synapse-start'; Optional = 'Record Synapse starting up (captures its init commands)?'
       Prep = 'Quit Synapse completely (tray icon > Exit; check Task Manager).'
       Action = 'Start Synapse and wait until it has fully loaded and the keypad lighting is back.' }
)
foreach ($s in $steps) { Invoke-Step $s }

Write-Host ''
Write-Host '--- Profile LEDs ---' -ForegroundColor Magenta
Write-Host '  Prepare: create profiles for the Tartarus Pro until you have 8, or as many as Synapse'
Write-Host '  allows. Leave their bindings and lighting identical. Make profile 1 active.'
$answer = Read-Line 'How many profiles are there (2-8)? [8]'
$count = if ($answer -match '^[2-8]$') { [int]$answer } else { 8 }
Add-Note "Profile 1 at start | $(Read-Line "With profile 1 active: $LedPrompt")"
for ($i = 1; $i -le $count; $i++) {
    $next = ($i % $count) + 1
    Invoke-Step @{ Name = '{0:D2}-profile-{1}-to-{2}' -f (9 + $i), $i, $next
        Prep = "Profile $i active, Synapse's profile selector at hand."
        Action = "Switch to profile $next in Synapse."; Ask = $LedPrompt }
}
$steps = @(
    @{ Name = '18-profile-reselect'; Optional = 'Re-select the already active profile (optional)?'
       Action = 'Select the profile that is already active again.'; Ask = $LedPrompt }
    @{ Name = '19-profile-indicator-setting'; Optional = 'Does Synapse have a setting for the profile LEDs/indicator?'
       Action = 'Change that setting once.'; Ask = 'What did you change, and which LEDs are lit now?' }
    @{ Name = '19b-profile-switch-by-key'; Optional = 'Can a keypad key switch profiles?'
       Action = 'Switch profile once with that key.'; Ask = "Which profile now? $LedPrompt" }
)
foreach ($s in $steps) { Invoke-Step $s }

Write-Host ''
Write-Host '--- Analog (stage 2) ---' -ForegroundColor Magenta
$valuePrompt = 'Value(s) Synapse shows now, and its exact wording for the setting'
$pressPrep = 'Click on an empty Notepad window so the key presses land there.'
$press = 'Slowly press key 01 halfway, hold 3 s, press fully, hold 3 s, release slowly. Repeat once.'
$steps = @(
    @{ Name = '20-actuation-key01-min'; Ask = $valuePrompt
       Prep = 'Open the actuation setting for key 01 (active profile).'
       Action = 'Set key 01 actuation to the minimum (shallowest), and apply/save if needed.' }
    @{ Name = '21-actuation-key01-max'; Action = 'Set key 01 actuation to the maximum.'; Ask = $valuePrompt }
    @{ Name = '22-actuation-key01-mid'; Action = 'Set key 01 actuation to a middle value.'; Ask = $valuePrompt }
    @{ Name = '23-actuation-all-keys'; Optional = 'Can Synapse set the actuation for all keys at once?'
       Action = 'Change the actuation for all keys at once.'; Ask = $valuePrompt }
    @{ Name = '24-dual-actuation-on-key01'; Action = 'Turn on dual-step / second actuation for key 01.'
       Ask = 'First and second actuation points shown, and the setting name' }
    @{ Name = '25-second-point-key01-change'; Action = "Move key 01's second actuation point to another value."
       Ask = 'Old and new value' }
    @{ Name = '26-press-key01-slow-dual-on'; Mode = 'timed'; Seconds = 25; Prep = $pressPrep; Action = $press }
    @{ Name = '27-dual-actuation-off-key01'; Prep = 'Back to key 01 in Synapse.'
       Action = 'Turn dual-step / second actuation off for key 01.'; Ask = $valuePrompt }
    @{ Name = '28-press-key01-slow-dual-off'; Mode = 'timed'; Seconds = 25; Prep = $pressPrep; Action = $press }
)
foreach ($s in $steps) { Invoke-Step $s }

$zip = "$OutDir.zip"
Compress-Archive -Path (Join-Path $OutDir '*') -DestinationPath $zip -Force
Write-Host ''
Write-Host "All done. Copy this one file to the Mac: $zip" -ForegroundColor Green

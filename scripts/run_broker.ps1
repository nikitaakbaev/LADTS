# PowerShell entry point for Windows.
$ErrorActionPreference = "Stop"
Set-Location -Path "$PSScriptRoot\..\"

$mosquitto = (Get-Command mosquitto.exe -ErrorAction SilentlyContinue).Source
if (-not $mosquitto) {
    $candidates = @(
        "$env:ProgramFiles\mosquitto\mosquitto.exe",
        "${env:ProgramFiles(x86)}\mosquitto\mosquitto.exe"
    )
    $mosquitto = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $mosquitto) {
    Write-Error "mosquitto.exe not found. Install via: winget install EclipseFoundation.Mosquitto"
    exit 1
}

& $mosquitto -c "mqtt\mosquitto.conf" -v

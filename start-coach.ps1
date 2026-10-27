$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$Host.UI.RawUI.WindowTitle = 'Garmin Coach - Running (keep this window open)'
try {
    $coachListener = @(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue)
    if ($coachListener.Count -gt 0) {
        Write-Host 'A service is already using the coach port. No second copy was started.'
        Write-Host 'If the coach is already online, send it a message in WeChat.'
    } else {
        Write-Host 'Starting your Garmin WeChat coach...'
        Write-Host 'Keep this window open and keep the computer awake and connected.'
        Write-Host 'To stop the coach, press Ctrl+C or close this window.'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'openclaw.ps1') gateway run --port 18789
        Write-Host "Coach stopped. Exit code: $LASTEXITCODE"
    }
} catch {
    Write-Host 'The coach could not start. Please report the error shown below.'
    Write-Host $_.Exception.Message
}
Read-Host 'Press Enter to close this window'

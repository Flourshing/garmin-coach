[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'
try {
    $garminLauncher = Join-Path $PSScriptRoot '.runtime\node_modules\openclaw\openclaw.mjs'
    $garminPattern = '(?i)(?:^|\s)"?' + [regex]::Escape($garminLauncher) + '"?\s+gateway\s+run(?:\s|$)'
    $garminProcesses = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -and ($_.CommandLine.Replace('/', '\') -match $garminPattern) })
    if ($garminProcesses.Count -eq 0) {
        Write-Host 'Garmin coach is already stopped.'
        exit 0
    }
    foreach ($garminProcess in $garminProcesses) {
        if ($PSCmdlet.ShouldProcess("Garmin gateway PID $($garminProcess.ProcessId)", 'Stop')) {
            if (Get-Process -Id $garminProcess.ProcessId -ErrorAction SilentlyContinue) {
                Stop-Process -Id $garminProcess.ProcessId -ErrorAction Stop
            }
        }
    }
    if ($WhatIfPreference) {
        Write-Host 'Preview complete. No process was stopped.'
    } else {
        Write-Host 'Garmin coach stopped. WeChat replies are now offline.'
    }
} catch {
    Write-Host 'Could not stop Garmin coach.'
    Write-Host $_.Exception.Message
    exit 1
}

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$railwayStatusPath = Join-Path $PSScriptRoot '.private\railway-login-status.json'
try {
    @{ phase = 'awaiting_account_setup'; started_at = [DateTimeOffset]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $railwayStatusPath -Encoding UTF8
    $Host.UI.RawUI.WindowTitle = 'Garmin Coach - Railway sign-in (register first)'
    . (Join-Path $PSScriptRoot 'project-network.ps1')
    Write-Host 'Sign in or create your own Railway account in the browser.'
    Write-Host 'Use the free Trial only. Do not select a paid plan or enter a card.'
    Write-Host 'Do not send passwords, pairing codes or sign-in links in chat.'
    Write-Host ''
    Write-Host 'STEP 1: Finish signing in or registering on the Railway website first.'
    Write-Host 'STEP 2: Return here and press Enter. A NEW authorization page will open.'
    Write-Host 'STEP 3: Approve the Railway CLI on that NEW page within 5 minutes.'
    Start-Process -FilePath 'https://railway.com/login'
    Read-Host 'When the Railway website is signed in, press Enter to START authorization'
    $railwayExecutable = Join-Path $PSScriptRoot '.private\railway-cli\node_modules\@railway\cli\bin\railway.exe'
    do {
        @{ phase = 'awaiting_authorization'; started_at = [DateTimeOffset]::UtcNow.ToString('o') } |
            ConvertTo-Json | Set-Content -LiteralPath $railwayStatusPath -Encoding UTF8
        & $railwayExecutable login
        $railwayLoginExit = $LASTEXITCODE
        @{ phase = 'finished'; exit_code = $railwayLoginExit; finished_at = [DateTimeOffset]::UtcNow.ToString('o') } |
            ConvertTo-Json | Set-Content -LiteralPath $railwayStatusPath -Encoding UTF8
        Write-Host "Login command exit code: $railwayLoginExit"
        $railwayRetry = ''
        if ($railwayLoginExit -ne 0) {
            $railwayRetry = Read-Host 'If ready to try a NEW authorization page, type R; otherwise press Enter'
        }
    } while ($railwayRetry -eq 'R')
} catch {
    @{ phase = 'failed'; error_type = $_.Exception.GetType().Name } |
        ConvertTo-Json | Set-Content -LiteralPath $railwayStatusPath -Encoding UTF8
    Write-Host 'Login could not start. Please report the error shown in this window.'
    Write-Host $_.Exception.Message
} finally {
    Read-Host 'Press Enter to close this window'
}

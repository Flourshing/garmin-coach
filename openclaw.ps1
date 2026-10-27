$ErrorActionPreference = 'Stop'
$garminProject = $PSScriptRoot
# Node resolution order:
#   1. OPENCLAW_NODE  (explicit override)
#   2. node on PATH, if it satisfies openclaw's engine requirement
#   3. OPENCLAW_NODE_FALLBACKS (optional ;-separated candidate list)
function Get-GarminNodeMajorMinor($exe) {
    try {
        $raw = (& $exe --version 2>$null)
        if ($raw -match '^v(\d+)\.(\d+)\.(\d+)') {
            return [version]("{0}.{1}.{2}" -f $matches[1], $matches[2], $matches[3])
        }
    } catch { }
    return $null
}
function Test-GarminNodeVersion($exe) {
    if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { return $false }
    $v = Get-GarminNodeMajorMinor $exe
    if (-not $v) { return $false }
    # openclaw 2026.10.6 requires Node >=24.22.1 <25, or >=26.12.1
    if ($v.Major -eq 24) { return $v -ge [version]'24.22.1' }
    if ($v.Major -ge 26) { return $v -ge [version]'26.12.1' }
    return $false
}
$garminNode = $null
if (Test-GarminNodeVersion $env:OPENCLAW_NODE) {
    $garminNode = $env:OPENCLAW_NODE
}
if (-not $garminNode) {
    $garminOnPath = Get-Command node -ErrorAction SilentlyContinue
    if ($garminOnPath -and (Test-GarminNodeVersion $garminOnPath.Source)) {
        $garminNode = $garminOnPath.Source
    }
}
if (-not $garminNode -and $env:OPENCLAW_NODE_FALLBACKS) {
    foreach ($candidate in ($env:OPENCLAW_NODE_FALLBACKS -split ';')) {
        if (Test-GarminNodeVersion $candidate) { $garminNode = $candidate; break }
    }
}
if (-not $garminNode) {
    # Common local locations (Codex-bundled runtime, nvm, fnm) as a convenience.
    $garminCandidates = @(
        (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'),
        (Join-Path $env:USERPROFILE 'AppData\Roaming\nvm\current\node.exe'),
        (Join-Path $env:LOCALAPPDATA 'fnm_multishells\current\node.exe')
    )
    foreach ($candidate in $garminCandidates) {
        if (Test-GarminNodeVersion $candidate) { $garminNode = $candidate; break }
    }
}
if (-not $garminNode) {
    throw 'No suitable Node.js found. Install Node >=24.22.1 (<25) or >=26.12.1, or set OPENCLAW_NODE to its path.'
}
$garminGit = $env:OPENCLAW_GIT_DIR
if (-not $garminGit -or -not (Test-Path -LiteralPath $garminGit)) {
    $garminGit = ''
}
$garminPathParts = @()
if ($garminNode) { $garminPathParts += (Split-Path -Parent $garminNode) }
if ($garminGit) { $garminPathParts += $garminGit }
$garminPathParts += (Join-Path $garminProject '.runtime\node_modules\.bin')
$env:PATH = ($garminPathParts -join ';') + ';' + $env:PATH
$env:OPENCLAW_STATE_DIR = Join-Path $garminProject '.private\openclaw'
$env:OPENCLAW_CONFIG_PATH = Join-Path $env:OPENCLAW_STATE_DIR 'openclaw.json'
$env:OPENCLAW_WORKSPACE_DIR = Join-Path $garminProject '.private\coach-workspace'
$env:PYTHONIOENCODING = 'utf-8'
# Load the DeepSeek API key from the gitignored .private\.env.dsh file.
# Keep this block ASCII-only: openclaw.cmd runs under Windows PowerShell 5.1,
# which decodes BOM-less UTF-8 as ANSI and can mis-parse non-ASCII text.
$garminDshenv = Join-Path $garminProject '.private\.env.dsh'
if ((Test-Path -LiteralPath $garminDshenv) -and -not $env:DEEPSEEK_API_KEY) {
    $garminLine = (Get-Content -LiteralPath $garminDshenv -TotalCount 20 -ErrorAction SilentlyContinue) |
        ForEach-Object { $_.TrimStart([char]0xFEFF, [char]0x200B) } |
        Where-Object { $_ -match '^\s*DEEPSEEK_API_KEY\s*=' } | Select-Object -First 1
    if ($garminLine -and $garminLine -match '^\s*DEEPSEEK_API_KEY\s*=\s*(\S+)\s*$') {
        $garminValue = $Matches[1].Trim()
        # Accept only a real DeepSeek key: sk- followed by ASCII key characters.
        # This skips the Chinese placeholder text left in the template file.
        if ($garminValue -match '^sk-[A-Za-z0-9_-]{16,}$') {
            $env:DEEPSEEK_API_KEY = $garminValue
        }
    }
}
. (Join-Path $garminProject 'project-network.ps1')
$garminLauncher = Join-Path $garminProject '.runtime\node_modules\openclaw\openclaw.mjs'
if ($garminNode) {
    & $garminNode $garminLauncher @args
} else {
    & node $garminLauncher @args
}
exit $LASTEXITCODE

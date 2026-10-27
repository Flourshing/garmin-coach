# Use the user's existing Windows loopback HTTP proxy for this process only.
# Never import proxy credentials, remote proxy servers, PAC scripts, or system PATH.
$garminProxySource = 'process-environment'
if (-not $env:HTTPS_PROXY -and -not $env:HTTP_PROXY -and -not $env:ALL_PROXY) {
    $garminProxySource = 'none'
    if ($env:GARMIN_USE_WINDOWS_PROXY -ne '0') {
        $garminInternet = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
        if ($garminInternet.ProxyEnable -and $garminInternet.ProxyServer) {
            $garminProxyEntries = ([string]$garminInternet.ProxyServer) -split ';'
            $garminChosenProxy = $garminProxyEntries | Where-Object { $_ -match '^https=' } | Select-Object -First 1
            if (-not $garminChosenProxy) {
                $garminChosenProxy = $garminProxyEntries | Where-Object { $_ -notmatch '=' -or $_ -match '^http=' } | Select-Object -First 1
            }
            if ($garminChosenProxy) {
                $garminProxyEndpoint = $garminChosenProxy -replace '^https?=', ''
                if ($garminProxyEndpoint -notmatch '://') { $garminProxyEndpoint = 'http://' + $garminProxyEndpoint }
                $garminProxyUri = $null
                if ([uri]::TryCreate($garminProxyEndpoint, [UriKind]::Absolute, [ref]$garminProxyUri) -and
                    $garminProxyUri.Scheme -eq 'http' -and $garminProxyUri.IsLoopback -and
                    -not $garminProxyUri.UserInfo -and $garminProxyUri.Port -gt 0) {
                    $env:HTTPS_PROXY = $garminProxyEndpoint
                    $env:HTTP_PROXY = $garminProxyEndpoint
                    $garminProxySource = 'windows-loopback'
                }
            }
        }
    }
}
if ($env:HTTPS_PROXY -or $env:HTTP_PROXY -or $env:ALL_PROXY) {
    $env:NODE_USE_ENV_PROXY = '1'
    # Local tool traffic, Garmin China and WeChat keep their direct route.
    $garminNoProxyDefaults = 'localhost,127.0.0.1,::1,garmin.cn,.garmin.cn,garmin.com,.garmin.com,ilinkai.weixin.qq.com,.weixin.qq.com'
    $env:NO_PROXY = if ($env:NO_PROXY) { $env:NO_PROXY + ',' + $garminNoProxyDefaults } else { $garminNoProxyDefaults }
}

// One device-code initialization probe; do not print or retain any code or token.
try {
  const response = await fetch('https://auth.openai.com/api/accounts/deviceauth/usercode', {
    method: 'POST',
    headers: { 'content-type': 'application/json', originator: 'openclaw', 'user-agent': 'openclaw/2026.10.6' },
    body: JSON.stringify({ client_id: 'app_EMoamEEZ73f0CkXaXp7hrann' }),
    signal: AbortSignal.timeout(30000),
  });
  const data = await response.json().catch(() => ({}));
  console.log(JSON.stringify({
    http_status: response.status,
    error_code: typeof data.error?.code === 'string' ? data.error.code : null,
    device_code_available: Boolean(data.device_auth_id && (data.user_code || data.usercode)),
    credentials_saved: false,
  }));
} catch (error) {
  console.log(JSON.stringify({ network_probe: 'failed', error_type: error.name, error_code: error.cause?.code ?? null }));
  process.exitCode = 1;
}

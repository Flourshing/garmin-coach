"""Read model status, printing selected non-secret fields only."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
result = subprocess.run(
    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "openclaw.ps1"), "models", "status", "--json"],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
)
decoder = json.JSONDecoder()
data = None
for pos, char in enumerate(result.stdout):
    if char != "{":
        continue
    try:
        candidate, _ = decoder.raw_decode(result.stdout[pos:])
    except ValueError:
        continue
    if isinstance(candidate, dict) and "defaultModel" in candidate:
        data = candidate
        break
if data is None:
    print(json.dumps({"status": "unavailable", "exit_code": result.returncode}))
    raise SystemExit(1)
auth = data.get("auth", {})
safe = {
    "default_model": data.get("defaultModel"),
    "resolved_default": data.get("resolvedDefault"),
    "auth_provider_count": len(auth.get("providers", [])),
    "auth_keys": sorted(auth),
    "oauth_status": auth.get("oauth", {}).get("status"),
    "status_keys": sorted(data),
}
for key in ("runtime", "runtimes", "runtimeStatus", "routes"):
    value = data.get(key, auth.get(key))
    if isinstance(value, list):
        safe[key] = [{k: item.get(k) for k in ("provider", "runtime", "status", "authStatus", "runtimeStatus") if k in item}
                     for item in value if isinstance(item, dict)]
    elif isinstance(value, dict):
        safe[key] = {k: value.get(k) for k in ("provider", "runtime", "status", "authStatus", "runtimeStatus") if k in value}
print(json.dumps(safe, ensure_ascii=False))

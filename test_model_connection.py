"""Make one bounded model test; disclose no provider errors or credentials."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "openclaw.ps1"),
        "infer", "model", "run", "--local", "--agent", "main", "--model", "openai/gpt-6-astra",
        "--prompt", "只回复：连接成功。", "--thinking", "low", "--json"]
try:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
except subprocess.TimeoutExpired:
    print(json.dumps({"connection_test": "process_timeout", "delivery_requested": False}))
    raise SystemExit(1)
decoder = json.JSONDecoder()
data = None
for pos, char in enumerate(result.stdout):
    if char != "{":
        continue
    try:
        candidate, _ = decoder.raw_decode(result.stdout[pos:])
    except ValueError:
        continue
    if isinstance(candidate, dict) and any(k in candidate for k in ("result", "ok", "status", "payloads")):
        data = candidate
        break
safe = {"exit_code": result.returncode, "delivery_requested": False}
if data:
    safe["status"] = data.get("status")
    safe["ok"] = data.get("ok")
    error = data.get("error", {})
    if isinstance(error, dict):
        safe["error_kind"] = error.get("kind", error.get("type"))
        message = str(error.get("message", ""))[:2000]
        message = re.sub(r"https?://\S+", "[URL omitted]", message)
        message = re.sub(r"(?i)(bearer\s+|(?:token|secret|api[_-]?key)\s*[:=]\s*)\S+", r"\1[omitted]", message)
        message = re.sub(r"[A-Za-z0-9_+/=.-]{45,}", "[long value omitted]", message)
        safe["error_message_redacted"] = message[:600]
    payload = data.get("result", data)
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    agent = meta.get("agentMeta", {})
    safe["model"] = agent.get("model", payload.get("model"))
    safe["provider"] = agent.get("provider", payload.get("provider"))
    safe["harness"] = agent.get("harness")
    # Only this predetermined reply is exposed, never arbitrary text/error messages.
    safe["expected_reply_received"] = any(
        "连接成功" in item.get("text", "") for item in payload.get("payloads", []) if isinstance(item, dict)
    ) if isinstance(payload, dict) else False
    if isinstance(payload, dict):
        texts = [payload.get("text", ""), payload.get("final", "")]
        texts += [item.get("text", "") for item in payload.get("outputs", []) if isinstance(item, dict)]
        safe["expected_reply_received"] = safe["expected_reply_received"] or any("连接成功" in text for text in texts if isinstance(text, str))
else:
    safe["status"] = "no_json_result"
combined = (result.stderr + result.stdout).lower()
safe["diagnostics"] = [label for marker, label in (
    ("no api key", "missing_credential"), ("no credentials", "missing_credential"),
    ("missing auth", "missing_credential"), ("not authenticated", "missing_credential"),
    ("timeout", "timeout"), ("econnrefused", "gateway_unreachable"),
    ("not ready", "gateway_not_ready"), ("401", "http_401"), ("403", "http_403"),
    ("not available", "unavailable"), ("pairing required", "gateway_pairing_required"),
    ("native plugin companion changed", "plugin_admission_changed"),
    ("codex app-server startup aborted", "codex_startup_aborted"),
    ("unknown option", "cli_unknown_option"), ("unknown command", "cli_unknown_command"),
) if marker in combined]
(ROOT / ".private/model-test-status.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(safe, ensure_ascii=False))
raise SystemExit(result.returncode)

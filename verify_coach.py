"""Verify the actual coach tool loop; retain health output only in the private workspace."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
prompt = (
    "验证佳明教练的数据接入。当前用户本地日期为2026-10-23，时区Asia/Shanghai。"
    "请实际调用只读佳明MCP的get_health_summary工具查询最近7天，不要读取历史测试日志。"
    "根据工具返回的真实数据，用中文写一段不超过250字的恢复与训练建议，注明数据日期。"
    "不调用发送消息工具，不修改任何文件，不诊断疾病。"
    "如果工具不可用或查询失败，直接说明失败，禁止编造指标。"
)
args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "openclaw.ps1"),
        "agent", "--agent", "main", "--session-id", "garmin-coach-validation-20261023", "--message", prompt,
        "--thinking", "low", "--timeout", "180", "--json"]
process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
try:
    stdout, stderr = process.communicate(timeout=300)
except subprocess.TimeoutExpired:
    # Terminate only this test's own process tree; never stop unrelated Node/Codex processes.
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    print(json.dumps({"coach_test": "process_timeout"}))
    raise SystemExit(1)
decoder = json.JSONDecoder()
data = None
for pos, char in enumerate(stdout):
    if char != "{":
        continue
    try:
        candidate, _ = decoder.raw_decode(stdout[pos:])
    except ValueError:
        continue
    if isinstance(candidate, dict) and any(key in candidate for key in ("ok", "status", "result")):
        data = candidate
        break
safe = {"exit_code": process.returncode, "delivery_requested": False}
if data:
    payload = data.get("result", data)
    meta = payload.get("meta", {})
    agent_meta = meta.get("agentMeta", {})
    tools = payload.get("toolSummary", meta.get("toolSummary", {})).get("tools", [])
    ok = data.get("ok", data.get("status") == "ok" and not meta.get("error"))
    safe.update(ok=ok, status=data.get("status"), model=payload.get("model", agent_meta.get("model")), provider=payload.get("provider", agent_meta.get("provider")), tools=tools)
    safe["health_tool_called"] = any("health_summary" in name for name in tools)
    if ok:
        # This is the user's own health analysis, kept private and not sent to WeChat.
        report = payload.get("final") or "\n".join(item.get("text", "") for item in payload.get("payloads", []) if isinstance(item, dict))
        (ROOT / ".private/coach-first-report.md").write_text(report, encoding="utf-8")
        safe["report"] = report
    else:
        message = str(data.get("error", meta.get("error", {})).get("message", ""))
        message = re.sub(r"https?://\S+", "[URL omitted]", message)
        message = re.sub(r"[A-Za-z0-9_+/=.-]{45,}", "[long value omitted]", message)
        safe["error_message_redacted"] = message[:600]
else:
    safe["status"] = "no_json_result"
(ROOT / ".private/coach-test-status.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(safe, ensure_ascii=False))
raise SystemExit(process.returncode)

"""Inspect local WeChat setup and readiness without reading message contents."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def channel_state(payload):
    """An HTTP-ready gateway may still have no installed WeChat channel owner."""
    name = "openclaw-weixin"
    channel = payload.get("channels", {}).get(name, {})
    accounts = payload.get("channelAccounts", {}).get(name, [])
    if isinstance(accounts, dict):
        accounts = list(accounts.values())
    records = accounts or ([channel] if channel else [])
    return {
        "wechat_channel_registered": bool(channel or name in payload.get("channelOrder", [])),
        "wechat_channel_running": any(a.get("running") is True and a.get("enabled") is not False for a in records),
        "wechat_channel_error_present": any(bool(a.get("lastError")) for a in records),
    }


def runtime_channel_status():
    command = (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "openclaw.ps1")]
               if os.name == "nt" else ["openclaw"])
    output = subprocess.run(command + ["channels", "status", "--json"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    decoder = json.JSONDecoder()
    for index, char in enumerate(output.stdout):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output.stdout[index:])
        except ValueError:
            continue
        if isinstance(value, dict) and "channels" in value:
            return channel_state(value)
    raise RuntimeError("Channel status unavailable; raw output hidden.")


def main():
    state = ROOT / ".private/openclaw"
    index = state / "openclaw-weixin/accounts.json"
    result = {"bound_account_count": 0, "gateway_ready": False,
              "wechat_channel_registered": False, "wechat_channel_running": False,
              "actual_message_delivery_verified": False}
    try:
        accounts = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
        result["bound_account_count"] = len(accounts)
        result["account_records_present"] = all(
            (state / "openclaw-weixin/accounts" / (str(account) + ".json")).is_file()
            for account in accounts)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:18789/readyz", timeout=3) as response:
            result["gateway_ready"] = response.status == 200
        if result["gateway_ready"]:
            result.update(runtime_channel_status())
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False))
    return 0 if (result["bound_account_count"] and result["gateway_ready"]
                 and result["wechat_channel_registered"] and result["wechat_channel_running"]
                 and not result.get("wechat_channel_error_present")) else 1


if __name__ == "__main__":
    raise SystemExit(main())

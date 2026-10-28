"""Inspect local WeChat setup and readiness without reading message contents."""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    state = ROOT / ".private/openclaw"
    index = state / "openclaw-weixin/accounts.json"
    result = {"bound_account_count": 0, "gateway_ready": False,
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
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["bound_account_count"] and result["gateway_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

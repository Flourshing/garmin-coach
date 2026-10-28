"""Optional bounded model request. Never print keys, response text or raw errors."""
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description="发送一次最多 8 token 的模型连接测试，可能产生 API 费用")
    parser.add_argument("--run", action="store_true", help="明确执行模型请求")
    if not parser.parse_args().run:
        parser.print_help()
        return 0
    key = os.environ.get("DEEPSEEK_API_KEY")
    env = ROOT / ".private/.env.dsh"
    if not key and env.is_file():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            match = re.fullmatch(r"\s*DEEPSEEK_API_KEY\s*=\s*(sk-[A-Za-z0-9_-]{16,})\s*", line)
            if match:
                key = match.group(1)
                break
    if not key:
        print(json.dumps({"ok": False, "reason": "missing_key"}))
        return 1
    provider = json.loads((ROOT / "deploy/deepseek-provider.json").read_text(encoding="utf-8"))
    try:
        import httpx
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        with httpx.Client(proxy=proxy or None, timeout=30) as client:
            response = client.post(provider["baseUrl"].rstrip("/") + "/chat/completions",
                                   headers={"Authorization": f"Bearer {key}"},
                                   json={"model": provider["models"][0]["id"],
                                         "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8})
        print(json.dumps({"ok": response.is_success, "http_status": response.status_code}))
        return 0 if response.is_success else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

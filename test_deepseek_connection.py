"""只读验证 DeepSeek API key 与模型 id 是否可用。绝不打印 key。

复用 .private/.env.dsh 中的 DEEPSEEK_API_KEY，并读取本机回环代理（与网关一致），
只报告状态码和简短结果，不显示请求头、密钥或请求原文。
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".private" / ".env.dsh"
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = "deepseek-flash"


def load_key():
    if not ENV_FILE.is_file():
        raise SystemExit("缺少 .private/.env.dsh")
    raw = ENV_FILE.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for line in raw.decode("utf-8", "replace").replace("\r", "").splitlines():
        m = re.match(r"\s*DEEPSEEK_API_KEY\s*=\s*(.+)", line)
        value = m.group(1).strip() if m else ""
        if value.startswith("sk-") and not value.startswith("sk-在这里") and not value.startswith("sk-在此"):
            return value
    raise SystemExit("未在 .private/.env.dsh 中找到有效 DEEPSEEK_API_KEY（sk-...）")


PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


def main():
    key = load_key()
    payload = {
        "model": "deepseek-flash",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "stream": False,
    }
    try:
        import httpx
    except ImportError:
        raise SystemExit("本环境没有 httpx，请改用 .venv 的 python 运行。")

    proxies = None
    if PROXY and PROXY.startswith("http://"):
        proxies = {"http://": PROXY, "https://": PROXY}
    url = BASE.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(proxy=proxies, timeout=30.0) as client:
            resp = client.post(
                url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
        body = resp.text
        status = resp.status_code
        ok = resp.is_success
        snippet = ""
        if ok:
            try:
                usage = resp.json().get("usage", {})
                snippet = f"usage={usage}"
            except Exception:
                snippet = body[:120]
        else:
            snippet = body[:160].replace(key, "***")
        print(json.dumps({
            "ok": ok, "http_status": status, "proxy": bool(PROXY),
            "model": payload["model"], "detail": snippet,
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "proxy": bool(PROXY)},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
"""一键检查 DeepSeek 切换是否就绪。绝不打印密钥。

依次检查：
  1. .private/.env.dsh 是否有真实 DeepSeek 密钥
  2. 运行配置 openclaw.json 的模型/供应商是否为 DeepSeek
  3. 佳明只读凭证是否仍在（不影响模型，但影响教练能否取数）
只报告布尔状态与 HTTP 状态，不显示任何密钥或账号信息。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".private" / ".env.dsh"
CONFIG = ROOT / ".private" / "openclaw" / "openclaw.json"
TOKEN = ROOT / ".private" / "tokens" / "garmin_tokens.json"

KEY_RE = re.compile(r"^\s*DEEPSEEK_API_KEY\s*=\s*(sk-[A-Za-z0-9_\-]{16,})\s*$")


def read_key():
    if not ENV_FILE.is_file():
        return None
    raw = ENV_FILE.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for line in raw.decode("utf-8", "replace").replace("\r", "").splitlines():
        m = KEY_RE.match(line)
        if m:
            return m.group(1)
    return None


def main():
    checks = {}

    key = read_key()
    checks["1_deepseek_key_present"] = bool(key)
    if key:
        checks["1_deepseek_key_length"] = len(key)

    if CONFIG.is_file():
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        providers = list(cfg.get("models", {}).get("providers", {}).keys())
        primary = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
        checks["2_primary_model"] = primary
        checks["2_providers"] = providers
        checks["2_is_deepseek"] = (
            primary == "deepseek/deepseek-flash" and providers == ["deepseek"]
        )
        checks["2_mcp_servers"] = list(cfg.get("mcp", {}).get("servers", {}).keys())
        checks["2_openai_plugin_enabled"] = (
            cfg.get("plugins", {}).get("entries", {}).get("openai", {}).get("enabled")
        )
    else:
        checks["2_is_deepseek"] = False
        checks["2_error"] = "配置不存在"

    checks["3_garmin_token_present"] = TOKEN.is_file()

    ok = checks.get("1_deepseek_key_present") and checks.get("2_is_deepseek")
    checks["ready_for_live_test"] = bool(ok)
    print(json.dumps(checks, ensure_ascii=False, indent=2))

    if not checks.get("1_deepseek_key_present"):
        print("\n下一步：把真实 DeepSeek 密钥填入 .private\\.env.dsh 的 DEEPSEEK_API_KEY=")
    if not checks.get("3_garmin_token_present"):
        print("\n注意：未找到佳明登录凭证，教练无法读取数据（先跑 login.cmd）。")
    if ok and not checks.get("3_garmin_token_present"):
        print("\n模型已就绪；补上佳明登录后即可用微信实测。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
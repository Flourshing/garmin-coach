"""Prepare an isolated OpenClaw coach config; never print secrets."""
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

from garmin_service import atomic_json

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("OPENCLAW_STATE_DIR", ROOT / ".private" / "openclaw"))
WORKSPACE = Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", ROOT / ".private" / "coach-workspace"))
CONFIG = Path(os.environ.get("OPENCLAW_CONFIG_PATH", STATE / "openclaw.json"))


def prepare():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "coach").glob("*.md"):
        target = WORKSPACE / source.name
        if not target.exists():
            shutil.copyfile(source, target)
    config = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
    gateway = config.setdefault("gateway", {})
    gateway.setdefault("mode", "local")
    gateway.setdefault("bind", "loopback")
    gateway.setdefault("port", 18789)
    auth = gateway.setdefault("auth", {})
    auth.setdefault("mode", "token")
    auth.setdefault("token", secrets.token_urlsafe(32))
    if os.environ.get("GARMIN_CLOUD") == "1":
        if not os.environ.get("OPENCLAW_GATEWAY_TOKEN"):
            raise ValueError("云端需要先设置 OPENCLAW_GATEWAY_TOKEN。")
        gateway["bind"] = "lan"
        gateway["port"] = int(os.environ.get("PORT", "8080"))
        auth["token"] = {"source": "env", "provider": "default", "id": "OPENCLAW_GATEWAY_TOKEN"}
        origin = os.environ.get("OPENCLAW_PUBLIC_ORIGIN")
        if origin:
            if not origin.startswith("https://") or "*" in origin:
                raise ValueError("OPENCLAW_PUBLIC_ORIGIN 必须是具体的 HTTPS 地址。")
            gateway.setdefault("controlUi", {})["allowedOrigins"] = [origin.rstrip("/")]
        weixin = Path("/opt/openclaw/node_modules/@tencent-weixin/openclaw-weixin")
        if weixin.is_dir():
            plugins = config.setdefault("plugins", {})
            paths = plugins.setdefault("load", {}).setdefault("paths", [])
            if str(weixin) not in paths:
                paths.append(str(weixin))
            plugins.setdefault("entries", {}).setdefault("openclaw-weixin", {})["enabled"] = True
            allow = plugins.setdefault("allow", [])
            if "openclaw-weixin" not in allow:
                allow.append("openclaw-weixin")
        codex = Path("/opt/openclaw/node_modules/@openclaw/codex")
        if codex.is_dir():
            approved = json.loads((ROOT / "deploy/codex-restricted-settings.json").read_text(encoding="utf-8"))
            plugins = config.setdefault("plugins", {})
            paths = plugins.setdefault("load", {}).setdefault("paths", [])
            if str(codex) not in paths:
                paths.append(str(codex))
            plugins.setdefault("entries", {})["codex"] = {"enabled": False, "config": approved["config"]}
            allow = plugins.setdefault("allow", [])
            if "codex" not in allow:
                allow.append("codex")
    defaults = config.setdefault("agents", {}).setdefault("defaults", {})
    defaults.update(workspace=str(WORKSPACE.resolve()), userTimezone="Asia/Shanghai", skipBootstrap=True)
    defaults.setdefault("skills", [])
    defaults["model"] = {"primary": "deepseek/deepseek-flash"}
    defaults.setdefault("models", {}).setdefault("deepseek/deepseek-flash", {})["agentRuntime"] = {"id": "openclaw"}
    # DeepSeek uses an API key (from DEEPSEEK_API_KEY), not an OAuth profile,
    # so no ordered auth-profile entry is required here.
    config.setdefault("auth", {}).pop("order", None)
    allowed_plugins = ["memory-core", "openclaw-weixin"]
    if "codex" in config.setdefault("plugins", {}).get("entries", {}):
        allowed_plugins.append("codex")
    config["plugins"]["allow"] = allowed_plugins
    config.setdefault("models", {}).setdefault("providers", {})["deepseek"] = json.loads((ROOT / "deploy/deepseek-provider.json").read_text(encoding="utf-8"))
    # 彻底停用 OpenAI(GPT) 供应商与插件，不再保留 GPT 配置。
    config.setdefault("models", {}).setdefault("providers", {}).pop("openai", None)
    config.setdefault("plugins", {}).setdefault("entries", {})["openai"] = {"enabled": False}
    defaults.pop("modelPolicy", None)
    defaults.setdefault("heartbeat", {})["every"] = "0m"
    config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("memory-core", {}).setdefault("config", {}).setdefault("dreaming", {})["enabled"] = False
    config.setdefault("session", {})["dmScope"] = "per-account-channel-peer"
    config.setdefault("mcp", {}).setdefault("servers", {})["garmin-cn"] = {
        "command": sys.executable,
        "args": ["-X", "utf8", str(ROOT / "garmin_mcp_server.py")],
        "requestTimeoutMs": 120000,
        "toolFilter": {"include": ["get_health_summary", "get_recent_activities", "get_data_status"]},
        "codex": {"defaultToolsApprovalMode": "approve"},
    }
    config["tools"] = {
        "profile": "minimal",
        "alsoAllow": ["bundle-mcp", "group:fs", "group:memory", "message"],
        "deny": ["gateway", "exec", "process", "code_execution", "sessions_spawn", "subagents"],
        "fs": {"workspaceOnly": True},
        "elevated": {"enabled": False},
    }
    atomic_json(CONFIG, config)
    print("教练工作区、只读佳明 MCP 和本地网关配置已准备。密钥未显示。")


if __name__ == "__main__":
    prepare()

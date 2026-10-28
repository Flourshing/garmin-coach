"""Prepare an isolated OpenClaw coach config; never print secrets."""
import json
import os
import secrets
import shutil
import sys
from hashlib import sha256
from pathlib import Path

from garmin_service import atomic_json
from garmin_data import TOOL_NAMES

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("OPENCLAW_STATE_DIR", ROOT / ".private" / "openclaw"))
WORKSPACE = Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", ROOT / ".private" / "coach-workspace"))
CONFIG = Path(os.environ.get("OPENCLAW_CONFIG_PATH", STATE / "openclaw.json"))


def sync_workspace(templates, workspace):
    """Update managed rules while preserving the user's preferences and memory."""
    workspace.mkdir(parents=True, exist_ok=True)
    for source in templates.glob("*.md"):
        target = workspace / source.name
        if not target.exists():
            shutil.copyfile(source, target)
        elif source.name in {"AGENTS.md", "SOUL.md"} and target.read_bytes() != source.read_bytes():
            # Local rule edits remain recoverable; personal files are never overwritten.
            previous = target.read_bytes()
            backups = workspace / ".template-backups"
            backups.mkdir(exist_ok=True)
            backup = backups / f"{target.stem}-{sha256(previous).hexdigest()[:12]}.md"
            if not backup.exists():
                backup.write_bytes(previous)
            shutil.copyfile(source, target)


def prepare():
    sync_workspace(ROOT / "coach", WORKSPACE)
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
    # Preparation must not undo the operator's model choice or fallback chain.
    defaults.setdefault("model", {"primary": "deepseek/deepseek-flash"})
    defaults.setdefault("models", {}).setdefault("deepseek/deepseek-flash", {})["agentRuntime"] = {"id": "openclaw"}
    # Preserve subscription auth ordering and approved provider plugins.
    allowed_plugins = list(config.setdefault("plugins", {}).get("allow", []))
    for plugin in ["memory-core", "openclaw-weixin"]:
        if plugin not in allowed_plugins:
            allowed_plugins.append(plugin)
    if "codex" in config.setdefault("plugins", {}).get("entries", {}):
        if "codex" not in allowed_plugins:
            allowed_plugins.append("codex")
    config["plugins"]["allow"] = allowed_plugins
    config.setdefault("models", {}).setdefault("providers", {})["deepseek"] = json.loads((ROOT / "deploy/deepseek-provider.json").read_text(encoding="utf-8"))
    config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("openai", {"enabled": False})
    defaults.setdefault("heartbeat", {})["every"] = "0m"
    config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("memory-core", {}).setdefault("config", {}).setdefault("dreaming", {})["enabled"] = False
    config.setdefault("session", {})["dmScope"] = "per-account-channel-peer"
    config.setdefault("mcp", {}).setdefault("servers", {})["garmin-cn"] = {
        "command": sys.executable,
        "args": ["-X", "utf8", str(ROOT / "garmin_mcp_server.py")],
        "requestTimeoutMs": 120000,
        "toolFilter": {"include": list(TOOL_NAMES)},
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

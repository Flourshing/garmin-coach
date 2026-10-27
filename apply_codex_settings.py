"""Apply the explicitly approved private Codex configuration without exposing secrets."""
import json
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


def main():
    approved = json.loads((ROOT / "deploy/codex-restricted-settings.json").read_text(encoding="utf-8"))
    path = ROOT / ".private/openclaw/openclaw.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    entry = config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("codex", {})
    entry["config"] = approved["config"]
    # Keep the native component installed with the approved settings, but use the
    # documented embedded runtime for subscription auth on this Windows host.
    entry["enabled"] = False
    config.setdefault("agents", {}).setdefault("defaults", {}).setdefault("heartbeat", {})["every"] = "0m"
    defaults = config["agents"]["defaults"]
    defaults["model"] = {"primary": "openai/gpt-6-astra"}
    defaults.setdefault("models", {}).setdefault("openai/gpt-6-astra", {})["agentRuntime"] = {"id": "openclaw"}
    config.setdefault("auth", {}).setdefault("order", {})["openai"] = ["openai:garmin-plus"]
    config["plugins"]["allow"] = ["openai", "memory-core", "openclaw-weixin", "codex"]
    provider = json.loads((ROOT / "deploy/plus-provider.json").read_text(encoding="utf-8"))
    provider["request"] = {"proxy": {"mode": "env-proxy"}}
    config.setdefault("models", {}).setdefault("providers", {})["openai"] = provider
    config["plugins"]["entries"].setdefault("memory-core", {}).setdefault("config", {}).setdefault("dreaming", {})["enabled"] = False
    # Commit the approved restrictions and activation in the same write.
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    print("Approved isolation retained; embedded Plus runtime selected; gateway not started.")


if __name__ == "__main__":
    main()

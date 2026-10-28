"""Configure subscription GPT + DeepSeek without reading or moving credentials."""
import argparse
import json
import re
from hashlib import sha256

from garmin_service import atomic_json
from prepare_openclaw import CONFIG, ROOT, sync_workspace, WORKSPACE

DEEPSEEK = "deepseek/deepseek-flash"
DEFAULT_GPT = "openai/gpt-6-astra"


def configure(config, gpt_model=DEFAULT_GPT):
    if not re.fullmatch(r"openai/gpt-[A-Za-z0-9._-]+", gpt_model):
        raise ValueError("GPT model must be an exact openai/gpt-* model ref from your account catalog.")
    defaults = config.setdefault("agents", {}).setdefault("defaults", {})
    defaults["model"] = {"primary": gpt_model, "fallbacks": [DEEPSEEK]}
    defaults["modelSelectionScope"] = "session"
    models = defaults.setdefault("models", {})
    # Only one model owns each alias after changing the selected GPT model.
    for ref, settings in models.items():
        if ref != gpt_model and settings.get("alias") == "gpt":
            settings.pop("alias")
    for ref, alias in [(gpt_model, "gpt"), (DEEPSEEK, "dsh")]:
        settings = models.setdefault(ref, {})
        settings["alias"] = alias
        # The shared runtime preserves MCP/media behavior and cross-provider fallback.
        settings["agentRuntime"] = {"id": "openclaw"}
        # The two providers expose different reasoning ladders; use each one's valid default.
        settings.setdefault("params", {}).setdefault("thinking", "low" if alias == "gpt" else "off")
    policy = defaults.get("modelPolicy", {})
    if policy.get("allow"):
        policy["allow"] = list(dict.fromkeys([*policy["allow"], gpt_model, DEEPSEEK]))
    plugins = config.setdefault("plugins", {})
    plugins.setdefault("entries", {}).setdefault("openai", {})["enabled"] = True
    allow = plugins.setdefault("allow", [])
    if "openai" not in allow:
        allow.append("openai")
    providers = config.setdefault("models", {}).setdefault("providers", {})
    providers["deepseek"] = json.loads((ROOT / "deploy/deepseek-provider.json").read_text(encoding="utf-8"))
    # Force the subscription transport. Never fall through to OpenAI API billing.
    providers["openai"] = {
        "baseUrl": "https://chatgpt.com/backend-api/codex",
        "api": "openai-chatgpt-responses", "auth": "oauth", "models": [],
        "agentRuntime": {"id": "openclaw"},
    }
    # Model chat commands must work independently of the selected model being online.
    config.setdefault("commands", {})["text"] = True
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpt-model", default=DEFAULT_GPT,
                        help="Exact account model ref; default is a candidate until live verification.")
    args = parser.parse_args()
    if not CONFIG.is_file():
        parser.error("Run prepare_openclaw.py first.")
    raw = CONFIG.read_bytes()
    config = configure(json.loads(raw), args.gpt_model)
    backups = CONFIG.parent.parent / "config-backups"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / ("before-dual-model-" + sha256(raw).hexdigest()[:12] + ".json")
    if not backup.exists():
        backup.write_bytes(raw)
    atomic_json(CONFIG, config)
    sync_workspace(ROOT / "coach", WORKSPACE)
    print(json.dumps({"primary": args.gpt_model, "fallbacks": [DEEPSEEK],
                      "aliases": ["gpt", "dsh"], "subscription_login_and_live_check_required": True}))


if __name__ == "__main__":
    main()

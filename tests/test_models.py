import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from configure_models import configure, DEFAULT_GPT, DEEPSEEK
import prepare_openclaw as prep


class ModelConfigurationTests(unittest.TestCase):
    def test_subscription_route_fallback_alias_and_permissions(self):
        config = {"auth": {"order": {"openai": ["openai:test"]}},
                  "tools": {"deny": ["exec"], "fs": {"workspaceOnly": True}},
                  "agents": {"defaults": {"modelPolicy": {"allow": [DEEPSEEK]}}}}
        old = copy.deepcopy(config)
        configure(config)
        defaults = config["agents"]["defaults"]
        self.assertEqual(defaults["model"], {"primary": DEFAULT_GPT, "fallbacks": [DEEPSEEK]})
        self.assertEqual(defaults["models"][DEEPSEEK]["alias"], "dsh")
        self.assertEqual(defaults["models"][DEFAULT_GPT]["agentRuntime"]["id"], "openclaw")
        self.assertEqual(defaults["models"][DEFAULT_GPT]["params"]["thinking"], "low")
        self.assertEqual(defaults["models"][DEEPSEEK]["params"]["thinking"], "off")
        self.assertIn(DEFAULT_GPT, defaults["modelPolicy"]["allow"])
        self.assertEqual(config["auth"], old["auth"])
        self.assertEqual(config["tools"], old["tools"])
        self.assertEqual(config["models"]["providers"]["openai"]["auth"], "oauth")
        self.assertNotIn("apiKey", config["models"]["providers"]["openai"])

    def test_reselection_has_one_gpt_alias_and_is_idempotent(self):
        config = configure({})
        configure(config, "openai/gpt-6.1-sol")
        self.assertNotIn("alias", config["agents"]["defaults"]["models"][DEFAULT_GPT])
        before = copy.deepcopy(config)
        configure(config, "openai/gpt-6.1-sol")
        self.assertEqual(before, config)
        with self.assertRaises(ValueError):
            configure(config, "other/untrusted")
        self.assertEqual(before, config)

    def test_preparation_preserves_model_auth_and_enabled_provider(self):
        with tempfile.TemporaryDirectory(dir=prep.ROOT) as folder:
            base = Path(folder)
            config_path = base / "state/openclaw.json"
            config_path.parent.mkdir()
            config = configure({"auth": {"order": {"openai": ["openai:test"]}}})
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with patch.object(prep, "CONFIG", config_path), patch.object(prep, "WORKSPACE", base / "workspace"), patch.dict("os.environ", {"GARMIN_CLOUD": "0"}):
                prep.prepare()
            after = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["auth"], after["auth"])
            self.assertEqual(config["agents"]["defaults"]["model"], after["agents"]["defaults"]["model"])
            self.assertEqual(config["models"]["providers"]["openai"], after["models"]["providers"]["openai"])
            self.assertTrue(after["plugins"]["entries"]["openai"]["enabled"])
            self.assertIn("openai", after["plugins"]["allow"])


if __name__ == "__main__":
    unittest.main()

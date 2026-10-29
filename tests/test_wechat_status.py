import unittest

from scripts.diagnostics.check_wechat import channel_state


class WechatStatusTests(unittest.TestCase):
    def test_http_ready_but_no_plugin_is_not_healthy(self):
        result = channel_state({"channels": {}, "channelOrder": [], "channelAccounts": {}})
        self.assertFalse(result["wechat_channel_registered"])
        self.assertFalse(result["wechat_channel_running"])

    def test_bound_but_stopped_account_is_not_running(self):
        result = channel_state({"channelOrder": ["openclaw-weixin"], "channelAccounts": {
            "openclaw-weixin": [{"configured": True, "running": False, "lastError": "private message"}]}})
        self.assertTrue(result["wechat_channel_registered"])
        self.assertFalse(result["wechat_channel_running"])
        self.assertTrue(result["wechat_channel_error_present"])
        self.assertNotIn("private message", str(result))

    def test_running_account_with_no_connected_field(self):
        result = channel_state({"channels": {"openclaw-weixin": {"running": True}}, "channelAccounts": {
            "openclaw-weixin": [{"enabled": True, "configured": True, "running": True, "lastError": None}]}})
        self.assertTrue(result["wechat_channel_running"])
        self.assertFalse(result["wechat_channel_error_present"])


if __name__ == "__main__":
    unittest.main()

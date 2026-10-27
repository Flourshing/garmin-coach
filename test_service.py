import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import garmin_service as service
from test_collect import FakeGarmin


class ServiceTests(unittest.TestCase):
    def test_future_and_excessive_queries_do_not_log_in(self):
        with patch.object(service, "connection") as connect:
            for days, end in [(29, None), (True, None), (1, "2999-01-01")]:
                with self.assertRaises(ValueError):
                    service.health_summary(days, end)
            connect.assert_not_called()

    def test_cache_prevents_repeat_requests_and_has_freshness(self):
        with tempfile.TemporaryDirectory(dir=service.ROOT) as folder:
            with patch.object(service, "CACHE", Path(folder)), patch.object(service, "connection", return_value=FakeGarmin()) as connect:
                first = service.health_summary(1)
                second = service.health_summary(1)
                self.assertEqual(first["records"], second["records"])
                self.assertIsNotNone(datetime.fromisoformat(second["records"][0]["retrieved_at"]).tzinfo)
                self.assertEqual(connect.call_count, 1)

    def test_upstream_secrets_are_not_returned_in_error(self):
        def broken():
            raise RuntimeError("SECRET_TOKEN private URL")
        with self.assertRaises(ValueError) as raised:
            service.safe_call(broken)
        self.assertNotIn("SECRET_TOKEN", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

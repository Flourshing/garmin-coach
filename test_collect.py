import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import collect


class FakeGarmin:
    def get_stats(self, day):
        return {"totalSteps": 0, "restingHeartRate": 51, "averageStressLevel": -1,
                "displayName": "PRIVATE_NAME", "userProfileId": 12345}

    def get_sleep_data(self, day):
        return {"dailySleepDTO": {"sleepTimeSeconds": 27000,
                                  "sleepScores": {"overall": {"value": 82}}}}

    def get_hrv_data(self, day):
        return {"hrvSummary": {"lastNightAvg": 44, "status": "BALANCED"}}

    def get_activities_by_date(self, start, end):
        return [{"distance": 5000, "duration": 1800, "averageSpeed": 2.78,
                 "startLatitude": 31.2, "activityName": "PRIVATE_ROUTE"}]


class CollectorTests(unittest.TestCase):
    def test_connection_labels_exclude_login_secrets(self):
        region, label = collect.request_category(
            "https://sso.garmin.cn/portal/api/login?ticket=SECRET&username=PRIVATE"
        )
        self.assertEqual((region, label), ("cn", "web_credentials"))
        self.assertNotIn("SECRET", label)
        self.assertEqual(
            collect.request_category("https://sso.garmin.cn.example.org/portal/api/login"),
            ("other", "external_request"),
        )

    def test_only_requested_dates_and_necessary_metrics(self):
        rows = collect.collect(FakeGarmin(), 3, date(2026, 10, 22))
        self.assertEqual([r["date"] for r in rows], ["2026-10-20", "2026-10-21", "2026-10-22"])
        self.assertEqual(rows[-1]["sleep"]["hours"], 7.5)
        self.assertEqual(rows[-1]["daily"]["totalSteps"], 0)
        self.assertIsNone(rows[-1]["daily"]["averageStressLevel"])
        for secret in ["PRIVATE_NAME", "PRIVATE_ROUTE", "startLatitude", "userProfileId"]:
            self.assertNotIn(secret, json.dumps(rows))

    def test_missing_sleep_and_hrv_are_not_zero(self):
        class Missing(FakeGarmin):
            def get_sleep_data(self, day):
                return None

            def get_hrv_data(self, day):
                return None
        row = collect.collect(Missing(), 1, date(2026, 10, 22))[0]
        self.assertIsNone(row["sleep"]["hours"])
        self.assertIsNone(row["sleep"]["score"])
        self.assertEqual(row["hrv"], {})

    def test_partial_failure_does_not_expose_exception_contents(self):
        class Partial(FakeGarmin):
            def get_sleep_data(self, day):
                raise ValueError("SECRET_TOKEN_IN_SERVER_ERROR")
        row = collect.collect(Partial(), 1, date(2026, 10, 22))[0]
        self.assertEqual(row["unavailable"], {"sleep": "ValueError"})
        self.assertNotIn("SECRET_TOKEN", json.dumps(row))
        self.assertEqual(row["hrv"]["lastNightAvg"], 44)

    def test_rate_limit_stops_following_requests(self):
        class GarminConnectTooManyRequestsError(Exception):
            pass
        class Limited(FakeGarmin):
            def get_stats(self, day):
                raise GarminConnectTooManyRequestsError()

            def get_sleep_data(self, day):
                self.fail("must not make another request")
        with self.assertRaises(GarminConnectTooManyRequestsError):
            collect.collect(Limited(), 3, date(2026, 10, 22))

    def test_saved_file_has_timestamp_units_and_no_temporary_leftover(self):
        # Workspace-local temporary files avoid interacting with real account storage.
        with tempfile.TemporaryDirectory(dir=collect.ROOT) as folder:
            with patch.object(collect, "PRIVATE", Path(folder)):
                target = collect.save_records(collect.collect(FakeGarmin(), 1, date(2026, 10, 22)))
                bundle = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(bundle["timezone"], "Asia/Shanghai")
                self.assertTrue(bundle["collected_at"].endswith("+08:00"))
                self.assertEqual(bundle["records"][0]["units"]["distance"], "meters")
                self.assertFalse(target.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()

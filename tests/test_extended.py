import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import garmin_extended as extended
import garmin_service as service
from garmin_data import clean_data, sampled


class FakeAccount:
    def __init__(self):
        self.calls = []

    def get_sleep_data(self, day):
        self.calls.append("sleep")
        return {"dailySleepDTO": {"userProfilePK": 111222, "deepSleepSeconds": 0,
                                  "remSleepSeconds": None, "sleepTimeSeconds": 100,
                                  "sleepNeed": {"deviceId": 333444, "actual": 480}},
                "sleepHeartRate": [{"startGMT": n, "value": n+40} for n in range(20)]}

    def get_heart_rates(self, day):
        self.calls.append("heart_rate")
        return {"userProfileId": 111222, "heartRateValueDescriptors": [{"index": 0, "key": "timestamp"}],
                "heartRateValues": [[n, None if n == 3 else 50] for n in range(20)]}

    def get_training_status(self, day):
        self.calls.append("status")
        return {"map": {"333444": {"deviceId": 333444, "calendarDate": day,
                                     "acuteTrainingLoad": 0}}}

    def get_cycling_ftp(self):
        self.calls.append("ftp")
        return {"userProfilePK": 111222, "functionalThresholdPower": 186,
                "calendarDate": "2023-11-02", "isStale": True}

    def get_activity(self, aid):
        self.calls.append("summary")
        return {"activityName": "Evening run", "summaryDTO": {"distance": 1000, "averagePower": 200,
                "userProfileId": 111222, "startLatitude": 12.34}, "metadataDTO": {"hasPolyline": True}}

    def get_activity_details(self, aid):
        self.calls.append("samples")
        return {"metricDescriptors": [{"metricsIndex": 0, "key": "directHeartRate"},
                                      {"metricsIndex": 1, "key": "directLatitude"}],
                "activityDetailMetrics": [{"metrics": [60+n, 12.34]} for n in range(20)],
                "geoPolylineDTO": {"polyline": [{"lat": 12.34, "lon": 56.78} for _ in range(20)]}}

    def get_activity_splits(self, aid):
        raise RuntimeError("SECRET_TOKEN and private URL")

    def get_activity_hr_in_timezones(self, aid):
        self.calls.append("zones")
        return [{"zoneNumber": 1, "secsInZone": 0}]


class ExtendedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=service.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.data = patch.object(service, "DATA", Path(self.temp.name))
        self.data.start()
        self.addCleanup(self.data.stop)
        self.account = FakeAccount()
        self.connection = patch.object(service, "connection", return_value=self.account)
        self.connect = self.connection.start()
        self.addCleanup(self.connection.stop)

    def test_invalid_inputs_do_not_connect(self):
        calls = [lambda: extended.sleep_details("2999-01-01"),
                 lambda: extended.health_timeseries(metrics=["unsupported"]),
                 lambda: extended.health_timeseries(max_points=True),
                 lambda: extended.training_metrics(groups=[]),
                 lambda: extended.training_metrics(days=29),
                 lambda: extended.activity_details("../secret"),
                 lambda: extended.activity_details("12", sections=["delete"]),
                 lambda: extended.training_workouts(month=13),
                 lambda: extended.training_workouts(kind="calendar", workout_id="1")]
        for call in calls:
            with self.assertRaises(ValueError):
                call()
        self.connect.assert_not_called()

    def test_sleep_zero_null_ids_and_opt_in_series(self):
        data = extended.sleep_details("2026-10-26")
        value = data["data"]["sleep"]["value"]
        self.assertEqual(value["dailySleepDTO"]["deepSleepSeconds"], 0)
        self.assertIsNone(value["dailySleepDTO"]["remSleepSeconds"])
        self.assertNotIn("series", value)
        self.assertNotIn("111222", json.dumps(data))
        self.assertNotIn("333444", json.dumps(data))
        curves = extended.sleep_details("2026-10-26", True, 5)["data"]["sleep"]["value"]["series"]
        self.assertEqual(curves["sleepHeartRate"]["source_points"], 20)
        self.assertEqual(curves["sleepHeartRate"]["returned_points"], 5)
        self.assertEqual(self.account.calls, ["sleep"])

    def test_category_selection_cache_and_refresh(self):
        first = extended.health_timeseries("2026-10-26", ["heart_rate"], 4)
        extended.health_timeseries("2026-10-26", ["heart_rate"], 4)
        self.assertEqual(self.account.calls, ["heart_rate"])
        values = first["data"]["heart_rate"]["value"]["series"]["heartRateValues"]
        self.assertEqual((values["source_points"], values["returned_points"]), (20, 4))
        self.assertEqual(values["values"][0][0], 0)
        self.assertEqual(values["values"][-1][0], 19)
        extended.health_timeseries("2026-10-26", ["heart_rate"], 4, True)
        self.assertEqual(self.account.calls, ["heart_rate", "heart_rate"])

    def test_training_only_selected_groups_retains_stale_date(self):
        data = extended.training_metrics(["status", "cycling_ftp"], 1, "2026-10-26")
        self.assertEqual(self.account.calls, ["status", "ftp"])
        self.assertNotIn("333444", json.dumps(data))
        ftp = data["data"]["cycling_ftp"]["value"]
        self.assertTrue(ftp["isStale"])
        self.assertEqual(ftp["calendarDate"], "2023-11-02")

    def test_activity_location_opt_in_and_bounded_samples(self):
        data = extended.activity_details("12", ["summary", "samples"], max_points=5)
        self.assertEqual(self.account.calls, ["summary", "samples"])
        self.assertNotIn("12.34", json.dumps(data))
        self.assertNotIn("directLatitude", json.dumps(data))
        self.assertEqual(data["data"]["samples"]["value"]["samples"]["returned_points"], 5)
        explicit = extended.activity_details("12", ["samples"], True, 5)
        self.assertIn("directLatitude", json.dumps(explicit))
        self.assertEqual(explicit["data"]["samples"]["value"]["location"]["polyline"]["returned_points"], 5)

    def test_partial_failure_is_visible_but_sanitized(self):
        data = extended.activity_details("12", ["splits", "heart_rate_zones"])
        self.assertEqual(data["unavailable"], {"splits": "RuntimeError"})
        self.assertIn("heart_rate_zones", data["data"])
        self.assertNotIn("SECRET_TOKEN", json.dumps(data))

    def test_rate_limit_stops_following_sections(self):
        class GarminConnectTooManyRequestsError(Exception):
            pass
        with patch.object(self.account, "get_activity_splits", side_effect=GarminConnectTooManyRequestsError):
            with self.assertRaises(GarminConnectTooManyRequestsError):
                extended.activity_details("12", ["splits", "heart_rate_zones"])
        self.assertEqual(self.account.calls, [])

    def test_recursive_identity_and_secrets_filter(self):
        data = clean_data({"userId": 1, "deviceId": 2, "activityId": 3, "workoutId": 4,
                           "token": "SECRET", "nested": {"ownerId": 5, "id": 6},
                           "directLongitude": 1.234, "lat": 1.234, "lon": 5.678, "value": 0})
        self.assertEqual(data, {"activityId": 3, "workoutId": 4, "nested": {}, "value": 0})


if __name__ == "__main__":
    unittest.main()

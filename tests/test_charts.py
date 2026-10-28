import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import garmin_charts as charts
import garmin_service as service

BASE = 1792944000000


def envelope(key, value):
    return {"data": {key: {"retrieved_at": "2026-10-27T12:00:00+08:00", "value": value}}, "unavailable": {}}


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=service.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.patch_env = patch.dict("os.environ", {"OPENCLAW_WORKSPACE_DIR": str(self.workspace)})
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)

    def test_bad_arguments_do_not_fetch_or_write(self):
        with patch.object(service, "connection") as connect:
            for kwargs in [{"kind": "../../file"}, {"metrics": ["invented"]}, {"max_points": 2},
                           {"kind": "activity", "activity_id": "../../secret"},
                           {"date": "2999-01-01"}, {"kind": "trend", "days": 29}]:
                with self.assertRaises(ValueError):
                    charts.render_curve_chart(**kwargs)
            connect.assert_not_called()
        self.assertFalse(self.workspace.exists())

    def test_missing_data_does_not_generate_fake_chart(self):
        source = envelope("heart_rate", {"series": {"heartRateValues": {"values": [[BASE, None], [BASE+60000, -1]]}}})
        with patch.object(charts.extended, "health_timeseries", return_value=source):
            result = charts.render_curve_chart(date="2026-10-26")
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["missing_metrics"], ["heart_rate"])
        self.assertNotIn("image_path", result)
        self.assertFalse(self.workspace.exists())

    def test_real_png_local_attachment_and_sample_disclosure(self):
        meta = {"values": [[BASE, 60], [BASE+60000, None], [BASE+120000, 80]],
                "source_points": 1000, "sampled": True}
        source = envelope("heart_rate", {"series": {"heartRateValues": meta}})
        with patch.object(charts.extended, "health_timeseries", return_value=source) as fetch:
            result = charts.render_curve_chart(date="2026-10-26")
        fetch.assert_called_once_with("2026-10-26", ["heart_rate"], 1000, False)
        path = Path(result["image_path"])
        self.assertTrue(path.is_relative_to(self.workspace))
        self.assertEqual(result["media_line"], "MEDIA:"+path.as_posix())
        self.assertEqual(result["series"][0]["valid_points"], 2)
        self.assertTrue(result["series"][0]["sampled"])
        self.assertEqual(result["series"][0]["sample_mean"], 70)
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertGreaterEqual(image.width, 1000)
            image.verify()
        self.assertEqual(json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))["status"], "ok")

    def test_body_battery_status_column_not_plotted_as_value(self):
        source = envelope("body_battery", {"series": {"bodyBatteryValuesArray": {
            "values": [[BASE, "MEASURED", 0, 3], [BASE+60000, "MEASURED", 45, 3]]}}})
        series, missing = charts._health_series(source, ["body_battery"])
        self.assertFalse(missing)
        self.assertEqual(series[0]["y"], [0, 45])

    def test_gmt_conversion_and_sleep_stage_codes(self):
        source = envelope("sleep", {"series": {"sleepLevels": {"values": [
            {"startGMT": "2026-10-25T17:00:00", "endGMT": "2026-10-25T17:10:00", "activityLevel": 0},
            {"startGMT": "2026-10-25T17:10:00", "endGMT": "2026-10-25T17:20:00", "activityLevel": 2}]}}})
        series, missing = charts._sleep_series(source, ["stages"])
        self.assertFalse(missing)
        self.assertEqual(series[0]["segments"][0][0].isoformat(), "2026-10-26T01:00:00+08:00")
        self.assertEqual([s[2] for s in series[0]["segments"]], [0, 2])

    def test_pace_conversion_zero_speed_and_factor(self):
        source = envelope("samples", {"metric_descriptors": [
            {"key": "directSpeed", "unit": {"key": "mps", "factor": .1}},
            {"key": "directDoubleCadence", "unit": {"key": "stepsPerMinute"}}],
            "samples": {"values": [{"sumElapsedDuration": 0, "directSpeed": 2, "directDoubleCadence": 180},
                                    {"sumElapsedDuration": 60, "directSpeed": 0, "directDoubleCadence": 0},
                                    {"sumElapsedDuration": 120, "directSpeed": 4, "directDoubleCadence": 190}]}})
        source["data"]["summary"] = {"value": {"activity_type": {"typeKey": "running"}}}
        series, missing = charts._activity_series(source, ["pace", "cadence"])
        self.assertFalse(missing)
        self.assertAlmostEqual(series[0]["y"][0], 1000/2/60)
        self.assertIsNone(series[0]["y"][1])
        self.assertEqual(series[0]["x"], [0, 1, 2])
        self.assertEqual(series[1]["y"], [180, 0, 190])

    def test_trend_preserves_missing_day_and_converts_seconds(self):
        rows = [{"date": "2026-10-25", "sleep": {"deep_seconds": 3600}},
                {"date": "2026-10-26", "sleep": {"deep_seconds": None}}]
        series, missing = charts._trend_series({"records": rows}, ["deep_hours"])
        self.assertFalse(missing)
        self.assertEqual(series[0]["y"], [1, None])


if __name__ == "__main__":
    unittest.main()

"""Verify the real MCP protocol; --live additionally reads one day from Garmin."""
import argparse
import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from garmin_service import DATA, atomic_json
from garmin_data import TOOL_NAMES


async def verify(live=False, days=1, end_date=None):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", str(Path(__file__).with_name("garmin_mcp_server.py"))],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120)) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            expected = set(TOOL_NAMES)
            assert {tool.name for tool in tools} == expected
            assert all(tool.annotations.readOnlyHint for tool in tools if tool.name != "render_garmin_chart")
            assert all(not tool.annotations.destructiveHint for tool in tools)
            status = await session.call_tool("get_data_status", {})
            assert not status.isError
            report = {"protocol": "passed", "read_only_tools": sorted(expected - {"render_garmin_chart"}),
                      "local_artifact_tools": ["render_garmin_chart"], "live": False}
            if live:
                responses = {}
                async def call(name, arguments, label=None):
                    result = await session.call_tool(name, arguments)
                    if result.isError:
                        raise RuntimeError(f"Live MCP tool failed: {name}; upstream text hidden.")
                    value = json.loads(next(block.text for block in result.content if block.type == "text"))
                    if value.get("unavailable"):
                        raise RuntimeError(f"MCP category failed: {name}; categories={','.join(value['unavailable'])}")
                    responses[label or name] = value
                    print(json.dumps({"verified_tool": label or name}, ensure_ascii=False), flush=True)
                    return value
                data = await call("get_health_summary", {"days": days, "end_date": end_date, "refresh": True})
                rows = data.get("records", [])
                assert rows and all(not row.get("unavailable") for row in rows)
                assert any(row["sleep"]["hours"] is not None or row["hrv"].get("lastNightAvg") is not None for row in rows)
                date = rows[-1]["date"]
                activities = await call("get_recent_activities", {"limit": 5, "activity_type": "running"})
                await call("get_sleep_details", {"date": date, "include_series": True, "max_points": 24, "refresh": True})
                await call("get_health_timeseries", {"date": date, "metrics": [
                    "heart_rate", "steps", "floors", "stress", "body_battery", "respiration", "spo2", "hrv",
                    "intensity_minutes", "events", "body_battery_events"], "max_points": 24, "refresh": True})
                await call("get_training_metrics", {"end_date": date, "days": 28, "groups": [
                    "status", "vo2max", "race_predictions", "fitness_age", "lactate_threshold", "cycling_ftp", "zones"], "refresh": True})
                if activities["activities"]:
                    aid = str(activities["activities"][0]["activityId"])
                    detail = await call("get_activity_details", {"activity_id": aid, "sections": [
                        "summary", "samples", "splits", "heart_rate_zones", "power_zones", "weather", "gear"],
                        "max_points": 24, "refresh": True})
                    assert "directLatitude" not in json.dumps(detail)
                    await call("get_activity_details", {"activity_id": aid, "sections": ["samples"],
                               "include_location": True, "max_points": 24}, "activity_with_location")
                workouts = await call("get_training_workouts", {"refresh": True})
                values = workouts["data"]["workouts"]["value"]
                if values:
                    await call("get_training_workouts", {"workout_id": str(values[0]["workoutId"]), "refresh": True}, "workout_steps")
                await call("get_training_workouts", {"kind": "calendar", "year": int(date[:4]), "month": int(date[5:7]), "refresh": True}, "calendar")
                await call("get_training_workouts", {"kind": "plans", "refresh": True}, "training_plans")
                await call("get_personal_records", {"refresh": True})
                await call("get_device_capabilities", {"refresh": True})
                chart = await call("render_garmin_chart", {"kind": "sleep", "date": date,
                                   "metrics": ["stages", "heart_rate"], "max_points": 100})
                assert chart["status"] == "ok" and Path(chart["image_path"]).is_file()
                responses["get_data_status"] = json.loads(next(b.text for b in status.content if b.type == "text"))
                atomic_json(DATA / "mcp-expanded-results.json", responses)
                report.update(live=True, date=date, days=len(rows), endpoints="passed", verified_queries=len(responses))
            atomic_json(DATA / "mcp-current-status.json", report)
            print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--days", type=int, default=1, choices=range(1, 8))
    parser.add_argument("--end-date", help="验证指定日期，默认今天")
    args = parser.parse_args()
    asyncio.run(verify(args.live, args.days, args.end_date))

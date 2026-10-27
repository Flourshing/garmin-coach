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


async def verify(live=False, days=1):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", str(Path(__file__).with_name("garmin_mcp_server.py"))],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120)) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            expected = {"get_health_summary", "get_recent_activities", "get_data_status"}
            assert {tool.name for tool in tools} == expected
            assert all(tool.annotations.readOnlyHint for tool in tools)
            status = await session.call_tool("get_data_status", {})
            assert not status.isError
            report = {"protocol": "passed", "read_only_tools": sorted(expected), "live": False}
            if live:
                result = await session.call_tool("get_health_summary", {"days": days, "refresh": True})
                if result.isError:
                    raise RuntimeError("Live MCP read failed; upstream error text is hidden.")
                data = json.loads(next(block.text for block in result.content if block.type == "text"))
                rows = data.get("records", [])
                assert rows and all(not row.get("unavailable") for row in rows)
                assert any(row["sleep"]["hours"] is not None or row["hrv"].get("lastNightAvg") is not None for row in rows)
                activities = await session.call_tool("get_recent_activities", {"limit": 1})
                assert not activities.isError
                report.update(live=True, date=rows[-1]["date"], days=len(rows), endpoints="passed")
            atomic_json(DATA / "mcp-current-status.json", report)
            print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--days", type=int, default=1, choices=range(1, 8))
    args = parser.parse_args()
    asyncio.run(verify(args.live, args.days))

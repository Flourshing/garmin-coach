"""Verify the installed BorisBW Garmin MCP using local, masked sign-in."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / ".private" / "mcp-verification"
TOKENS = PRIVATE / "tokens"
STATUS = PRIVATE / "status.json"
CHINA = timezone(timedelta(hours=8))
STATE = {"project": "BorisBW/garmin-mcp-cn", "region": "cn", "checks": {}}


def status(stage: str, **values):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    STATE.update(values, stage=stage, updated_at=datetime.now(CHINA).isoformat())
    temporary = STATUS.with_suffix(".tmp")
    temporary.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATUS)


def safe_error(exc):
    """Record exception classes and HTTP codes, never response bodies or URLs."""
    classes, codes, seen = set(), set(), set()
    pending = [exc]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        classes.add(type(item).__name__)
        response = getattr(item, "response", None)
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            codes.add(code)
        pending.extend(getattr(item, "exceptions", ()))
        pending.extend(x for x in (item.__cause__, item.__context__) if x is not None)
    return {"error_types": sorted(classes), "http_statuses": sorted(codes)}


def login():
    from garminconnect import Garmin

    status("awaiting_credentials")
    print("请在此窗口输入佳明中国区账号、密码；输入内容均不显示。")
    print("请勿在聊天中发送密码或验证码。\n")
    account = getpass("佳明中国区账号（输入后按回车）：").strip()
    password = getpass("密码（输入后按回车）：")
    if not account or not password:
        raise ValueError("Empty credentials")

    def mfa():
        status("awaiting_verification_code")
        return getpass("请输入佳明发送的验证码（输入后按回车）：").strip()

    api = Garmin(email=account, password=password, is_cn=True, prompt_mfa=mfa)
    api.garth.configure(timeout=25, retries=0)
    # An explicit login always uses the credentials entered above.
    os.environ.pop("GARMINTOKENS", None)
    del account, password
    print("\n正在验证中国区登录，请稍候……")
    status("authenticating")
    api.login()
    TOKENS.mkdir(parents=True, exist_ok=True)
    api.garth.dump(str(TOKENS))
    STATE["checks"]["login"] = "passed"
    status("authenticated")
    del api


def parse_result(result, name):
    if result.isError:
        return {"result": "tool_error"}
    blocks = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    try:
        data = json.loads("\n".join(blocks))
    except (ValueError, TypeError):
        # The original tools may return failure messages without isError=True.
        text = "\n".join(blocks).lower()
        if text.startswith("no "):
            return {"result": "no_data"}
        return {"result": "non_json_or_error"}
    if not isinstance(data, dict):
        return {"result": "unexpected_format"}
    if name == "get_activities":
        count = data.get("count")
        if not isinstance(count, int) or count < 1:
            return {"result": "no_data"}
        return {"result": "data_received", "activity_count": count}
    keys = {
        "get_sleep_summary": ("sleep_seconds", "sleep_score", "sleep_hours", "avg_overnight_hrv"),
        "get_heart_rates_summary": ("resting_heart_rate_bpm", "max_heart_rate_bpm", "data_points_count"),
    }[name]
    metrics = {key: data[key] for key in keys if isinstance(data.get(key), (int, float))}
    return {"result": "data_received" if metrics else "no_data", "metrics": metrics}


async def verify_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Only cached tokens go to the original MCP subprocess, never the password.
    env = os.environ.copy()
    for key in ("GARMIN_EMAIL", "GARMIN_PASSWORD", "GARMIN_EMAIL_FILE", "GARMIN_PASSWORD_FILE"):
        env.pop(key, None)
    env.update(GARMIN_IS_CN="true", GARMINTOKENS=str(TOKENS),
               GARMINTOKENS_BASE64=str(PRIVATE / "tokens-base64"), PYTHONIOENCODING="utf-8")
    entry = ("import os,sys,logging;sys.stderr=open(os.devnull,'w');"
             "logging.disable(logging.CRITICAL);from garmin_mcp import main;main()")
    params = StdioServerParameters(command=sys.executable, args=["-c", entry], env=env)
    # Yesterday is complete, unlike today's still-changing metrics.
    day = (datetime.now(CHINA).date() - timedelta(days=1)).isoformat()
    STATE["date_checked"] = day
    status("starting_mcp")
    print("正在启动原版 MCP，并只读查询昨天的健康数据和最近一条运动……")
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=90)) as session:
            await session.initialize()
            STATE["checks"]["mcp_connection"] = "passed"
            available = {tool.name for tool in (await session.list_tools()).tools}
            calls = [("get_sleep_summary", {"date": day}),
                     ("get_heart_rates_summary", {"date": day}),
                     ("get_activities", {"start": 0, "limit": 1})]
            for name, arguments in calls:
                status("reading_data", current_tool=name)
                if name not in available:
                    STATE["checks"][name] = {"result": "missing_tool"}
                    continue
                try:
                    result = await session.call_tool(name, arguments)
                    STATE["checks"][name] = parse_result(result, name)
                except Exception as exc:
                    STATE["checks"][name] = {"result": "request_failed", **safe_error(exc)}
                    # Stop instead of retrying a failing account or transport.
                    break
                status("reading_data")
                print(f"  {name}: {STATE['checks'][name]['result']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--login", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    for key in ("garmin-mcp", "garminconnect", "mcp", "garth"):
        STATE.setdefault("versions", {})[key] = importlib.metadata.version(key)
    if args.check:
        import garmin_mcp
        from mcp import ClientSession
        print(json.dumps({"environment": "ready", "versions": STATE["versions"]}))
        return 0
    try:
        if args.login:
            if not sys.stdin.isatty():
                print("请双击 verify-mcp.cmd，在本机交互窗口输入登录信息。")
                return 2
            login()
        elif not (TOKENS / "oauth1_token.json").is_file():
            status("needs_local_login")
            print("尚无登录凭证，请双击 verify-mcp.cmd。")
            return 2
        asyncio.run(verify_tools())
        outcomes = [value.get("result") for value in STATE["checks"].values() if isinstance(value, dict)]
        stage = "verified" if len(outcomes) == 3 and all(x == "data_received" for x in outcomes) else "partial"
        status(stage, current_tool=None)
        print("\n验证完成。" if stage == "verified" else "\n验证未全部通过，已记录缺失或失败项目。")
        print(f"验证状态已保存：{STATUS}")
        return 0 if stage == "verified" else 1
    except (KeyboardInterrupt, EOFError):
        status("cancelled")
        print("\n已取消。")
        return 2
    except Exception as exc:
        status("failed", failure=safe_error(exc))
        print("\n验证未成功。已保存错误类型和 HTTP 状态，未保存密码或错误响应原文。")
        print("请回到聊天，我会根据验证状态继续排查。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

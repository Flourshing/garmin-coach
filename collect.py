"""Read-only Garmin China data collector. Credentials stay in the local terminal."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import os
import sys
from functools import wraps
from datetime import datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

from verify_mcp import safe_error

ROOT = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get("GARMIN_DATA_DIR", ROOT / ".private")).resolve()
TOKENS = PRIVATE / "tokens"
CHINA = timezone(timedelta(hours=8))
STATUS = PRIVATE / "collector-status.json"
CONNECTION_STATE = {"source": "garminconnect 0.3.10", "region": "cn"}


def record_status(stage, **values):
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    CONNECTION_STATE.update(values, stage=stage, updated_at=datetime.now(CHINA).isoformat())
    temporary = STATUS.with_suffix(".tmp")
    temporary.write_text(json.dumps(CONNECTION_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATUS)


def request_category(url):
    """Return only fixed labels. URLs, parameters, headers and bodies stay private."""
    parts = urlsplit(str(url))
    host = parts.hostname or ""
    region = "cn" if host.endswith(".garmin.cn") else "global" if host.endswith(".garmin.com") else "other"
    if region == "other":
        return region, "external_request"
    for prefix, label in (
        ("/portal/sso/", "web_login_page"),
        ("/portal/api/login", "web_credentials"),
        ("/portal/api/", "web_authentication"),
        ("/sso/verifyMFA/", "verification_code"),
        ("/di-oauth2-service/", "access_token"),
        ("/userprofile-service/", "profile_or_settings"),
        ("/usersummary-service/", "daily_summary"),
        ("/wellness-service/", "health_metrics"),
        ("/hrv-service/", "hrv"),
        ("/activitylist-service/", "activities"),
    ):
        if parts.path.startswith(prefix):
            return region, label
    return region, "other_garmin_request"


def install_request_trace():
    import requests
    from curl_cffi import requests as curl_requests

    events = []

    def wrap(original):
        @wraps(original)
        def request(session, method, url, *args, **kwargs):
            region, category = request_category(url)
            event = {"region": region, "step": category}
            try:
                response = original(session, method, url, *args, **kwargs)
                event["http_status"] = response.status_code
                return response
            except Exception as exc:
                event.update(safe_error(exc))
                raise
            finally:
                events.append(event)
                record_status(CONNECTION_STATE.get("stage", "connecting"), requests=events[-30:])
        return request

    for cls in (requests.Session, curl_requests.Session):
        cls.request = wrap(cls.request)


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if value >= 0 else None
    return None


def subset(data, keys):
    return {key: data.get(key) for key in keys if data.get(key) is not None}


def summarize(day, stats, sleep, hrv, activities):
    """Keep necessary metrics only; exclude account IDs, names and GPS routes."""
    stats = stats if isinstance(stats, dict) else {}
    sleep = sleep if isinstance(sleep, dict) else {}
    hrv = hrv if isinstance(hrv, dict) else {}
    dto = sleep.get("dailySleepDTO") or {}
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    seconds = number(dto.get("sleepTimeSeconds"))
    # Duration avoids China-region sleep *Local timestamp double-offset issues.
    return {
        "date": day,
        "daily": {key: number(stats.get(key)) for key in
                  ["totalSteps", "restingHeartRate", "averageStressLevel",
                   "bodyBatteryHighestValue", "bodyBatteryLowestValue"]},
        "sleep": {
            "hours": round(seconds / 3600, 2) if seconds is not None else None,
            "score": number(overall.get("value")),
        },
        "hrv": subset(hrv.get("hrvSummary") or {},
                      ["lastNightAvg", "weeklyAvg", "status", "baseline"]),
        "activities": [subset(item, ["activityType", "distance", "duration",
                                     "movingDuration", "averageHR", "maxHR",
                                     "averageSpeed", "aerobicTrainingEffect",
                                     "anaerobicTrainingEffect"])
                       for item in activities if isinstance(item, dict)],
        "units": {"distance": "meters", "duration": "seconds",
                  "averageSpeed": "meters/second", "heartRate": "bpm", "hrv": "ms"},
    }


def collect(api, days, end_day):
    records = []
    for offset in range(days - 1, -1, -1):
        day = (end_day - timedelta(days=offset)).isoformat()
        payload = {}
        errors = {}
        for name, fetch in [
            ("stats", lambda: api.get_stats(day)),
            ("sleep", lambda: api.get_sleep_data(day)),
            ("hrv", lambda: api.get_hrv_data(day)),
            ("activities", lambda: api.get_activities_by_date(day, day)),
        ]:
            try:
                payload[name] = fetch()
            except Exception as exc:
                kind = type(exc).__name__
                # Stop for authentication and rate limits, rather than repeat requests.
                if kind in {"GarminConnectAuthenticationError", "GarminConnectTooManyRequestsError"}:
                    raise
                errors[name] = kind
                payload[name] = [] if name == "activities" else {}
        row = summarize(day, payload["stats"], payload["sleep"],
                        payload["hrv"], payload["activities"] or [])
        row["unavailable"] = errors
        records.append(row)
    return records


def save_records(records):
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    target = PRIVATE / "latest-summary.json"
    temporary = target.with_suffix(".tmp")
    bundle = {
        "source": "Garmin Connect China; unofficial read-only client",
        "collected_at": datetime.now(CHINA).isoformat(),
        "timezone": "Asia/Shanghai",
        "notes": "Today's activity totals may be incomplete. Missing values are not zero. "
                 "Sleep dates follow Garmin's dailySleepDTO. Confirm against Garmin Connect.",
        "records": records,
    }
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target


def print_summary(records):
    def show(value):
        return "未同步或不可用" if value is None else str(value)
    print("\n日期          睡眠(小时)       睡眠评分          夜间HRV(ms)")
    for row in records:
        print(f"{row['date']}    {show(row['sleep']['hours']):<14} "
              f"{show(row['sleep']['score']):<14} {show(row['hrv'].get('lastNightAvg'))}")
    missing = sum(len(row.get("unavailable", {})) for row in records)
    if missing:
        print(f"\n有 {missing} 项请求未成功，已标记，不会按 0 参与分析。")


def main():
    parser = argparse.ArgumentParser(description="Garmin 255 中国区：本机登录和只读数据验证")
    parser.add_argument("--login", action="store_true", help="在本机输入账号、密码及验证码")
    parser.add_argument("--check", action="store_true", help="只检查环境，不访问账号或网络")
    parser.add_argument("--portal", action="store_true", help="使用新版网页认证流程，只尝试一次")
    parser.add_argument("--days", type=int, default=3, choices=range(1, 29), metavar="1-28")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Never expose auth exceptions or response bodies.
    try:
        version = importlib.metadata.version("garminconnect")
    except importlib.metadata.PackageNotFoundError:
        print("尚未安装数据读取依赖。请查看 README.md 的安装说明。")
        return 2
    if args.check:
        print(f"Python {sys.version.split()[0]}；garminconnect {version}；中国区配置已就绪。")
        print("此检查没有登录 Garmin，也没有连接 GPT 或微信。")
        return 0
    if version != "0.3.10":
        print("请安装 requirements.txt 指定版本；当前版本尚未核对接口。")
        return 2
    from garminconnect import Garmin
    install_request_trace()
    if args.login:
        if not sys.stdin.isatty():
            print("请在本机交互终端登录，避免账号密码进入日志。")
            return 2
        record_status("awaiting_credentials")
        account = getpass("Garmin 中国区账号（输入不显示）：").strip()
        password = getpass("密码（输入时不显示）：")
        if not account or not password:
            print("账号和密码不能为空。")
            return 2
        def prompt_mfa():
            record_status("awaiting_verification_code")
            return getpass("Garmin 验证码（输入时不显示）：").strip()

        api = Garmin(account, password, is_cn=True,
                     prompt_mfa=prompt_mfa,
                     retry_attempts=0)
        del password
    else:
        if not (TOKENS / "garmin_tokens.json").is_file():
            print("还没有本机登录凭证。请先运行 login.cmd。")
            return 2
        api = Garmin(is_cn=True, retry_attempts=0)
    TOKENS.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        if args.portal and args.login:
            from garminconnect import client as client_module
            # The user confirmed that CN website sign-in works. Use that flow
            # directly, without repeated attempts through mobile/widget auth.
            api.client.skip_strategies = {
                "mobile+cffi", "mobile+requests", "widget+cffi", "portal+requests"
            }
            client_module.PORTAL_IMPERSONATIONS = ("chrome",)
        record_status("authenticating", method="portal" if args.portal else "default")
        print("正在连接 Garmin 中国区，请稍候……")
        if args.login:
            # Explicit login must not silently resume a different cached account.
            os.environ.pop("GARMINTOKENS", None)
            api.login()
            # This client version only serializes native DI tokens. A successful
            # web-cookie fallback can be used now, but must not be saved as an
            # empty and unusable native-token file.
            reusable = bool(api.client.di_token)
            if reusable:
                api.client.dump(str(TOKENS))
            CONNECTION_STATE["session_reusable"] = reusable
        else:
            api.login(str(TOKENS))
        record_status("authenticated")
        today = datetime.now(CHINA).date()
        record_status("reading_data")
        records = collect(api, args.days, today)
        target = save_records(records)
        received = any(
            row["sleep"].get("hours") is not None
            or row["daily"].get("restingHeartRate") is not None
            or row["hrv"].get("lastNightAvg") is not None
            or row["activities"]
            for row in records
        )
        record_status("data_received" if received else "no_data", days=len(records),
                      unavailable=[row.get("unavailable", {}) for row in records])
        print_summary(records)
        print(f"\n摘要保存在：{target}")
        print("这是数据读取结果；尚未进行 GPT 分析或微信推送。")
        return 0
    except Exception as exc:
        kind = type(exc).__name__
        record_status("failed", failure=safe_error(exc))
        hints = {
            "GarminConnectAuthenticationError": "登录未成功或凭证失效。请核对中国区账号，重新运行 login.cmd。",
            "GarminConnectTooManyRequestsError": "Garmin 暂时限制请求，请稍后再试，勿连续重试。",
        }
        print(hints.get(kind, "连接或读取未成功；请先确认 Garmin Connect 中国区网页登录和网络正常。"))
        print(f"错误类型：{kind}（已隐藏账号、令牌和服务器原文）")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

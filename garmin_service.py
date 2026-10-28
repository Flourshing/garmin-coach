"""Small, read-only Garmin China interface shared by MCP and daily reports."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from collect import CHINA, collect, subset
from garmin_data import ACTIVITY_FIELDS, clean_data

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("GARMIN_DATA_DIR", ROOT / ".private")).resolve()
TOKENS = DATA / "tokens"
CACHE = DATA / "health-cache"
LOCK = threading.RLock()
CACHE_SCHEMA = 2


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def connection():
    from garminconnect import Garmin

    logging.disable(logging.CRITICAL)
    if not (TOKENS / "garmin_tokens.json").is_file():
        raise ValueError("需要先在本机完成佳明中国区登录。")
    api = Garmin(is_cn=True, retry_attempts=0)
    api.login(str(TOKENS))
    return api


def selected_dates(days: int, end_date: str | None):
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 28:
        raise ValueError("days 必须在 1 到 28 之间。")
    today = datetime.now(CHINA).date()
    end = date.fromisoformat(end_date) if end_date else today
    if end > today:
        raise ValueError("不能查询未来日期。")
    return [end - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def health_summary(days: int = 7, end_date: str | None = None, refresh: bool = False):
    """Read daily sleep, HRV, resting HR, Body Battery and activities (max 28 days)."""
    dates = selected_dates(days, end_date)
    now = datetime.now(CHINA)
    records = []
    with LOCK:
        api = None
        for day in dates:
            cached = None
            path = CACHE / f"{day.isoformat()}.json"
            if not refresh and path.is_file():
                try:
                    candidate = json.loads(path.read_text(encoding="utf-8"))
                    age = now - datetime.fromisoformat(candidate["retrieved_at"])
                    ttl = timedelta(minutes=15) if day == now.date() else timedelta(hours=24)
                    if (candidate.get("schema_version") == CACHE_SCHEMA and
                            timedelta(0) <= age < ttl and candidate["record"]["date"] == day.isoformat()):
                        cached = candidate
                except (ValueError, KeyError, TypeError):
                    pass
            if cached is None:
                api = api or connection()
                row = collect(api, 1, day)[0]
                cached = {"schema_version": CACHE_SCHEMA,
                          "retrieved_at": datetime.now(CHINA).isoformat(), "record": row}
                # Failed endpoints are not cached as a complete day.
                if not row.get("unavailable"):
                    atomic_json(path, cached)
            row = dict(cached["record"])
            row["retrieved_at"] = cached["retrieved_at"]
            records.append(row)
    return {
        "source": "Garmin Connect China",
        "timezone": "Asia/Shanghai",
        "generated_at": datetime.now(CHINA).isoformat(),
        "notes": ["空值不是零；今天的运动总量仍可能变化。",
                  "Body Battery 为当日最高/最低值，不代表此刻电量。",
                  "bodyBatteryMostRecentValue 是所查日期的最近同步值，不是此刻实时值。",
                  "睡眠时间使用 GMT 毫秒时间戳转北京时间；清醒时长不计入总睡眠。",
                  "HRV 状态 NONE 表示状态不可用，不能解释成恢复不佳。"],
        "records": records,
    }


def recent_activities(limit: int = 5, start: int = 0, activity_type: str | None = None):
    if isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit 必须在 1 到 20 之间。")
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start <= 10000:
        raise ValueError("start 必须在 0 到 10000 之间。")
    if activity_type not in {None, "running", "cycling", "swimming", "multi_sport", "fitness_equipment", "hiking", "walking", "other"}:
        raise ValueError("请使用支持的运动大类；子类型请在返回列表中识别。")
    with LOCK:
        api = connection()
        rows = api.get_activities(start, limit, activity_type) or []
    return {"timezone": "Asia/Shanghai", "retrieved_at": datetime.now(CHINA).isoformat(),
            "start": start, "limit": limit,
            "activities": [clean_data(subset(row, ACTIVITY_FIELDS)) for row in rows],
            "units": {"distance": "meters", "duration": "seconds", "averageSpeed": "meters/second"}}


def data_status():
    return {"region": "cn", "token_available": (TOKENS / "garmin_tokens.json").is_file(),
            "read_only": True, "timezone": "Asia/Shanghai"}


def safe_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        # Upstream exceptions may contain URLs, service tickets, IDs or cookies.
        raise ValueError(f"佳明请求未完成；错误类型：{type(exc).__name__}。请检查本机登录状态。") from None

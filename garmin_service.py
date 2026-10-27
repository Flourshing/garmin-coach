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

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("GARMIN_DATA_DIR", ROOT / ".private")).resolve()
TOKENS = DATA / "tokens"
CACHE = DATA / "health-cache"
LOCK = threading.RLock()


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
    if isinstance(days, bool) or not 1 <= days <= 28:
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
                    if timedelta(0) <= age < ttl and candidate["record"]["date"] == day.isoformat():
                        cached = candidate
                except (ValueError, KeyError, TypeError):
                    pass
            if cached is None:
                api = api or connection()
                row = collect(api, 1, day)[0]
                cached = {"retrieved_at": datetime.now(CHINA).isoformat(), "record": row}
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
                  "HRV 状态 NONE 表示状态不可用，不能解释成恢复不佳。"],
        "records": records,
    }


def recent_activities(limit: int = 5):
    if isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit 必须在 1 到 20 之间。")
    with LOCK:
        rows = connection().get_activities(0, limit) or []
    keys = ("startTimeLocal", "activityType", "distance", "duration", "movingDuration",
            "averageHR", "maxHR", "averageSpeed", "aerobicTrainingEffect")
    # No account IDs, activity names, activity IDs or GPS points leave this service.
    return {"timezone": "Asia/Shanghai", "activities": [subset(row, keys) for row in rows],
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

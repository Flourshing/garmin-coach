"""Bounded, on-demand read access to verified Garmin 255 data categories."""
from datetime import datetime, timedelta
from hashlib import sha256
import json

import garmin_service as service
from collect import CHINA
from garmin_data import ACTIVITY_FIELDS, clean_data, sampled, selected

SERIES_METHODS = {
    "heart_rate": "get_heart_rates", "steps": "get_steps_data", "floors": "get_floors",
    "stress": "get_stress_data", "body_battery": "get_stress_data",
    "respiration": "get_respiration_data", "spo2": "get_spo2_data", "hrv": "get_hrv_data",
    "intensity_minutes": "get_intensity_minutes_data", "events": "get_all_day_events",
    "body_battery_events": "get_body_battery_events",
}
TRAINING_GROUPS = ("status", "vo2max", "race_predictions", "fitness_age",
                   "lactate_threshold", "cycling_ftp", "zones")
ACTIVITY_SECTIONS = ("summary", "samples", "splits", "heart_rate_zones", "power_zones",
                     "exercise_sets", "weather", "gear")
SLEEP_SERIES = (
    "sleepLevels", "sleepMovement", "sleepRestlessMoments", "sleepHeartRate", "sleepStress",
    "sleepBodyBattery", "wellnessEpochSPO2DataDTOList", "wellnessEpochRespirationDataDTOList",
    "wellnessEpochRespirationAveragesList", "hrvData",
)


def _day(day):
    return service.selected_dates(1, day)[0].isoformat()


def _points(max_points):
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 2 <= max_points <= 2000:
        raise ValueError("max_points 必须为 2–2000；默认 240，长曲线会抽样并标记原始点数。")


def _groups(value, allowed, defaults):
    chosen = list(defaults) if value is None else value
    if not isinstance(chosen, list) or not chosen or any(not isinstance(v, str) or v not in allowed for v in chosen):
        raise ValueError("查询类别必须为非空列表，且只能使用工具说明中的类别。")
    return list(dict.fromkeys(chosen))


def _id(value):
    if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit() or not 0 < int(value) < 10**20:
        raise ValueError("需要列表工具返回的有效 activity_id 或 workout_id。")
    return str(int(value))


def _envelope(day=None):
    return {"source": "Garmin Connect China", "timezone": "Asia/Shanghai", "date": day,
            "generated_at": datetime.now(CHINA).isoformat(), "data": {}, "unavailable": {},
            "notes": ["空值和空列表不是零；历史值不代表此刻。",
                      "仅查询请求的类别；返回数据不要求全部出现在回复或日报中。"]}


def _fetch(api, method, args=(), kwargs=None, *, day=None, refresh=False):
    """Cache raw health data privately; apply output policy at each public boundary."""
    kwargs = kwargs or {}
    key = sha256(json.dumps([method, args, kwargs], sort_keys=True).encode()).hexdigest()
    path = service.DATA / "extended-cache" / (key + ".json")
    now = datetime.now(CHINA)
    ttl = timedelta(minutes=15) if day is None or day == now.date().isoformat() else timedelta(hours=24)
    if not refresh and path.is_file():
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
            age = now - datetime.fromisoformat(cache["retrieved_at"])
            if cache.get("schema_version") == 1 and timedelta(0) <= age < ttl:
                return cache["value"], cache["retrieved_at"]
        except (ValueError, TypeError, KeyError):
            pass
    value = getattr(api, method)(*args, **kwargs)
    timestamp = datetime.now(CHINA).isoformat()
    service.atomic_json(path, {"schema_version": 1, "retrieved_at": timestamp, "value": value})
    return value, timestamp


def _read(result, api, key, method, args=(), kwargs=None, *, day=None, refresh=False, transform=clean_data):
    try:
        value, timestamp = _fetch(api, method, args, kwargs, day=day, refresh=refresh)
        result["data"][key] = {"retrieved_at": timestamp, "value": transform(value)}
    except Exception as exc:
        kind = type(exc).__name__
        if kind in {"GarminConnectAuthenticationError", "GarminConnectTooManyRequestsError"}:
            raise
        result["unavailable"][key] = kind


def _series_payload(value, max_points):
    if isinstance(value, list):
        return sampled(clean_data(value), max_points)
    if not isinstance(value, dict):
        return None
    summary, descriptors, series = {}, {}, {}
    for key, part in clean_data(value).items():
        if "descriptor" in key.lower():
            descriptors[key] = part
        elif isinstance(part, list):
            series[key] = sampled(part, max_points)
        else:
            summary[key] = part
    return {"summary": summary, "descriptors": descriptors, "series": series}


def sleep_details(day=None, include_series=False, max_points=240, refresh=False):
    day = _day(day)
    _points(max_points)
    result = _envelope(day)
    result["notes"] += ["sleep*TimestampGMT 为 GMT 毫秒时间戳，转北京时间仅加一次时区。",
                        "awakeSleepSeconds 不计入 sleepTimeSeconds；午睡为 0 可以是当天无午睡。",
                        "sleepNeed 的单位以佳明实际字段为准，不能擅自当作小时。"]
    def transform(raw):
        if not isinstance(raw, dict):
            return None
        data = selected(raw, ("dailySleepDTO", "restlessMomentsCount", "avgOvernightHrv",
                              "hrvStatus", "bodyBatteryChange", "restingHeartRate", "skinTempDataExists"))
        if include_series:
            data["series"] = {key: sampled(clean_data(raw.get(key)), max_points) for key in SLEEP_SERIES}
        return data
    with service.LOCK:
        _read(result, service.connection(), "sleep", "get_sleep_data", (day,),
              day=day, refresh=refresh, transform=transform)
    return result


def health_timeseries(day=None, metrics=None, max_points=240, refresh=False):
    day = _day(day)
    _points(max_points)
    chosen = _groups(metrics, SERIES_METHODS, ["heart_rate"])
    result = _envelope(day)
    result["notes"] += ["曲线保留接口描述符；负数状态码（如压力 -1/-2）表示不可测量，不能当真实读数。",
                        "sampled=true 表示均匀抽样，不是平均值或完整逐点导出。"]
    with service.LOCK:
        api = service.connection()
        for metric in chosen:
            def transform(value, metric=metric):
                if metric == "body_battery" and isinstance(value, dict):
                    value = {key: v for key, v in value.items() if "bodybattery" in key.lower() or "timestamp" in key.lower() or key == "calendarDate"}
                elif metric == "stress" and isinstance(value, dict):
                    value = {key: v for key, v in value.items() if "bodybattery" not in key.lower()}
                return _series_payload(value, max_points)
            _read(result, api, metric, SERIES_METHODS[metric], (day,),
                  day=day, refresh=refresh, transform=transform)
    return result


def training_metrics(groups=None, days=28, end_date=None, refresh=False):
    dates = service.selected_dates(days, end_date)
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    chosen = _groups(groups, TRAINING_GROUPS, ["status", "vo2max"])
    calls = {
        "status": [("status", "get_training_status", (end,), {})],
        "vo2max": [("vo2max", "get_max_metrics_range", (start, end), {})],
        "race_predictions": [("race_predictions", "get_race_predictions", (start, end, "daily"), {})],
        "fitness_age": [("fitness_age", "get_fitnessage_data", (end,), {})],
        # These library methods return the latest available record, possibly old.
        "lactate_threshold": [("lactate_threshold", "get_lactate_threshold", (), {})],
        "cycling_ftp": [("cycling_ftp", "get_cycling_ftp", (), {})],
        "zones": [("heart_rate_zones", "get_heart_rate_zones", (), {}),
                  ("power_zones", "get_power_zones", (), {})],
    }
    result = _envelope(end)
    result["range_start"] = start
    result["notes"] += ["按记录自身 calendarDate/更新时间解释，不将旧阈值写成当天测量。",
                        "阈值和区间配置为最新可用记录，未必落在查询日期范围内；isStale=true 表示旧值。",
                        "乳酸阈值速度字段未统一转换单位，不确定其单位时只报告可确认的心率/功率，勿自行换算配速。",
                        "255 不提供训练准备度、耐力/爬坡得分；当前未读到恢复倒计时，不编造这些分数。"]
    with service.LOCK:
        api = service.connection()
        for group in chosen:
            for key, method, args, kwargs in calls[group]:
                _read(result, api, key, method, args, kwargs,
                      day=None if group in {"lactate_threshold", "cycling_ftp", "zones"} else end,
                      refresh=refresh)
    return result


def activity_details(activity_id, sections=None, include_location=False, max_points=240, refresh=False):
    aid = _id(activity_id)
    _points(max_points)
    chosen = _groups(sections, ACTIVITY_SECTIONS, ["summary"])
    result = _envelope()
    result["activity_id"] = aid
    result["location_included"] = include_location
    result["notes"] += ["速度通常为米/秒，时长为秒；明细采样单位按 metricDescriptors，勿套用其他接口的比例。",
                        "温度通道不是皮肤温度；记录中的步幅单位按接口描述符。",
                        "GPS 仅在 include_location=true 时返回；活动日期以记录本身为准。"]
    def summary(raw):
        if not isinstance(raw, dict):
            return None
        data = selected(raw.get("summaryDTO", {}), ACTIVITY_FIELDS)
        data["activity_type"] = clean_data(raw.get("activityTypeDTO"))
        data["activity_name"] = raw.get("activityName")
        data["has_location"] = bool((raw.get("metadataDTO") or {}).get("hasPolyline"))
        data["units"] = {"distance": "meters", "duration": "seconds", "movingDuration": "seconds",
                         "elapsedDuration": "seconds", "averageSpeed": "meters/second", "maxSpeed": "meters/second",
                         "averageHR": "bpm", "averagePower": "watts", "groundContactTime": "milliseconds",
                         "strideLength": "centimeters", "verticalOscillation": "centimeters", "verticalRatio": "percent"}
        return data
    def samples(raw):
        if not isinstance(raw, dict):
            return None
        descriptors = raw.get("metricDescriptors") or []
        allowed = [d for d in descriptors if include_location or not any(
            word in str(d.get("key", "")).lower() for word in ("latitude", "longitude", "position"))]
        points = []
        for row in raw.get("activityDetailMetrics") or []:
            values = row.get("metrics") or []
            points.append({d["key"]: values[d["metricsIndex"]] for d in allowed
                           if isinstance(d.get("metricsIndex"), int) and 0 <= d["metricsIndex"] < len(values)})
        data = {"upstream_measurement_count": raw.get("measurementCount"),
                "details_available": raw.get("detailsAvailable"),
                "metric_descriptors": clean_data(allowed, allow_location=include_location),
                "samples": sampled(points, max_points)}
        if include_location:
            geo = raw.get("geoPolylineDTO") or {}
            data["location"] = {key: sampled(value, max_points) if isinstance(value, list) else value
                                for key, value in clean_data(geo, allow_location=True).items()}
        return data
    calls = {
        "summary": ("get_activity", summary),
        "samples": ("get_activity_details", samples),
        "splits": ("get_activity_splits", lambda v: clean_data(v, allow_location=include_location)),
        "heart_rate_zones": ("get_activity_hr_in_timezones", clean_data),
        "power_zones": ("get_activity_power_in_timezones", clean_data),
        "exercise_sets": ("get_activity_exercise_sets", clean_data),
        "weather": ("get_activity_weather", lambda v: clean_data(v, allow_location=include_location)),
        "gear": ("get_activity_gear", clean_data),
    }
    with service.LOCK:
        api = service.connection()
        for section in chosen:
            method, transform = calls[section]
            _read(result, api, section, method, (aid,), refresh=refresh, transform=transform)
    return result


def training_workouts(kind="workouts", workout_id=None, year=None, month=None, refresh=False):
    if kind not in {"workouts", "calendar", "plans"}:
        raise ValueError("kind 必须为 workouts、calendar 或 plans。")
    if workout_id is not None and kind != "workouts":
        raise ValueError("workout_id 仅用于 workouts。")
    wid = _id(workout_id) if workout_id is not None else None
    now = datetime.now(CHINA)
    year, month = (now.year if year is None else year), (now.month if month is None else month)
    if (isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= now.year + 1 or
            isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12):
        raise ValueError("请提供有效的年和月份（1–12）。")
    method, args = {"workouts": ("get_workout_by_id", (wid,)) if wid else ("get_workouts", (0, 100)),
                    "calendar": ("get_scheduled_workouts", (year, month)),
                    "plans": ("get_training_plans", ())}[kind]
    result = _envelope()
    result["notes"] += ["日历包括已完成运动、午睡和安排训练，请按 itemType 区分，不将活动误当成训练计划。"]
    with service.LOCK:
        _read(result, service.connection(), kind, method, args, refresh=refresh)
    return result


def personal_records(refresh=False):
    result = _envelope()
    with service.LOCK:
        _read(result, service.connection(), "personal_records", "get_personal_record", refresh=refresh)
    return result


def device_capabilities(refresh=False):
    result = _envelope()
    def transform(value):
        return [{"model": device.get("displayName"), "application": device.get("applicationKey"),
                 "capabilities": {key: val for key, val in device.items() if key.endswith("Capable")}}
                for device in (value or [])]
    with service.LOCK:
        _read(result, service.connection(), "devices", "get_devices", refresh=refresh, transform=transform)
    return result

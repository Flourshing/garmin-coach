"""Render real Garmin data locally; return an attachment path, never send messages."""
import math
import os
import statistics
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

import garmin_extended as extended
import garmin_service as service
from collect import CHINA

PLOT_LOCK = threading.Lock()
HEALTH = {
    "heart_rate": ("心率", "Heart rate", "bpm", "heartRateValues", 1),
    "stress": ("压力", "Stress", "0–100", "stressValuesArray", 1),
    "body_battery": ("身体电量", "Body Battery", "0–100", "bodyBatteryValuesArray", 2),
    "respiration": ("呼吸频率", "Respiration", "/min", "respirationValuesArray", 1),
    "spo2": ("血氧", "SpO2", "%", "spO2HourlyAverages", 1),
    "hrv": ("夜间 HRV", "Overnight HRV", "ms", "hrvReadings", 1),
    "steps": ("分时段步数", "Steps per interval", "steps", "", 1),
}
SLEEP = {
    "stages": ("睡眠阶段", "Sleep stages", "stage", "sleepLevels"),
    "heart_rate": ("睡眠心率", "Sleep heart rate", "bpm", "sleepHeartRate"),
    "stress": ("睡眠压力", "Sleep stress", "0–100", "sleepStress"),
    "body_battery": ("睡眠身体电量", "Sleep Body Battery", "0–100", "sleepBodyBattery"),
    "spo2": ("睡眠血氧", "Sleep SpO2", "%", "wellnessEpochSPO2DataDTOList"),
    "respiration": ("睡眠呼吸", "Sleep respiration", "/min", "wellnessEpochRespirationDataDTOList"),
    "hrv": ("夜间 HRV", "Overnight HRV", "ms", "hrvData"),
    "movement": ("睡眠体动", "Sleep movement", "level", "sleepMovement"),
}
ACTIVITY = {
    "heart_rate": ("运动心率", "Heart rate", "bpm", "directHeartRate"),
    "power": ("运动功率", "Power", "W", "directPower"),
    "pace": ("配速", "Pace", "min/km", "directSpeed"),
    "speed": ("速度", "Speed", "km/h", "directSpeed"),
    "cadence": ("步频 / 踏频", "Cadence", "/min", "directDoubleCadence"),
    "stride_length": ("步幅", "Stride length", "cm", "directStrideLength"),
    "ground_contact_time": ("触地时间", "Ground contact time", "ms", "directGroundContactTime"),
    "vertical_oscillation": ("垂直振幅", "Vertical oscillation", "cm", "directVerticalOscillation"),
    "vertical_ratio": ("垂直比", "Vertical ratio", "%", "directVerticalRatio"),
    "elevation": ("海拔", "Elevation", "m", "directElevation"),
    "temperature": ("运动温度（非皮肤温度）", "Activity temperature (not skin)", "C", "directAirTemperature"),
    "performance_condition": ("表现状态", "Performance condition", "score", "directPerformanceCondition"),
}
TREND = {
    "sleep_hours": ("睡眠时长", "Sleep duration", "h", "sleep", "hours", 1),
    "sleep_score": ("睡眠评分", "Sleep score", "0–100", "sleep", "score", 1),
    "deep_hours": ("深睡时长", "Deep sleep", "h", "sleep", "deep_seconds", 1/3600),
    "rem_hours": ("REM 时长", "REM duration", "h", "sleep", "rem_seconds", 1/3600),
    "hrv": ("夜间 HRV", "Overnight HRV", "ms", "hrv", "lastNightAvg", 1),
    "resting_hr": ("静息心率", "Resting heart rate", "bpm", "daily", "restingHeartRate", 1),
    "steps": ("每日步数", "Daily steps", "steps", "daily", "totalSteps", 1),
    "stress": ("平均压力", "Average stress", "0–100", "daily", "averageStressLevel", 1),
}
KINDS = {"health": HEALTH, "sleep": SLEEP, "activity": ACTIVITY, "trend": TREND}
DEFAULTS = {"health": ["heart_rate"], "sleep": ["stages", "heart_rate"],
            "activity": ["heart_rate", "pace", "power"], "trend": ["sleep_hours", "hrv", "resting_hr"]}


def _number(value, *, negative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if negative or value >= 0 else None


def _time(value):
    """GMT inputs are interpreted as UTC exactly once, then displayed in China time."""
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            seconds = value / 1000 if abs(value) > 10**11 else value
            return datetime.fromtimestamp(seconds, timezone.utc).astimezone(CHINA)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(CHINA)
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    return None


def _line(metric, info, pairs, metadata, *, time_axis=True, negative=False):
    points = {}
    for x, value in pairs:
        x = _time(x) if time_axis else _number(x)
        if x is not None:
            points[x] = _number(value, negative=negative)
    ordered = sorted(points.items())
    if not any(y is not None for _, y in ordered):
        return None
    return {"metric": metric, "zh": info[0], "en": info[1], "unit": info[2],
            "x": [x for x, _ in ordered], "y": [y for _, y in ordered],
            "time_axis": time_axis, "source_points": metadata.get("source_points", len(ordered)),
            "sampled": metadata.get("sampled", False)}


def _health_series(result, metrics):
    output, missing = [], []
    for metric in metrics:
        info = HEALTH[metric]
        value = result.get("data", {}).get(metric, {}).get("value") or {}
        if metric == "steps":
            meta = value
            pairs = [(r.get("startGMT"), r.get("steps")) for r in value.get("values", [])]
        else:
            meta = value.get("series", {}).get(info[3]) or {}
            rows = meta.get("values", [])
            if metric == "hrv":
                pairs = [(r.get("readingTimeGMT"), r.get("hrvValue")) for r in rows]
            else:
                pairs = []
                for row in rows:
                    if not isinstance(row, list) or len(row) < 2:
                        continue
                    index = 2 if metric == "body_battery" and len(row) > 2 and isinstance(row[1], str) else 1
                    if len(row) > index:
                        pairs.append((row[0], row[index]))
        series = _line(metric, info, pairs, meta)
        (output if series else missing).append(series if series else metric)
    return output, missing


def _sleep_series(result, metrics):
    value = result.get("data", {}).get("sleep", {}).get("value") or {}
    output, missing = [], []
    for metric in metrics:
        info = SLEEP[metric]
        meta = value.get("series", {}).get(info[3]) or {}
        rows = meta.get("values", [])
        if metric == "stages":
            segments = []
            for row in rows:
                start, end = _time(row.get("startGMT")), _time(row.get("endGMT"))
                level = _number(row.get("activityLevel"))
                if start is not None and end is not None and end > start and level in {0, 1, 2, 3}:
                    segments.append((start, end, int(level)))
            if segments:
                output.append({"metric": metric, "zh": info[0], "en": info[1], "unit": "stage",
                               "segments": segments, "time_axis": True,
                               "source_points": meta.get("source_points", len(segments)), "sampled": meta.get("sampled", False)})
            else:
                missing.append(metric)
            continue
        if metric == "spo2":
            pairs = [(r.get("epochTimestamp"), r.get("spo2Reading")) for r in rows]
        elif metric == "respiration":
            pairs = [(r.get("startTimeGMT"), r.get("respirationValue")) for r in rows]
        elif metric == "movement":
            pairs = [(r.get("startGMT"), r.get("activityLevel")) for r in rows]
        else:
            pairs = [(r.get("startGMT"), r.get("value")) for r in rows]
        series = _line(metric, info, pairs, meta)
        (output if series else missing).append(series if series else metric)
    return output, missing


def _activity_series(result, metrics):
    value = result.get("data", {}).get("samples", {}).get("value") or {}
    meta = value.get("samples") or {}
    rows = meta.get("values", [])
    descriptors = {d.get("key"): d.get("unit", {}).get("key") for d in value.get("metric_descriptors", [])}
    summary = result.get("data", {}).get("summary", {}).get("value") or {}
    activity_type = (summary.get("activity_type") or {}).get("typeKey", "")
    output, missing = [], []
    timestamps = [_time(r.get("directTimestamp")) for r in rows]
    origin = next((t for t in timestamps if t is not None), None)
    for metric in metrics:
        info = ACTIVITY[metric]
        key = info[3]
        multiplier = 1
        if metric == "cadence" and key not in descriptors:
            if "running" in activity_type and "directRunCadence" in descriptors:
                key, multiplier = "directRunCadence", 2
            else:
                key = next((k for k in ["directBikeCadence", "directCadence"] if k in descriptors), key)
        # These raw channels already use the named units. `unit.factor` is not a universal multiplier.
        if metric in {"pace", "speed"} and descriptors.get(key) not in {"mps", "metersPerSecond"}:
            missing.append(metric)
            continue
        pairs = []
        for row, timestamp in zip(rows, timestamps):
            elapsed = _number(row.get("sumElapsedDuration"))
            if elapsed is None and origin is not None and timestamp is not None:
                elapsed = (timestamp-origin).total_seconds()
            y = _number(row.get(key), negative=metric in {"elevation", "temperature", "performance_condition"})
            if y is not None:
                y *= multiplier
                if metric == "pace":
                    y = 1000 / y / 60 if y > 0 else None
                elif metric == "speed":
                    y *= 3.6
            pairs.append((elapsed/60 if elapsed is not None else None, y))
        series = _line(metric, info, pairs, meta, time_axis=False,
                       negative=metric in {"elevation", "temperature", "performance_condition"})
        (output if series else missing).append(series if series else metric)
    return output, missing


def _trend_series(result, metrics):
    output, missing = [], []
    rows = result.get("records", [])
    for metric in metrics:
        info = TREND[metric]
        pairs = []
        for row in rows:
            y = _number((row.get(info[3]) or {}).get(info[4]))
            # Date is already the Garmin-labelled local calendar date, not a UTC timestamp.
            x = datetime.fromisoformat(row["date"]).replace(tzinfo=CHINA)
            pairs.append((x, y*info[5] if y is not None else None))
        points = [(x, y) for x, y in pairs]
        if any(y is not None for _, y in points):
            output.append({"metric": metric, "zh": info[0], "en": info[1], "unit": info[2],
                           "x": [x for x, _ in points], "y": [y for _, y in points], "time_axis": True,
                           "source_points": len(rows), "sampled": False, "trend": True})
        else:
            missing.append(metric)
    return output, missing


def _workspace():
    return Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", service.ROOT / ".private/coach-workspace")).resolve()


def prepare_renderer():
    """Load native plotting libraries before the MCP event loop creates worker threads.

    In particular, late NumPy DLL initialization can stall in a Windows stdio worker.
    Plotting does not benefit from a large BLAS thread pool.
    """
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MPLCONFIGDIR", str(service.DATA / "matplotlib-cache"))
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import dates, font_manager  # noqa: F401
    from matplotlib.figure import Figure  # noqa: F401
    from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: F401


def _render(series, kind, day, notes):
    with PLOT_LOCK:
        return _render_locked(series, kind, day, notes)


def _render_locked(series, kind, day, notes):
    prepare_renderer()
    import matplotlib
    from matplotlib import dates as mdates, font_manager
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.ticker import FuncFormatter

    workspace = _workspace()
    directory = (workspace / "charts").resolve()
    directory.relative_to(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"garmin-chart-{kind}-{day}-{uuid4().hex[:12]}.png"
    fonts = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc",
             Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]
    font_file = next((p for p in fonts if p.is_file()), None)
    if font_file:
        font_manager.fontManager.addfont(str(font_file))
        family = font_manager.FontProperties(fname=str(font_file)).get_name()
    else:
        family = "DejaVu Sans"
        notes.append("未找到中文字体，图中使用英文标签。")
    chinese = font_file is not None
    colors = ["#1975D1", "#E28A35", "#1B9985", "#8A63C7", "#D34F73", "#4C8494"]
    summaries = []
    with matplotlib.rc_context({"font.family": family, "font.size": 10,
                                           "axes.unicode_minus": False}):
        figure = Figure(figsize=(8.4, 1.45 + 2.5*len(series)), dpi=150, facecolor="#F5F7FB")
        FigureCanvasAgg(figure)
        axes = figure.subplots(len(series), 1, squeeze=False).ravel()
        titles = {"health": ("日间健康曲线", "Daily health"), "sleep": ("睡眠曲线", "Sleep"),
                  "activity": ("运动曲线", "Activity"), "trend": ("健康趋势", "Health trends")}
        figure.suptitle(f"{titles[kind][0 if chinese else 1]}  |  {day}", x=.12, y=.975,
                        ha="left", fontsize=17, fontweight="bold", color="#17263C")
        for index, (axis, data) in enumerate(zip(axes, series)):
            color = colors[index % len(colors)]
            axis.set_facecolor("white")
            axis.grid(axis="y", color="#E3E8F0", linewidth=.7)
            axis.set_axisbelow(True)
            for spine in ["top", "right"]:
                axis.spines[spine].set_visible(False)
            axis.spines["left"].set_color("#CED6E1")
            axis.spines["bottom"].set_color("#CED6E1")
            label = data["zh"] if chinese else data["en"]
            subtitle = (f"{data['source_points']} 个源点" if chinese else f"{data['source_points']} source points")
            if data["sampled"]:
                subtitle += " · 已抽样" if chinese else " · sampled"
            axis.set_title(f"{label}   ·   {subtitle}", loc="left", pad=12, fontsize=11, color="#24354C")
            if "segments" in data:
                for start, end, stage in data["segments"]:
                    axis.broken_barh([(mdates.date2num(start), (end-start).total_seconds()/86400)],
                                     (stage-.34, .68), facecolors=["#4359AC", "#73B7E6", "#A57BD4", "#E5A05A"][stage])
                axis.set_yticks([0, 1, 2, 3], ["深睡", "浅睡", "REM", "清醒"] if chinese else ["Deep", "Light", "REM", "Awake"])
                axis.set_ylim(-.6, 3.6)
                summaries.append({"metric": data["metric"], "segments": len(data["segments"]),
                                  "source_points": data["source_points"], "sampled": data["sampled"]})
            else:
                xs, ys = data["x"], data["y"]
                # Leave missing readings and long gaps blank; never fill with zero or interpolate.
                gaps = [(b-a).total_seconds() if data["time_axis"] else (b-a)*60 for a, b in zip(xs, xs[1:]) if b > a]
                threshold = max(1200 if data["time_axis"] else 60, statistics.median(gaps)*4) if gaps else math.inf
                draw_x, draw_y = [], []
                for i, (x, y) in enumerate(zip(xs, ys)):
                    if i and gaps:
                        delta = (x-xs[i-1]).total_seconds() if data["time_axis"] else (x-xs[i-1])*60
                        if delta > threshold:
                            draw_x.append(x); draw_y.append(math.nan)
                    draw_x.append(x); draw_y.append(y if y is not None else math.nan)
                axis.plot(draw_x, draw_y, color=color, linewidth=1.25,
                          marker="o" if data.get("trend") or len(xs)<4 else None, markersize=3)
                if len(xs) == 1 and data["time_axis"]:
                    half = timedelta(hours=12) if data.get("trend") else timedelta(minutes=30)
                    axis.set_xlim(xs[0]-half, xs[0]+half)
                elif data.get("trend"):
                    # Retain the requested range even when its first or last days lack readings.
                    axis.set_xlim(min(xs)-timedelta(hours=3), max(xs)+timedelta(hours=3))
                axis.set_ylabel(data["unit"])
                if data["metric"] == "pace":
                    axis.invert_yaxis()
                    axis.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(round(x*60))//60}:{int(round(x*60))%60:02d}"))
                values = [y for y in ys if y is not None]
                summaries.append({"metric": data["metric"], "unit": data["unit"], "valid_points": len(values),
                                  "source_points": data["source_points"], "sampled": data["sampled"],
                                  "min": round(min(values), 3), "max": round(max(values), 3),
                                  "sample_mean": round(statistics.mean(values), 3)})
            if data["time_axis"]:
                axis.xaxis_date(tz=CHINA)
                axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7, tz=CHINA))
                axis.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d" if data.get("trend") else "%H:%M", tz=CHINA))
                axis.set_xlabel("北京时间" if chinese else "China time (UTC+8)")
            else:
                axis.set_xlabel("运动经过时间（分钟）" if chinese else "Elapsed minutes")
            axis.margins(x=.015)
        footer = "Garmin Connect · 北京时间 · 缺失保留空白，未插值；统计来自所绘样本" if chinese else "Garmin Connect · UTC+8 · Gaps retained, no interpolation; statistics use plotted samples"
        figure.text(.12, .018, footer, fontsize=8, color="#62728B")
        figure.subplots_adjust(left=.12, right=.96, top=1-.8/(1.45+2.5*len(series)), bottom=.1, hspace=.62)
        figure.savefig(target, dpi=150, facecolor=figure.get_facecolor())
        figure.clear()
    return target, summaries


def render_curve_chart(kind="health", date=None, metrics=None, activity_id=None, days=7,
                       max_points=1000, refresh=False):
    if kind not in KINDS:
        raise ValueError("kind 必须为 health、sleep、activity 或 trend。")
    chosen = extended._groups(metrics, KINDS[kind], DEFAULTS[kind])
    if len(chosen) > 6:
        raise ValueError("每张图最多 6 项指标，请按主题分开绘制。")
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 100 <= max_points <= 2000:
        raise ValueError("绘图 max_points 必须为 100–2000，默认 1000。")
    day = extended._day(date)
    service.selected_dates(days, day)
    if kind != "activity" and activity_id is not None:
        raise ValueError("activity_id 只用于 activity 图。")
    notes = ["图像由真实接口数据绘制，不使用模型生成数据。", "负数测量状态、零速度配速和缺失值留空。",
             "sample_mean 仅为所绘样本均值，不等同于佳明全天/活动汇总的平均值。"]
    if kind == "health":
        source = extended.health_timeseries(day, chosen, max_points, refresh)
        series, missing = _health_series(source, chosen)
    elif kind == "sleep":
        source = extended.sleep_details(day, True, max_points, refresh)
        series, missing = _sleep_series(source, chosen)
    elif kind == "activity":
        aid = extended._id(activity_id)
        source = extended.activity_details(aid, ["summary", "samples"], False, max_points, refresh)
        start = source.get("data", {}).get("summary", {}).get("value", {}).get("startTimeLocal")
        if start:
            day = start[:10]
        series, missing = _activity_series(source, chosen)
        notes.append("配速由已确认米/秒速度换算；不会把描述符 factor 当作通用倍率。")
    else:
        source = service.health_summary(days, day, refresh)
        series, missing = _trend_series(source, chosen)
    unavailable = source.get("unavailable", {})
    if kind == "trend":
        unavailable = {r["date"]: r["unavailable"] for r in source.get("records", []) if r.get("unavailable")}
    result = {"status": "no_data", "kind": kind, "date": day, "timezone": "Asia/Shanghai",
              "requested_metrics": chosen, "missing_metrics": missing, "unavailable": unavailable,
              "generated_at": datetime.now(CHINA).isoformat(), "notes": notes}
    if not series:
        result["message"] = "所选指标没有有效数据，未生成图片；不会生成空白曲线或用零填充。"
        return result
    target, statistics_data = _render(series, kind, day, notes)
    result.update(status="ok", image_path=str(target), mime_type="image/png",
                  media_line="MEDIA:" + target.as_posix(), series=statistics_data,
                  delivery_instruction="在当前微信回复中将 media_line 原样独占一行，交给渠道作为图片附件发送；不要重复调用 message 发送同一图片。不要将路径文字当作已送达，也不要声称模型看过图片。")
    service.atomic_json(target.with_suffix(".json"), result)
    return result

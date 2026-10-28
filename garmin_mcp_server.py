"""Read-only MCP bridge using the China authentication already verified locally."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

import garmin_service as service
import garmin_extended as extended

app = FastMCP("Garmin China Coach")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)


@app.tool(annotations=READ_ONLY)
def get_health_summary(days: int = 7, end_date: str | None = None, refresh: bool = False) -> dict:
    """读取连续 1–28 天健康摘要：睡眠分期、评分、HRV、心率、压力、电量、步数、热量和活动。

    end_date 为北京时间 YYYY-MM-DD，默认为今天。refresh=True 会忽略缓存。
    今天的缓存最多保留 15 分钟，历史缓存最多保留 24 小时。缺失值不能当作零。
    """
    return service.safe_call(service.health_summary, days, end_date, refresh)


@app.tool(annotations=READ_ONLY)
def get_recent_activities(limit: int = 5, start: int = 0, activity_type: str | None = None) -> dict:
    """分页读取运动摘要（每页 1–20 条），含 activityId、名称、功率、跑步动态及训练效果。

    start 从 0 开始。activity_type 可为 running/cycling/swimming/multi_sport/
    fitness_equipment/hiking/walking/other；子类型筛选应在返回列表中识别。
    需要曲线、分圈或力量组数时，用返回的 activityId 调 get_activity_details。此工具不返回 GPS。
    """
    return service.safe_call(service.recent_activities, limit, start, activity_type)


@app.tool(annotations=READ_ONLY)
def get_data_status() -> dict:
    """只检查本地中国区凭证是否存在，不显示凭证内容，也不发网络请求。"""
    return service.data_status()


@app.tool(annotations=READ_ONLY)
def get_sleep_details(date: str | None = None, include_series: bool = False,
                      max_points: int = 240, refresh: bool = False) -> dict:
    """查询某晚睡眠详情（日期 YYYY-MM-DD，默认今天），含阶段秒数、起止、血氧、呼吸、HRV、睡眠需求。

    include_series=true 才返回阶段时间线、心率/压力/电量/血氧/呼吸/HRV/体动曲线。
    每条曲线最多 max_points 点（2–2000），抽样会明确标记；默认只读摘要。
    """
    return service.safe_call(extended.sleep_details, date, include_series, max_points, refresh)


@app.tool(annotations=READ_ONLY)
def get_health_timeseries(date: str | None = None, metrics: list[str] | None = None,
                          max_points: int = 240, refresh: bool = False) -> dict:
    """按需读取一天的指定健康曲线，默认只查 heart_rate，不会读取全部类别。

    metrics 可选 heart_rate、steps、floors、stress、body_battery、respiration、spo2、hrv、
    intensity_minutes、events、body_battery_events。每条曲线最多 2–2000 点；抽样有标记。
    返回描述符用于解释时间及单位；负数状态码不是有效健康读数。
    """
    return service.safe_call(extended.health_timeseries, date, metrics, max_points, refresh)


@app.tool(annotations=READ_ONLY)
def get_training_metrics(groups: list[str] | None = None, days: int = 28,
                         end_date: str | None = None, refresh: bool = False) -> dict:
    """查询训练指标，默认仅 status 和 vo2max；按问题选择 groups，勿每次全量读取。

    groups 可选 status（状态、负荷与分布）、vo2max、race_predictions、fitness_age、
    lactate_threshold、cycling_ftp、zones。days=1–28；end_date 默认今天。
    阈值/FTP/区间为最新可用记录，可能早于日期范围，必须检查日期和 isStale。
    不提供255不支持的训练准备度/耐力/爬坡分数；当前无可用恢复倒计时。
    """
    return service.safe_call(extended.training_metrics, groups, days, end_date, refresh)


@app.tool(annotations=READ_ONLY)
def get_activity_details(activity_id: str, sections: list[str] | None = None,
                         include_location: bool = False, max_points: int = 240,
                         refresh: bool = False) -> dict:
    """按列表返回的 activityId 查询单次运动，默认只读 summary。

    sections 可选 summary、samples（曲线/跑步动态）、splits、heart_rate_zones、power_zones、
    exercise_sets（力量组数/次数/重量）、weather、gear。曲线最多 2–2000 点，抽样有标记。
    仅当用户问题需要路线时设置 include_location=true 读取 GPS，其余查询不返回坐标。
    """
    return service.safe_call(extended.activity_details, activity_id, sections, include_location, max_points, refresh)


@app.tool(annotations=READ_ONLY)
def get_training_workouts(kind: str = "workouts", workout_id: str | None = None,
                          year: int | None = None, month: int | None = None,
                          refresh: bool = False) -> dict:
    """查询自定义训练课/日历/计划，不创建或下发训练。

    kind=workouts 默认返回训练课列表，指定 workout_id 可读步骤；kind=calendar 按 year/month
    （默认本月，月份1–12）查日历，区分已完成活动、午睡和安排训练；kind=plans 查计划。
    没有训练计划时返回空，不能把接口外壳或已完成活动当成已安排训练。
    """
    return service.safe_call(extended.training_workouts, kind, workout_id, year, month, refresh)


@app.tool(annotations=READ_ONLY)
def get_personal_records(refresh: bool = False) -> dict:
    """读取账号已有个人最佳纪录、关联运动编号及日期；不创建或修改纪录。"""
    return service.safe_call(extended.personal_records, refresh)


@app.tool(annotations=READ_ONLY)
def get_device_capabilities(refresh: bool = False) -> dict:
    """查询手表型号与功能支持标记，不返回序列号或账号/设备编号；支持标记不等于已有测量。"""
    return service.safe_call(extended.device_capabilities, refresh)


if __name__ == "__main__":
    app.run(transport="stdio")

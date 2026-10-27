"""Read-only MCP bridge using the China authentication already verified locally."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

import garmin_service as service

app = FastMCP("Garmin China Coach")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)


@app.tool(annotations=READ_ONLY)
def get_health_summary(days: int = 7, end_date: str | None = None, refresh: bool = False) -> dict:
    """读取佳明中国区最近 1–28 天睡眠、HRV、静息心率、电量和活动摘要。

    end_date 为北京时间 YYYY-MM-DD，默认为今天。refresh=True 会忽略缓存。
    今天的缓存最多保留 15 分钟，历史缓存最多保留 24 小时。缺失值不能当作零。
    """
    return service.safe_call(service.health_summary, days, end_date, refresh)


@app.tool(annotations=READ_ONLY)
def get_recent_activities(limit: int = 5) -> dict:
    """读取最近 1–20 条运动的日期、距离、时长和心率，不返回路线、活动名称或账号信息。"""
    return service.safe_call(service.recent_activities, limit)


@app.tool(annotations=READ_ONLY)
def get_data_status() -> dict:
    """只检查本地中国区凭证是否存在，不显示凭证内容，也不发网络请求。"""
    return service.data_status()


if __name__ == "__main__":
    app.run(transport="stdio")

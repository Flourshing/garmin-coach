# 佳明曲线图片

在微信里说“画出我昨天的心率和压力曲线”或“把昨晚睡眠阶段与心率画成图”。bot 调用 `render_garmin_chart`，本机 Matplotlib 根据真实数据生成 PNG，微信回复管线发送图片附件。

模型不需要识图能力，也不自行编造数据点。它可根据工具返回的单位、有效点数、最小值、最大值和样本均值解释图像。

## 图表种类

| kind | 数据 | 默认指标 |
| --- | --- | --- |
| `health` | 指定一天的心率、压力、身体电量、呼吸、血氧、HRV、分时段步数 | `heart_rate` |
| `sleep` | 睡眠阶段、心率、压力、电量、血氧、呼吸、HRV、体动 | `stages`, `heart_rate` |
| `activity` | 心率、功率、配速、速度、步频/踏频、步幅、触地时间、垂直振幅/比、海拔、温度、表现状态 | `heart_rate`, `pace`, `power` |
| `trend` | 多日睡眠时长/评分、深睡/REM 时长、HRV、静息心率、步数、压力 | `sleep_hours`, `hrv`, `resting_hr` |

`date` 是所查日期或趋势截止日，默认今天；`trend` 的 `days` 为 1–28。运动图需要已有的 `activity_id`，日期以活动自身为准。

每张图最多 6 个指标，每条曲线 `max_points=100–2000`，默认 1000。上游或工具抽样会保留标记；缺失不填 0、不插值，长时间缺口留空。没有有效数据时返回 `status=no_data`，不生成假图。部分指标缺失时绘制有数据的部分，并在 `missing_metrics` 或 `unavailable` 中说明。

## 调用示例

```json
{"kind":"health","date":"2026-10-26","metrics":["heart_rate","stress","body_battery"]}
```

```json
{"kind":"sleep","date":"2026-10-26","metrics":["stages","heart_rate","hrv"]}
```

```json
{"kind":"trend","days":7,"metrics":["sleep_hours","hrv","resting_hr"]}
```

运动图先查询运动列表，再传入真实活动编号；不能编造编号。绘图不会读取 GPS。

## 微信附件

成功结果返回 `image_path`、`media_line` 和数值摘要。bot 应把 `media_line` 原样独占最终回复的一行，其他行可放简短解释。OpenClaw 将 `MEDIA:绝对路径.png` 解析成附件，微信插件读取本地 PNG 后上传。

不要只回复路径文字，也不要再调用一次 `message` 重复发送同一图片。生成文件不等于实际送达；传输错误时应如实说明。

PNG 和同名 JSON 元数据保存在 `OPENCLAW_WORKSPACE_DIR/charts/`。默认本机是 `.private/coach-workspace/charts/`，云端使用持久工作区；它们包含个人健康数据，不进入 Git 或构建镜像。

## 单位与显示

- 所有日间和睡眠时钟使用北京时间，GMT 只转换一次。
- 配速由确认单位为米/秒的速度换算，零速度处留空；不把描述符 `factor` 当作通用倍率。
- 睡眠阶段编码已结合实际返回时长核对：0 深睡、1 浅睡、2 REM、3 清醒。
- 图中 `sample_mean` 是所绘样本的均值，不等于佳明汇总均值。
- 普通日报默认不附图。可以在微信要求“以后日报附一张睡眠图，请保存偏好”。

Windows 使用微软雅黑，Linux 镜像使用 Noto CJK；找不到中文字体时退回英文标签，不会生成缺字标签。

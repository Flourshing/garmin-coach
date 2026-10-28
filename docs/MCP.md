# MCP 数据接口

所有工具只读佳明数据。默认读取摘要；按问题选择类别。工具可读范围、某次读取范围和最终回复内容是三件事。

## 查询示例

| 问题 | 建议调用 |
| --- | --- |
| 最近一周恢复怎么样 | `get_health_summary(days=7)` |
| 昨晚深睡和 REM 多久 | `get_sleep_details(date="YYYY-MM-DD")` |
| 睡眠阶段和心率如何随时间变化 | `get_sleep_details(date="YYYY-MM-DD", include_series=true)` |
| 昨天压力和电量变化 | `get_health_timeseries(date="YYYY-MM-DD", metrics=["stress", "body_battery"])` |
| 最近训练负荷 | `get_training_metrics(groups=["status", "vo2max"])` |
| 分析某次跑步功率 | 先列运动拿到 `activityId`，再查 `get_activity_details(activity_id="编号", sections=["summary", "samples", "power_zones"])` |
| 看力量训练组数 | `get_activity_details(activity_id="编号", sections=["summary", "exercise_sets"])` |
| 查看已有训练课步骤 | 先查 `get_training_workouts()`，再传入返回的 `workout_id` |

## 参数与范围

- `get_health_summary`：`days=1–28`，`end_date` 可指定历史截止日。返回扩展的每日健康、睡眠分期、HRV 和活动摘要。
- `get_recent_activities`：每页 `limit=1–20`，`start` 从 0 起。`activity_type` 只接受工具说明中的大类，子类型从返回结果中识别。
- `get_sleep_details`：默认只返回详情汇总；`include_series=true` 时附带睡眠阶段、体动、心率、压力、电量、血氧、呼吸及 HRV 曲线。
- `get_health_timeseries`：默认只查 `heart_rate`。可选 `steps`、`floors`、`stress`、`body_battery`、`respiration`、`spo2`、`hrv`、`intensity_minutes`、`events`、`body_battery_events`。
- `get_training_metrics`：默认 `status`、`vo2max`；还可选 `race_predictions`、`fitness_age`、`lactate_threshold`、`cycling_ftp`、`zones`。
- `get_activity_details`：默认 `summary`；可选 `samples`、`splits`、`heart_rate_zones`、`power_zones`、`exercise_sets`、`weather`、`gear`。`include_location=true` 才返回坐标。
- `get_training_workouts`：`kind` 为 `workouts`、`calendar` 或 `plans`；训练课详情可指定 `workout_id`；日历月份为 1–12。
- `get_personal_records`：返回已有个人纪录，不创建或修改纪录。
- `get_device_capabilities`：返回型号和能力布尔标记，能力存在不代表已产生测量。
- `get_data_status`：仅检查凭证文件是否存在，不访问佳明，不能据此判断在线登录有效。

扩展工具按类别返回 `data`，每组包含 `retrieved_at` 和 `value`；失败类别记录在 `unavailable`。使用真实 JSON 结果中的工具参数名称，不要把自然语言描述当成字段名。

## 数据解释

- 空值、空数组、没有活动和测量值 0 分别处理，不互相替代。
- 日期、记录更新时间和读取时间分别保留。`isStale=true` 的阈值或 FTP 是旧记录，不能写成今天的测量。
- 速度通常是米/秒，距离是米，时长是秒；运动明细按 `metric_descriptors` 解释，勿跨接口套用比例。阈值速度未统一换算，单位不明确时不要计算配速。
- 睡眠 GMT 字段是毫秒时间戳，转北京时间只处理一次时区。清醒时长不计入总睡眠。
- 压力等曲线中的负数状态码表示不可测量，不是健康读数。
- 最高、最低和某个历史日期的最近身体电量都不代表此刻电量。运动温度通道不是皮肤温度。
- 长曲线默认均匀抽样到最多 240 点，可设 2–2000 点。`source_points`、`returned_points`、`sampled` 说明抽样情况；上游自身也可能限制采样数量。

## 缓存与边界

当天和最新类数据缓存 15 分钟，历史日期缓存 24 小时；支持 `refresh=true`。账号标识、设备序列号和凭据被过滤，GPS 只有显式开启时返回。原始响应与缓存留在私有目录。

255 没有原生训练准备度、耐力得分、爬坡得分和跑步耐受度。当前接入也未成功读取恢复倒计时，不用其他分数冒充。游泳、铁三等有设备能力但账号没有记录的项目，不能声称已验证其有效字段。

验证脚本会把账号结果写到 `.private/`。不要把验证快照、运动轨迹或个人测量值作为公开测试样本提交。

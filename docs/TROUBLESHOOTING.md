# 故障排查

## 微信无法回复

先确认电脑未睡眠、启动进程仍在，再检查本机就绪状态：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/diagnostics/check_wechat.py
```

这个检查不读取聊天内容，也不发送消息。服务就绪和渠道已绑定不等于实际收发成功，最后仍需自己在微信发起一条查询验证。

检查同时核对微信插件是否注册、账号接收通道是否运行，以及是否存在渠道错误；只有 HTTP 端口在线不会判为正常。若日志出现 `no-channel-owner` 或 `peer link audit failed`，应先修复插件路径。

复制到其他盘符后，源码目录、工作区、MCP 的 Python/脚本路径、插件安装登记及依赖链接必须同步迁移。不要把旧目录的绝对路径直接带到新目录。先备份私有配置和数据库，再使用新目录的启动封装修复或同版本重装插件；保留账号绑定和历史数据。运行中的进程路径才是实际使用的项目，打开另一份目录的配置不会改变它。

本机默认地址为 `http://127.0.0.1:18789/readyz`。不要把带令牌的链接或完整配置发到公共 issue。

## MCP 读取失败

先区分工具注册失败、佳明登录失败、网络失败和数据为空，不要直接重装所有依赖。

```powershell
.\.venv\Scripts\python.exe -X utf8 collect.py --check
.\.venv\Scripts\python.exe -X utf8 verify_current_mcp.py
```

需要检查真实读取时使用 `--live`。凭证失效再运行 `login.cmd`；出现限流应停止重复请求。网络权限或代理错误不能直接解释为密码错误。

## 数据缺失或时间不对

先在手机 Garmin Connect 完成同步，检查查询日期、记录日期与 `retrieved_at`。当前缓存可能尚未刷新；需要时指定 `refresh=true`。空值、没有运动、当天数值 0 分别处理。睡眠 GMT 时间只转换一次时区。

## 模型没有回应

```powershell
.\.venv\Scripts\python.exe -X utf8 check_deepseek_setup.py
```

如需单独请求一次模型：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/diagnostics/check_deepseek_connection.py --run
```

该命令可能产生少量 API 费用，仅报告状态，不打印密钥或原始响应。代理设置需要与网关一致。

## 偏好没有延续

在微信说“请把已保存的日报偏好列给我看”。确认 bot 的文件写入成功，运行工作区有 `PREFERENCES.md`，且没有在迁移时丢失。仅说“这次简短一点”不会自动更新长期偏好。

## 日报没有按时推送

准备脚本默认创建停用任务。先检查任务是否启用、电脑是否在线、渠道是否可用，再核对任务执行和送达记录。`prepare_daily_job.py --run-test` 会发真实测试日报，只在明确要测试时运行，且不会自动开启正式定时。

## Node 版本不符

本项目启动脚本检查 Node `>=24.22.1 <25` 或 `>=26.12.1`。用 `OPENCLAW_NODE` 指定合适的可执行文件；不要重命名低版本程序来绕过检查。

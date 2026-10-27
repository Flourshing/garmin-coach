# 电脑关机后运行

这是托管容器部署准备文件，尚未部署或计费；当前电脑没有 Docker，镜像构建尚未实测。不要把本机测试成功理解成云端已经在线。

> 说明（2026-10-26）：**云端部署已对齐 DeepSeek**。Dockerfile 改为 COPY `deploy/deepseek-provider.json`（原 `plus-provider.json` 已不再引用），`.dockerignore` 与 `prepare_railway_build.py` 的白名单同步更新。云端凭据通过**平台环境变量 `DEEPSEEK_API_KEY`** 注入（镜像内不含任何密钥）。本机与云端现在共用同一份 `prepare_openclaw.py` 生成逻辑，默认模型均为 `deepseek/deepseek-flash`。
>
> 仍待实测：本机没有 Docker，**镜像尚未构建验证**，云端运行、微信扫码、佳明登录与隔夜送达都还没有在真实平台上跑过。不要把本机验证当成云端已在线。

部署平台需要支持常驻服务和持久磁盘。微信渠道采用长轮询，不能依赖会随时休眠的免费网页进程。可参考 OpenClaw 的 Railway 托管部署说明：https://docs.openclaw.ai/install/railway 。

## 部署时的配置

1. 用本项目的 Dockerfile 构建服务，配置至少一个挂载到 `/data` 的持久卷。
2. 平台变量中配置随机的 `OPENCLAW_GATEWAY_TOKEN`，不要发到聊天、写入 Git 或作为构建参数。
3. 配置 `PORT=8080`；启用平台的 HTTPS 访问后，将具体域名写入 `OPENCLAW_PUBLIC_ORIGIN`。
4. **在平台环境变量中配置 `DEEPSEEK_API_KEY`**（DeepSeek 密钥，从 https://platform.deepseek.com/api_keys 获取）。配置为平台变量，不要写入 Git、不要作为构建参数、不要发到聊天里。模型凭据不落盘到镜像。微信扫码在云端终端完成；持久卷保存登录状态。整个容器仍未构建验证。
5. 佳明凭证需要在云端私下配置：可以运行 `python collect.py --login --portal --days 1` 重新登录中国区。不要公开上传本机 `.private` 目录。
6. 先验证微信询问可以获得真实佳明数据，再运行 `python prepare_daily_job.py --run-test`。它只接受一个已绑定、且有本人来信记录的微信账号，创建北京时间每天 08:00 的停用任务，并手动测试一次；不会启用正式定时。再次运行不会重复发送测试，必须先检查原测试记录。
7. 实测主动发送和隔夜发送。记录真正的下一次执行时间与微信送达结果后，再验收电脑关机场景。

日报提示词位于 `daily-report-prompt.txt`。部署后应监测令牌失效、佳明限流和微信发送失败，并保留未发送的报告以便恢复。不得把发送失败记录成已送达。

模型连接使用 `deepseek-provider.json` 中的 DeepSeek 官方 OpenAI 兼容端点（`https://api.deepseek.com`，`openai-completions`）和 OpenClaw 自身运行循环，密钥来自平台环境变量 `DEEPSEEK_API_KEY`。云端镜像不额外安装未使用的原生 Codex 组件；本机已安装组件保持禁用，此前批准的隔离配置仍保留。Windows 的本机代理不会带入镜像，托管平台的网络和授权需要重新实际验证——**特别是要确认云主机能直连 `api.deepseek.com`**。若迁移同一个微信机器人账号，切换前停止本机接收服务，避免两处同时接收和回复。

## 运行检查

云端控制台中运行：

```text
python collect.py --check
openclaw config validate
openclaw channels status
openclaw automations list
```

以上文件只准备部署结构，平台账号、费用和地区需实际选择后再部署。源码可以公开；所有私人数据和登录凭证应保存在持久卷中。

本机已验证模型回复、佳明工具调用、微信双向聊天及手动日报发送；每天 08:00 的正式任务保持停用。云端配置已通过本机配置生成检查，构建上下文采用允许列表，只包含所需程序和模板，不打包私人数据与登录目录。当前仍没有本地 Docker，镜像构建、云端运行和隔夜送达尚未实测。

## Railway 试用部署

用户已选择先使用试用额度；尚未授权升级付费套餐。先用 `connect-railway.cmd` 由本人注册或登录，再核对试用类型及剩余额度。部分未验证账号有出站网络限制，需要实际检测佳明、DeepSeek 和微信连接，不应直接升级解决。

运行 `python prepare_railway_build.py` 会创建只含明确列出的程序文件的全新目录，路径和校验值保存到 `.private/railway-build-status.json`。Railway 上传必须以该目录为根，并指定 `--path-as-root`；不得从项目根目录直接上传，也不得将整个 `.private` 加入构建。`railway.json` 配置新加坡单实例、健康检查和最多三次故障重启。平台仍需实际配置 `/data` 持久卷、关闭服务休眠，并核对试用资源限制。

2026-10-23，用户确认本机测试日报已经在微信收到。正式云端定时仍需部署和验证后启用。

2026-10-23 后续核查：Railway 官方状态页 https://status.railway.com/ 报告平台事故仍在处理中，且新用户注册暂时暂停。用户 Google 登录页面显示 `Invalid state in Google OAuth`；不能据此断定浏览器校验错误的具体成因，但平台暂停注册本身已阻止新账号试用。已停止本项目等待中的登录请求；未创建云服务、未购买套餐，也未上传账号凭证。继续注册前必须重新核对官方状态，不能反复开启授权窗口。

## 部署清单（按顺序执行）

> 下面每一步都需要**你本人**在平台控制台操作。助手无法代注册、代付费或代完成实名认证。

**第 1 步：选平台并开机器**
- 需要满足：**常驻不休眠** + **可挂持久磁盘** + **能自定义环境变量**。
- 国内可选阿里云/腾讯云的轻量服务器（约 5–15 元/月的入门款即可）；海外可选 Railway / Fly.io 等。
- ⚠️ 避开会「闲置休眠」的免费 PaaS——微信是长轮询，一休眠机器人就掉线。

**第 2 步：打包上传内容**
在本机项目目录执行：
```powershell
& '.\.venv\Scripts\python.exe' -X utf8 prepare_railway_build.py
```
它会在 `.private\railway-build-<随机>` 下生成一个**只含 19 个程序文件**的干净目录，并把清单与 SHA256 存到 `.private/railway-build-status.json`。已核对：**不含 `.private`、不含任何密钥**。上传必须以该目录为根。

**第 3 步：配置平台环境变量（关键）**

| 变量 | 值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 你的 `sk-...` | **模型凭据，必须配** |
| `OPENCLAW_GATEWAY_TOKEN` | 随机长字符串 | 网关访问令牌，自己生成一个 |
| `PORT` | `8080` | |
| `OPENCLAW_PUBLIC_ORIGIN` | 你的 HTTPS 域名 | 启用 HTTPS 后再填 |
| `GARMIN_DATA_DIR` | `/data/garmin` | |

这些**只配在平台变量里**，不要写进 Git、不要当构建参数、不要发聊天。

**第 4 步：挂持久卷**
必须把持久磁盘挂到 `/data`。佳明令牌、微信登录状态、健康缓存都在这里，容器重建后靠它恢复。

**第 5 步：云端完成登录**
- **佳明**：在云端终端跑 `python collect.py --login --portal --days 1`，按提示输入中国区账号、密码、验证码。不要把凭据发聊天。
- **微信**：在云端完成扫码绑定。

**第 6 步：验证（别跳过）**
```text
python collect.py --check
openclaw config validate
openclaw channels status
```
再用微信实际发一条问健康数据的消息，确认能取到真实数据再往下走。

**第 7 步：迁移微信账号前先停本机**
同一个微信机器人账号**不能两处同时接收**。切云端前，先关掉本机的 `启动佳明教练.cmd` 窗口。

**第 8 步：最后才启用日报**
先 `python prepare_daily_job.py --run-test` 手动测一次；确认收到后再考虑启用每天 08:00 的正式任务。

### 尚存风险（如实列出）
- **镜像从未构建过**：本机没有 Docker，Dockerfile 只做过静态检查，第一次构建可能还要修。
- **云端网络未验证**：需确认云主机能直连 `api.deepseek.com`；国内机房通常可以，但有例外。
- **佳明登录在云端可能要重新过验证码**，且令牌有失效风险，需要监测。
- **费用**：按量计费，DeepSeek 的模型费另算（与换云端无关，本来就付）。

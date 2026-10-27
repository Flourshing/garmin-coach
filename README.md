# Garmin 微信私人教练（OpenClaw + DeepSeek）

> 通过微信和你的 Garmin 数据对话：一个只读、隐私优先的个人健康教练机器人。

你在微信里问「我最近七天睡得怎么样」，它会真正去佳明中国区拉取你的睡眠、HRV、静息心率和运动记录，再由大模型给出中文分析和建议——**数据只经过你自己的机器和模型 API，不发给第三方。**

---

## 目录

- [这是什么](#这是什么)
- [架构](#架构)
- [功能](#功能)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [可用工具](#可用工具)
- [部署到云端](#部署到云端)
- [安全与隐私](#安全与隐私)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [参考资料](#参考资料)

---

## 这是什么

一个把四样东西串起来的小系统：

| 组件 | 作用 |
|---|---|
| **Garmin Connect（中国区）** | 数据源：睡眠、HRV、静息心率、Body Battery、运动记录 |
| **只读 MCP 服务器** | 把佳明数据包装成 3 个只读工具，供模型调用 |
| **OpenClaw 网关** | 教练的「大脑外壳」：接微信、加载工具、管理会话 |
| **DeepSeek API** | 真正的大模型，负责理解问题和生成中文回复 |

核心设计原则是**只读**：它不会修改你的佳明账号、活动或手表设置，也拿不到 GPS 路线、活动名称等敏感字段。

## 架构

```
       ┌──────────────┐
       │    微信      │  发消息 / 收回复
       └──────┬───────┘
              │  长轮询（openclaw-weixin 插件）
              ▼
   ┌──────────────────────┐
   │   OpenClaw Gateway   │  本机 127.0.0.1:18789
   │  ┌────────────────┐  │
   │  │ 教练人格与规则  │  │  coach/SOUL.md、AGENTS.md
   │  └───────┬────────┘  │
   └──────────┼───────────┘
              │  MCP (stdio)
              ▼
   ┌──────────────────────┐        ┌────────────────┐
   │  garmin_mcp_server   │        │  DeepSeek API  │
   │  （只读 3 个工具）   │        └───────┬────────┘
   └──────────┬───────────┘                │ HTTPS
              │                            │
              ▼                            │
   ┌──────────────────────┐                │
   │ Garmin Connect 中国区 │                │
   │   （复用本地令牌）    │                │
   └──────────────────────┘                │
                                           │
              OpenClaw 网关 ───────────────┘
```

## 功能

- **微信双向对话** —— 在微信里直接问，机器人直接答
- **真实数据，不编造** —— 工具返回空值时明确说「没有数据」，不会把缺失值当成 0
- **只读安全边界** —— 三个工具都标注 `readOnlyHint`，无写入能力
- **本地缓存** —— 历史数据缓存 24 小时、当天数据 15 分钟，减少对佳明的请求
- **日报** —— 可配置北京时间每天 08:00 主动推送健康摘要
- **凭据隔离** —— 令牌、API 密钥全部在 `.private/`（已被 Git 忽略）
- **可换模型** —— 供应商定义在配置文件里，换模型只改一个字段

## 快速开始

### 前置条件

- Windows（脚本面向 Windows；Linux 可用 [Docker 方式](deploy/README.md)）
- Python 3.12
- Node.js **>=24.22.1 <25** 或 **>=26.12.1**（OpenClaw 2026.10.6 的要求）
- 佳明中国区账号
- DeepSeek API 密钥（[platform.deepseek.com](https://platform.deepseek.com/api_keys)）
- 一个可扫码绑定的微信机器人入口

### 步骤

**1. 安装 Python 依赖**

```powershell
git clone <你的仓库地址>
cd garmin

python -m venv .venv
& '.\.venv\Scripts\python.exe' -m ensurepip --upgrade --default-pip
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

**2. 安装 OpenClaw 运行时**

```powershell
cd .runtime
npm install --no-audit --no-fund
cd ..
```

> ⚠️ 注意 Node 版本。若默认 `node` 版本过低，用 `OPENCLAW_NODE` 指定符合要求的路径。

**3. 填写模型密钥**

```powershell
New-Item -ItemType Directory -Force .private | Out-Null
Copy-Item .env.example .private\.env.dsh
notepad .private\.env.dsh   # 填入 DEEPSEEK_API_KEY=sk-...
```

**4. 登录佳明中国区（只需一次）**

双击 `login.cmd`，按提示输入中国区账号、密码和验证码。

> 密码和验证码不会写入脚本或日志。登录令牌保存在 `.private/tokens/`，**请像密码一样保管**——它未额外加密。

**5. 验证链路**

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 collect.py --check
& '.\.venv\Scripts\python.exe' -X utf8 check_deepseek_setup.py
```

**6. 绑定微信并启动**

```powershell
.\connect-wechat.cmd       # 首次绑定，弹出二维码
.\启动佳明教练.cmd          # 日常启动，窗口需保持打开
```

看到 `http server listening (2 plugins: memory-core, openclaw-weixin)` 即成功。

## 配置说明

### 模型供应商

默认使用 DeepSeek 官方 OpenAI 兼容端点，定义在 [`deploy/deepseek-provider.json`](deploy/deepseek-provider.json)：

```json
{
  "baseUrl": "https://api.deepseek.com",
  "api": "openai-completions",
  "auth": "api-key",
  "apiKey": "${DEEPSEEK_API_KEY}",
  "models": [{ "id": "deepseek-flash", "name": "DeepSeek V4 Flash" }]
}
```

换模型只改 `models[0].id`，例如 `deepseek-v4-pro`。

### 环境变量

见 [`.env.example`](.env.example)：

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | 模型密钥，**必填** |
| `OPENCLAW_GATEWAY_TOKEN` | 网关访问令牌，云端必填 |
| `OPENCLAW_PUBLIC_ORIGIN` | 公开 HTTPS 域名，云端填写 |
| `PORT` | 监听端口，云端为 8080 |
| `GARMIN_DATA_DIR` | 佳明数据目录，云端建议 `/data/garmin` |
| `OPENCLAW_NODE` | 指定 Node 路径（版本不符时使用） |

### 教练人格

教练的语气、规则和记忆都在 [`coach/`](coach/)，都是 Markdown，改它们不需要碰代码：

| 文件 | 用途 |
|---|---|
| `SOUL.md` | 人格、回答风格、安全边界 |
| `AGENTS.md` | 工作区约定：每次会话读哪些文件 |
| `USER.md` | 用户已确认的信息（手表、时区、渠道等） |
| `MEMORY.md` | 长期记忆 |

## 可用工具

MCP 服务器 [`garmin_mcp_server.py`](garmin_mcp_server.py) 暴露三个**只读**工具：

| 工具 | 说明 |
|---|---|
| `get_health_summary` | 最近 1–28 天的睡眠、HRV、静息心率、Body Battery、活动摘要 |
| `get_recent_activities` | 最近 1–20 条运动的日期、距离、时长、心率（**不含路线和活动名称**） |
| `get_data_status` | 仅检查本地凭证是否存在，不发网络请求 |

缺失指标保持为空并单独标记——**空值不等于零**，这是刻意的设计。

## 部署到云端

本地运行的前提是电脑一直开机。想让关机后也能用，需要把服务搬到常开的机器上。

项目已准备好容器化部署：

```powershell
# 生成只含必需程序文件的干净构建目录（不含任何密钥）
& '.\.venv\Scripts\python.exe' -X utf8 prepare_railway_build.py
```

完整部署清单见 **[deploy/README.md](deploy/README.md)**。关键点：

- 需要**常驻不休眠**的平台——微信是长轮询，休眠即掉线
- 必须挂载持久卷到 `/data`，否则容器重建后要重新登录
- **同一个微信账号不能本机与云端同时接收**，切换前先停本机

## 安全与隐私

| 措施 | 实现 |
|---|---|
| 凭据不入库 | `.private/` 在 `.gitignore` 中；镜像构建白名单不含密钥 |
| 只读工具 | 三个 MCP 工具全部标注 `readOnlyHint=True` |
| 数据最小化 | 不返回 GPS 路线、活动名称、活动 ID、账号标识 |
| 错误脱敏 | 上游异常统一包装，避免泄露 URL、cookie、service ticket |
| 工具白名单 | `tools.deny` 禁用 `exec`、`process`、`subagents` 等 |
| 文件范围限制 | `tools.fs.workspaceOnly: true` |

**你需要自己保管好：**

- `.private/tokens/` —— 佳明登录令牌，等同密码
- `.private/.env.dsh` —— 模型 API 密钥
- `.private/openclaw/openclaw.json` —— 含网关访问令牌

## 常见问题

**Q：手机上提示「暂时无法连接 OpenClaw」？**
A：网关没在跑。双击 `启动佳明教练.cmd`，等 1–2 分钟，别关那个黑窗口。

**Q：过一段时间就断了？**
A：电脑睡眠了。把电源设置改成「永不睡眠」，或部署到云端。

**Q：佳明 MCP 连不上（`MCP error -32000`）？**
A：多为 Python 依赖损坏，重装即可：

```powershell
& '.\.venv\Scripts\python.exe' -m pip install --force-reinstall -r requirements.txt
```

**Q：微信插件加载失败（`missing-openclaw-peer-link`）？**
A：插件的 peer link 断了。在插件安装目录重建指向 openclaw 的链接，或重跑插件安装。

**Q：`No suitable Node.js found`？**
A：Node 版本不满足要求。安装 Node 24.22.1+ 或 26.12.1+，或用 `OPENCLAW_NODE` 指定路径。

**Q：日报没有按时推送？**
A：正式定时任务默认**停用**。先手动测一次：`python prepare_daily_job.py --run-test`。

## 项目结构

```
.
├── coach/                  # 教练人格与记忆（Markdown，可自由修改）
├── deploy/                 # 云端部署：供应商配置、容器定义、部署清单
├── collect.py              # 佳明数据采集（CLI）
├── garmin_service.py       # 只读佳明接口 + 缓存
├── garmin_mcp_server.py    # MCP 服务器（3 个只读工具）
├── prepare_openclaw.py     # 生成 OpenClaw 配置
├── prepare_daily_job.py    # 创建日报定时任务
├── verify_mcp.py           # MCP 链路验证
├── check_deepseek_setup.py # 一键自检（不打印密钥）
├── openclaw.ps1 / .cmd     # OpenClaw 启动封装（自动定位 Node、注入密钥）
├── start-coach.ps1         # 教练启动脚本
├── 启动佳明教练.cmd         # ← 日常双击这个
├── login.cmd               # 佳明登录
├── Dockerfile              # 云端容器定义
└── .env.example            # 环境变量模板
```

## 参考资料

- [python-garminconnect 0.3.10](https://github.com/cyberjunky/python-garminconnect/tree/0.3.10) —— 非官方佳明客户端
- [Garth 维护者公告](https://github.com/matin/garth#garth) —— 旧认证流程变更说明
- [腾讯微信插件](https://github.com/Tencent/openclaw-weixin/blob/main/README.zh_CN.md)
- [微信渠道协议与发送限制](https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol.md)
- [OpenClaw 文档](https://docs.openclaw.ai)
- [DeepSeek API 文档](https://api-docs.deepseek.com)

## 免责声明

本项目使用**非官方**的佳明客户端（`python-garminconnect`），与 Garmin 官方无关，接口变更可能导致失效。

在依赖本项目的健康建议之前请记住：**它不是医疗器械，不能替代医生。**

## License

[MIT](LICENSE)
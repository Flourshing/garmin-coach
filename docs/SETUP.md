# 安装与启动

以下命令在项目根目录的 PowerShell 中执行。仓库名和本机文件夹名可以不同，不需要改代码。

## 1. Python 依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 collect.py --check
```

`requirements.txt` 固定佳明和 MCP 版本；`--check` 只检查本地环境。

## 2. OpenClaw 运行时

先安装满足启动脚本要求的 Node：`>=24.22.1 <25` 或 `>=26.12.1`。

```powershell
New-Item -ItemType Directory -Force .runtime | Out-Null
Copy-Item deploy/runtime-package.json .runtime/package.json
npm install --prefix .runtime --no-audit --no-fund
```

`.runtime` 不在 Git 中，需要从仓库里的清单创建，不能直接进入一个尚不存在的 `.runtime` 目录安装。

若默认 Node 版本不符，可以在当前 PowerShell 设置：

```powershell
$env:OPENCLAW_NODE = 'C:\path\to\node.exe'
```

## 3. 本机模型密钥

```powershell
New-Item -ItemType Directory -Force .private | Out-Null
Copy-Item .env.example .private/.env.dsh
notepad .private/.env.dsh
```

填写自己的 `DEEPSEEK_API_KEY`。启动封装会从该文件读取密钥；不要把真实值写进源码或聊天。DeepSeek 供应商和编号定义在 `deploy/deepseek-provider.json`。如需 GPT 订阅优先、DeepSeek 自动备用和微信切换，完成基础准备后按 [双模型设置](MODELS.md) 操作；准备脚本会保留已经设置的模型与认证顺序。

## 4. 微信插件与教练配置

先查看微信插件是否已随运行时可用；缺少时再安装：

```powershell
.\openclaw.cmd plugins list
# 仅在没有 openclaw-weixin 时执行
.\openclaw.cmd plugins install "@tencent-weixin/openclaw-weixin"
.\openclaw.cmd config set plugins.entries.openclaw-weixin.enabled true
.\.venv\Scripts\python.exe -X utf8 prepare_openclaw.py
.\openclaw.cmd config validate --json
```

插件安装和扫码流程以[腾讯官方说明](https://github.com/Tencent/openclaw-weixin/blob/main/README.zh_CN.md)为准。本项目封装将状态保存在 `.private/openclaw`。

准备脚本同步 `SOUL.md`、`AGENTS.md`，更新前保存规则备份；`USER.md`、`MEMORY.md`、`PREFERENCES.md` 只在缺失时创建，不覆盖个人设置。

## 5. 登录佳明并绑定微信

```powershell
.\login.cmd
.\connect-wechat.cmd
```

在本机窗口填写佳明中国区账号和验证码，通过微信扫码授权。佳明令牌位于 `.private/tokens`；不要公开上传该目录。

## 6. 验证和日常启动

```powershell
.\.venv\Scripts\python.exe -X utf8 check_deepseek_setup.py
.\.venv\Scripts\python.exe -X utf8 verify_current_mcp.py
.\启动佳明教练.cmd
```

首次启动可能需要等待。就绪后在微信里发起一次数据查询，区分“服务正常”“渠道已绑定”和“实际收发成功”。日常使用保持电脑联网、唤醒及运行窗口打开。

## 更新项目

先查看本地修改并备份个人状态，再正常拉取 Git 更新。依赖版本变化时重新安装相应依赖，然后运行准备脚本和 MCP 检查。已经运行的 MCP 进程需要重新加载代码，可在没有聊天执行时关闭原运行窗口，再通过日常入口启动，避免启动两份服务。

不要用 `git reset --hard` 或覆盖 `.private` 的方式更新。个性化设置保存在私有工作区，不应写回公开的 `coach/` 模板。

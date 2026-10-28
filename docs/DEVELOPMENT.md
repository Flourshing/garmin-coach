# 开发与维护

## 目录约定

根目录保留运行模块和用户入口，避免移动入口导致已配置的 MCP 路径失效。`tests/` 只放离线测试，`scripts/diagnostics/` 放可选的运行诊断，`docs/` 放操作说明，`deploy/` 放部署文件。

旧订阅接入、旧认证客户端和带固定日期的验证脚本已退出当前流程。现用客户端为 `garminconnect==0.3.10`，共享错误信息处理位于 `garmin_data.safe_error`，MCP 验证入口是 `verify_current_mcp.py`。

## 本地检查

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m compileall -q collect.py garmin_data.py garmin_extended.py garmin_service.py garmin_mcp_server.py prepare_openclaw.py
.\.venv\Scripts\python.exe -X utf8 verify_current_mcp.py
```

单元测试不使用个人凭据、不访问网络、不产生模型费用。GitHub Actions 在 Windows 和 Linux 上运行离线检查。

真实查询需本机已登录：

```powershell
# 日期换成有已同步数据的一天
.\.venv\Scripts\python.exe -X utf8 verify_current_mcp.py --live --end-date 2026-10-26
```

真实验证只查询佳明，不调用模型、不发送微信。结果保存在 `.private/mcp-expanded-results.json` 等私有文件中。

## 修改字段或新增工具

1. 在 `garmin_data.py` 调整共享字段和过滤规则，或在 `garmin_extended.py` 添加分类查询。
2. 在 `garmin_mcp_server.py` 注册只读工具，并同步 `TOOL_NAMES`；不要给只读接口增加写入操作。
3. 保留日期、单位、空值、读取失败、旧记录和抽样信息。新增字段不能默认填 0。
4. 更新离线测试和 `docs/MCP.md`；工具或默认查询变动时同步教练规则。
5. 新增运行模块时同步 `Dockerfile`、`.dockerignore` 和 `prepare_railway_build.FILES`。
6. 准备配置并重新加载运行中的 MCP，再用真实账号做必要的有界验证。

健康摘要结构变化时增加缓存版本，避免旧缓存遮住新字段。不要把真实账号样本提交为单元测试数据。

## 工作区升级

`prepare_openclaw.py` 会备份并同步 `SOUL.md`、`AGENTS.md`，个人资料、偏好和记忆仅在缺失时初始化。修改回答偏好应放在运行工作区 `PREFERENCES.md`，不要改公开模板来存个人设置。

本机只更新规则、不改模型配置时，可调用 `sync_workspace`；正常安装使用完整准备脚本。已有网关需要重新加载代码，不要启动两个微信接收进程。

## 发布到 GitHub

先检查差异，再提交明确的源码与文档路径，正常推送到已有远端：

```powershell
git status --short
git diff --check
git diff --stat
# 确认待提交文件不包含 .private、密钥、个人报告或缓存后再提交
git push origin HEAD
```

`push-github.cmd` 只推送现有提交，不自动暂存或提交、不改远端、不强制覆盖。首次使用需要安装 Git 并完成自己的 GitHub 登录。

## 容器准备

```powershell
.\.venv\Scripts\python.exe -X utf8 prepare_railway_build.py
```

它生成允许列表中的干净源码目录，不会上传或部署。实际 Linux 镜像构建与云端收发需单独验证，见 [部署文档](../deploy/README.md)。

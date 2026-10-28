# GPT 订阅与 DeepSeek

双模型模式使用 ChatGPT/Codex 订阅授权作为主模型，DeepSeek API 作为备用。两边均使用 OpenClaw 运行工具，沿用同一套佳明 MCP、绘图与工作区偏好。

## 配置与登录

先完成基础安装、佳明和 DeepSeek 配置，再运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 configure_models.py
.\openclaw.ps1 models auth login --provider openai
.\openclaw.ps1 models list --provider openai --refresh
```

浏览器中登录自己的 ChatGPT 账号并授权。凭证由 OpenClaw 保存在私有状态目录；不需要复制桌面应用的登录文件，也不要把密码、授权码或令牌放进聊天或 Git。

`configure_models.py` 的初始候选为 `openai/gpt-6-astra`；模型列表不是可调用证明，必须以账号实际可用模型和成功请求为准。如账号没有该候选，用实际模型重新配置：

```powershell
.\.venv\Scripts\python.exe -X utf8 configure_models.py --gpt-model openai/账号实际可用的模型编号
```

脚本会保留配置备份，设置 `gpt` 和 `dsh` 别名。普通准备脚本不会再删除 OpenAI 配置、认证顺序或覆盖已选模型。OpenAI 路由显式使用订阅 OAuth，不配置 OpenAI API Key；DeepSeek 仍按其 API 用量计费。

两个模型的思考档位不同：初始 GPT 候选使用 `low`，DeepSeek Flash 使用 `off`；脚本为它们分别设置默认值，保留已有自定义值。新建日报不再硬编码共用的 `low`。若手动传入 `/think` 或 CLI `--thinking`，须使用该模型支持的档位；不兼容的显式参数可能在发出请求前被拒绝。

## 在微信切换

| 命令 | 行为 |
| --- | --- |
| `/model gpt` | 回到已配置默认 GPT，并恢复 DeepSeek 自动备用 |
| `/model default` | 清除会话锁定，跟随项目默认模型与备用链 |
| `/model dsh` | 当前会话固定使用 DeepSeek |
| `/model` | 查看当前选择 |
| `/status` | 查看本会话状态及实际回答模型/回退提示 |

切换命令单独发一条消息；自然语言“改用 GPT”不保证会修改底层路由。命令默认只影响当前聊天，不改其他会话或定时任务。若全局默认已改为其他模型，`/model gpt` 将成为严格选择；此时用 `/model default` 跟随全局备用策略。

已有聊天可能保留之前选择的模型；配置双模型后先发送 `/model default`。继承项目默认的日报会使用同一备用链；显式指定了模型或空备用列表的任务需要单独检查，不能仅凭默认配置认定任务已改变。

## 自动备用的边界

默认链为 GPT → DeepSeek。OpenClaw 对可恢复的额度/限流、认证、供应商连接等失败做有限重试，再尝试备用模型。它按实际请求错误和凭证冷却状态工作，不会提前保证剩余额度，也不会无限等待。

回退只作用于本次请求，不把 DeepSeek 永久写成默认；后续请求仍按 GPT 优先及冷却策略选择。取消、总运行超时、本地状态冲突或不可安全重放的工具副作用等终止条件不会强制改用备用。整个网络均不可用时，两边都可能失败。

备用模式会将完成该次分析所需的数据和聊天上下文交给 DeepSeek。图表仍由本地程序生成；模型更换不扩大佳明工具范围。

可用范围与认证方式参考 [OpenAI 官方认证说明](https://learn.chatgpt.com/docs/auth)。订阅有使用额度；可用模型与权限以账号返回为准。

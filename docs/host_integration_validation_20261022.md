# TOMC 宿主接入验证（2026-10-22）

接口验证阶段完成官方文档核对、用户配置只读检查和隔离运行测试，未发出付费模型请求。随后主集成已安装本机 0.1.5、升级已有小猫及 Claude MCP 路径并备份配置，写入两端会话 hooks；未绕过宿主 hook 信任审查。

## 已确认的能力与边界

| 项目 | Codex | Claude Code |
|---|---|---|
| 用户级配置 | 本机配置已有 `tomc-memory@tomc-local` 启用项 | 本机 `.claude.json` 顶层已有 TOMC MCP；不是 marketplace 安装记录 |
| 配置是否等于运行成功 | 否；会话加载、连接与调用需另行观测 | 否；同左 |
| 注册事件 | `SessionStart`、`UserPromptSubmit`、`Stop` | 同左 |
| 会话身份来源 | hook stdin 的 `session_id`，不从标题/项目猜测 | 同左 |
| 逐会话暂停 | 受支持的 TOMC 工具在 `PreToolUse` 返回 `deny` | 同左 |
| 调用参数归因 | 启动时提供身份上下文，调用方显式传入；属于已声明身份 | `PreToolUse` 替换参数中的身份字段，不返回 `allow` |
| 自动替换整个模型请求 | 已核对的 hooks 未提供此接口 | 已核对的 hooks 未提供此接口 |
| 实际请求输入/费用降低 | 本轮未测量 | 本轮未测量 |

官方 hook 接口支持登记事件、附加上下文、控制或修改工具调用。它们没有在这里提供删除并替换整个模型请求历史的入口；不能把 `updatedInput`（工具参数）说成模型请求重写。[Codex hooks](https://learn.chatgpt.com/docs/hooks)、[Claude hooks](https://code.claude.com/docs/en/hooks)

Codex 改写工具参数要求同时返回 `permissionDecision: allow`。本实现只在暂停时拒绝，不为身份注入自动批准调用。Claude 可只返回 `updatedInput`，保留正常审批。两个实现都只匹配 TOMC 的 `prepare_context` / `recall_memory`，不改其他工具参数或审批配置。[Codex PreToolUse](https://learn.chatgpt.com/docs/hooks#pretooluse)、[Claude PreToolUse](https://code.claude.com/docs/en/hooks#pretooluse-decision-control)

## 身份与界面状态

`session_hook.py` 将宿主明确传入的 ID、项目、可选标题和事件写入 `SessionStore`。不打开 `transcript_path`，不把 prompt、tool_input 或工具正文存入会话目录。CLI 的 `claude_code` 统一写为存储中的 `claude`。

“最近活动会话”由最近一次启动/恢复或提交输入事件选择；工具调用和回复停止只更新时间，不抢走已选择的会话。单纯点击另一个聊天标签不一定产生事件。因此它不是前台窗口焦点，更不能作为 MCP 请求身份。

本机执行工具环境中能观察到 `CODEX_THREAD_ID`，但这没有验证 TOMC MCP 子进程继承它或每次调用都绑定当前会话。实现不使用它作为自动身份，也不读取全局 active 行归因。Codex 调用方传入的已登记 ID 仍是声明值，不具备不可伪造的逐请求认证。缺少身份的调用须显示未关联。Claude 的 hook 注入路径还需在用户真实客户端中验证。

Codex 官方还说明根线程、fork 及 session tree 存在区别；本阶段以 hook 明确报告的会话为单位，不将其宣传为所有子线程的独立身份。[App server 会话模型](https://learn.chatgpt.com/docs/app-server#start-or-resume-a-thread)

## 安装与运行验证

`scripts/install_session_hooks.py` 默认只预览。`--install` 才写用户级 hooks：Codex 为 `.codex/hooks.json`，Claude 为 `.claude/settings.json`。只替换带 TOMC 专用标记的处理器，保留其他设置和 hook；写入前保存原文件的精确字节备份，使用唯一文件名与原子替换。预览不会打印原有账户环境配置。

Windows 的 Codex command override 用经过字面量引用的 PowerShell 编码命令；Claude 用官方 exec-form `command` 加 `args`，避免再次解析路径。测试实际启动隐藏的 PowerShell 子进程，验证含中文、空格、单引号、美元符号、分号、反引号和 `&` 的路径及 UTF-8 stdin 均正确。

Codex 新 hook 必须先由用户在 `/hooks` 审阅并信任。本安装器不写 trust、permissions 或 bypass 配置。未被宿主加载/信任的 hook 不执行，不能声称此时逐会话暂停已生效；宿主级运行失败、超时和特殊工具路径也需要客户端验收。[Codex 信任规则](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

本机检查结果：`codex-cli 0.163.0`；其 `--help`、`app-server --help` 能正常返回。Claude CLI 不在当前 shell PATH，随后在 VS Code 扩展目录找到二进制，实际 `--version` 返回 `2.1.308 (Claude Code)`。未使用 `codex exec` 或 `claude -p` 发起模型任务。

隔离测试覆盖：只读配置的启用/禁用/未知，损坏与不可读配置，项目 scope 不冒充全局，启动/活动元数据登记，不读取聊天文件，两个会话之间的开关隔离，全局暂停，缺失身份拒绝，Claude 注入与 Codex 不自动审批，非 TOMC 工具不干预，安装预览无写入，假 home 安装备份与幂等合并，以及 Windows 实际命令执行。运行：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest tests/test_integration_status.py tests/test_session_hooks.py -q --basetemp tests/.tmp_host_integration
```

结果：34 项通过（包括后台完成和工具调用不抢占活动卡片的验证）。Windows 沙箱临时目录不支持本次测试所需的 `os.replace`，因此使用工作区内的隔离测试目录完成原子写入测试；未降低安装器的原子更新要求。

## 下一步实际验收

在明确安装并完成宿主 hook 信任后，分别用两个聊天验证登记、暂停和归因；单独检查纯 UI 切换时的展示。TOMC 的 API 请求包装器可作为后续可控请求替换入口，但真实节省仍需比较完整输入（含工具/提示开销和缓存），并核验结果质量。当前不能把目录登记、估算文本减少或动画计为真实请求节省。

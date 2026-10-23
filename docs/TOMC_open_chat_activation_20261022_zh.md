# 已打开会话的 TOMC 接入核验

2026-10-22。本轮目标是当前真实桌面对话和其他已加载聊天，不以 CLI 合成测试代替覆盖验收。

## 22:42 UTC：用户重开窗口后的复核

此次窗口重开后，Desktop 主进程 37268（08:22:07 UTC）及 app-server 41008（08:22:10 UTC）仍是原进程。安装资源明确 Windows 的 window-all-closed 不退出应用，single-instance 会把重开请求交给旧进程。因此不能把“关窗口后重开”当作后台重启。

准确的正常退出入口是 Windows 右下角通知区域/隐藏图标里的 ChatGPT/Codex 图标，右键菜单最底部“退出 / Exit / Quit”。安装代码的该项调用 app.quit()，通过正常生命周期关闭 app-server。当前工具没有该正常退出接口，未强杀或注入应用。

本次应用清单增加到 13 条本机已加载聊天；全部开关有效值为开启，但实际网关请求数仍均为 0。主聊天 ID 不变。证据目录 `outputs/desktop_activation_after_restart_20261022T224107Z` 中包含清单及 `final-session-evidence.json`，不代表这些聊天已接通。

普通小猫进程本次检查时已不存在，已在 22:42:35 UTC 用原 pet.pyw 入口恢复。22:42:50 UTC 验证实际进程 47828、launcher 84600，test_mode=false、语言 zh、error=null、网关 ready=true；见该目录 `normal-runtime-restored.json`。未操作全屏或系统鼠标键盘。

部署版单会话关闭逻辑 21 项隔离验证通过；关闭 Codex 会话原字节透传、无新 prepared 事件，重新登记保留关闭，其他默认开启会话仍可编译。Claude 既有签名前缀关闭后可能兼容重放，但不重新编译。生产开关未改，也未向其他真实聊天发送测试消息；此结果不代替实际桌面会话关闭验收。报告 `outputs/session_switch_deployed_20261022T224153Z/verification.json`。

Claude Code 已有一个自然产生的日常会话请求到达网关，但本轮观察到的请求为原样转发，没有新压缩事件。普通小猫的摘要状态文件不含动画播放轨迹；不能拿健康状态或旧验证动画当成本轮“每次真实压缩可见”的证据。仍待旧 Codex 后台真正退出后的原会话请求与动画联动验收。

## 当前结果

22:31:40 UTC：TOMC 网关健康，用户级默认开关开启，Codex 与 Claude Code 的配置地址均已指向本机 TOMC。Codex 应用清单中选出的 12 个本机已加载聊天（active/idle，非云端、非 ChatGPT 聊天）均没有对应的网关请求记录。包括当前聊天 `01a16537-0fd1-7c93-972e-8298f07c5570`。因此目前不能称这些聊天已经接通，也不能据此声称节省了 token。

证据：`outputs/open_session_activation_20261022/loaded-codex-sessions.json`、`routing-state.json`、`session-evidence-before-reload.json`。会话登记、开关开启、请求到达、完成新编译、发往上游和可见动画是不同状态。

## Codex 根因与最小生效动作

用实际桌面捆绑的 Codex `0.163.0-alpha.10.2`、隔离空 CODEX_HOME、假凭证、两个本地假上游 A/B 检验，未调用真实模型，也未修改运行中的应用：

| 同一个聊天的操作 | 下一请求地址 |
|---|---|
| 初始加载 | A |
| 配置文件改为 B，config/read 已读到 B | A |
| config/batchWrite，reloadUserConfig=true | A |
| thread/resume 显式携带 B | A |
| unsubscribe 后立即 resume | A；仍在 loaded 列表 |
| 重新启动隔离 app-server，再 resume 原聊天 ID | B；聊天 ID 不变 |
| 同一进程新加载的新聊天 | B |

假上游按设计返回 400；报告中的 failed 是预期假响应，不是生产错误。该实验测的是请求路由，非模型生成或压缩质量。完整记录：`outputs/codex_config_reload_probe_20261022T223126Z/report.json`。

当前桌面 app-server 通过默认 stdio 连接，无外部 RPC 监听地址；当前可用应用工具没有重载请求客户端/卸载聊天/重启 app-server 的接口。可靠动作是在本轮结束后正常退出并重新打开 Codex，继续原有聊天，无需逐条新建或手动启动 TOMC。不要用强杀进程、伪造压缩事件或修改应用二进制替代正常加载。

## Claude Code

用户 settings.json 中已有 ANTHROPIC_BASE_URL 和 CLAUDE_CODE_GATEWAY_HINT_HEADERS。两个已运行的 VS Code Claude Code 2.1.306 实例早于设置写入启动；该版本支持 settings.env 热更新，本机实现与[官方文档](https://code.claude.com/docs/en/env-vars#set-variables-in-settings-files)一致。设置值正确时无需为触发文件时间而重复改写。仍需用这些实例自然产生的真实请求记录确认接入，不能仅凭设置值宣布成功。

Claude Desktop 的聊天不是这两个 Claude Code 实例；它有[独立推理路由配置](https://code.claude.com/docs/en/llm-gateway-connect#desktop-app)，不能把 CLI 配置说成覆盖了 Desktop 所有聊天。

## 重开后的验收

1. 在原当前聊天正常续问，检查相同聊天 ID 出现真实请求记录。
2. 在其他原有聊天自然续问时按原 ID 核验，未产生请求的聊天保留“尚未观察到”，不能补造记录。
3. 达到压缩条件时，关联同一 request_id 的 prepared 事件、上下文长度与小猫播放；短历史、原生压缩或透传不应假播压缩动画。
4. 关闭一个确切会话后只停止该会话的新编译，其他默认开启；关闭选择在后续登记中保留。

只读工具 `scripts/audit_session_gateway.py --sessions-json outputs/open_session_activation_20261022/loaded-codex-sessions.json` 可重复核验。这不会发送消息、读取正文、改变会话或调用模型；返回码 0 仅表示读取成功，必须检查各会话的 observed。

原有真实请求逐次动画、四阶段、双语验收见 `docs/TOMC_animation_acceptance_20261022_zh.md`；其成功范围仍是明确记录的验收会话，不扩大成所有桌面聊天。

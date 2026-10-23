# Codex Desktop 已打开聊天的模型地址生效边界

2026-10-22；只读安装资源检查，加隔离协议探针。没有连接生产 app-server 的私有传输，没有改写生产配置、认证或程序，也没有重启桌面应用。

## 结论

本机 `0.163.0-alpha.10.2` 的已加载聊天保留创建/恢复时的模型连接地址。修改用户 `openai_base_url` 后，单纯下一轮、`reloadUserConfig` 和对已加载聊天再次 `thread/resume` 都不能切换该地址。新聊天或真正卸载后恢复的原聊天会采用新地址。原聊天 ID 和历史可以保留，无需另建聊天。

当前工具没有受支持的 Desktop app-server 重载/卸载入口。对所有已加载的本机 Desktop 聊天，最小可靠操作是本轮结束后通过应用的正常退出入口退出，再重开应用，让原聊天按原 ID 恢复。此操作尚未执行；不能声称当前聊天或所有已打开聊天已经接入 TOMC。VS Code、独立 CLI、远程宿主和云端聊天各有自己的运行边界。

## 本机证据

- Desktop 安装包：`OpenAI.Codex_26.1013.4894.0_x64__2p2nqsd0c76g0`；实际使用的 bundled CLI 报告 `codex-cli 0.163.0-alpha.10.2`。
- Desktop app-server PID 41008、父进程 37268，启动时间为 `2026-10-22T08:22:10Z`。启动参数没有 `openai_base_url` / `model_provider` 覆盖；仅输出了允许检查的配置键名，没有输出完整命令行。
- 用户配置的默认 provider 为内置 `openai`，无 profile provider 覆盖，`openai_base_url` 为 `http://127.0.0.1:43187/codex`。没有读取认证文件，也没有输出环境变量全集。
- app-server 没有 `--listen` 或 WebSocket listen 参数，没有 TCP 监听端口；官方协议的默认传输是 stdio。该 stdio 由桌面应用持有，本次未尝试写入或注入它。
- 只读查看安装包 `app.asar` 中的普通 JavaScript：`.vite/build/application-network-startup-DB1VeU3v.js` 的 `rc()` 会把存在的 `CODEX_APP_SERVER_OPENAI_BASE_URL` 映射为 `-c openai_base_url=...`；实际进程没有该参数。没有发现 Desktop 在当前启动参数中强制覆盖到另一模型地址。
- `.vite/build/main-C4DYk222.js` 存在 `config/batchWrite` 的 `reloadUserConfig:true` 调用；这证明应用使用原生热加载协议，但不能证明模型连接地址可热加载。
- 同一安装二进制导出的 `ConfigBatchWriteParams` 说明该选项更新 loaded threads 的 runtime settings，且排除 session-static model 等默认值；`TurnStartParams` 没有 `config` / `modelProvider` 字段。导出文件见 `outputs/codex_desktop_protocol_20261022T230000Z`。这里只生成协议描述，没有启动生产会话。

## 隔离双端点验证

脚本：`scripts/probe_codex_config_reload.py`。使用同一 bundled 二进制、独立空 `CODEX_HOME`、空工作目录、内置 `openai` provider 和两个本地假 HTTP 端点 A/B。只提供无效的测试用认证占位值，不继承真实认证或代理环境。假端点对模型请求返回固定 HTTP 400，因此所有 turn 均按设计失败，**没有执行模型，也没有工具执行或费用**；这些失败不表示生产模型故障。

| 操作 | 实际 `/responses` 请求去向 |
| --- | --- |
| 配置 A 后创建聊天并开始第一轮 | A |
| 用户文件改为 B；`config/read` 确认已经读到 B；继续同一 loaded thread | A |
| `config/batchWrite {edits: [], reloadUserConfig: true}` 成功后继续 | A |
| `thread/resume {threadId, excludeTurns: true, config: {openai_base_url: B}}` 成功后继续 | A |
| 同一 app-server 进程 `thread/start` 新聊天 | B |
| 原聊天 `thread/unsubscribe` 后立即 resume | A |
| 只重启隔离测试 app-server，再 resume 原聊天 ID | B；聊天 ID 相同 |

`thread/unsubscribe` 返回 `unsubscribed` 后，`thread/loaded/list` 仍包含该 ID。官方文档说明最后订阅者退出后，仍需无订阅且无活动 30 分钟才卸载，因此切换/关闭聊天视图不等于立即卸载。没有为验证而等待或影响任何真实聊天。

最终数字报告：[report.json](../outputs/codex_config_reload_probe_20261022T223126Z/report.json)。报告仅含端点 A/B、方法、路径、RPC 成败和同 ID 检查，不含请求正文、响应正文或认证头。两个假 HTTP 服务和测试 app-server 均已停止。

本探针验证的是此安装版本的连接地址生命周期，使用假 API 认证；它不替代重开 Desktop 后对真实 ChatGPT 登录流量的观测验收。

## 官方支持边界

`openai_base_url` 是内置 OpenAI provider 的正式代理入口，应放在用户级配置；项目配置不允许覆盖此路由。[Advanced Configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)

App-server 默认 stdio，支持明确选择的 WebSocket/Unix socket；`config/mcpServer/reload` 只重载 MCP。官方线程协议分别定义 start、resume、unsubscribe 及上述 30 分钟卸载宽限期。[Codex App Server](https://learn.chatgpt.com/docs/app-server)

现有 `mcp__codex_app` 工具可管理聊天与项目，但没有配置 RPC、thread unload、app-server restart 或任意 RPC 转发工具。本次未利用聊天工具、副作用设置、进程注入或私有管道绕过这一边界。

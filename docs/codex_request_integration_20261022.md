# Codex 请求接入核验（2026-10-22）

当前结论：本机 Codex CLI 已通过内置 OpenAI provider 的 `openai_base_url` 进入回环 HTTP 代理，沿用既有 ChatGPT 登录，完成同一真实线程的连续对话、工具读取、实际压缩与逐会话关闭验证。用户级安装后，又在不传任何地址、模型或权限覆盖的情况下继续该合成测试线程，确认默认配置进入生产网关并完成真实压缩。启用 MCP 插件本身不拦截模型请求。

## 安装前核实的本机状态

只读取配置中的白名单字段和 CLI 状态分类，没有读取或输出任何 token、key、认证文件或完整配置。

- CLI：`0.163.0-alpha.10.2`；当前模型 `gpt-6-astra`。
- 登录类别：ChatGPT；没有显式自定义 `model_provider`、provider 列表或 profile provider 覆盖。
- 没有 `openai_base_url`、`chatgpt_base_url` 或 `OPENAI_BASE_URL` 覆盖。
- CLI `features list` 显示 `responses_websockets` 和 `responses_websockets_v2` 都已 removed；旧 feature flag 不能作为关闭 WebSocket 的实现依据。
- 安装二进制包含 `openai_base_url`、`thread-id`、`client_metadata` 和 `x-codex-turn-metadata` 字段名。这只能证明字段存在，不能替代运行验证。

## 上游、认证与传输

[官方配置说明](https://developers.openai.com/codex/config-advanced)支持用 `openai_base_url` 修改内置 provider 的地址。保留内置 provider 比新建同名兼容 provider 更完整：内置 provider 的 internal metadata 开关属于运行期属性，无法通过序列化 provider 配置补回。源码还显示内置 provider 启用 Responses、WebSocket 和原生远程压缩能力；不要为了接入 TOMC 改掉模型或压缩能力。[provider 定义](https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs)

ChatGPT 登录的默认模型上游是 `https://chatgpt.com/backend-api/codex`。`requires_openai_auth=true` 继续使用 Codex 的 AuthManager；请求认证生成 Authorization 和 ChatGPT-Account-ID，刷新仍由 Codex 管理。代理只能在内存中向已批准的原上游转发这些头，不能写入日志、收据或归档，也不需要复制认证文件。[认证选择](https://github.com/openai/codex/blob/main/codex-rs/model-provider/src/auth.rs)、[认证头实现](https://github.com/openai/codex/blob/main/codex-rs/model-provider/src/bearer_auth_provider.rs)

公开 client 源码针对 WebSocket 握手的 HTTP 426 有明确的 HTTP fallback 分支；进入 fallback 时会清除 WebSocket 增量状态。测试代理对 `/responses` 的 Upgrade 请求返回 426，再接收 POST，已完成本机真实模型验证。HTTP 路径使用 SSE；请求可能采用 zstd 压缩，代理必须解码后重算长度/编码头，或完整透传不支持的编码。不能把压缩字节直接当 JSON。[客户端传输实现](https://github.com/openai/codex/blob/main/codex-rs/core/src/client.rs)、[HTTP Responses endpoint](https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/endpoint/responses.rs)

需要验证的边界：ChatGPT workspace routing 可能重写后端 origin；代理不能宣称覆盖被路由到别处的流量，也不能移除账户区域要求。模型目录、搜索、原生压缩等非普通推理端点应保留原行为。用户已有权限、审批和沙箱配置不因代理改变。[provider routing](https://github.com/openai/codex/blob/main/codex-rs/model-provider/src/provider.rs)、[workspace routing](https://github.com/openai/codex/blob/main/codex-rs/model-provider/src/workspace_routing.rs)

## 会话与上下文协议

`thread-id` 是线程标识；`session-id` 可能服务于缓存亲和性，不能直接作为真实聊天目录主键。`client_metadata.thread_id` 是备用来源，若与头冲突则拒绝归因。不要使用 PID、最后活动窗口、prompt_cache_key 或普通用户 metadata 猜测会话。[请求头构造](https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/requests/headers.rs)、[Core metadata](https://github.com/openai/codex/blob/main/codex-rs/core/src/responses_metadata.rs)

`responses_request.adapt_request` 使用真实 TOMC `prepare_context` 处理完整旧 user 轮中的可读证据，完整保留顶层配置和 system/developer。最新 user 起的全部项目和近期边界所在整轮不变。选中的旧轮原子移除其消息、完整工具对和 opaque reasoning；opaque 内容不解码、不送编译器、不持久保存。带未知字段、图像、configuration_update、无法完整适配的 encrypted 字段的旧轮整轮保留。未完成或跨边界工具链整轮受保护。超出编译器长度上限的完整旧轮保留在原请求中，绝不先截断再声称完整适配。

官方 reasoning 文档允许优化更早的上下文，但要求最后 user 与后续工具输出之间的项目原样保留；本适配器据此保护整个当前轮。官方 Agents SDK 文档还明确说明 reasoning ID 与其后续输出的配套约束，因此不能保留旧 reasoning 却单独删除其 message/call，也不能随意清除 ID。采用整轮原子替换，避免产生 orphan。文本协议测试不替代真实服务验证。[reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning)、[Agents SDK replay 规则](https://github.com/openai/openai-agents-python/blob/main/docs/running_agents.md#reasoning_item_id_policy)

带 `previous_response_id` / conversation 的请求没有完整独立历史，直接透传；原生 compaction 项、context_management、compaction 请求也透传。Codex 的原生事件可能藏在 `client_metadata['x-codex-turn-metadata']` JSON 字符串，网关还应检查同名 HTTP 头。Standalone compact 返回的新输入窗口不能当作 response ID 链接。[WebSocket 续接协议](https://developers.openai.com/api/docs/guides/websocket-mode)

适配前后使用同一个词法计数器计算完整 payload JSON；只有总大小严格减少才采用候选。该差值不是 API 计费节省，修改前缀还可能降低 prompt cache 命中。不得把准备成功等同于已发送或模型已采纳。

## 验证和生效范围

39 项重点测试及 Ruff 已通过，覆盖真实编译、当前工具链、opaque 内容、未知字段、UTF-8、长材料、冲突身份、无收益和原生透传。使用 `scripts/validate_codex_gateway.py --run` 和隔离诊断代理，在同一真实 CLI 线程完成 10 轮对话，包括安全读取 fixture、修复本机真实 metadata 格式、实际改写与关闭后继续正常回答。脚本默认 dry-run，仅使用本次进程 `-c openai_base_url=...`，不修改用户全局配置。[最终真实验收报告](../outputs/codex_live_20261022T205410Z_f9cebc3e/codex_gateway_verified_20261022T210311Z.md)

一次严格相同请求的原始/压缩真实比较显示 provider input **28,650 → 27,382**，减少 **1,268（4.43%）**；双方均答对五项合成事实。cached input **28,288 → 19,328**，所以未缓存输入反而从 362 增至 8,054，不能声称费用降低。对照只在测试代码中额外发送一次，原始请求与认证头仅驻内存，不写盘；生产网关不会自动双发。

本机 CLI 的 `turn.completed.usage` 是累计会话数字；本次匹配比较采用每个上游响应的 usage，未把跨轮差分当匹配节省。真实上游出现 Content-Type 缺失但 body 为 SSE 的情形，网关已通过有限前缀检测正常读取 response.completed 的 usage。关闭后记录 session_disabled，模型仍正确回答，压缩档案数保持 1 → 1。

用户级配置生效需要新进程/配置重载；安装前已在运行的会话可能继续使用启动时 provider。配置 profile 或显式不同 provider 的会话、云端执行宿主、另一台电脑不会被本机配置自动覆盖。“默认全部会话”应准确描述为本机已加载该 provider 配置的受支持 Codex 会话，并显示实际请求观测覆盖情况。

## 用户级安装后的真实验收

2026-10-22 21:08 UTC，`scripts/validate_codex_global.py --run` 通过默认配置继续同一已授权合成测试线程。实际命令只有 `codex exec --json resume <test-thread-id> -`，没有 `-c`、模型、推理、认证、审批或沙箱覆盖。生产网关端口为 43187；生产库中仅查询该测试线程，记录 `forwarded`、`sent=1` 和 `old_history_compiled_cache_may_change`。

该请求的完整 JSON 词法估算 **36,690 → 33,410**；单次真实 provider input **27,549**、cached input **19,328**。模型正确恢复 BLUEGLASS、teal、EU、Friday、TOMC_FIXTURE_OK_47 五项事实。CLI 报告的 335,715 input 是会话累计量，不能与单次 provider input 混算；本次全局验收没有再次发送未压缩对照，也不据此宣称费用节省。

原验收 Python 缺少 PySide6，造成状态格式化检查假阴性。随后用实际小猫 Qt 环境对同一条元数据调用状态函数，得到“已观察到处理后请求转发”，没有重复调用模型。最终报告所有功能检查通过；`desktop_visual_verified=false` 明确表示未据此声称已目视检查真实桌面动画。[全局默认配置验收报告](../outputs/codex_global_verified_20261022T211042Z_07248400.json)

版本限制：上面的 GitHub 证据来自官方公开 `main`，不保证与本机 alpha 构建逐行相同。本机 `0.163.0-alpha.10.2` 的真实运行证据已补充；其他版本、账户路由和宿主仍需独立验证。本次是一条合成会话的功能验收，不是普遍的模型质量或成本基准。隔离代理已停止。

# API 请求优化与原生压缩的配合

[English](context_ownership.md) · [模型容量表](model_context_limits_20261012.md) · [API 指南](api_reference.md)

统一按**逻辑模型 API 请求次数**计数，不按用户对话轮数。Agent 处理一条用户消息时，可能发出多次模型请求。`AutomaticChatSession` 是自己控制请求入口时使用的前置层；安装 MCP 插件不会自动拦截这些请求。

## 简单规则

- 模型规格缓存在本地，仅模型 ID 改变时重新对应，不反复查提供商，也不额外调用模型判断。
- 默认每两次请求刷新旧历史记忆，可设为每次。间隔中的新增消息保持原样；任务或原始前缀变化时重新准备。
- 上下文长度提示首次跨过有效窗口的 50% 或 90% 时，各退让一次。1M 模型大约对应 500K、900K。这是 TOMC 的近似避让点，不是宣称宿主的真实触发阈值。优先使用调用方传入或已有 usage；初次字符串长度估算较粗，不能当作精确分词。
- 收到可信的原生压缩进行中事件时跳过；刚完成后冷却一或两次 API 请求，默认两次，然后恢复。普通、符合处理条件的原生摘要以后可以再次优化，不永久排除。

模型最大容量不等于 Code Agent 的压缩阈值；套餐、部署和客户端设置可能更小。未知模型不会被猜成 1M 或 10M，可用已确认的 `deployment_context_limit` 指定，否则保持原请求。

## 接在已有 SDK 前面

```python
from tomc import AutomaticChatSession

session = AutomaticChatSession(refresh_every=2, native_cooldown_requests=2)

# 每个会话复用一个 session，传应用保留的原始 messages。
response = session.create(
    client,
    model="deepseek-flash",
    messages=messages,
    task="下一步 Agent 应该做什么？",
    max_tokens=8192,
    stream=True,
)
```

保留原来的 client、密钥、模型、tools 和请求设置；返回原 response 或 stream，不额外调用模型，也不读取并消耗流。只替换本次请求的 `messages`。应用保留完整原始历史，不把上一份 TOMC 发送视图当作原历史继续输入。

旧历史默认沿用约 80% 的词法预算、最低 1,024，并受模型/部署余量限制。系统与开发者指令、当前用户任务、最近消息和未结束的工具协议保留原样；已结束的较旧工具组一起处理。多模态、不支持的消息、不可解释的推理结构、未缩小的输出保持原请求。估计数不是提供商计费数，也不能保证所有请求都不超窗口。

正常在 SDK 请求中指定输出上限。省略时，`output_reserve` 只是规划余量（默认 8,192），不会改变提供商的实际输出限制；例如 Kimi K3 的公开默认值是 131,072。程序不会悄悄改写输出参数。

## 与 Code Agent 的接入边界

`session.on_native_event("codex", event)` 接收真实 app-server `contextCompaction` 开始/完成事件；`session.on_native_event("claude", event)` 接收 `PreCompact`/`PostCompact`。外层可信接入负责把正确会话的事件送进来。支持压缩、开启压缩或 usage 更新，不等于压缩事件；不需要持续轮询日志。

本版本没有自动安装这些监听器、修改 Claude Code/Codex/WorkBuddy 设置或代理内置模型。MCP 保留外部历史处理和可选记忆本，其助手规则把当前聊天留给宿主；MCP 本身不是上述请求拦截入口。

首版 SDK 包装器支持同步、文本 Chat Completions；Anthropic Messages 和 OpenAI Responses 需要对应传输适配，不能把签名推理或不透明的原生压缩项直接变成文本。GPT-6.1 Sol 的工具调用要求 Responses，见[官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol)。

## CPU 开销

判断使用计数器和缓存规格，没有额外 LLM 或神经模型。默认词法打包已改为每行只计数一次，避免反复扫描越来越长的输出。本机同一组合成状态/日志样例中，80% 记忆预算下，20K 历史编译约 0.026 秒、100K 约 0.293 秒；旧实现分别约 1.58 秒、38–47 秒。短随机计数器对照及完整 20K 样例保持文本、记录和估计数一致。这是 CPU/编译计时，不是提供商端到端延迟、计费或回答质量测试，也不代表任意历史、其他分词器或 1M 输入的速度。

[Claude 压缩 hooks](https://code.claude.com/docs/en/hooks) · [Codex app-server](https://learn.chatgpt.com/docs/app-server)

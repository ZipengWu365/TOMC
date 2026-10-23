# Claude Code 请求接入核查（2026-10-22）

本报告区分协议支持、本机静态核查、隔离测试和用户授权的真实 CLI 验证。已通过原有 claude.ai 登录发送真实 Opus 5.5 请求，并观察到实际供应商输入减少。隔离验证不修改全局 Claude 配置，不替换认证、模型或 thinking 设置；主任务另已安装用户级网关。**输入减少不等于账单节省**。

## 本机入口与认证

确切入口为 `%USERPROFILE%/.vscode/extensions/anthropic.claude-code-2.1.308-win32-x64/resources/native-binary/claude.exe`。运行 `--version` 返回 `2.1.308 (Claude Code)`。`auth status --json` 仅提取四个非秘密字段，结果为：已登录、`authMethod=claude.ai`、`apiProvider=firstParty`、`subscriptionType=team`。

只读取 `~/.claude/settings.json`、`~/.claude.json` 中选定的网络字段和当前进程的相同字段。未配置 `ANTHROPIC_BASE_URL`、gateway API key/token、`apiKeyHelper` 或 Bedrock/Vertex/Foundry flags；当前 CLI 使用默认上游 `https://api.anthropic.com`。没有读取凭据文件或输出完整环境、账号邮箱、token。这个结论不证明某个已运行的 VS Code/桌面进程没有独立覆盖配置。

可实施的入口是本机 HTTP 反向代理：只把新启动的 Claude Code 的 `ANTHROPIC_BASE_URL` 指向 loopback，保留现有认证及请求 `model`。官方确认不设置 gateway 凭据变量时仍可使用 claude.ai 登录；`anthropic-beta` 包含 OAuth 所需 capability，必须原样转发。不得用新 API key 替换原 OAuth，也不应把认证复制进 TOMC 数据库。[官方 gateway 协议](https://code.claude.com/docs/en/llm-gateway-protocol#request-headers)

CLI、VS Code 与桌面应用的配置入口不同。VS Code 可以使用自身的 `claudeCode.environmentVariables`；桌面应用另有 third-party inference 配置。本次只核验上述 CLI，不把 CLI 结果外推到所有表面。[官方连接配置](https://code.claude.com/docs/en/llm-gateway-connect)

## 请求身份和自动压缩范围

使用 `X-Claude-Code-Session-Id`；HTTP header 名大小写不敏感。2.1.308 二进制内嵌源码存在此常量，并存在 `x-claude-code-agent-id`、`x-claude-code-request-class`、compaction hint 生成逻辑。`metadata.user_id` 的本机实际构造是 JSON 字符串，包含 `session_id`；适配器只提取该字段，不使用 device/account 信息。header 和 JSON 身份冲突时返回未关联，不猜测小猫“活动会话”。

自定义 base URL 需显式设置 `CLAUDE_CODE_GATEWAY_HINT_HEADERS=1` 才可靠收到请求分类提示。代理只改 `main`，旁路 `subagent`、`workflow`、`compaction`、`auxiliary` 和未知类别。`x-claude-code-compaction` 标记原生摘要调用；`x-claude-code-context-compacted` 是之后首个主对话请求的重置标记。`x-claude-code-prompt-id` 标识同一用户 prompt，工具后续请求沿用它；适配器用它判断同轮重放，避免宿主追加 user 内容时误判成新任务。会话身份和主请求路由已在本次真实运行中使用；原生 compaction/reset 路由本次只有隔离测试覆盖。[官方提示头说明](https://code.claude.com/docs/en/llm-gateway-protocol#gateway-hint-headers)

`extract_session_id(payload, headers)` 仅识别上述两种已核查来源。身份仍是宿主声明，授权由网关检查已登记会话承担；不凭 header 自行开通陌生会话。

## 已实现适配器

`src/tomc/anthropic_request.py` 的 `adapt_request` 使用真实 `prepare_context` 编译已完成旧轮，并替换实际请求 `messages`。保留原 `system`、`tools`、模型等所有顶层字段和最新用户任务；最近工具循环完整保留。已完成旧工具组可作为明确标记的不可信历史数据进入 TOMC，不能重新作为工具调用执行。未知内容/消息字段、图片/文档、异常或未完成工具配对、真正的 native context editing 原样旁路。`clear_thinking_20251015` 的 `keep=all` 仅保留原设置。

工具结果必须紧邻对应工具调用，且 user 消息中结果块必须在普通文字之前。适配器检查完整配对，不切断当前工具循环。[官方工具配对规则](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-results-from-client-tools)

thinking 不能只按“字节未改”判断安全：Fable 5.1、Opus/Sonnet/Haiku 5.5 的保留 thinking 可能绑定全部早期消息。删掉完整旧轮仍会使后面保留的签名块失效。适配器仅在被替换区间之后不保留 thinking 时新编译；区间内旧 thinking 与完整旧轮一起移除，不读取成普通文本。区间之前的原始 anchor（包含其 thinking）保持原样。[官方 prefix 约束](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking#keeping-the-prefix-unchanged)

真实 2.1.308 请求含 `messages` 内的 `role=system`、`output_config.effort=high`。完整默认用户配置还在首个 system 中发送三个 `tool_addition` 块。此类工具定义、正文与未知 system 字段都保持原值、原顺序，连同它之前的全部历史和它约束的完整轮形成 anchor；适配器只编译 anchor 后已完成的长中段，再保留当前轮。未知 system 没有后续可压旧轮时安全旁路，不用长首条捷径改它前面的原始历史。已知空正文 effort 控制保留。这支持“第一轮很短、后续聊天才变长”，不限于长首条输入。[官方中途 system 与工具变更规则](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)

适配函数默认 `recent_messages=6`；本次真实验证显式使用 `recent_messages=1`、`min_history_tokens=4000`，保留当前整轮并允许压缩已完成旧轮。不能把该验证直接当成默认六条配置在每个 thinking 会话中都能压缩的证明。

`AnthropicAdapter(path).adapt(payload, headers, enabled=...)` 在同一 SQLite 中保存编译后的中段、anchor 条数、原前缀 SHA-256、前缀条数、任务、轮次哈希及 prompt ID。数据库不保存原始 anchor 或原前缀全文；重放时从已通过哈希核验的宿主输入重建 anchor。第一次改写前先成功持久化；同一 prompt 的后续工具请求及代理重启后复用原有映射。只忽略协议消息块的 `cache_control` 标记移动，工具参数内同名业务键仍参与哈希。原前缀发生其他变化时不套用旧位置映射；原生重置标记删除旧映射。

如果新 system 使下一次候选 anchor 包含在旧编译前缀上生成的 thinking，不能用原始历史直接重建它；此时继续重放已建立的前缀。新 prompt 中若存在安全可压区间，则仍按当前任务重新编译。无条件跨任务复用摘要可能漏掉新问题所需证据，所以本版没有为了提高缓存命中率悄悄改成长期固定摘要。新增历史阈值或主题切换策略还需质量与成本的联合验证。

关闭立即停止新编译。当前工具轮，以及仍含已绑定新前缀 thinking 的后续轮，继续兼容重放已准备上下文，返回 `disabled_compatible_replay` 且 `prepared=None`，不记成新准备/成长。不含绑定 thinking 的新独立 user turn，或原生 compact/reset 后，才完全原样转发。把开关关掉就立刻恢复旧前缀会损坏这些签名，不能如此实现。未知前缀变化或状态数据库不可读会原样返回，并附具体原因；这不保证宿主已改变的签名历史能被上游接受。

## token、缓存与费用

`before_tokens` / `after_tokens` 是整个请求 JSON 的同一 regex 估算，包含保留尾部和包装，不是模型 tokenizer，也不是账单。只有总估算减小时才返回新编译。修改历史可能让消息缓存失效；system/tools 缓存标记保留不代表后续前缀缓存仍命中。实测必须分别保存供应商 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`，并记录输出用量，才能比较成本；不能把明文差额直接称为费用节省。[官方缓存说明](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#tracking-cache-performance)

## 隔离测试

`tests/test_anthropic_request.py` 已通过 51 个隔离测试，覆盖真实 TOMC 编译、最新任务与完整工具组、未知内容旁路、旧 thinking 移除、保留签名保护、短首轮与长中段、重启重放、同 prompt 的 user 内容变化、协议缓存标记与业务同名键区别、禁用恢复、原前缀变化、原生重置、持久化失败和不保存原始 anchor/全文。另覆盖再次压缩不能把已绑定 thinking 的 anchor 恢复成 raw 历史、真实 system 工具定义与未知 system 字段完整保护、未知结构化 effort 值的类型防护，以及后述 direct caller 兼容。测试均使用临时数据库。

## 真实 CLI 验证

复现入口是 `scripts/validate_claude_gateway.py --run`；不加 `--run` 只显示计划。测试创建独立 SQLite、合成档案及一个只读 fixture，在子进程设置 `ANTHROPIC_BASE_URL=http://127.0.0.1:18740/claude` 和 hint headers。只为该 invocation 禁用 hooks、加载空 MCP，以免测试向用户日常 TOMC 数据库登记。保留默认审批，只明确允许 `Read(./synthetic_fixture.txt)`；没有使用 `dangerously-skip-permissions`。原始请求和认证仅在转发内存中使用，不写入验证报告。

上述默认模式是较早的隔离工具验证。**覆盖日常用户配置的最终复验命令是 `scripts/validate_claude_gateway.py --run --inherit-user-settings`**：它仅覆盖临时测试网关 URL，保留用户 hooks、MCP、全部工具及其 schema、模型和认证；无 `--strict-mcp-config`、无 `--tools Read`、无禁用 hooks。只额外允许精确 fixture Read，默认审批不变。启用的用户 hooks 正常登记这个合成测试会话的元数据。请求诊断仅保存字段名、类型和固定枚举，不保存 system 正文、工具定义内容或认证 headers。

两种场景均使用原有登录，实际返回模型 `claude-opus-5-5`，未覆盖 model/thinking。长首条四轮与短首轮长中段五轮均保留 `Bristol / CYAN-73`，真实 Read 返回 `HARBOUR-52 / 19`；包含真实 thinking、代理重启后继续和关闭后继续。关闭前后准备快照数相同，关闭没有拒绝聊天。供应商未返回签名或工具配对错误，记录到的 `input_transformations` 为空；这不替代所有协议边界的覆盖。

匹配比较仅在测试网关进行：首次压缩时把相同原始请求另发一次上游作 baseline，然后发送生产适配结果。两次保留同一认证、模型及原始参数，原始 body 只驻留内存；生产网关不会双发。这是同输入的一次观察，不是随机重复实验，也不是费用对照。

| 合成场景 | 原始请求供应商总输入 | 改写后总输入 | 减少 | Cache read 原始→改写 | Cache write 原始→改写 | 输出原始→改写 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 隔离工具：长首条，4 轮 | 22,547 | 18,925 | 3,622（16.06%） | 22,083→3,104 | 460→15,817 | 21→117 |
| 隔离工具：短首轮 + 长中段，5 轮初验 | 23,049 | 21,073 | 1,976（8.57%） | 22,983→12,569 | 62→8,500 | 21→102 |
| 隔离工具：短首轮 + 长中段，5 轮复验 | 23,032 | 21,056 | 1,976（8.58%） | 22,966→12,552 | 62→8,500 | 21→73 |
| **完整默认用户配置：短首轮 + 长中段，5 轮最终复验** | **53,944** | **51,968** | **1,976（3.66%）** | **53,878→43,464** | **62→8,500** | **21→21** |

总输入是供应商 `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`，不是 regex 估算；各组非缓存 `input_tokens` 均为 4→4。每组两个请求的事实回答均正确，但缓存读取下降、缓存写入和输出上升，因此**没有证明账单降低，费用可能上升**。摘要按新任务重新构建会损失部分前缀缓存；当前版本没有成本优化保证。

原始验证回执（保留，不覆盖）：

- [长首条 4 轮，20:59:40 UTC](../outputs/gateway_validation_claude_20261022T205940Z_bcedf225/validation.json)
- [短首轮与长中段 5 轮，21:02:20 UTC](../outputs/gateway_validation_claude_20261022T210220Z_7997903d/validation.json)
- [最终 5 轮复验，21:06:06 UTC](../outputs/gateway_validation_claude_20261022T210606Z_9ac18c20/validation.json)
- [完整默认用户配置 5 轮最终复验，21:11:51 UTC](../outputs/gateway_validation_claude_20261022T211151Z_28586c66/validation.json)

21:02 运行发现同一工具 prompt 的 user 内容变化会触发一次重复准备。现已改用官方 prompt ID 优先匹配，并保留消息哈希回退。该历史回执如实保留三次准备，不能被描述为工具轮已精确重放的最终证据。21:06 最终复验收到官方 prompt ID，Read 后续请求明确记录 `replayed_prefix`，准备次数为 2；关闭前后均为 2，全部九项检查通过。最终答案为 `CITY=Bristol; CODE=CYAN-73; FIXTURE=HARBOUR-52; VALUE=19`，计算检查返回 `10223`。最终工具轮未产生新 thinking，故关闭后走 `session_disabled` 原样发送；前两份回执则真实覆盖仍有绑定 thinking 时的 `disabled_compatible_replay`。

21:09 在主任务安装的 `127.0.0.1:43187` 上做了全新会话验收，没有任何临时 env/settings 覆盖。返回 `TOMC_GLOBAL_OK`；生产数据库记录该 session 已登记、`sent=1`、供应商输入 42,964。该历史版本因 system 内 `tool_addition` 原样旁路，**此短请求只证明全局设置接通**。[用户级路由验收回执](../outputs/global_claude_acceptance_20261022T210909Z_4a4e4701/validation.json)

随后只采 schema 定位此结构并加入完整 anchor 保护，21:11 的完整用户配置五轮验证通过全部九项检查。真实 Read、原始 thinking anchor、重启后继续、工具轮精确重放、关闭后原样发送均成功，权限拒绝为 0，准备次数在关闭前后为 2→2。这份回执证明源码适配在真实完整用户配置下可用。

主任务随后备份并更新生产 runtime 的 `anthropic_request.py`，保留原端口、数据库、prefix 映射及客户端设置。**21:15:33 UTC 已通过最终生产三轮验收**：全新会话 `ae3a0d56-b414-492d-baba-d94923e92cac` 没有任何环境、settings、模型、认证、审批或工具覆盖；直接继承已安装用户级配置。模型返回 `READY`、`ARCHIVE_READY`、`CITY=Bristol; CODE=CYAN-73`。前两轮分别是 `insufficient_old_history` / `protected_system_history`，第三轮记录真实 `forwarded`、`old_history_compiled_cache_may_change`、`sent=1`，整请求 regex 估算 37,105→35,897，供应商实际总输入 51,456（非缓存 4、cache write 8,500、cache read 42,952），输出 21。生产 `~/.tomc/memory.sqlite3` 中有该会话的三条实际请求事件，服务继续运行。

[最终生产三轮验收回执](../outputs/global_claude_compression_20261022T211533Z_199266ae/validation.json)；复现脚本为 `scripts/validate_claude_production.py --run`（默认 dry-run）。此验收没有额外发送 baseline，所以不从相邻两轮用量推算节省比例；同请求的实际输入减量依据仍是上表的匹配比较。

本次证明本机 CLI 的合成多轮路径可用。尚未验证长期开放任务的答案质量、带图片/文档的压缩、真实 native compact/reset、所有 provider/backend、VS Code/桌面 UI 启动环境及账单节省。其他表面仍需各自配置并验证，不能称安装插件后所有已运行对话自动接入。

## 21:45 活动记录后的 direct caller 兼容审计

主任务观察到生产活动原因 `unsupported_tool_use`。此原因来自工具调用的角色、未知字段或 name/input 类型检查；仅凭该原因不能认定当前生产请求的具体字段，也不能断言网关未启用。此次只审源码与此前合成验证的 schema，不读取用户聊天正文、认证或生产请求内容，不重启生产服务，也不新增模型调用。

21:11 的合成回执已记录 `tool_use` 字段名包含 `caller`；旧版白名单未包含此字段。这是可复现的兼容缺口。[官方 caller 格式](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling#the-caller-field-in-responses)区分普通 `{"type":"direct"}` 与绑定服务端执行工具的 caller。源码现仅接受 caller 缺省或精确的 direct 对象；服务端/程序化 caller、额外未知字段及 `server_tool_use` 仍安全旁路，完整工具配对规则不变。

既有映射的同一工具轮先重放已准备前缀，保留后续原始工具块，因而早前真实 Read 验证没有暴露“旧工具轮在新任务中重新编译”这一缺口。新增隔离测试覆盖当前 direct 工具轮保留、已完成 direct 工具轮编译、跨代理实例同轮重放后新用户轮重新编译，以及未知 caller 与错误配对。51 项测试全部通过；此修复尚未部署或进行新的真实模型验收，之前的生产验收与实测数字仍对应当时版本。

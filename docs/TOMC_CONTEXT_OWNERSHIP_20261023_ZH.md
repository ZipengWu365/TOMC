# TOMC 上下文所有权：能力矩阵、接口探针与架构决策

2026-10-23。面向用户与接手开发者。本文回答交接 P0：“谁拥有活动聊天的历史，TOMC 输出能否被已有真实聊天实际采用”。**本文不是“全量自动省 token 已完成”的声明。**

## 1. 结论

1. **已核验的两个宿主都没有受支持的接口，能用 TOMC 输出替换已有聊天的模型可见历史。** 核验对象为 Codex 0.163.0 / 0.163.0-alpha.11.2 与 Claude Code 2.1.308。历史始终归宿主所有。本机网关确实能改写单次请求，但那会让网关成为第二个所有者，不是宿主提供的替换入口。
2. **Codex 的压缩协议已变。** 当前版本不再调用 `/responses/compact`，而是发起一个普通 `/responses` “压缩回合”，并且只接受**恰好一个**不透明 `compaction` 输出项。要让宿主采用 TOMC 结果，网关只能伪造这个项，并在以后的每次请求里展开它；线程从此离不开网关，一旦绕过即损坏。本次不采用这一方案。
3. **三条真实 Codex 聊天的透传判断是正确的，不是误判。** 当前聊天、BEAM 聊天和另一条原聊天，以及由它们派生的 guardian 自动审核子代理，都携带宿主的不透明压缩状态（见 §4.3）。
4. **缓存已经吸收了大部分重复输入。** 真实请求的缓存命中率：Codex 当前聊天 164,071 输入中 163,072 为缓存（99.4%）；本 Claude Code 会话 507,607 中 505,087 为缓存（99.5%）。先前同一请求的 A/B 实测中，改写让未缓存输入从 362 升至 8,054。估算 token 减少不等于账单减少。
5. **本次已部署**（精确备份、回执、可回滚）：结构化透传原因与协议细节；宿主取消与上游失败分开记录；按 request_id 的动画收据；审计脚本联查；Windows 拒绝路径连接重置修复。小猫此前未运行，已经通过 Windows 外壳从正常入口重启。
6. **真实动画已验证（12:25 补充）：** 新建的真实 Codex 聊天在宿主第一次压缩之前会被 TOMC 编译。小猫重启后的 18 个真实编译事件，每个都有排队、开始、完成收据（§4.4）。但这些编译的效果很小（约 0.5%），新用户回合的第一个请求还会出现大面积缓存未命中。**18:20 补充：** 效果小、小猫不进阶的原因是 bug，编译的其实是 AGENTS.md 与环境信息，已修复（§8）。
7. **20 万字符保护常量已移除。** 网关 12:45 部署，MCP 运行时 13:05 更新。默认改为保留 60%–80% 的历史，长历史压得更多。真实长历史请求编译了 107,638 tokens，请求估算减少 21%；13:03 的真实请求播放了第 3 阶段动画并有收据（§8）。
8. **仍未实现：** 已有带不透明状态的聊天由 TOMC 额外省 token；第 4 阶段的真实验证；第二台电脑续接。验收表见 [TOMC_ACCEPTANCE_20261023_ZH.md](TOMC_ACCEPTANCE_20261023_ZH.md)，部署与回滚见 [TOMC_DEPLOY_ROLLBACK_20261023_ZH.md](TOMC_DEPLOY_ROLLBACK_20261023_ZH.md)。

## 2. 核验对象

| 宿主 | 版本 | 本机入口 | 核验方式 |
|---|---|---|---|
| Codex Desktop | 包 26.1016.8622.0，内置 CLI 0.163.0-alpha.11.2 | `%LOCALAPPDATA%\OpenAI\Codex\bin\37f54d68e5533a51\codex.exe` | 隔离探针、协议导出、生产请求结构统计 |
| Codex CLI（npm） | 0.163.0 | `%APPDATA%\npm\node_modules\@openai\codex\…\codex.exe` | 隔离探针 |
| Claude Code（VS Code 扩展） | 2.1.308 | `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-2.1.308-win32-x64` | 官方文档、生产请求结构统计 |
| Claude Desktop | 不在范围 | 未经网关路由 | 未核验 |

**版本变化：** 10-22 的全部探针基于 alpha.10.2；该二进制已在 10-22 22:46 UTC 随 Desktop 更新而消失。本文结论只对上表版本有效。

## 3. 能力矩阵

| 项目 | Codex 0.163.0 / alpha.11.2 | Claude Code 2.1.308 |
|---|---|---|
| 谁拥有历史 | 宿主（app-server）；`store:false`，每次请求发送完整 `input` | 宿主；每次请求发送完整 `messages`，带 `cache_control` |
| 原生压缩 | 压缩回合：`request_kind=compaction`，末项为 `compaction_trigger`；服务器返回 1 个加密 `compaction` 项；宿主保留“memento”窗口（重新注入的指令、保留的用户消息、该项）；`window_number` 每次加一 | 客户端发起摘要请求（`x-claude-code-compaction`: auto / manual / reactive）；其后第一条主请求带 `x-claude-code-context-compacted` |
| 不透明状态 | 有，加密 `compaction` 项，子代理会继承 | 本机流量中未见（摘要是明文）；服务端 `compaction` 块会被标为不透明 |
| 显式压缩 | 用户 `/compact` → `trigger:manual, phase:standalone_turn` | `/compact` → `manual` |
| 自动压缩 | 按宿主统计的用量 → `trigger:auto, phase:pre_turn`；上下文溢出后，下一回合自动压缩 | 接近窗口上限 / 空闲 / 被拒为过长（`reactive`） |
| 服务端或增量历史 | `previous_response_id` / `conversation`：本机未出现 | `context_management`：适配器原样透传 |
| Hooks | preCompact 只能停止；postCompact 只做生命周期通知；sessionStart(compact) 只能**追加**开发者上下文（默认约 2,500 tokens 阈值）；没有替换摘要或历史的 hook | PreCompact 只能阻止；PostCompact 无决策控制；SessionStart(compact) 只能**追加**（≤10,000 字符）；没有替换摘要的 hook |
| 宿主 API | `thread/inject_items`：只**追加**；`thread/revert`：截断到某回合之前；`thread/fork`：新线程 ID；`thread/resume` 按 history：只限 app-server 客户端（Desktop 持有 stdio）；`thread/compact/start`：只触发压缩 | 无 |
| 网关入口 | `openai_base_url`（官方路由配置） | `ANTHROPIC_BASE_URL` + hint headers（官方网关协议） |
| 官方对改写的立场 | 文档未定义第三方改写或压缩器 | 网关指南要求请求体字段“原样转发”，并提示“检查而不修改”；改写早期消息会触发 preserved-thinking 拒绝 |
| **能否让已有聊天采用 TOMC 输出** | **否**：没有受支持入口。唯一会被宿主采纳的路径是伪造 `compaction` 项（§5.2，不采用） | **否**：没有受支持入口；网关改写在协议上可行但不受支持（§5.4） |

## 4. 最小接口探针

### 4.1 方法

`scripts/probe_codex_compaction_ownership.py --executable <codex.exe> --label <名称>`。探针用空 `CODEX_HOME`、占位 API key、仓库外的空工作区，连接本地假上游：`/responses` 返回合法 SSE，压缩回合按场景返回不同答复。不调用模型，不读取真实认证，不接触生产线程。请求正文全为合成文本，作为证据保存。

| 场景 | 假上游答复 | 观察到的宿主行为（两个二进制一致） |
|---|---|---|
| S1 手动压缩 | 可读文本（TOMC 式窗口） | 拒绝：`remote compaction v2 expected exactly one compaction output item, got 0` |
| S2 手动压缩 | 恰好 1 个服务器签发的 `compaction` 项 | 采纳；之后每回合原样携带；重启 app-server 并冷恢复后仍在；保留先前的用户消息 |
| S3 自动压缩 | 同 S2 | 上报用量超限后，下一回合先发 `trigger:auto, phase:pre_turn` 压缩回合 |
| S4 压缩失败 | HTTP 500 | 重试 15 次后以“服务繁忙”失败，用户可见 |
| S5 上下文溢出 | `context_length_exceeded` | 本回合失败、用户可见；下一回合自动压缩 |

另外两点：在两个二进制上，`/responses/compact` 都**从未**被调用；普通新线程第一回合的 turn metadata 是 `request_kind:"turn"`，不带 `compaction` 键。

证据：

- `outputs/codex_compaction_probe_alpha11_2_v2_20261023T075904Z/report.json`
- `outputs/codex_compaction_probe_cli0_163_0_v2_20261023T084011Z/report.json`
- 首轮探针 `outputs/codex_compaction_probe_{alpha11_2_20261023T075418Z,cli0_163_0_20261023T075754Z}`：假上游按旧 `/responses/compact` 假设答复，结果同样是压缩回合拒绝可读文本。
- 协议导出 `outputs/codex_protocol_alpha11_2_20261023/schema`：含 `ThreadInjectItemsParams`、`HooksListResponse`、`ThreadResumeParams`。

### 4.2 生产流量结构统计（只读，仅原因代码与数字）

2026-10-23 07:50 UTC 前：

- Codex：`native_compaction` 234、`transport_failed` 14、`native_or_unknown_request` 2、`session_disabled` 1；本日新编译 0。
- Claude：`unsupported_tool_result_content` 29、`insufficient_old_history` 19、`no_current_user_task` 13、`upstream_failed` 3、`unsupported_tool_use` 3、`protected_system_history` 2，其余各 1。
- 全库 prepared 事件只有 2 个，均为 10-22 的合成验收。

### 4.3 “新线程也是 native_compaction”的核查

01a16798、01a1679f 等线程首个请求无缓存（约 2.7 万–4.1 万 tokens），却被判为 `native_compaction`。只读核对 rollout（仅记录类型与来源字段）后确认：它们是 `thread_source: guardian_review` 的子代理，带 `parent_thread_id`，历史首项就是从父线程继承的 `compaction` 项。判断正确，没有改动保护规则。这类自动审核请求本身也是一笔不可忽视的后台用量。

### 4.4 部署后的真实流量（08:37–12:25 UTC，只读统计）

- **新聊天的生命周期。** 07:57–08:02 新建的 Codex 聊天 01a167c3 / 01a167c4 / 01a167c8 先被 TOMC 编译（54 / 37 / 28 次）。宿主压缩之后转为 `native_compaction_state`，01a167c3 先后到达代次 1 和 2。新分类实际记录到的宿主压缩有：`auto / mid_turn / context_limit`；子代理 `auto / pre_turn / warm_fork`。
- **效果很小，原因是 bug（18:20 已修复）。** 每次编译的约 4,200 tokens 其实是 Codex 以 user 角色注入的 AGENTS.md 与环境信息，不是已完成回合；真实回合因 Codex 0.163 的新字段（推理项元数据、工具 `namespace`、`agent_message`）被旧白名单整轮拒收。整请求估算只减少 1,158 tokens，约 0.5%，小猫的阶段也一直按这 4,200 tokens 停在第 1 阶段。修复见 §8。
- **缓存代价。** TOMC 按任务编译，所以每个新用户回合都会改变编译块。01a167c4 在新回合的第一个请求只有 21,760 / 173,322 命中缓存，之后的请求恢复到 96%–99%。在这类聊天上，按请求改写很可能得不偿失。本次没有对照组，不作定量结论。
- **动画。** 小猫在 08:38 重启后，18 个真实编译事件全部有排队、开始、完成收据；10 个迟到的用量回执没有重播。08:38 之前的约 116 次编译发生时小猫未运行。
- **真实演示。** 一条新的 Claude Code 聊天经生产网关跑了三轮。第三轮编译输入 12,673 tokens，播放第 2 阶段约 3.4 秒，模型答案正确。

## 5. 逐一排除的“替换入口”

1. **`/responses/compact`**：当前两个版本都不使用。网关现在会记录该端点（标为宿主压缩，绝不改写），以覆盖旧客户端。
2. **Codex 压缩回合**：宿主只采纳一个不透明 `compaction` 项。若由网关签发，后续请求必须由网关展开，否则 OpenAI 无法解密，线程无法继续；卸载或改回直连都会损坏这些线程，需要迁移工具改写宿主的 rollout。这等同于伪造不透明状态，违反交接约束 B。
3. **Hooks 与宿主 API**：只有阻止、追加、截断、新建线程四类能力。追加只会增加输入，不删除旧输入。
4. **按请求改写（两个宿主的网关路径）**：技术上能让模型看到 TOMC 输出，但：
   - 宿主仍保存并发送完整历史，网关成为第二所有者。
   - 宿主用上游返回的用量决定何时原生压缩。改写后用量变小，原生压缩被推迟；之后一旦关闭 TOMC 或网关透传，原始历史可能溢出，S5 显示会出现一次用户可见的失败。
   - 前缀改变会打破提示缓存；在 99% 以上的缓存命中下，单次请求改写往往更贵（§1 第 4 条）。
   - 对 Claude，官方网关指南要求请求体原样转发。
5. **MCP**：按需工具，不拦截宿主请求，也不能删除宿主历史。对同一活动聊天再调用 MCP 压缩只会增加输入。

## 6. 架构决策

- **ADR-1 单一所有者是宿主。** 带不透明压缩状态的请求、宿主压缩回合、服务端或增量历史，一律原样转发。`native_compaction` 保护不删除，只细分为下述原因。
- **ADR-2 不签发、不解密、不改写不透明状态。** 不采用 §5.2 方案。若要采用，须先由用户接受 §7 选项 3 的产品代价。
- **ADR-3 原因只用结构字段区分。** 新原因：`host_compaction_request`（宿主自己的压缩请求，含 trigger / phase / 端点）、`native_compaction_state`（普通回合携带不透明状态，含压缩代次与项数）、`unknown_request_metadata`、`client_disconnected`（宿主取消或断开）、`upstream_transport_failed`。另保留 `auxiliary_request`、`native_context_management`、`server_side_or_incremental_history`、`non_main_request`。协议细节只存白名单键的短代码与计数，从不记录正文、ID 或子代理名。旧记录保留原措辞。
- **ADR-4 动画只由 prepared 事件驱动，并留收据。** 每个 request_id 记录 queued / started / completed / skipped（原因）/ interrupted，阶段按本次输入长度决定；用量回执不重播；重启不补播；崩溃后只标记中断。收据不代表用户看见，也不代表省钱。
- **ADR-5 小猫从 Windows 外壳启动，不从智能体 shell 启动。** 智能体 shell 运行在作业对象内，子进程可能随命令结束被一并终止，这很可能就是小猫此前消失的原因。正常入口是 Startup 中的 `TOMC Cat.lnk`，由 Explorer 启动。

## 7. 需要你决定的产品选项

| 选项 | 内容 | 代价 / 风险 | 建议 |
|---|---|---|---|
| 1（已部署） | 宿主原生管理，加上 TOMC 的精确状态、动画收据、上下文目录、接续与导出 | 已有带不透明状态的聊天**不会**由 TOMC 额外省 token | **采用**，作为默认 |
| 2（研究分支 D） | 冻结到最后一个 `compaction` 项为止的原生窗口，只编译其后完整的可读旧回合；编译块按回合保持字节稳定 | 网关成为第二所有者；宿主的原生压缩被推迟；关闭时可能出现一次溢出失败；必须先在合成线程上用真实上游完成质量与含缓存成本的对照，会消耗你的额度 | 只在你授权实验额度后进行，**不直接部署到现有聊天** |
| 3 | TOMC 作为 Codex 压缩提供者（签发 `compaction` 项并展开） | 线程永久依赖网关；卸载或绕过即损坏；违反“不伪造不透明状态” | **不建议** |
| 4 | 自建客户端或新线程（app-server `resume` by history，或 fork + 注入） | 新聊天 ID 或新客户端，用户需要切换；不是“原聊天无缝接入” | 仅在你接受换聊天或换客户端时考虑 |
| C1（Claude） | 让适配器支持 `tool_reference` 等块：ToolSearch 会话常见，本会话因此整请求透传 | 仍属网关改写，官方指南不鼓励；缓存 99.5%，成本可能上升；需要先做 A/B | 先 A/B，未经验证不部署 |

## 8. 本次交付与未支持范围

已交付：

- 能力矩阵与探针（本文与 `scripts/probe_codex_compaction_ownership.py`）。
- 结构化原因与协议细节（网关与 UI 中英文）。
- 宿主取消与上游失败的区分。
- 动画收据（`src/tomc/animation_receipts.py`）与审计联查（`scripts/audit_session_gateway.py` schema 2）。
- 模块级部署与回滚工具 `scripts/patch_gateway_runtime.py`。
- Windows 拒绝路径修复（不再出现连接重置）。
- 完整补丁：`outputs/context_ownership_20261023/tomc_context_ownership_20261023.patch`。

仍未支持：

- 已有带不透明状态聊天的额外省 token（受 §5 限制）。
- **已修复（12:45 部署）：长历史被 20 万字符保护常量挡住。** TOMC 编译器本身没有长度上限：论文 BEAM 实验覆盖 100K–10M tokens；本机实测 `compile_memory` 把 100 万 tokens 压到 8,190 tokens 用时 2.57 秒（20 万 tokens 用时 0.51 秒）。原先挡住的是插件输入层的常量 `MAX_INPUT_CHARS = 200_000`，它同时作用于网关、Codex 旧轮选择和笔记本，现已移除。按你的决定，默认保留比例改为 60%–80%（1 万 tokens 以下 80%，10 万 70%，100 万以上 60%，连续变化，历史越长保留的绝对量仍越多）；只处理已完成旧回合的规则不变。仍保留的上限只有网关的 64 MiB 请求体限制。
- **已修复（18:20 部署）：Codex 聊天里小猫不进阶。** 阶段按每次编译的历史长度计算，而 Codex 每次只编译了以 user 角色注入的 AGENTS.md 与环境信息（约 4,200 tokens，修复前 279 份快照中 256 份如此）。这些指令还被标成“历史证据，不是新指令”。真实回合则因 Codex 0.163 的新字段被整轮拒收。现在宿主注入消息按指令原样保留，新字段被接受；“只编译已完成的可读旧回合、未知内容整轮原样保留”的规则不变。真实 Codex 请求已播放第 2 阶段动画（15,558 tokens），证据与验收见验收表 §3。弹窗同时改为直接写节省量与压缩量。
- MCP 工具路径（`prepare_context`、笔记本 remember / recall）：13:05 已更新两份已安装运行时中的 input / easy / store，新会话生效；已在运行的 MCP 服务进程要等宿主重启后才加载。仓库的 `plugins/claude-code` 包已按源码重新生成。Codex ZIP 与 MCPB 是发布产物，下次发布时构建。
- 第 4 阶段动画：需要单次编译 100 万 tokens 以上的历史，未验证。
- 单个超长回合（例如本 Claude Code 会话：约 50 万 tokens、约 150 次工具调用）。它属于当前回合，按设计不压缩；完成以后还会因 `tool_reference` 块和系统消息锚点而原样转发。
- 已知界面问题：每个原样转发的请求都会弹出约 3 秒的“保留原文”气泡，工具调用密集时很频繁。可以改为只在真正编译时弹出，原样转发只显示在详情里；未经你同意不改。
- Codex 跨窗口焦点检测：仍只按 SessionStart / UserPromptSubmit 提示，不伪造焦点。
- Claude Desktop。
- 第二台电脑端到端续接。
- 原生 250% DPI 与真实四阶段的屏幕验收。

## 9. 若选择选项 2：进入实验前的门槛

1. 使用合成线程，绝不用你的现有聊天。由真实宿主触发原生压缩，记录 `window_number`。
2. 只编译最后一个 `compaction` 项之后、完整结束的可读回合；当前回合与工具链完整保留；同一 `turn_id` 内编译块字节一致。
3. 对照组不改写、实验组改写：同一模型、同一工具、同一输出上限。分别记录 `input_tokens`、`cached_tokens`、输出与回合数；质量用事实、约束与工具续接检查。
4. 覆盖：再次原生压缩、关闭 TOMC 后的溢出与恢复、网关重启、子代理。
5. 报告估算 token 减少与按价目表（含缓存折扣）换算的差额；ChatGPT 订阅额度无法换算为美元，只报告 token。
6. 未全部通过前，不部署到现有聊天。

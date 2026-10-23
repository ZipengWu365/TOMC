# TOMC 验收表

2026-10-23，12:25 UTC 补入真实流量证据。对应架构决策 [TOMC_CONTEXT_OWNERSHIP_20261023_ZH.md](TOMC_CONTEXT_OWNERSHIP_20261023_ZH.md)。

状态只取以下几种：

- **已验证**：本次在真实环境中执行并留有证据。
- **离屏已验证**：隔离测试中通过，未经真实桌面或真实请求验证。
- **沿用早前证据**：本日较早时的真实验证，本次补丁未改相关逻辑。
- **已部署，待真实事件**：代码已上线，但触发它的真实请求尚未发生。
- **未实现** / **未验证**：字面含义。

默认开关、服务健康、测试会话、预览动画、同机临时目录，均不代替对应的真实验收。

## 1. 真实聊天与上下文采用

| 场景 | 状态 | 证据 / 说明 |
|---|---|---|
| 当前 Codex 聊天及 BEAM 聊天与另一条原聊天都经过网关、默认开启 | 已验证 | 依次为 44 / 8 / 18 条真实请求，effective_enabled=true：`outputs/context_ownership_20261023/audit-three-codex-sessions-after-patch.json` |
| 可压缩时 TOMC 输出被这些聊天实际采用，并有质量与用量证据 | **未实现** | 三条聊天及其子代理都携带宿主不透明压缩状态，当前版本没有受支持的替换入口（架构决策 §3–§5） |
| 新建的真实 Codex 聊天，在宿主第一次压缩之前 | 已验证（采用）；效果很小 | 01a167c3 / 01a167c4 / 01a167c8 分别有 54 / 37 / 28 次真实请求被编译后转发。以 01a167c4 为例：每次只编译早期 4,200 tokens 的已完成回合，整请求估算减少 1,158 tokens（约 0.5%）；新用户回合的第一个请求只有 21,760 / 173,322 命中缓存，同一回合内的后续请求恢复到 96%–99%。宿主自动压缩后，这些聊天转为 `native_compaction_state`，由宿主管理。证据：`outputs/context_ownership_20261023/audit-real-compiled-chats-20261023T1225Z.json` |
| 已有原生压缩历史：所有权与协议边界 | 已验证 | 两个 Codex 版本的隔离探针、rollout 结构核对、官方文档（架构决策 §4） |
| 新原因标注出现在真实请求上 | 已验证 | Claude：5ba56af8、8e20722f 带 `request_class:main`。Codex 真实流量：宿主压缩（auto / mid_turn / context_limit，代次 1；子代理 auto / pre_turn / warm_fork）；压缩后普通回合带代次 1、2；5 次宿主取消记为 `client_disconnected` |
| 透传原因不再统一显示为“正在压缩” | 离屏已验证 | `tests/test_animation_receipts_qt.py::test_status_names_host_compaction_separately_from_tomc_work` |

## 2. 开关、并发与子代理

| 场景 | 状态 | 证据 / 说明 |
|---|---|---|
| A 关闭 → A 不再新编译、B 正常；恢复 A；原有快照保留 | 沿用早前证据 | 07:06 的真实请求被记为 `session_disabled`：`outputs/open_session_acceptance_20261023/switch-*.json`。补丁未改开关逻辑；新测试确认关闭的会话即使遇到压缩回合，仍记为 `session_disabled` |
| 子代理请求被识别，不改写、不串开关 | 已验证（结构） | 只读核对 guardian_review 子代理：继承父线程压缩项，判为 `native_compaction_state`，标记 `agent: subagent`，不记录其名字 |
| 并发编译各播放一次，不串统计 | 离屏已验证 | 既有测试 `test_all_concurrent_preparations_play_once_even_with_other_request_busy`，以及新收据测试 |
| 不把后台请求当切换，不反复弹窗 | 沿用早前证据 | 弹窗修复代码未改动，`usage_widget_qt.py` 从已部署版本逐字节继承；相关 Qt 测试全部通过。本次未在原生桌面重做 |

## 3. 动画

| 场景 | 状态 | 证据 / 说明 |
|---|---|---|
| request_id ↔ prepared ↔ 播放开始 / 完成 | 已验证 | 小猫 08:38 重启后共 18 个真实 prepared 事件（17 个来自真实 Codex 聊天，1 个来自真实 Claude Code 演示聊天 42b059be），每个都有 queued / started / completed 收据。08:38 之前的编译发生时小猫未运行，所以没有收据 |
| 真实演示（Claude Code 新聊天，三轮，经生产网关） | 已验证 | 12:22:37.86 编译（输入 12,673）→ 38.25 开始第 2 阶段 → 41.67 完成。模型答对合成事实；估算 53,950 → 51,568；供应商输入 73,517，其中缓存 56,601。证据：`outputs/global_claude_compression_20261023T122232Z_35fbdab6/validation.json`、`outputs/context_ownership_20261023/audit-real-demo-42b059be-0033-419d-98ee-3b4f95681d46.json` |
| 用量回执不重播 | 已验证 | 10 个迟到的用量回执记为 `skipped / already_animated` |
| 重启不补播、崩溃只标中断 | 离屏已验证 | `tests/test_animation_receipts*.py` |
| 四阶段 | 第 1、2、3 阶段：已验证（真实请求与动画收据）。第 4 阶段：未验证 | 20 万字符常量已在 12:45 移除（见下行）。第 3 阶段：真实 Claude Code 聊天 95c0bee7 在 13:03:32.81 编译 107,638 tokens，13:03:33.69 开始第 3 阶段动画，13:03:36.50 完成。证据：`outputs/context_ownership_20261023/audit-real-stage3-95c0bee7-9c33-4bb7-9aca-9f1e3139162e.json`。12:45 那次编译发生时小猫已被正常关闭（无崩溃记录），按交接要求没有自动重开；13:03 经你同意由 Explorer 重开。第 4 阶段需要单次编译 100 万 tokens 以上的历史，一次真实演示约消耗 130 万 tokens 额度，本次未做。降档已有离屏测试 |
| 20 万字符保护常量 bug | 已修复并部署 | 修复前 11 个复现测试中 8 个失败（`prepare_context`、Claude 适配器、Codex 适配器、笔记本都被拒，默认仍是 80%）；修复后全部通过，全套 694 passed / 0 failed。默认改为保留 60%–80%：1 万 tokens 以下 80%，10 万 70%，100 万以上 60%，连续变化。真实长历史 Claude Code 聊天（1fb18c0f）第三轮：估算 151,418 → 119,478（−21%）；供应商输入 181,723，上一轮同一历史未改写时为 233,638（非同请求对照）；事实答对。证据：`outputs/context_ownership_20261023/audit-real-long-history-1fb18c0f-79a9-449b-b4ce-26836448d1dc.json` |
| 结束后回到待机 | 已验证（收据）；原生屏幕未截图 | completed 收据之后不再有该 request_id 的动画 |
| MCP 工具路径去掉 20 万上限（`prepare_context`、笔记本） | 已修复（新会话生效） | 两份已安装的 MCP 运行时（context-preview.1、assistant-preview.5）中的 input / easy / store 与修改前源码逐字节一致，因此用新文件替换，并保留精确备份。替换前先用各自的解释器在暂存副本中验证：旧版 mcp_server 能正常导入，631,580 字符历史可以编译，笔记本可超过 20 万字符。回执：`%USERPROFILE%\.codex\tomc\archive\session-update-20261023T130531078201Z-d987834e`。已在运行的 MCP 服务进程要等宿主重启它们后才加载新代码。旧版 mcp_server 的工具说明仍写“约 80%”，下次插件发布时更新 |
| 仓库插件包与源码一致 | 已验证 | `plugins/claude-code` 已重新生成（74 个文件，其中 26 个更新），`--check` 通过。Codex ZIP 与 MCPB 属于发布产物，本次未构建 |
| 当前这条 Claude Code 对话能否演示 | 目前不能 | 20 万字符常量已移除；剩下的原因是 ToolSearch 产生的 `tool_reference` 块不受支持，以及对话中的系统消息锚点 |

## 4. 语言、显示与启动

| 场景 | 状态 | 证据 / 说明 |
|---|---|---|
| 新状态文本中英文正确 | 离屏已验证 | 新增中英文断言 |
| 原生窗口按钮切换、持久化、DPI 250%、长英文截断 | 未验证 | 本次未做原生截图验收 |
| 小猫运行，且不随智能体 shell 退出而消失 | 已验证 | 08:38 发现小猫未运行（推测被先前智能体 shell 的作业对象终止），经 Startup 快捷方式由 Explorer 启动；启动它的 shell 退出后仍在运行；08:43 为加载新模块又重启一次 |
| Windows 重新登录后自动启动 | 未验证 | 快捷方式已存在（07:13 回执），本次未重新登录 |

## 5. 故障、安装与回滚

| 场景 | 状态 | 证据 / 说明 |
|---|---|---|
| 宿主取消与上游中断分开记录 | 已验证 | 真实流量中 5 次 `client_disconnected`，另有离屏测试。部署前的 `transport_failed` 记录无法事后细分 |
| 网关重启不打断进行中的请求 | 已验证 | 两次真实模块部署，开始时进行中请求为 0；新监听进程健康 |
| 恶意或畸形请求被拒时不再出现连接重置 | 离屏已验证 | 网关测试连续 8 轮全部通过（修复前同一组测试在不同参数上间歇失败） |
| 精确备份、限定模块、回执；运行包与源码哈希一致 | 已验证 | 4 份回执见部署文档；`outputs/context_ownership_20261023/runtime-vs-source-sha256.json`（gateway=true, pet=true） |
| 回滚 | 未验证 | 工具与备份已就绪，未实际执行（不需要） |
| 网关不可达、锁库时的状态显示 | 未验证 | 本次未注入故障 |

## 6. 跨 Agent 与跨电脑

| 场景 | 状态 | 说明 |
|---|---|---|
| A 机真实快照 → 导出 → B 机导入 → 新 Agent 继续 | 未验证（你将用另一台电脑测试） | 现在已有真实快照可导出：01a167c3 / 01a167c4 / 01a167c8 三条新 Codex 聊天，以及演示聊天 42b059be。入口：点小猫 → 上下文与接续 → 选择快照 → “复制接续提示词”或“导出便携包”（CONTEXT.md、START_HERE.md、metadata.json） |
| 同机跨 Agent 接续 | 未验证 | 本次未执行 |

## 7. 测试

| 项目 | 结果 |
|---|---|
| 补丁前基线 | 646 passed，9 skipped，3 failed |
| 补丁后 | **694 passed，9 skipped，0 failed**（含 11 个长历史测试） |
| 3 个既有失败 | 1 个是过期断言：事件流已改为分页、不截断；2 个是 Windows 拒绝路径的连接重置，已从根因修复 |
| Ruff | 通过 |
| 运行环境 | `.venv-usage` 解释器，`PYTHONPATH` 指向 hourglass-ui 的 site-packages（PySide6），`QT_QPA_PLATFORM=offscreen`，`--basetemp` 放在仓库外 |

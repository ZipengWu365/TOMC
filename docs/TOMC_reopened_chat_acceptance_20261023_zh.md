# 重开后真实会话验收

2026-10-23，最后更新于 08:14 英国时间（07:14 UTC）。结论是接入与单会话开关通过；截至末次检查，应用报告已加载的三条真实聊天都经过网关、保持开启，但没有产生 TOMC 新编译，因此本轮没有真实压缩动画可验收。不能把默认开启或原样转发表述为自动节省 token 已通过。

## 接入

应用清单本轮报告两条本机聊天处于 active 状态，均已有真实网关请求：

- 当前开发聊天：`01a16537-0fd1-7c93-972e-8298f07c5570`。
- BEAM 评估聊天：`01a11602-bdf1-71a1-b91d-c42c0f3c9e53`。

07:09 的快照中分别有 17 / 8 条请求，均保留默认开启，真实编译事件均为 0。当前聊天在重开后确实采用了本机地址，不再是仅配置文件上的启用。其他此前列出的聊天本轮没有新的请求证据，不能逐条宣称已核验；用户级默认路由和默认开关仍开启。

证据：`outputs/open_session_acceptance_20261023/loaded-codex-sessions.json`、`sessions-after-restored.json`。

末次刷新又发现第三条聊天（`01a13afa-a481-7992-9d42-229a21ff3990`）已加载。再次按三个真实 ID 核对：当前聊天 25 条请求、BEAM 聊天 8 条、第三条聊天 10 条，全部 observed=true、effective_enabled=true、prepared_event_count=0，最后原因均 native_compaction。末次证据：`outputs/open_session_acceptance_20261023/final-three-sessions.json`。这是当前应用已加载三条聊天的覆盖，不包含未加载且没有新请求的其他历史聊天。

## 单会话关闭

短暂关闭当前聊天，下一次真实模型请求 `b55bf683-2cd0-4ab1-b01a-48b02ff7cfb1` 被记录为 `passthrough / session_disabled`，已发往上游并收到用量回执。同期另一条聊天保持开启，继续以自身协议原因原样转发。07:06:38 UTC 已恢复当前聊天开启；原有其他会话开关全部保留，未关闭全局开关。

这是实际请求层开关验证，使用与界面相同的 SessionStore 设置接口；本轮未自动点击桌面按钮。

证据：同目录 `switch-baseline.json`、`switch-disabled-observation.json`、`switch-restored.json`。

## 为什么当前没有压缩动画

两条聊天的请求均触发 `native_compaction` 原样转发规则。代码按协议字段判定，未用聊天中的关键词匹配。当前聊天历史确有五次宿主 compacted 事件，每次替换历史均含一个带 encrypted_content 的不透明 compaction 项。该项由宿主维护，不应为强行触发小猫动画而删除或重写。

因此这次确认的是流量已经经过 TOMC，而不是 TOMC 已为当前聊天减少输入。prepared 事件为 0，不能播放一次演示并算作本轮真实压缩成功。之前合成验收会话的真实请求动画结果仍只证明那些明确记录的测试，见 `TOMC_animation_acceptance_20261022_zh.md`。

## 小猫运行状态

本轮检查发现网关在运行，但普通小猫进程未运行。已通过安装的 `pet.pyw` 正常入口恢复，无 --demo，也没有注入压缩事件、改变系统鼠标键盘或控制其他应用。

07:10:19 UTC 复核：普通入口 launcher PID 40720、实际进程 PID 56212；gateway health ready=true。状态文件已更新至今天，test_mode=false、error=null、language=zh，stderr 为空。这些证据确认进程正常运行，不代替屏幕可见动画验收。

证据：同目录 `runtime-health.json`、`cat-state-after-start.json`、`cat-start.stderr.txt`。

08:13 英国时间补齐用户级 Windows 登录自启动 `Startup/TOMC Cat.lnk`，目标为现有 pythonw + 普通 pet.pyw，无演示参数。原先只有网关自启动；桌面快捷方式不会随 Codex 重开自动执行。此次创建后读回核对目标、参数与哈希，未替换其他快捷方式。证据：`cat-startup-receipt.json`；维护脚本为 `scripts/install_pet_startup.ps1`（默认预览）。这证明自启动项已安装，不表示已经重启 Windows 验证登录触发，也不表示关闭小猫后重开 Codex 会强制再次启动它。

## 尚未通过的部分

- 所有此前聊天逐条真实请求覆盖：尚有未产生新请求的聊天。
- 当前三个真实聊天的 TOMC 自动压缩：被宿主原生压缩保护跳过，当前新编译为零。
- 本轮每次真实压缩的可见动画：没有新编译事件，无法作本轮成功结论。

本轮未向其他用户聊天发送测试消息，也未用新的测试聊天替代这些真实聊天的覆盖验收。

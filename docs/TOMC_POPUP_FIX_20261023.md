# 重复“保持开启”提示修复补记
2026-10-23，已部署到当前普通小猫。

## 原因
网关每个模型请求都可能更新最近会话；多个真实聊天、后台 Agent 的请求交错时，event_seq 连续变化。旧 UI 对每次变化都调用 SessionNotice.present，因此把后台活动当成切换提示。点击“保持开启”只隐藏当下窗口，下一事件又显示。

## 本次修复
- model_request 等后台事件不触发弹窗。
- 首次成功读取建立基线，不补播旧宿主事件。
- 仅 SessionStart / UserPromptSubmit 两种明确宿主事件可触发。
- 按 host + session_id 每个小猫进程最多提示一次；不同宿主同字符串 ID 不串用。
- 保留默认开启、手动关闭／重新开启、中英文和压缩动画队列。
- 这是防打扰修复，不是已实现可靠的桌面焦点检测。将来要做到“每次用户主动切换时提示”，须接入可靠焦点事件，不能恢复按模型请求弹窗。

## 修改与验收
仅生产 usage_widget_qt.py 更新；源码测试涉及 tests/test_usage_widget_language.py、tests/test_context_library_qt.py。
56 项 Qt 测试通过，覆盖后台交替、启动历史、初次锁库、同 ID 用户事件、去重、开关、双语与动画相关回归。测试使用隔离数据库，未伪造生产压缩事件。
部署回执：
%USERPROFILE%/.codex/tomc/archive/session-update-20261023T072301572513Z-a6fe85f8/receipt.json

随后仅重启普通 pet.pyw，未重启网关、Codex、Claude，未改用户会话开关；非 demo。
这是源码测试与部署记录，不把它当成所有实际动画的原生屏幕验收。

本机原生复核日志在 outputs/open_session_acceptance_20261023/cat-popup-fix.stderr.txt。接手时保留已部署修复，不用旧源码覆盖。


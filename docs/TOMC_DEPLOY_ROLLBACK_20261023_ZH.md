# TOMC 部署与回滚记录

2026-10-23。只替换下列模块。没有改动 Codex / Claude 配置、认证、会话开关、启动快捷方式或数据库内容。数据库只新增了一列，见 §4。

## 1. 已部署内容与回执

| 时间 (UTC) | 位置 | 模块 | 回执 |
|---|---|---|---|
| 08:37:21 | 网关 `%USERPROFILE%\.codex\tomc\gateway-016-20261022T210600Z\src\tomc` | request_gateway、responses_request、anthropic_request、request_activity | `…\backups\classify-receipts-20261023T083721Z\patch-receipt.json` |
| 08:37:58 | 小猫 `%USERPROFILE%\.codex\tomc\pet-current\src\tomc` | usage_widget_qt、context_library_qt、request_activity；新增 animation_receipts | `%USERPROFILE%\.codex\tomc\archive\session-update-20261023T083758451024Z-37e00b07\receipt.json` |
| 08:42:44 | 网关 | request_gateway、request_activity（记录旧 `/responses/compact` 端点） | `…\backups\compact-endpoint-20261023T084244Z\patch-receipt.json` |
| 08:43:04 | 小猫 | context_library_qt、request_activity | `…\archive\session-update-20261023T084304400536Z-35c8da60\receipt.json` |
| 12:45:17 | 网关 | input、easy、responses_request（移除 20 万字符常量；默认保留 60%–80%） | `…\backups\no-char-cap-20261023T124517Z\patch-receipt.json` |
| 13:05:31 | MCP 运行时 `context-preview.1`、`assistant-preview.5` 的 `plugins\tomc-memory\src\tomc` | input、easy、store（替换前与修改前源码逐字节一致；工具：`scripts\update_mcp_runtime_core.py --base-ref refs/snapshots/handoff-20261023T074454Z`） | `…\archive\session-update-20261023T130531078201Z-d987834e\receipt.json` |
| 18:20:22 | 网关 | responses_request（宿主注入的 AGENTS.md / 环境信息不再当历史编译；支持 Codex 0.163 的新字段）、usage（摘要直接写节省量） | `…\backups\host-context-stage-20261023T182022Z\patch-receipt.json` |
| 18:20:48 | 小猫 | 全部 13 个界面模块（只有 usage_widget_qt、context_library_qt、usage 有实际改动：弹窗直接写节省与压缩量；其余与已部署版本语法树一致，仅格式不同） | `…\archive\session-update-20261023T182048683981Z-b842c5c9\receipt.json` |

| 20:11:11 | 网关 | request_gateway、request_activity（每个请求记录所用模型 ID，用于按模型折算金额） | `…\backups\request-model-20261023T201111Z\patch-receipt.json` |
| 20:11:25 | 小猫 | usage_widget_qt（新的省 token 看板）、request_activity；新增 savings | `…\archive\session-update-20261023T201125807471Z-cd331116\receipt.json` |
| 21:56:32 | 小猫 | context_library_qt（“上下文与接续”改为看板 + 按对话整理）、context_library（便携包带原对话名）、usage_widget_qt、savings；新增 savings_qt、conversation_names、conversations | `…\archive\session-update-20261023T215632685302Z-2638f1ad\receipt.json` |
| 22:34:57 | 小猫 | usage_widget_qt、context_library_qt、savings_qt（内测版 e0df4c2：合并 macOS 窗口处理与界面小修） | `…\archive\session-update-20261023T223457865599Z-ce025ad5\receipt.json` |
| 23:19:59 | 小猫 | usage_widget_qt（看板加“分析报告 ›”入口，滚动区不再是系统灰底）、context_library_qt（新增“分析报告”标签页）、savings（每个请求带日期与请求大小）；新增 categories、analysis、analysis_qt | `…\archive\session-update-20261023T231959701297Z-9e6beadf\receipt.json` |
| 10-24 00:01:42 | 小猫 | context_library_qt、analysis_qt（按钮改为“匿名提交反馈 ›”，紧挨按钮写明只提交工作类型和数字；提交窗口顶部列出会提交 / 不会提交） | `…\archive\session-update-20261024T000142606182Z-5e2e840d\receipt.json` |
| 10-24 00:04:34 | 小猫 | usage_widget_qt（Esc 只关闭看板，不再退出小猫） | `…\archive\session-update-20261024T000434354569Z-7d012038\receipt.json` |
| 10-24 08:22:17 | 小猫 | usage_widget_qt（关闭“上下文与接续 / 分析报告”等窗口不再退出整个小猫） | `…\archive\session-update-20261024T082217172738Z-05e9bbdb\receipt.json` |

18:20:22 部署前，已安装的 responses_request、usage 与当时的提交（8492321）语法树一致；20:11 部署前，已安装的网关与小猫模块与 b22bb11 语法树一致。网关第一次写入时给 `tomc_request_activity` 增加一列 `model`（TEXT，可为空），见 §4。MCP 运行时里的 usage.py 是更早的构建，与 8492321 不同，更新工具按规则没有替换它，所以 `prepare_context` 的聊天摘要仍是旧措辞，下次重建插件时更新。

MCP 运行时的回滚方式与小猫相同：用 §3 的循环，把回执目录换成 `session-update-20261023T130531078201Z-d987834e`。已在运行的 MCP 服务进程不受文件替换影响，要等宿主重启后才会加载新代码。

五次网关部署开始时进行中的请求都为 0。每次都只重启受监督的 `--serve` 子进程，健康检查通过并出现新的监听进程（PID 48860 → 69248 → 25364 → 40276 → 75240 → 35300）。小猫在 08:43:32、13:03:06、18:21:09、20:11:34、21:56:34、22:34 部署后、23:20:13、10-24 00:04:43、08:12:05、08:22:20 由 Explorer 重启（21:56、23:20、00:04、08:12 与 08:22 时小猫已不在运行，Windows 日志里没有它的崩溃记录；原因见验收表“小猫自己消失”一行，08:22 起已修复）。部署后哈希核对：`outputs/context_ownership_20261023/runtime-vs-source-sha256.json`。

源码补丁（相对交接快照，不含被忽略的 outputs）：`outputs/context_ownership_20261023/tomc_context_ownership_20261023.patch`。交接快照引用：`refs/snapshots/handoff-20261023T074454Z`。

## 2. 安装（重复或下一次更新）

在仓库根目录执行。各命令默认只预览，加 `--install` 才会生效。

```powershell
# 1) 测试。Qt 测试需要 PySide6：
$env:PYTHONPATH = "$env:USERPROFILE\.codex\tomc\hourglass-ui\Lib\site-packages"
$env:QT_QPA_PLATFORM = "offscreen"
.venv-usage\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp <仓库外目录> --ignore-glob "tests/.tmp_*"

# 2) 网关模块（预览，然后安装）
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime "$env:USERPROFILE\.codex\tomc\gateway-016-20261022T210600Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime "$env:USERPROFILE\.codex\tomc\gateway-016-20261022T210600Z" --label <名称> --install

# 3) 小猫模块（需在 scripts 目录内运行）
cd scripts; ..\.venv-usage\Scripts\python.exe -B update_pet_ui.py; ..\.venv-usage\Scripts\python.exe -B update_pet_ui.py --install; cd ..
```

`patch_gateway_runtime.py --install` 的执行顺序：

1. 用运行时自己的解释器，在暂存副本上导入全部网关模块。
2. 等待最多 120 秒，直到近期没有进行中的请求；仍有请求则不做任何改动（退出码 3）。
3. 逐字节备份并写回执，然后替换文件。
4. 只结束 `--serve` 进程树，由 supervisor 在约 3 秒后拉起新进程。
5. 等待 `/health` 正常且出现新的监听进程。
6. 任一步失败时，自动恢复备份并再次重启（回执状态记为 `rolled_back`）。

## 3. 回滚

**网关：** 按部署的逆序执行，每次回滚本身也会留下新的备份与回执。

```powershell
$rt = "$env:USERPROFILE\.codex\tomc\gateway-016-20261022T210600Z"
# 只撤销模型记录时执行第一行；只撤销宿主注入消息与新字段的修复时再执行第二行：
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\request-model-20261023T201111Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\host-context-stage-20261023T182022Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\no-char-cap-20261023T124517Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\compact-endpoint-20261023T084244Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\classify-receipts-20261023T083721Z"
```

**小猫：** 同样逆序，用回执中的逐字节备份覆盖回去，然后重启小猫。

```powershell
$t = "$env:USERPROFILE\.codex\tomc"
foreach ($r in "session-update-20261024T082217172738Z-05e9bbdb", "session-update-20261024T000434354569Z-7d012038", "session-update-20261024T000142606182Z-5e2e840d", "session-update-20261023T231959701297Z-9e6beadf", "session-update-20261023T223457865599Z-ce025ad5", "session-update-20261023T215632685302Z-2638f1ad", "session-update-20261023T201125807471Z-cd331116", "session-update-20261023T182048683981Z-b842c5c9", "session-update-20261023T084304400536Z-35c8da60", "session-update-20261023T083758451024Z-37e00b07") {
  $receipt = Get-Content "$t\archive\$r\receipt.json" -Raw | ConvertFrom-Json
  foreach ($c in $receipt.changes) {
    $target = Join-Path $env:USERPROFILE $c.target
    if ($c.backup) { Copy-Item (Join-Path "$t\archive\$r" $c.backup) $target -Force } else { Remove-Item $target }
  }
}
```

23:19:59 回执中 `categories.py`、`analysis.py`、`analysis_qt.py` 的 `backup` 为空（部署前不存在），循环会删除它们；同一回执恢复的旧 `usage_widget_qt.py`、`context_library_qt.py` 不导入这些模块。08:37:58 回执中 `animation_receipts.py` 的 `backup` 为空（部署前它不存在），上面的循环会删除它。删除时旧的 `usage_widget_qt.py` 已同时恢复，不再导入该模块。恢复后的 `usage_widget_qt.py` 即交接时已部署、含弹窗修复的版本（SHA-256 `569c2a1f…`）。

## 4. 数据库与兼容性

- 新网关第一次写入时会给 `tomc_request_activity` 增加一列 `protocol_detail`（TEXT，可为空）。旧代码一律按列名读写（已有测试覆盖），回滚代码不需要删除这一列。
- 这一列只保存白名单内的结构键：请求类型、压缩 trigger / phase / reason、压缩代次、不透明项数、子代理标记、端点。值只能是短代码、布尔或计数，不保存正文、线程或回合 ID、子代理名。
- 20:11 起网关第一次写入时再增加一列 `model`（TEXT，可为空），只保存请求声明的模型 ID（如 `gpt-6-astra`），格式不符的值不保存。旧代码按列名读写，回滚不需要删列；看板在没有这一列的旧库上照常工作。
- 21:56 起，导入带原对话名的便携包或删除快照时，会建表 `tomc_snapshot_conversations`（快照 ID → 原对话名），只保存导入包自带的名字。本机对话名不入库：每次打开窗口时，从 Codex（`state_*.sqlite` 的 threads 表、`session_index.jsonl`）和 Claude Code（会话记录里的 `ai-title` / `custom-title` 行）只读查找。
- 23:19 起的分析报告只读：从请求记录、节省统计、上下文准备事件和上下文库读取，不建表、不写库。匿名反馈报告只在用户提交时由浏览器发到 GitHub，不写入数据库。
- 动画收据位于 `%USERPROFILE%\.tomc\animation_receipts.jsonl`，超过 512 KiB 时轮换出一份 `.1`。只含 request_id、阶段、长度、时间与 UI 实例号。目前没有关闭开关；删除文件不影响小猫运行，下一次事件时会重新创建。

## 5. 重启小猫的正确方式

不要从 Codex / Claude 等智能体的 shell 直接运行 `pythonw pet.pyw`。那些 shell 位于作业对象中，子进程可能随命令结束被一并终止。正确做法：

```powershell
# 只结束核对过命令行（含 hourglass-ui\Scripts\pythonw.exe 与 pet.pyw、不含 --demo）的进程树：
taskkill /PID <pid> /T /F
# 由 Windows 外壳从正常入口启动：
explorer.exe "$([Environment]::GetFolderPath('Startup'))\TOMC Cat.lnk"
```

`pet.pyw` 是单实例程序：旧进程还在时，新启动会立即退出。

## 6. 只读核查

```powershell
.venv-usage\Scripts\python.exe -B scripts/audit_session_gateway.py --session-id <线程 ID> [--session-id …]
```

schema 2 新增：每会话的 `reason_counts`；最后一条请求的 `protocol_detail`；每个 prepared 事件对应的 `animation_receipts`。

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

MCP 运行时的回滚方式与小猫相同：用 §3 的循环，把回执目录换成 `session-update-20261023T130531078201Z-d987834e`。已在运行的 MCP 服务进程不受文件替换影响，要等宿主重启后才会加载新代码。

三次网关部署开始时进行中的请求都为 0。每次都只重启受监督的 `--serve` 子进程，健康检查通过并出现新的监听进程（PID 48860 → 69248 → 25364 → 40276）。小猫在 08:43:32 由 Explorer 重启。部署后哈希核对：`outputs/context_ownership_20261023/runtime-vs-source-sha256.json`。

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
# 只撤销 20 万字符修复与 60–80% 默认时，执行第一行即可：
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\no-char-cap-20261023T124517Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\compact-endpoint-20261023T084244Z"
.venv-usage\Scripts\python.exe -B scripts/patch_gateway_runtime.py --runtime $rt --rollback "$rt\backups\classify-receipts-20261023T083721Z"
```

**小猫：** 同样逆序，用回执中的逐字节备份覆盖回去，然后重启小猫。

```powershell
$t = "$env:USERPROFILE\.codex\tomc"
foreach ($r in "session-update-20261023T084304400536Z-35c8da60", "session-update-20261023T083758451024Z-37e00b07") {
  $receipt = Get-Content "$t\archive\$r\receipt.json" -Raw | ConvertFrom-Json
  foreach ($c in $receipt.changes) {
    $target = Join-Path $env:USERPROFILE $c.target
    if ($c.backup) { Copy-Item (Join-Path "$t\archive\$r" $c.backup) $target -Force } else { Remove-Item $target }
  }
}
```

08:37:58 回执中 `animation_receipts.py` 的 `backup` 为空（部署前它不存在），上面的循环会删除它。删除时旧的 `usage_widget_qt.py` 已同时恢复，不再导入该模块。恢复后的 `usage_widget_qt.py` 即交接时已部署、含弹窗修复的版本（SHA-256 `569c2a1f…`）。

## 4. 数据库与兼容性

- 新网关第一次写入时会给 `tomc_request_activity` 增加一列 `protocol_detail`（TEXT，可为空）。旧代码一律按列名读写（已有测试覆盖），回滚代码不需要删除这一列。
- 这一列只保存白名单内的结构键：请求类型、压缩 trigger / phase / reason、压缩代次、不透明项数、子代理标记、端点。值只能是短代码、布尔或计数，不保存正文、线程或回合 ID、子代理名。
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

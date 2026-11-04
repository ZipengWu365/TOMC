# TOMC desktop companion (beta)

[中文速查](#chinese-quickstart) · [macOS details](macos_usage.md) · [Install the assistant plugins](assistant_plugin.md)

The desktop companion is a small cat on your screen. It shows how many tokens TOMC has removed (an estimate),
what they are worth at each model's listed input price, and which conversations they came from.
It also keeps the contexts TOMC prepared, organized by your original conversation names, so you can
copy a continuation prompt for another assistant or move a context to another computer.

On Windows you can also turn on **automatic request processing**: a local gateway that compresses
eligible old history in Codex and Claude Code requests before they leave your computer. Without the
gateway, the cat counts savings from TOMC's own tools (`prepare_context`, `recall_memory`).

| | Windows | macOS |
|---|---|---|
| Desktop cat, savings dashboard, context library, analysis report | Yes | Yes |
| Automatic request processing for Codex and Claude Code | Yes (optional) | Not yet |
| Installer | `scripts/install_windows_companion.py` | `scripts/install_macos_pet.py` |

## Install on Windows

You need Windows 10 or 11, Python 3.10 or newer ([python.org](https://www.python.org/downloads/)
or the Microsoft Store) and this repository:

```powershell
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
py scripts\install_windows_companion.py
```

The first command only shows the plan; nothing changes. Then install the cat:

```powershell
py scripts\install_windows_companion.py --install
```

or the cat plus automatic request processing:

```powershell
py scripts\install_windows_companion.py --install --gateway
```

The installer:

- creates a private Python environment for the cat in `%USERPROFILE%\.codex\tomc` and downloads Qt
  (PySide6-Essentials) into it;
- copies TOMC from this checkout, so the cat keeps working if you move or delete the checkout;
- adds **TOMC** to the Start menu and starts the cat at Windows sign-in;
- starts the cat in the bottom-right corner of the screen.

With `--gateway` it also creates the gateway's own environment, starts it at sign-in (hidden),
waits until it answers on `127.0.0.1:43187`, and only then points Codex
(`openai_base_url` in `.codex\config.toml`) and Claude Code (`ANTHROPIC_BASE_URL` in
`.claude\settings.json`) at it. Your sign-in, models and other settings are kept, and exact copies
of both files are saved first. **Quit and reopen Codex and Claude Code** afterwards so new requests
use the gateway.

Gateway requirements and choices:

- Codex must be signed in with ChatGPT; API-key Codex setups are not supported by the gateway yet.
  Open Codex once before installing so `.codex\config.toml` exists.
- `--hosts claude` (or `--hosts codex`) routes only one assistant.
- If Codex or Claude Code already uses a custom endpoint, another model provider or a Codex profile,
  the installer says so and changes nothing.

The command prints a receipt path. Keep it: it is how you undo the installation.

## Install on macOS

Follow [Desktop companion beta: macOS](macos_usage.md#desktop-companion-beta-macos). It builds a
local `TOMC.app` from this checkout; automatic request processing is not available on macOS yet.

## Using the cat

- **The label under the cat** shows today's estimated saving, such as "Today −82K". It is hidden
  on days with no saving.
- **Click the cat** to see estimated tokens removed, their value at each model's listed input price and the last 14 days. These are estimates, not your bill. Choose today,
  the last seven days or all time.
- **Analysis ›** opens a report: savings per conversation and per kind of work, a ranked table, how
  requests were handled, how much each compression removed, context lengths and 30 days of savings.
- **All records ›** opens the context library: your conversations under their original names, each
  saved context with copy, export, rename and delete, and import of a package from another computer.
- **Right-click the cat** for the menu. To quit, hover over the cat and click the **×** on its head,
  or choose **Quit TOMC**. Closing other windows never quits the cat; it restarts at sign-in.
- **Weekly report** (menu, dashboard or analysis page) draws the last 7 days as an image you can
  copy or save. It is made on your computer and never uploaded; see [Weekly report card](share_card.md).

The cat grows through four stages as your estimated total saving passes about 100K, 1M and 10M
tokens, and a stage once reached is kept. A short bubble says when it grows. The length of each
context only changes how much paper flies in that one animation.

## What to expect

Savings appear only for requests TOMC actually shortens. Codex and Claude Code manage much of their
context themselves, short histories already fit, and some content formats are not supported yet;
those requests pass through unchanged, and the analysis report shows how many of each there were.
Long working sessions benefit most. Amounts are the tokens removed, valued at each model's listed
input price.

## Your data and privacy

- Statistics, saved contexts and settings stay in `%USERPROFILE%\.tomc\memory.sqlite3`
  (`~/.tomc` on macOS), an owner-only file. Turn off context recording, or TOMC for one
  conversation, in **All records › Settings and connections**. The first start shows a one-time
  privacy notice.
- The gateway listens on `127.0.0.1` only. Full request bodies and sign-in headers are forwarded in
  memory and never written to disk. While **Save context records** is on (the default), it keeps the
  compressed old conversation and your latest message, with common secrets replaced by
  `[REDACTED]`, for 30 days (`tomc settings --retention-days N`). With the switch off, no
  conversation text from the gateway reaches the disk. It always records request metadata (IDs,
  model names, token counts, times).
- **Erase all records…** next to the switches deletes notebooks, saved contexts, replay data and
  request and session metadata (`tomc erase-all --yes` does the same). Numeric statistics stay.
  Details: [Security and privacy](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md).
- **Send anonymous feedback** in the analysis report shows the complete report first. It contains
  kinds of work (coding, writing, papers …) and numbers only: no conversation names, content,
  folders or IDs. It is submitted only when you confirm it on GitHub, as a public pull request
  under your account. See [feedback/README.md](https://github.com/ZipengWu365/TOMC/tree/main/feedback).

## Update and uninstall (Windows)

To update the cat, update the checkout (`git pull`) and run the installer again with `--install`.
The previous copy is kept in `%USERPROFILE%\.codex\tomc\archive`. An existing gateway is updated with
`py scripts\patch_gateway_runtime.py --runtime <gateway folder>` (preview first, then `--install`).

To uninstall:

```powershell
py scripts\install_windows_companion.py --uninstall "<receipt path>"
```

This restores the Codex and Claude Code settings it changed, stops the cat and the gateway, and
removes the shortcuts and the programs it installed. Files nobody has touched since installation go
back to their exact backup; if Codex or Claude Code edited them since, only TOMC Memory's keys are
removed and everything else stays. Running it twice is safe (`already_restored`). Your data in
`.tomc` is kept.

If the gateway stops (process killed, sign-in startup disabled), Codex and Claude Code still point
at it and their requests fail. Point them back at their providers; this works with TOMC Memory
stopped:

```powershell
py -m tomc restore-direct                                 # from an environment with TOMC installed
py scripts\install_windows_companion.py --restore-direct  # or from the checkout
```

The Start menu also has **TOMC Memory - Restore direct connection** (installed with `--gateway`).
Then quit and reopen Codex and Claude Code. Receipts are
under `%USERPROFILE%\.codex\tomc\archive\windows-install-*`.

## Chinese quickstart

桌面小猫显示 TOMC 节省了多少 token、按各模型输入价值多少钱、来自哪些对话，并按原对话名整理压缩后的上下文，可以复制接续提示词交给别的 Agent，或导出到另一台电脑。Windows 上还可以开启自动请求处理：本机网关在请求发出前压缩 Codex 和 Claude Code 中符合条件的旧历史。macOS 暂不支持自动请求处理。

Windows 安装（需要 Python 3.10+ 和本仓库）：

```powershell
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
py scripts\install_windows_companion.py                      # 只预览，不做任何修改
py scripts\install_windows_companion.py --install            # 安装小猫
py scripts\install_windows_companion.py --install --gateway  # 小猫 + 自动请求处理
```

开启自动请求处理后，退出并重新打开 Codex 和 Claude Code。Codex 需要用 ChatGPT 登录（暂不支持 API key 方式）；`--hosts claude` 只接入 Claude Code。安装会打印回执路径，卸载时用：

```powershell
py scripts\install_windows_companion.py --uninstall "<回执路径>"
```

卸载会恢复它改过的 Codex / Claude Code 设置、移除快捷方式和安装的程序，保留 `.tomc` 里的数据。没被改过的文件恢复成安装前的备份；如果 Codex 或 Claude Code 之后改过这些文件，只删掉 TOMC Memory 加的那几项，其他内容不动。重复卸载也没问题。

网关停了（进程被关、开机启动被禁用）时，Codex 和 Claude Code 还指向它，请求会失败。用下面任一方式恢复直连，TOMC Memory 没运行也能用：开始菜单里的 **TOMC Memory - Restore direct connection**，或运行 `py scripts\install_windows_companion.py --restore-direct`，或 `py -m tomc restore-direct`。然后退出并重新打开 Codex 和 Claude Code。

开启网关且「保存上下文记录」打开（默认）时，网关会把压缩后的旧对话和你最新的一句话存到本机，常见密钥先替换成 `[REDACTED]`，30 天后删除；关掉这个开关后，网关不再把对话文字写入磁盘。「清空全部记录…」按钮或 `tomc erase-all --yes` 会删除全部保存的记录。macOS 安装见 [macOS 说明](macos_usage.md#desktop-companion-beta-macos)。

使用：猫头下面常驻今天估算少发了多少（比如「今日 −82K」，没省到就不显示）；点小猫看估算减少的 token 和「按标价估算 ≈」的金额（不是账单）；右键或看板里的「本周战报」把最近 7 天画成一张图，可以复制或存成 PNG，不上传，见[本周战报](share_card_zh.md)；「分析报告 ›」看各对话和工作类型的节省；「全部记录 ›」管理上下文。退出请把鼠标移到小猫上，点猫头上的 ×，或右键选「退出 TOMC」；关闭其他窗口不会退出小猫。数据都保存在本机；「匿名提交反馈」只提交工作类型和数字，提交前会先给你看完整内容。

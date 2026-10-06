# TOMC on macOS

[中文速查](#chinese-quickstart) · [Assistant installation](assistant_plugin.md) · [Dated validation](validation.md)

On **2026-10-02**, the downloaded `v0.1.0-assistant-preview.2` installed and enabled as a native Codex plugin on **macOS 26.3 (25D125), Apple Silicon arm64, Codex CLI 0.159.2**. A real model called `prepare_context` and correctly answered `framework = FastAPI`, `backup_framework = Flask`. The local browser demo also prepared the correct result for a manually entered Chinese task. See the [original test report](validation/macos-20261002-preview2.json) and [demo screenshot](assets/macos_demo_20261002.jpg).

Installation worked after preparing the prerequisites. This Mac initially had no UV on PATH and Python 3.9.6; TOMC requires Python 3.10 or later. The trial used UV 0.12.22 and Python 3.12.14; the Claude bundle's separate managed runtime used Python 3.13.16. These are recorded versions, rather than requirements to install these exact releases. Codex, Claude Desktop and Cursor **GUI installation was not tested**. Claude Code on macOS has not been tested. Claude's extracted `.mcpb` passed stdio runtime checks, which do not validate its desktop installation flow.

## Install the Codex ZIP

1. Install [UV using its official instructions](https://docs.astral.sh/uv/getting-started/installation/), and use a Codex CLI with plugin support. Check the available executables:

```bash
uv --version
codex --version
codex plugin --help
```

2. Download the ZIP and its checksum from the [assistant preview release](https://github.com/ZipengWu365/TOMC/releases), then extract to a directory you will keep. On macOS, check the downloaded bytes before extracting:

```bash
shasum -a 256 -c tomc-memory-codex-0.1.0.zip.sha256
unzip tomc-memory-codex-0.1.0.zip -d tomc-codex
cd tomc-codex
```

3. Check prerequisites, then install. A separate trial database keeps test notes apart from existing notebooks:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py \
  --store "$HOME/.tomc/macos-trial.sqlite3"
```

`--check` validates package files, executable paths and Codex plugin support without writing configuration or registering anything. UV itself may download Python for this command. Regular installation registers the local marketplace and plugin. TOMC's first startup needs network access for compatible Python and locked dependencies. Start a new Codex session after installing.

If UV or Codex is outside PATH, replace the placeholders with the actual executables on your computer:

```bash
"/absolute/path/to/uv" run --no-project --python 3.12 install.py --check \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"
"/absolute/path/to/uv" run --no-project --python 3.12 install.py \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex" \
  --store "$HOME/.tomc/macos-trial.sqlite3"
```

This also works with a desktop-bundled Codex CLI that your terminal cannot find as `codex`. Keep quotes around paths containing spaces or Chinese characters. The installer writes absolute runtime paths; keep the extracted directory and UV executable available, and rerun installation after moving them. `--configure-only` writes the local launch configuration and prints registration commands; it does not install the plugin.

The installer itself also runs under this Mac's system Python 3.9.6. If UV is installed but not on PATH, you can bootstrap with `python3 install.py --check --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"`. UV then provides TOMC's compatible runtime; system Python 3.9 is not used to run TOMC. The updated ZIP passed this system-Python preflight without modifying its existing `mcp.json`; remove `--check` when ready to install.

## Run the demo without installing a plugin

From the repository checkout:

```bash
uv run --python 3.12 --extra demo python -m demo.app
```

Open **http://127.0.0.1:7860**, choose **Use now**, then click **Try demo**. For the tested Chinese task, enter `当前 framework 和 backup_framework 的值是什么？` and click **Prepare**. Inspect the source links: `framework` should be FastAPI, while `backup_framework` keeps the Flask value copied earlier. The default demo prepares text locally without a reader API call. It does not create cross-chat notebooks.

## Use the result effectively

- **Replace the history for the next API request.** In a Python integration, send `prepared.messages` to your existing client in place of the original history, keeping required application instructions. Appending both adds input. A plugin tool call inside an existing chat does not clear that host's messages or automatically intercept requests; use the result in a new chat when working manually.
- **Give TOMC the next task.** Preparation selects evidence for that question. Inspect the returned source links and keep the original history available for omitted details. A small history can remain intact, and extra record labels can add overhead.
- **Use explicit syntax for structured state.** The reference parser supports forms such as `framework = Flask` and `backup_framework copies framework`. The copy is a snapshot, so a later `framework = FastAPI` leaves the backup as Flask. Implicit updates and paraphrases can miss this parser; ordinary prose may use retrieval and retained source text.
- **Measure the request you send.** The budget covers memory under a lexical estimate. Task text, tools and provider framing add input. Token counts from a lexical estimate and a model tokenizer are different measurements; the same saving percentage does not apply to every task or model.
- **Save notes only when persistence is needed.** `prepare_context` does not save history. `remember_memory` appends supplied original text to a local notebook; `recall_memory` prepares that text for a task without rewriting the stored source. The other tools are `list_memories` and `forget_memory`. The plugin sees content supplied to these tools rather than capturing all chats. Notes are stored as local plaintext and enter the host's context when recalled.

The measured example used the same instruction and English task on both sides:

| Counter and input | Before | After | Scope |
|---|---:|---:|---|
| `tiktoken:cl100k_base`, English task | 147 | 108 | Message text, a **26.53%** reduction |
| Demo lexical estimate, English task | 138 | 90 | Message-text estimate |
| Demo lexical estimate, Chinese task | 140 | 92 | Message-text estimate with the translated task |

These counts exclude provider chat framing, tool schemas and hidden tokens. The BPE check made no model request and does not measure billed usage. From the checkout, reproduce its counting with:

```bash
uv run --python 3.12 --extra tokenizers python examples/api_context.py \
  --tokenizer tiktoken:cl100k_base
```

For API integration details and complete-input measurement, see the [API guide](api_reference.md#prepare-context-before-your-api-call).

## Uninstall after a trial

Use the same Codex executable used for installation; replace `codex` with its quoted absolute path if needed:

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

Stop the demo and TOMC sessions. You can then delete the extracted trial package and, if no longer needed, the isolated database you selected with `--store`. The default `~/.tomc/memory.sqlite3` **persists after uninstall**; preserve existing notebooks or delete a specific notebook with `forget_memory` before uninstalling. The macOS trial removed the plugin, marketplace, temporary runtimes, packages, databases and new test caches, and checked that Codex configuration matched its prior state. It did not create the default notebook database.

## Chinese quickstart

**安装成功，但这台 Mac 需要先补齐运行环境。** 2026-10-02 实测的是 preview.2、macOS 26.3 / arm64 和 Codex CLI 0.159.2：通过 ZIP 内安装助手安装并启用原生插件，模型实际调用 `prepare_context` 并正确回答 FastAPI 当前值与 Flask 复制快照。五个 MCP 工具、中文笔记保存、重启后取回、独立记忆本与删除均通过；本地浏览器手动输入中文任务并点击 **Prepare** 也通过。126 项测试及 Ruff 检查通过。Codex、Claude Desktop、Cursor 的 **GUI 安装仍未验收**，Claude Code 在 macOS 上也尚未测试。[原始实测记录](validation/macos-20261002-preview2.json) · [Demo 截图](assets/macos_demo_20261002.jpg)。

系统原先没有 UV，Python 为 3.9.6；TOMC 需要 Python 3.10 或更新版本。按 [UV 官方说明](https://docs.astral.sh/uv/getting-started/installation/)安装，在解压目录执行上面的 `--check` 检查，再执行安装命令。`--python 3.12` 让 UV 提供兼容 Python；首次安装需要联网。UV/Codex 不在 PATH 中时，通过 `--uv` 和 `--codex` 指定实际路径，启动命令也使用 UV 的绝对路径。带空格或中文的路径加引号；保留解压目录，移动后重新运行安装助手。

安装助手本身可由这台 Mac 的系统 Python 3.9.6 启动：`python3 install.py --check --uv "/实际路径/uv" --codex "/实际路径/codex"`。UV 会为 TOMC 准备兼容运行环境，无需为了启动安装助手先替换系统 Python。新 ZIP 已通过系统 Python 启动的预检查，确认不会改写 `mcp.json`；正式安装时去掉 `--check`。

使用技巧：

- 应用中用 `prepared.messages` **替换原历史**，保留必要的应用指令；追加在原历史后面会增加输入。在长聊天中调用工具不会清除旧消息，手动使用时可把准备后的结果交给新聊天。
- 给出具体的下一步任务，并检查来源链接。结构化状态使用 `key = value`、`B copies A` 等支持的形式；普通文本可能使用检索。短历史可能不缩短，记录标签也可能增加输入。
- 英文例子按 `cl100k_base` 得到 **147 → 108 token，减少 26.53%**；Demo 词法估计是英文 138 → 90、中文任务 140 → 92。它们都是消息文本计数，不含供应商封装、工具 schema 或隐藏 token，也不是账单用量或固定节省率。上面的 `--tokenizer tiktoken:cl100k_base` 命令可复现 BPE 计数。
- `prepare_context` 不保存历史。需要跨聊天时才用 `remember_memory` 保存原文，再用 `recall_memory` 按任务取回；取回不会改写原文。用 `--store` 为试用选择独立数据库，避免混入已有记忆本。
- 试用结束，先执行上面的 `codex plugin remove` 与 `codex plugin marketplace remove` 两条命令。停止会话后可删除解压目录，以及确认不再需要的独立测试数据库。默认 `~/.tomc/memory.sqlite3` 在卸载后保留，不要为了卸载而删除已有笔记。

更完整的步骤见[中文安装指南](assistant_plugin_zh.md)。

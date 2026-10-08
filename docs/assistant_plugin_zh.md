# 把 TOMC 装进常用助手

[English guide](assistant_plugin.md)

TOMC 按任务准备上下文，让你用结果替换较长的历史。传入历史、下一步任务和记忆预算后，它选择原文，对支持的状态、关系或计数操作计算记录，输出文本，交给原来的助手。准备过程在 CPU 上运行，无需训练；插件本身不需要额外的大模型 API key、GPU 或模型服务。

安装后调用 `prepare_context`，检查结果，再用于新聊天或应用请求。短历史可以保持原样；记录与提示开销有时会增加输入。编译器本身不保存历史，记忆本是可选功能。直接接入请求可参考 [Python API](api_reference.md#prepare-context-before-your-api-call)。

## 选择安装方式

| 客户端 | 安装方式 | 当前范围 |
|---|---|---|
| Claude Desktop | 安装 `.mcpb` 文件 | UV 安装候选包，桌面界面仍待实测 |
| Claude Code | 用 `claude mcp add` 注册解压后的 `.mcpb` 运行环境 | 已在 VS Code 扩展中用新会话测试；面板内的交互使用尚未测试 |
| Cursor | 生成 Add to Cursor 链接 | 需要先安装 TOMC MCP 环境，链接负责注册 |
| Codex | 运行 ZIP 内的安装助手 | preview.4 已通过 Windows 个人配置中的原生安装与默认模型调用；此前 macOS 试用使用 preview.2 |

从[插件预览 Release](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.5)下载：[Claude `.mcpb`](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-0.1.0.mcpb)（[校验文件](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-0.1.0.mcpb.sha256)）、[Codex ZIP](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-codex-0.1.0.zip)（[校验文件](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-codex-0.1.0.zip.sha256)）。

尚未发布到 PyPI 或公开插件市场。新版本需要手动重新安装。[Claude 官方安装与私下分发说明](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

## Linux/macOS 的手动 MCP 环境

Cursor、Codex IDE 或独立 MCP 接入需要本地 Python 环境。克隆仓库后，推荐用 [`uv`](https://docs.astral.sh/uv/getting-started/installation/) 创建带 pip 的 Python 3.12 环境：

```bash
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python -m pip install -e '.[mcp]'
```

UV 首次使用可能需要联网下载 Python 和依赖。Codex 原生插件 ZIP 的用户直接运行下文的 `install.py`，无需另建这份手动环境。Windows PowerShell 步骤继续见[接入指南](assistant_setup.md)。

如果使用系统 Python，可将创建命令换成 `python3 -m venv .venv`。Ubuntu/Debian 的系统 Python 需要匹配的 venv/ensurepip 组件；默认 Python 可先用 `sudo apt install python3-venv` 安装。本轮 Ubuntu 的系统 Python 缺少 `ensurepip`，若先前因此只生成了部分环境，可运行：

```bash
uv venv --python 3.12 --allow-existing --seed .venv
source .venv/bin/activate
python -m pip install -e '.[mcp]'
```

要同时使用本地 Demo，可改装 `python -m pip install -e '.[demo,mcp]'`，再运行 `python -m demo.app`，打开 `http://127.0.0.1:7860`。本轮 Demo 验证环境为 **Ubuntu 24.04.5、Python 3.12.13、Gradio 5.49.1**；macOS 安装未在这轮重测。[Linux 验证与安装反馈](linux_validation.md)。

## Claude Desktop

本地构建的安装候选包位于 `outputs/plugins/tomc-memory-0.1.0.mcpb`。它带有 TOMC 源码，采用官方 MCPB UV runtime，由支持该运行方式的客户端管理 Python 和依赖，创建独立环境。首次安装需要联网下载，并非离线安装包；用户不必先手动安装 Python。[官方 UV 安装包示例](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv)

维护者可以在仓库中构建和检查：

```bash
python scripts/build_plugin.py
python scripts/plugin_smoke.py outputs/plugins/tomc-memory-0.1.0.mcpb
```

第二条命令需要 `uv` 和 MCP 测试客户端（`.[mcp]`）。它在仓库外解压安装包并启动锁定的运行环境，不会安装到助手中，也不会更改助手配置。分享时提供 `.mcpb` 文件及其 `.sha256` 校验文件；不要把自己电脑生成的 Cursor 路径链接当成可移植安装包。

1. 更新 Claude Desktop，取得 `.mcpb` 文件。
2. 进入 **Settings → Extensions → Advanced settings → Install Extension…**。
3. 选择文件，查看说明并按提示确认安装。
4. 开启对话，检查下列五个 TOMC 工具是否可用。

这是[官方支持的自定义安装路径](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)。完成打包和 MCP 协议检查，并不等于已通过所有桌面环境验收；macOS、Windows 上的实际 Claude Desktop 安装仍需验证。

## Claude Code

Claude Code 不能直接安装 `.mcpb` 文件，但可以把包里同一套锁定环境作为本地 stdio MCP 服务启动。

1. 下载 `tomc-memory-0.1.0.mcpb`，核对 SHA-256，再解压（它是 ZIP 格式）到一个会长期保留的目录。
2. 安装 [UV](https://docs.astral.sh/uv/getting-started/installation/)，确保 `uv` 在 PATH 中，再运行下文的命令。将示例路径替换为实际解压目录；路径包含空格时保留引号。
3. 运行 `uv sync --locked --directory "/absolute/path/to/extracted"`，安装锁定的依赖。
4. 注册服务，在所有项目中可用：

   ```bash
   claude mcp add tomc-memory --scope user -- uv run --locked --directory "/absolute/path/to/extracted" src/server.py
   ```

   如果想把笔记本放在单独的数据库里，在 `--` 前加上 `-e TOMC_MEMORY_PATH="/absolute/path/to/memory.sqlite3"`。`claude mcp get tomc-memory` 应显示 **Connected**。
5. 新开一个 Claude Code 会话，或重新加载 VS Code 窗口，再输入 `/mcp`。每个工具第一次使用时，Claude Code 会请求权限。

用 `claude mcp remove tomc-memory --scope user` 可以删除。请保留解压目录；移动目录后需要重新注册。

### VS Code 扩展注意事项

以下内容适用于所有操作系统，只是文件路径不同。

- VS Code 里的 Claude Code 面板和 `claude` 命令是同一个 Claude Code，用 `--scope user` 注册的服务在面板里同样可用。注册后重新加载 VS Code 窗口，或新开一个会话即可。
- 如果 `claude` 不在 PATH 中，扩展自带的 CLI 位于 `~/.vscode/extensions/anthropic.claude-code-<版本>-<平台>/resources/native-binary/`。在 Windows 上是 `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<版本>-win32-x64\resources\native-binary\claude.exe`。用完整路径调用即可。
- 虚拟环境里的可执行文件，在 Windows 上位于 `.venv/Scripts/`，在 macOS 和 Linux 上位于 `.venv/bin/`。
- 如果当前激活了 conda 或其他虚拟环境，uv 会提示 `VIRTUAL_ENV ... will be ignored`。这不影响使用：`--directory` 会选用包自己的环境。
- 会话进行中新加的服务，要到下一个会话才能用。

### 使用技巧

- **请求里要点名工具。** 如果历史已经在对话里，Claude 会直接回答：工具调用无法缩减宿主已经持有的上下文。可以明确写：*"用 tomc-memory 的 prepare_context 处理这段历史，task 是……，budget 设为 200，然后根据返回的 memory 回答。"*
- **适合跨会话使用，或在 API 调用前使用。** 用 `remember_memory` 保存长历史，之后在新会话里用 `recall_memory` 加上任务和预算取回；也可以在下一次 API 请求中改发准备好的上下文，代替完整历史。
- **预算要小于历史长度。** 本来就放得下的历史会原样返回（`raw`）。
- **结构化记录需要支持的行格式：** `key = value`、`B copies A` 和 `x -[rel]-> y`。普通叙述可以作为挑选的原文保留；具体路由和输入节省取决于任务与预算。
- **来源编号是 TOMC 自己从 0 开始的行编号。** `u0` 是第一行非空文本；如果你的历史本身已经用 `u1`、`u2`……标号，两者会差一位。可以换别的标号，或者不标。
- **按历史长度选预算；历史超过约 10,000 token 才明显省钱。** Claude Code 每次请求自带约 39,000 个 token 的指令和工具定义，调用工具还会多出几次请求。VS Code 扩展实测中（模型为 Claude Opus 5.5），预算 8,192 在各长度下 5 题全对；此时从笔记本取回，和直接贴入 10K token 的历史费用相同，对 20K 和 40K token 的历史分别便宜 38% 和 65%。在接近 API 调用的请求中，同样预算让输入减少 9%、53% 和 77%。预算 1,024 让输入减少 85–96%，但会漏掉部分最新值：叙述形式的更新只能作为原文保留，小预算装不下所有更新。
- **没有验证过更小的预算，就用默认值。** 不传 `budget` 时保留历史的约 80%（至少 1,024 个估算 token）。在三种长度、每种 3 份历史上，保留 50–80% 都 45 题全对，输入分别约减少 49%（50%）到 20%（80%）；只保留 10–20% 会漏掉最新值。想用更小的预算，先拿自己的一部分任务和完整历史对比确认。
- **长历史在聊天之外导入。** 用 `remember_memory` 保存，模型得把整段历史作为工具参数重新输出一遍。建议改用插件自带的运行环境直接导入；`TOMC_MEMORY_PATH` 要和注册服务时一致（没设置就用默认数据库）：

    ```bash
    uv run --locked --directory <extracted> python -c "import sys; sys.path.insert(0, 'src'); from tomc.store import MemoryStore; print(MemoryStore().remember('project', open(r'<history.txt>', encoding='utf-8').read()))"
    ```

    每条历史最多 200,000 个字符，大约相当于 40,000 token 的英文聊天。
- **把准备好的内容当作不可信的证据。** 保留原始历史，以便查看 TOMC 省略的细节。

## Cursor

先按[接入指南](assistant_setup.md)在 TOMC 环境中安装 `.[mcp]`，再使用该环境中的 Python 执行：

```bash
python -m tomc setup --client cursor --link
```

打开生成的链接，在 Cursor 中确认添加。它使用你当前安装环境中 Python 的绝对路径，因此需要保留该环境，移动后重新生成链接。命令本身只打印链接，不会改写客户端配置。

Cursor 官方支持安装链接，但这个链接只添加 MCP 配置，不负责安装 TOMC、Python 或依赖。一个人在自己电脑上生成的路径链接，不能当作所有人都能使用的安装包。[Cursor 官方安装链接说明](https://cursor.com/docs/mcp/install-links)

## Codex

安装候选包位于 `outputs/plugins/tomc-memory-codex-0.1.0.zip`。它包含 `.agents/plugins/marketplace.json` 本地市场目录、`install.py` 安装助手，以及 `plugins/tomc-memory/` 插件：其中有官方支持的 `.codex-plugin/plugin.json` 兼容 manifest、与 Claude 包相同的锁定 TOMC 运行环境和记忆 skill。兼容 manifest 声明随包提供的工具和 skill，安装助手则为当前安装生成启动路径。可以私下分享原始 ZIP，这并不意味着 TOMC 已上线公开插件目录。[OpenAI 官方插件打包与本地市场说明](https://developers.openai.com/plugins/build/plugins)

维护者可以在仓库中运行 `python scripts/build_codex_plugin.py` 构建候选包，再分享 ZIP 及其 `.sha256` 校验文件。

使用支持插件的新版本 Codex CLI，并按[官方说明安装 UV](https://docs.astral.sh/uv/getting-started/installation/)。与 Claude Desktop 自动管理 UV 扩展不同，这个包需要已有的 UV 可执行文件。TOMC 需要 Python 3.10 或更新版本，macOS 的系统 Python 可能过旧。无需单独安装兼容 Python：下面的命令让 UV 提供 Python 3.12 和依赖，因此首次启动需要联网。

1. 将 ZIP 解压到准备长期保留的目录。
2. 在包含 `install.py` 的解压目录中打开终端，执行：

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

3. 新开 Codex 会话，检查 TOMC 工具是否可用。

`--check` 检查包文件、可执行文件路径和 Codex 插件支持，不写入配置或注册插件。可执行文件不在 PATH 中时，把占位路径替换为这台电脑的实际路径：

```bash
"/absolute/path/to/uv" run --no-project --python 3.12 install.py \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"
```

安装助手会解析这台电脑上 UV 和运行环境的绝对路径，更新解压目录中的候选包启动配置，再调用官方 Codex 市场注册和插件安装命令。它不会整份覆盖已有的 Codex 配置。生成的路径属于当前安装，移动解压目录后需要重新运行助手。分享时请使用原始 ZIP，不要分享包含自己电脑路径的已配置副本。

需要独立记忆本时，在安装命令后加 `--store /path/to/notebooks.sqlite3`，为 Codex 的 MCP 进程显式设置数据库路径；默认仍为 `~/.tomc/memory.sqlite3`。

### Windows：先检查目标 Codex

在 PowerShell 中查看终端实际选择的程序：

```powershell
Get-Command codex | Select-Object Source
codex --version
Get-Command uv | Select-Object Source
uv --version
```

PATH 中的 CLI 可能与桌面应用内置引擎不同。安装助手默认选择 PATH 中的 CLI；需要指定其他程序时，用 `--codex`，并将下面占位路径换成真实路径：

```powershell
uv run --no-project install.py --codex 'C:\path\to\codex.exe'
```

目标 host 应同时支持插件命令和你的模型账户。安装成功提示说明完成了注册，不代表模型请求一定成功。新开会话后，先检查五个 TOMC 工具，再运行[准备例子](#prepare-context)。明确要求调用 `prepare_context`，并查看实际工具结果。[Windows 反馈](windows_installation_feedback_zh.md)分别记录安装、运行和真实模型试用。

若只希望生成本地启动配置、打印后续安装命令，而不注册市场或安装插件，可以执行：

```bash
uv run --no-project --python 3.12 install.py --configure-only
```

市场注册后，也可以在支持的 Codex CLI 中输入 `/plugins`，浏览该市场并安装 TOMC。[官方插件命令](https://learn.chatgpt.com/docs/developer-commands)、[插件浏览器](https://developers.openai.com/codex/plugins)

Codex IDE 扩展目前不支持原生插件。IDE 用户或没有插件命令的旧版 CLI 用户，可以按[接入指南](assistant_setup.md)安装 `.[mcp]`，再用该环境中的 Python 生成配置：

```bash
python -m tomc setup --client codex
```

将打印出的条目加入 MCP 设置。也可以使用 CLI 直接注册已安装的 Python，将占位路径替换为实际路径：

```bash
codex mcp add tomc -- /absolute/path/to/installed/python -m tomc mcp
```

Codex CLI 和 IDE 均支持直接 MCP 接入。同一客户端中，原生插件与单独注册的 TOMC 服务二选一，避免工具重复。[官方 MCP 接入说明](https://developers.openai.com/codex/mcp)

2026-10-04，已发布 preview.4 ZIP 通过桌面内置 CLI 0.160.0，作为原生插件长期安装到这台 Windows 的 Codex 个人配置中。原有 `gpt-6.1-sol` 模型、OpenAI provider 和登录完成两次模型回合、四次 TOMC 调用：第一段聊天准备、保存并取回；独立新聊天只收到记忆本名称和任务，也取回成功。准备和取回都没有传入预算参数，使用新默认值；两段回答均给出正确的当前值 FastAPI 与复制快照 Flask。没有配置、feature、MCP server 或工具 namespace 覆盖设置，其他插件保持启用。安装目录长期保留在 `~/.codex/tomc/assistant-preview.4`，UV 位于 `~/.codex/tomc/tools/Scripts/uv.exe`。

合成记忆本实际保存到默认 `~/.tomc/memory.sqlite3`，完整 host 重启后仍可取回，随后被精确删除。保存前和删除后的 host 列表均为空，独立只读 SQLite 检查确认最终零条目。正常存取使数据库元数据发生变化；安装后的配置和认证元数据保持不变。桌面 GUI 安装按钮仍未逐步点击验收。具体条件及证据见 [Windows 反馈](windows_installation_feedback_zh.md)与 [preview.4 验证记录](validation.md#windows-codex-preview4)。移除插件不会删除已有记忆本。

历史 2026-10-02 的检查范围更窄：preview.2 和 preview.3 在 Windows CLI 0.146.0、0.159.2 的隔离配置中通过完整安装及实际 host 工具检查，没有模型调用；preview.1 的模型准备及新聊天取回使用临时 MCP 设置与直接开放工具。这些条件按原日期保留，不代表上文的 preview.4 安装。Claude Desktop 与 Cursor 仍只有运行检查。

本轮 Linux 使用 **Codex CLI 0.159.0-alpha.12.1** 对 preview.2 验证了原生插件安装及 MCP 工具，并检查 `.mcpb` 的后端运行。检查仅使用临时配置和记忆库，没有调用模型；Claude/Cursor GUI 安装、个人配置中的永久安装以及模型自动使用工具仍未验证。此前 Windows 的模型调用结果与本轮 Linux 协议检查分别报告，不互相替代。[Linux 验证记录](linux_validation.md)。

2026-10-02 下载的 preview.2 ZIP 在 macOS 26.3 arm64、Codex CLI 0.159.2 上作为原生插件安装并启用。模型实际调用其 `prepare_context` 工具，正确回答当前值 FastAPI 与此前复制的 Flask 快照。已安装的客户端提供全部五个工具；独立数据库上的中文笔记经进程重启仍可取回，也能删除。这台 Mac 原先没有 UV，系统 Python 为 3.9.6，因此需要先准备兼容运行环境。Codex、Claude Desktop、Cursor 的 GUI 安装仍未验收。[macOS 安装与使用技巧](macos_usage.md#chinese-quickstart) · [验证记录](validation.md)。

历史 Windows preview.1 排查中，npm Codex CLI 0.146.0 可以安装插件，但原默认模型请求返回 HTTP 400；桌面内置 CLI 0.159.2 则支持相同模型和登录。应指定预期可执行文件，不要假设 PATH 中的 CLI 就是桌面引擎。

### 试用后移除原生插件

使用安装时同一个 Codex 可执行文件：

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

停止 TOMC 会话后可删除试用解压目录。若使用 `--store`，确认笔记不再需要后，可选择删除该独立测试数据库。卸载保留默认 `~/.tomc/memory.sqlite3`；不要仅为卸载插件而删除已有记忆本。如需删除某个记忆本，可先调用 `forget_memory` 再卸载。

<a id="prepare-context"></a>

## 准备上下文

日常使用可以参考[使用技巧](usage_tips_zh.md)：具体任务、更新顺序、原文核对和 notebook 提示词。

安装后，让助手调用 TOMC 的 `prepare_context` 工具：把下面的文本传给 `history`，将 `task` 设为 `"当前 framework 和 backup_framework 的值是什么？"`，`budget` 设为 `64`，再让助手根据返回的记忆回答。

```text
framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available.
```

这个例子使用显式赋值和复制。TOMC 准备 `framework = FastAPI`、`backup_framework = Flask` 两条记录，并保留来源链接。是否调用工具由客户端控制，回答由原来的模型生成。

`prepare_context` 不保存这段历史。已能放进预算的历史保持完整；较长的普通文本可以使用检索，不一定产生结构化记录。`budget` 按词法计数器限制记忆文本，任务和工具消息框架还会增加输入。

上面的 64-token 预算是明确指定的小例子。使用当前默认值时，省略 `budget`：TOMC 按历史 lexical 估算长度的约 80% 选择预算，最低为 1,024；本来就放得下的历史原样保留。这不是固定节省比例。

### 在下一次调用中使用更少的上下文

应用请求使用 `prepared.messages` 替换原历史；助手中可以把准备后的文本交给新聊天。在已有长聊天里调用 TOMC，不会清除客户端保存的原消息，因此一次工具调用本身并不代表节省了 token。插件不会全局拦截 API 请求。衡量节省量时，用模型的 tokenizer 检查完整输入；保留原历史，以便查看结果未包含的细节。

先核对选中的原文、来源链接和计算出的状态，再交给模型。Demo 的 **Small request** 面向短记录示例；普通段落可在 **Memory size** 中选择 **Balanced** 或 **More detail**，并展开 **How this context was prepared** 查看结果。预算太小可能放不下完整原文行，不能把空上下文当作成功压缩。

## 工具

| 工具 | 用途 |
|---|---|
| `prepare_context` | 临时处理传入的历史，不保存 |
| `remember_memory` | 将传入的笔记追加到指定记忆本 |
| `recall_memory` | 为当前任务取回指定记忆本 |
| `list_memories` | 查看记忆本名称，不返回内容 |
| `forget_memory` | 按要求删除指定记忆本 |

<details markdown="1">
<summary>可选：跨聊天保存与取回历史</summary>

记忆本保存传入的原始文本；`recall_memory` 在取回时按任务准备上下文。`prepare_context` 直接处理提供的历史，不保存它。

## 用两次对话试一下

第一段对话：

> 请用 TOMC 把这些笔记保存到 workshop：研讨会人数现为 28 人，B 会议室有空但尚未预订，还需确认无障碍设施。

新开一段对话：

> 从 TOMC 取回 workshop，告诉我接下来需要确认什么。

助手决定是否调用工具，并遵循客户端的权限设置；保存笔记不会替你预订会议室，也不会把待确认事项变成已完成。

## 存储与能力范围

要从 Codex 切到 Claude Code 继续，或反过来，让两边的 TOMC 服务使用同一数据库，并传入同一记忆本名称。[共享路径设置与两段接续提示词](usage_tips_zh.md#reuse-notebooks)。

默认记忆存放在用户目录的 `~/.tomc/memory.sqlite3`，不放在安装包中。同一台电脑上使用同一数据库的客户端可以共享记忆；不同路径则相互独立。笔记以本地明文存储，取回后进入助手上下文，遵循助手平台的数据政策；卸载插件不会自动删除数据库。

插件只看到传给工具的内容，不会自动读取全部聊天、拦截 API 请求或替换客户端的上下文窗口。这个日常使用接口采用 Demo 的任务路由和本地记忆本，并非论文 BEAM 实验的精确配置；论文分数不能直接当作此插件流程的效果保证。

</details>

# Windows 安装反馈

[English](windows_installation_feedback.md) · [安装指南](assistant_plugin_zh.md) · [使用技巧](usage_tips_zh.md)

2026-10-04，preview.4 已作为原生插件长期安装到这台 Windows 的 Codex 个人配置中。原有默认模型实际调用工具成功，独立新聊天也能取回记忆。桌面 GUI 安装按钮仍未逐步点击验收。2026-10-02 的包与客户端检查在下文保留，各自的日期和范围不变。

## 当前 Windows Codex 安装：preview.4

原始已发布 ZIP 为 91,034 字节，校验、前置检查及完整安装均成功。SHA-256 是 `96b05b516efadba2e6e7f691a8869365233aad5088e7a484d0c0e63b60a013b0`。安装目录长期保留在 `~/.codex/tomc/assistant-preview.4`；UV 0.12.22 位于固定 Windows 路径 `~/.codex/tomc/tools/Scripts/uv.exe`。已安装运行代码及 skill 与 ZIP 核对一致，这次安装不依赖旧试用目录。

实际使用桌面内置 Codex CLI 0.160.0，保留原有 `gpt-6.1-sol` 模型、OpenAI provider 和登录。模型试用没有采用配置、feature、MCP server 或工具 namespace 覆盖设置，也没有禁用其他插件。

| 检查 | 结果 |
|---|---|
| 第一段模型聊天 | 不传预算调用 `prepare_context`，用 `remember_memory` 保存完全相同的合成历史，再不传预算调用 `recall_memory` |
| 独立新模型聊天 | 只收到记忆本名称和任务，没有原历史或预期值；调用 `recall_memory` 成功 |
| 回答 | 两段聊天均给出 `framework = FastAPI`、`backup_framework = Flask` |
| 默认预算分支 | 实际 host 调用测得输入 1,534 个 lexical 估算 token，自动选择预算 1,228，返回 1,223 个 memory token |

两次模型回合共调用 TOMC 四次。默认预算为 `max(1024, ceil(input_estimated_tokens × 0.8))`，不包含任务文本与工具封装。这是一个合成例子的功能验收，不是 API 账单节省测量，也不是通用质量保证。详见[本次验证记录](validation.md#windows-codex-preview4)及[去除个人信息的 preview.4 证据](validation_data/windows_codex_preview4_20261004.json)。

存储测试实际使用默认 `~/.tomc/memory.sqlite3`。第一次保存前没有记忆本；模型保存了一个唯一命名的合成测试记忆本，完整 host 重启后取回成功，随后精确删除了它的一条记录。最终 host 列表及独立只读 SQLite 检查均确认零条目。该数据库元数据在测试中发生变化，它不是隔离测试库。安装后的配置和认证元数据保持不变；安装本身只加入 TOMC 插件与市场，保留其他插件设置。

## 上下文预算与实际输入 — 2026-10-05

已安装的原生 MCP 工具在回答模型之外准备了九份合成历史。Windows Codex 0.160.0 随后保留原有 `gpt-6.1-sol` 模型及 `ultra` effort，在 36 个全新聊天中回答，没有改变个人配置。完整历史、40%、60% 和默认 80% 历史预算均答对 45/45 个最新状态问题。

| 发送的上下文 | 平均请求输入 token | 平均配对输入减少 |
|---|---:|---:|
| 完整历史 | 42,191 | 参照 |
| TOMC · 40% 历史预算 | 28,713 | 29.7% |
| TOMC · 60% 历史预算 | 33,344 | 19.5% |
| TOMC · 默认 80% 历史预算 | 38,035 | 9.2% |

输入是提供商返回的完整总量，包含缓存输入、宿主指令及工具定义。减少比例对九份历史各自的配对比例取平均。准备在 CPU 上完成，位于回答回合之外；在聊天中准备或取回上下文会增加模型回合。全部准备结果都选择原文，没有操作记录。这次只测试合成历史的最新状态查找，不代表通用编程质量或费用节省。[完整英文报告](codex_retention_20261005.md) · [中文报告](codex_retention_20261005_zh.md) · [实测数据](validation_data/windows_codex_retention_20261005.json)

另一次[当前聊天的工具连接检查](validation_data/windows_codex_foreground_20261005.json)也返回了正确的赋值与复制状态。它没有收集 provider usage，不属于保留比例对比。桌面图形安装流程仍未测试。

## 安装方便吗？

| 入口 | 用户需要做什么 | 实际使用门槛 |
|---|---|---|
| Codex CLI | 准备 `uv` 和支持插件命令的 Codex CLI；下载、解压 ZIP；执行 `uv run --no-project install.py`；新开会话 | 前提满足后只需一条安装命令。解压目录要保留，移动后重新运行安装助手。 |
| Claude Desktop | 下载 `.mcpb`，在客户端扩展设置中安装 | 支持该 UV 包的客户端负责 Python 和依赖；这里尚未验收 GUI 安装。 |
| Claude Code | 解压 `.mcpb`，用 `uv` 安装锁定依赖，再通过 `claude mcp add` 注册运行环境 | 已用 Windows VS Code 扩展捆绑的可执行文件测试 CLI 注册。解压目录需要保留。 |
| Cursor | 安装 TOMC 的 `.[mcp]` 环境，生成链接，再在 Cursor 中确认 | 步骤最多。链接只注册已有环境，不能作为其他电脑的便携安装包。 |
| Python 应用 | 从仓库安装包，在原模型调用前加入 `prepare_context` | 应用需要用准备后的 messages 替换原历史，并适配自己的 API 格式。 |

仓库目前是私有的，下载需要访问权限或合作者直接分享文件。首次安装依赖需要联网。TOMC 准备上下文本身无需额外模型 key 或 GPU；助手仍使用自己的模型账户。

## 哪些步骤成功了？

| 包或客户端 | 已验证结果 | 验证范围 |
|---|---|---|
| 当前 Codex preview.4，桌面内置 CLI 0.160.0，2026-10-04 | 个人配置中的长期原生安装及两次真实默认模型聊天均通过 | 四次 TOMC 调用；准备与取回使用新默认预算；独立新聊天没有历史或预期值；GUI 安装未测试 |
| 历史 Codex preview.3 已发布 ZIP，CLI 0.146.0 和桌面内置 CLI 0.159.2，2026-10-02 | 两个 host 均通过不改配置的前置检查及完整市场注册、插件安装 | 实际 host 的五工具、临时准备、中文重启存取和删除；没有模型调用 |
| Codex preview.1 ZIP，CLI 0.146.0 | 完成市场注册和插件安装，真实 host 发现五个工具 | 全新的隔离 Codex 配置；该安装测试没有模型调用 |
| Windows 桌面内置 Codex 0.159.2，preview.1 运行环境 | 真实模型准备、保存、取回成功；独立新聊天只收到记忆本名称和任务，也取回了正确内容 | 保留原模型和登录，使用临时 MCP 设置和独立合成数据库 |
| Claude Desktop preview.1 / preview.2 包 | 官方 MCPB 2.1.2 manifest 验证及解压后的锁定 stdio 运行检查成功 | 包与运行环境检查；未测试 Claude Desktop GUI 安装或模型聊天 |
| Claude Code 2.1.287，preview.2 运行环境 | 独立合并的记录报告用户级注册及新建 headless 会话的工具调用成功 | 点名准备、跨会话存取和删除；VS Code 互动面板未测试 |
| Cursor preview.1 环境 | 新安装 `.[mcp]`，生成链接所指向的实际启动配置通过检查 | 在仓库外运行；未测试 Cursor GUI 确认或模型聊天 |
| Codex preview.2 已发布 ZIP，CLI 0.146.0 和桌面内置 CLI 0.159.2 | 两个 host 均完成完整安装、市场注册和插件安装，实际 app-server 各发现五个工具 | 全新隔离配置；上下文准备、中文存取、完整 host 重启和删除成功；没有模型调用 |

运行检查覆盖五个工具、中文和 emoji、记忆本隔离、进程重启后的保存内容、重复保存重试和准确删除。直接准备上下文后，数据库仍为空。[验证记录](validation.md)保留了每次检查的日期和范围；[去除个人信息的证据摘要](validation_data/windows_installation_20261002.json)列出包校验值和原始记录来源。

preview.2 的后续检查使用原始已发布 ZIP，而非工作目录源码。SHA-256 为 `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e`，与 release 和校验文件相同。这次执行了完整安装助手，不只是先前的 configure-only。host 工具发现和直接 MCP 调用无需 namespace 覆盖设置，但未测试模型自主选用工具。运行使用了已有依赖缓存，耗时不能作为冷安装性能。首次尝试因测试脚本未创建隔离配置目录失败；修正测试脚本即可，未修改安装包。

[历史 preview.3](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.3)于 2026-10-02 另行下载，并在两个 Windows host 上重测。90,444 字节的 Codex ZIP，SHA-256 为 `8db8ac312d6dd5e8b07a28cc66f98027a852fbec5de447ba682363acc9bf9a10`，与校验文件及 release digest 相同。`--check` 未改写 `mcp.json`；显式指定 `--uv` / `--codex` 的完整安装首次即成功，并打印了插件和市场的移除命令。直接 host 工具检查无需覆盖设置，该轮没有模型调用。它的 Claude MCPB 与 preview.2 字节相同。

## Claude Code 的独立 Windows 试用

[已合并的 Claude Code 记录](validation.md#claude-code-windows-validation)报告了使用原默认模型的五个新建 headless 会话。明确点名 `prepare_context`、保存、未收到原历史的新会话取回，以及删除均成功。一次未点名 TOMC 的对照直接从完整历史回答，没有调用工具。最后的模型 `list_memories` 调用被测试 allowlist 阻止；五工具枚举来自 stdio 检查。

这份普通叙述例子选择六条相关原文，没有生成 typed records。准备估计为 2,085 → 101，记忆本取回为 2,090 → 101，均为 memory 文本的 lexical 估计，不是整个请求或计费输入。记录中的 US$0.27 / US$0.13 来自不同工作流，不能据此宣传节省费用。TOMC 源编号从 `u0` 开始，与历史原文里自带的编号不同。[Claude Code 指南](assistant_plugin_zh.md#claude-code)提供 Windows 注意事项和提示词。

该服务已在用户级配置中持久注册，仍从测试目录运行。删除或移动这个目录会使注册失效。原始模型输出未归档到仓库；这里引用已合并记录，没有声称重新独立跑过模型。VS Code 互动面板与 macOS/Linux 仍未测试。

## 历史 Codex 排查记录：2026-10-02

**PATH 中的 CLI 与桌面引擎版本不同。** npm CLI 0.146.0 可以安装插件，但两次真实模型请求被 HTTP 400 拒绝，涉及该账户的默认模型和 ChatGPT 登录。改用桌面内置 0.159.2 后，保留相同模型和登录，测试成功。因此旧 CLI 的安装成功不能等同于模型可用。

**早期最小桌面测试需要临时直接开放工具。** 未加覆盖设置的模型回合完成了，但无法使用 TOMC。preview.1 的成功试用临时设置了 `features.code_mode.direct_only_tool_namespaces=["mcp__tomc"]`。这是排查条件，未永久写入个人配置，也不是通用安装建议。2026-10-04 的 preview.4 原生安装已在没有该覆盖设置的情况下通过模型工具调用。

所有模型排查共发起七个回合请求：四个成功回合、八次 TOMC 调用，两次旧引擎拒绝，一次完成但无法访问 TOMC。上下文编译例子得到正确的 FastAPI/Flask 状态。93 → 45 是记忆文本的 lexical 估计，不是 API 账单 token 数。

## 需要修改吗？

先前包检查发现，测试 host 未加载 portable root manifest，也未向 MCP 子进程提供插件目录变量。现有兼容 manifest 和安装助手生成的绝对路径已处理这些记录中的启动问题。此次 Windows 运行检查未发现需要修改编译器或存储实现的新缺陷。

这次补充了直接使用虚拟环境 Python 的 Windows 命令，无需激活环境；说明了用 `--codex` 指定目标可执行文件的方法，并把注册、工具运行和模型试用分别解释。见[手动接入指南](assistant_setup.md)及 [Codex 安装步骤](assistant_plugin_zh.md#codex)。

**Windows demo 的资源解码问题已修复。** 在 Python 3.11.9、Windows cp936 默认编码下，复现了 Claude Code 记录中的六个失败。tour 将 UTF-8 snapshot 按 GBK 读取，两个现有测试文件也依赖默认编码读取 UTF-8 资源。三处 demo 资源读取和两个测试文件现已明确使用 UTF-8；修复当时的版本在默认编码与 UTF-8 模式下均通过全部 126 项测试。修复覆盖本地 demo 和资源检查，未改动编译内核、插件代码、资源内容或已发布包，也无需更改全局环境变量。见[修复记录](validation.md#windows-encoding-fix)。

2026-10-02 合并 Linux 与 macOS 更新后，两种 Windows 编码模式均通过 141 项测试；总共收集 142 项，其中一项 POSIX 可执行权限检查按设计在 Windows 上跳过。重新构建的本地包与历史 preview.3 的发布校验值一致。该轮验证了合并后的代码和打包，没有新增 GUI 或模型试用。

当前安装助手保留了 preview.3 加入的前置检查、显式程序路径和卸载说明。安装前可执行 `uv run --no-project --python 3.12 install.py --check`，检查包和所需命令，而不注册 TOMC。此次指定的 Windows host 已通过 preview.4 原生安装及默认模型工具调用；下一步仍需验收桌面 GUI，并减少 Cursor 的安装步骤。安装后应检查工具连接并实际调用；前置检查通过不等于模型已经能够调用工具。

历史 2026-10-02 的 Codex 检查只使用合成笔记，没有在个人配置中永久安装 TOMC；当时的个人配置及默认记忆数据库元数据保持不变。2026-10-04 的安装则有意添加了原生插件，已在上文单独记录。原始 Codex 诊断流含机器路径和 host 元数据，因此保留在本地；仓库摘要不含凭据、私人笔记或聊天标识。

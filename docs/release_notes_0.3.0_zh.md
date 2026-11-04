# TOMC Memory 0.3.0 更新说明

[English](release_notes_0.3.0.md) | **简体中文** · 2026-10-30 · 发布标签 `v0.3.0-preview.1`

0.3.0 主要解决"敢不敢用"：默认少存东西，能一键清空，更稳地交出最新值，也更容易上手试。论文用的编译核心没有改。

## 你会注意到的变化

### 隐私默认值

- **MCP 结果默认不再保存。** 0.2.0–0.2.1 里，`prepare_context` 和 `recall_memory` 每次都会把结果和任务存成本地快照。现在默认什么都不存，想存要自己打开：`tomc settings --save-mcp-results on`，同时"保存上下文记录"开关也要开着。没保存时，返回里会写 `context_record.status = "disabled"`。
- **保存的内容会遮住密钥。** API key、Bearer token、私钥、URL 里的密码、`KEY=value` 这类密钥，写入前都换成 `[REDACTED]`。
- **保存的内容会过期。** 默认 30 天后删除（`tomc settings --retention-days N`，1 到 3650）。0.2.x 存下的快照，会在下次启动 MCP 服务或网关时统一遮一次密钥，并按时间清理。
- **关掉记录就真的不写。** "保存上下文记录"关闭时，Windows 网关的 Claude 路径只在内存里保留重放数据。
- **文件只有你自己能读。** 数据库和安装器的备份都设成仅本人可读（文件 0600，文件夹 0700），删除的数据会在磁盘上覆盖掉。
- 桌面小猫第一次运行时会显示一次隐私说明。

### 删除和还原

- `forget_memory` 现在会把从这个笔记本准备出来的上下文一起删掉。
- 全部清空：MCP 工具 `erase_all_memory`（要传 `confirm="ERASE ALL"`）、`tomc erase-all --yes`，或者上下文库里的 **清空全部记录…** 按钮。
- `tomc restore-direct` 把 Codex 和 Claude Code 改回直接连接各自的服务商。TOMC Memory 没在运行也能用，只删 TOMC 自己加的设置。`scripts/install_request_gateway.py`、`scripts/install_windows_companion.py` 也有 `--restore-direct`，Windows 开始菜单里有 **TOMC Memory - Restore direct connection** 快捷方式。
- Codex 改过 `config.toml` 之后，还原和卸载不会再失败；运行两次也没问题。

### 更常拿到最新值

- 如果后面某一行可能改过某个值，这条记录会显示成 `[STATE?] key = value (later: uN)`（或 `PATH?`），后面紧跟那一行原文，方便你或模型核对。
- 能读懂更多写法：`key: value`、列表项、`Update:` 和说话人前缀、用 `;` 分开的多个赋值、全角 `＝`/`：`、中文等 Unicode 字段名。代码块、文件头、比较式和"如果你想要……可以这样写"这类假设例子会跳过。
- 问当前值和计数时，同分的行优先留后面的；预算里还专门留一小块给最新提到问题关键词或宣布改动的行。
- 特别长的一行会按句子拆开（`u12.1`、`u12.2` …），一段话不会再吃掉整个预算。
- 路由修正：account、discount、country 不再被当成计数；concurrent 不再被当成 current；能认出"现在、目前、改成"等中文状态词；"… now?" 会被当成问当前状态。
- 离线旧值测评（`python benchmarks/stale/run.py`，每种预算 144 题，不调用模型），准备好的上下文里带着最新值的题目占比：

| 预算 | 10% | 20% | 40% | 60% | 80% | 默认 |
|---|---|---|---|---|---|---|
| v0.2.1 | 51% | 51% | 51% | 53% | 59% | 58% |
| v0.3.0 | 85% | 88% | 98% | 100% | 100% | 100% |

剩下没过的，都是 10–40% 预算下、没说改的是什么的改口。[完整表格和注意事项](evidence_zh.md#stale-benchmark)

### 试一下 TOMC Memory

对助手说 **"试一下 TOMC Memory"**（或 "Try TOMC Memory"），在 Claude Code 里也可以运行 `/tomc-memory:try`，终端里运行 `tomc try`。它在内存里处理一份内置的 120 天项目聊天，给出一张小卡片：处理前后的 token 数、找到的值和所在行号、下一步怎么用。什么都不保存。新增 MCP 工具 `try_tomc` 和 MCP 提示 `quickstart`；Codex 插件的第一条推荐提示也是它。

### `tomc doctor`

`tomc doctor`（或加 `--json`）检查 Python、MCP 支持、数据库、uv，用临时数据库真的启动一次服务并数工具，再看哪些客户端已经配好。没通过的每一项都会给出修法。

### `tomc setup --write`

`tomc setup --client <claude-desktop|claude-code|cursor|codex|workbuddy> --write` 把 TOMC Memory 写进该客户端的配置文件。写之前先做带时间戳的备份，保留你原有的其他服务和文件权限，重复运行也没问题。TRAE 或项目级配置用 `--config 路径`。`--client claude-code` 不加 `--write` 时会打印 `claude mcp add …` 命令。Cursor 的 JSON 现在带 `"type": "stdio"`。

Codex 安装器现在会一次列出所有缺的前提条件，给出安装 uv 的几种方法（包括国内镜像），运行时固定用 Python 3.12，装完自己启动一次服务检查（`--no-verify` 跳过）。

### 工具更严格，回答更清楚

- 共 12 个工具：`try_tomc`、`prepare_context`、`remember_memory`、`recall_memory`、`get_status`、`list_contexts`、`get_context`、`make_handoff`、`get_usage_stats`、`list_memories`、`forget_memory`、`erase_all_memory`。
- 参数检查更严：`budget` 必须是正整数，宿主和统计周期只能从固定选项里选，`limit` 是 1 到 1000，不认识的参数直接报错。
- 每个返回都以一行 `summary` 开头，诊断信息挪到 `details` 里。输入很短时会说"Short enough to use as is"，不再说"省了 0 token"。
- 给模型的服务说明缩短了一半，不再让模型对 1 万 token 以下的历史跳过 TOMC。

### 服务进程

客户端断开连接或父进程退出时，MCP 服务会跟着退出，不会留下孤儿进程。在终端里手动运行 `tomc mcp` 会打印一行提示然后退出。

## 没有变的

- 论文用的编译核心（`src/tomc/_vendor/`）没动，BEAM 和 RULER 还是原来存档的结果。
- Codex 和 Claude Code 的实测数字是在 0.1.0 预览版上测的，0.3.0 **没有**用模型重测。0.3.0 准备出来的上下文不一样了，请把那些数字当成旧版本的结果。[证据页](evidence_zh.md#assistant-trials)
- 核心包仍然要求 Python 3.10+，没有第三方依赖。仍然没有发布到 PyPI。
- 插件仍然不会让助手当前的对话变短。

## 升级须知

- **旧的 MCP 快照。** 如果你通过 MCP 用过 0.2.0 或 0.2.1，每次准备和召回的结果都存下来了。升级后它们会被遮一次密钥，超过 30 天的会删掉。想马上全部删除：`tomc erase-all --yes`（笔记本也会一起删）。想像以前一样继续保存：`tomc settings --save-mcp-results on`。
- **设置。** `tomc settings` 显示当前设置，用 `--save-mcp-results on|off`、`--save-contexts on|off`、`--retention-days N` 修改。
- **读取 MCP 返回的脚本。** `selected_method`、token 估算、`warnings`、`usage`、`preparation_id`、`host`、`session_id` 等字段挪到了 `details` 里。`memory`、`status`、`context_reduction`、`context_record`、`delivery`、`budget`、`max_chars` 还在顶层。传了不认识的参数现在会报错。
- **输出大小。** 自适应模式的下限（768 token 或预算的 25%）现在一定会填满，所以输出可能比 0.2.1 大。日文、韩文改成按字计数，预算和显示的节省量会变。
- **笔记本名称**不区分大小写：`Proj` 会追加到已有的 `proj`。
- **插件。** Claude Code：用 `/plugin` 更新插件，新开会话。Codex：下载 0.3.0 的 ZIP，重新运行安装器。Claude Desktop：安装 0.3.0 的 `.mcpb`。然后说"试一下 TOMC Memory"。

## 已知限制

- 用普通说法写的更新只作为原文保留，不会变成状态记录，预算小的时候仍可能丢。
- 用文字否定的关系（"Alice no longer owns repo1"）会标成 `PATH?`，不会被删掉。
- 计数用的分词只支持英文（问题里点名的中文词会直接按字符串计数）；中文任务不做自适应缩减。
- 用 `remember_memory` 存的笔记和导入的包按原样保存，不遮密钥。
- Windows 网关还没有客户端认证。见 [SECURITY.md](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md#known-limits)。

## 本次发布的检查

`python -m pytest -q`：1109 通过，2 跳过。`ruff check` 和 `ruff format --check`：通过。`make reproduce`：离线检查全部通过，`git status` 不变。[可复现性](reproducibility.md)

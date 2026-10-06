# TOMC 使用技巧

先告诉 TOMC 下一步要解决什么，再让它准备上下文。插件负责准备与你的问题相关的内容，你原来使用的模型负责回答。直接调用 `prepare_context` 就可以使用，不需要先建 notebook。

[安装插件](assistant_plugin_zh.md) · [Python API](api_reference.md) · [English](usage_tips.md)

## 1. 把下一步任务说具体

在 `task` 中写清要查的对象和希望的回答形式。例如，“当前 framework 和 backup_framework 分别是什么？”比“压缩一下聊天”更明确。写代码时，可以说明涉及哪个组件、要遵守什么约束、哪些工作还没完成。需要解释原因或引用原文时，也要直接说明。

安装后可以把下面这段复制给你的助手：

```text
请调用 TOMC 的 prepare_context 工具，参数如下：

history:
framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available.

task: 当前 framework 和 backup_framework 分别是什么？每行给出一个值；如果证据缺失，请明确说明。
budget: 64

先展示工具返回的 memory、note 和 warnings，再依据这些证据回答。
不要把这段 history 保存到 notebook。
```

工具的实际参数是 `history`、`task`、`budget`。回答格式写在 `task` 里，没有独立的“回答格式”参数。是否调用工具由宿主助手决定；可以查看它是否真的返回了 TOMC 工具结果。

在 Claude Code 中，点名已注册服务，例如“用 tomc-memory 的 prepare_context 处理这段 history，task 是……，budget 设为 200”。[Windows 试用](validation.md#claude-code-windows-validation)中的明确请求成功；一次未点名对照没有调用 TOMC。工具不可用时，先检查 [Claude Code 接入](assistant_plugin_zh.md#claude-code)。

## 2. 保留完整更新链，按发生顺序提供

把最初的值、复制操作和后续修改一起提供。示例中的 `backup_framework copies framework` 读取的是复制发生时的值。如果删掉最初的 Flask 赋值，备份值就失去了依据。

按时间顺序排列消息，并保留已有日期。当前参考解析器按输入顺序执行支持的操作，不会按日期自动重排。对同一个对象使用一致的名称。已经确认的结构化事实可以使用 `framework = FastAPI`、`backup_framework copies framework` 等支持的形式；“可能迁移到 FastAPI”不能写成已确认的赋值。

普通对话可以保留原文，再明确下一步任务。插件会选择相关源文本，但不能可靠识别所有隐含更新或别称。完整原文要另外保留，以便回查。

## 3. 把准备结果用于下一次请求

在自己的应用里，用准备后的消息替换这次请求中的原始历史：

```python
from tomc import prepare_context

prepared = prepare_context(history, task)
if not prepared.prompt:
    raise ValueError(prepared.note)

# 保留你的应用需要的其他指令。
response = client.chat.completions.create(
    model=model,
    messages=prepared.messages,
)
```

这里的 `history`、`task`、`client` 和 `model` 来自你的应用；`client` 使用 chat-completions 调用形式。其他 API 需要把返回的文本或消息映射到对应格式，不能理解为安装后自动兼容所有 SDK。

在助手里，可以把 demo 生成的完整 prompt 复制到新聊天，再继续任务。在已有长聊天中调用 MCP，不会清除宿主已经持有的消息。把准备结果追加到完整历史后面会增加输入；仅仅调用工具，不能证明 API token 已经减少。

<a id="choose-budget"></a>

## 4. 根据遗漏的内容调整预算

不传 `budget` 时，TOMC 保留历史词法估计长度的约 80%（至少 1,024）；在 [Claude Code 实测](validation.md#claude-code-windows-validation)中，这个默认值的答案与完整历史全部一致，输入约减少 20%。显式传入的预算限制的是词法估计下的 memory 文本，不是整个模型请求。任务、应用指令和提供商封装还会增加输入。

[Windows Codex 对比](codex_retention_20261005_zh.md)在同样九份合成历史上测试了完整历史、40%、60% 和默认 80% 历史预算。四种条件均为 45/45，请求输入的平均配对减少分别为 29.7%、19.5%、9.2%。40% 是这次测试中更小的选项；60% 给证据留下更多空间，80% 仍是默认值。采用较小预算前，先用自己的任务检查。这次普通叙述历史使用原文选择，没有生成操作记录。

Python API 接受绝对预算。要试历史估算长度的 60%，可以这样写：

```python
from tomc import prepare_context

probe = prepare_context(history, task)
history_tokens = probe.compilation.stats.input_tokens
prepared = prepare_context(history, task, budget=int(history_tokens * 0.60))
# 将 0.60 换成 0.40，可试本次测试中更小的预算。
```

两次准备都在 CPU 上完成，不调用 LLM。MCP 工具同样接受绝对 `budget`，没有 `retention_ratio` 参数。先从默认准备结果读取 `input_estimated_tokens`，乘以 0.40 或 0.60，向下取整，再把这个整数作为 `budget` 传入。使用默认值时省略 `budget`；其公式为 `max(1024, ceil(history_estimate × 0.8))`。

先为同一个任务准备一份预算较宽松的结果，检查保留了哪些事实，再降低预算，观察哪些内容消失。记录需要完整放入预算；如果 memory 为空，先增加预算再交给模型。如果缺少重要证据，可以增加预算，或者直接补上所需原文。

本来就能放下的短历史会原样保留，这是正常行为，不代表发生了压缩。源标记和指令也可能使小请求变大。

## 5. 别称、隐含修改和原文细节需要回查

参考实现使用明确的操作语法和词法规则。同一个人的不同称呼、同义词、否定表达和隐含修改，都可能造成漏选证据或路由不合适。增大预算也不会让解析器理解不支持的更新方式。

先看工具返回的 `memory`、`note` 和 `warnings`。需要查看完整审计信息时，使用 demo 的 **Workbench**，或者检查 Python 返回值：

```python
print(prepared.prompt)
print(prepared.compilation.ledger)
print(prepared.compilation.evidence)
```

ledger 中的行是候选记录，只有 `included=True` 的记录进入 memory。既要检查实际保留的记录，也要检查选中的源文本；缺少关键事实时回到原文。MCP 返回值不包含完整 ledger 或源文本检查器。源链接便于核对，但不能证明所有相关证据都被保留了。

TOMC 从 `u0` 开始分配源编号，对应第一条非空行。历史原文里已有的 `u1:` 等标签只是原文内容，不是 TOMC 的编号。用返回的源文本核对对应关系，不要假定两套编号一致。

## 6. 只把需要复用的内容存进 notebook

每个项目或主题使用一个名字，例如 `api-refactor`。适合保存下一次还要用的约束、已确认决策和未完成工作。安装插件不会自动收集你的所有聊天。

可以按需要复制这些提示词：

| 操作 | 提示词 |
|---|---|
| 保存 | “请用 TOMC 的 remember_memory 把这些内容保存到 api-refactor：公共 API 路由和返回字段保持不变。分页测试尚未编写，也没有运行。” |
| 新聊天继续 | “请用 TOMC 的 recall_memory 读取 api-refactor。task：继续之前，提醒我 API 的约束和还没完成的测试。budget：1024。” |
| 查找名字 | “请用 TOMC 的 list_memories 列出 notebook 名称。” |
| 补充已确认的纠正 | “请用 remember_memory 向 api-refactor 追加这条已确认更新：framework = FastAPI。保留之前的历史，这是最新确认的框架。” |
| 删除 | “请用 TOMC 的 forget_memory 删除名称恰好为 api-refactor 的 notebook。” |

`remember_memory` 是追加，不会编辑某条旧记录。把已纠正的值和顺序说清楚，并检查下一次 recall。`forget_memory` 删除整个指定 notebook，工具不能撤销删除。如果要完全重建，先保留需要的原文，明确要求删除该名称，再保存替换内容。

notebook 以明文保存传给工具的内容。使用同一数据库的客户端会共享它，卸载插件不会删除数据库。只想临时准备一次上下文时，直接使用 `prepare_context`。

## 7. 先比较实际请求，再检查答案

比较原始请求与准备后的请求时，使用相同模型、任务、应用指令和准备预算，统计实际发送的全部文本，包括任务和 memory 的封装。比较答案时，也保持模型的回答设置一致。

工具中的 `input_estimated_tokens` 和 `memory_estimated_tokens` 是历史与 memory 的词法估计，不包含整个宿主请求。可以运行仓库中的本地示例：

```bash
python examples/api_context.py
# 可选：用 BPE 编码统计消息正文
python -m pip install -e '.[tokenizers]'
python examples/api_context.py --tokenizer tiktoken:cl100k_base
```

该示例保持 system 指令和 task 一致，使用 64-token 的词法 memory 预算。`cl100k_base` 统计的是一种编码下的消息正文，你的模型可能使用其他 tokenizer。这里没有计算提供商聊天封装、工具 schema 或隐藏 token；判断实际计费输入时，应查看提供商返回的 usage。

用有代表性的任务检查：准备后的证据是否仍能支持回答。输入变小本身不能证明答案更好或总费用更低。论文实验与当前插件工作流的评测范围不同，也没有适用于所有历史的固定节省比例。

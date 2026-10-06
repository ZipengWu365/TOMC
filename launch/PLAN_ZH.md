# TOMC Demo：让用户看懂怎么接入、值得在哪里试

更新：2026-10-01。当前 GitHub 和 Hugging Face Space 均为私有，发布稿见 [CONTENT_KIT.md](CONTENT_KIT.md)。本计划安排文案和演示准备；公开发布、联系试用者和发送帖子由作者另行决定。

## 1. 首页先回答用户的三个问题

**TOMC 是可以接在现有 LLM API 前面的 CPU 记忆模块。** 用户提供历史和当前任务，TOMC 执行支持的状态更新、关系连接或计数，输出记录与选中的原文，再交给原来的模型回答。输出是普通文本，不需要改 reader 参数或加载辅助神经模型。

首次访问应该很快找到三个答案：它做什么、怎么接到我的模型、有什么实测证据。首页按这个顺序呈现：一句话用途、短调用代码、一个可修改的状态例子、三个 reader 的配对结果，以及安装和完整结果入口。算法名称、来源审计和工程历史保留在相关文档中。

默认网页入口供用户粘贴历史、描述任务、复制上下文。开发者入口展示如何把文本或消息交给已有客户端。研究入口保留完整结果、消融和协议。MCP 笔记本提供明确的保存与取回操作，安装说明放在助手接入入口。

## 2. 参考相关仓库的展示方式

| 项目 | 可借鉴的呈现方式 | TOMC 的具体做法 |
|---|---|---|
| [Mem0](https://github.com/mem0ai/mem0) | 用聊天客户端代码展示记忆接入的位置 | 让 `reader_messages(question)` 紧邻用户已有的 API 调用 |
| [LLMLingua](https://github.com/microsoft/LLMLingua) | 安装、最短调用和真实输出在一起 | 展示输入操作、编译记录和来源；保留真实 token 数 |
| [LightMem](https://github.com/zjunlp/LightMem) | 用场景教程连接演示和实验复现 | 分别链接直接使用、状态例子、助手接入和研究结果 |

借鉴的是说明顺序和入口，不是它们的宣传用语或实验结论。LightMem 与论文中的 LIGHT baseline 是不同工作。TOMC 的方法和实现范围以[论文与 Demo 的对应说明](../docs/paper_scope.md)为准。

## 3. 用一段代码展示即插即用的位置

英文首页主句：**CPU-built memory for the model you already use.** 中文说明：在调用模型之前，用 CPU 准备当前任务需要的记忆。

先给一个可以离线运行的例子：

```python
from tomc import compile_memory

history = "drink = tea\nbackup_drink copies drink\ndrink = decaf tea"
question = "What are the current drink and backup_drink values?"
memory = compile_memory(history, question, token_budget=256, strategy="tomc_raw")
messages = memory.reader_messages(question)
print(memory.compiled_memory)
```

然后接上用户已有的 Chat Completions 客户端：

```python
response = client.chat.completions.create(model=model, messages=messages)
```

这里的 `client` 和 `model` 由用户已有的应用提供。其他 API 可以把 `memory.compiled_memory` 放进自己的请求格式。核心模块与 provider 无关；内置 HTTP connector 直接支持 Chat Completions 兼容接口。兼容普通文本输入与“所有 API 都已测试”是两回事。

网页演示的顺序同样围绕接入：看历史和问题、运行编译、打开来源、复制输出。主例子保留 `drink = decaf tea` 和 `backup_drink = tea`，让用户看到当前值与先前副本的差别。需要原因或原话的问题再展示原文路径。录制脚本在 [CONTENT_KIT.md](CONTENT_KIT.md)，视频尚未录制。

## 4. 主表要让人一眼看懂比较对象

主表每个 reader 下写 **Baseline / TOMC**，先列基线分数，再列 TOMC 分数。同一个 reader 分别读取该行基线构建的记忆和 TOMC 构建的记忆，每对使用匹配的问题和评分。这是两种记忆方法的成对比较；API 接入则是把 TOMC 的输出交给已有模型，主表没有测量它与另一种记忆方法叠加后的效果。

以 LIGHT 的总体配对结果为例：

| Reader | Baseline memory (LIGHT) | TOMC memory |
|---|---:|---:|
| GPT-5.1 | 53.75 | **59.48** |
| Rednote preview | 51.75 | **55.90** |
| DeepSeek 4.1 Flash | 55.65 | **56.91** |

分数范围为 0–100，每一对使用匹配的有效问题和评分设置。完整主表保留六种 baseline 和各自的配对数字；不同 baseline 行的 TOMC 绝对分数可能来自不同有效集和评分协议，不能横向排名。独立的编译消融使用 **Full TOMC / TOMC w/o compilation** 标签，移除 records/instructions，保留 source/routing。

正文宣传保留三条实测结果：500K/1M 的 36 个 reader–baseline–长度比较中，TOMC 质量均值都更高；三个 reader 等权平均后，总体输入比 LIGHT 和分层 LLMLingua-2 分别少 34.77% 和 34.35%；CPU 构建阶段六次回放平均为 4.21 秒/次。质量均值与统计显著性分开，输入节省也要带上具体对照。

速度说明只比较相同的每次调用单位：BRIEF-Pro 为 47.94 秒/次，LongLLMLingua 为 72.07 秒/次，分别是 TOMC 阶段时间的 11.4 和 17.1 倍。BEAM-RAG 的 23.94 秒/会话、LLMLingua-2 的每会话时间、LIGHT 的 41.53 小时/600 条记忆批次保留原单位。TOMC 峰值 host RSS 为 3.75 GiB，观测 CUDA allocation 为零。这些是构建阶段测量，完整应用还包括 reader 调用。[完整结果](../benchmarks/RESULTS.md)

## 5. 把字符串匹配的限制说具体

内置 parser 识别 `key = value`、`B copies A` 和 typed edges 等显式操作。它不会自动理解任意自由对话中的状态变化。任务路由和 BM25 检索也使用词法规则，可能漏掉同义表达或选错路线。

当前代码中有一个可复现的路由例子：`Which account is linked to user Alice?` 会因 `account` 包含 `count` 而被选为计数任务。这个问题应该进入失败案例和后续修复清单。文案同时告诉用户能做什么：检查 route 和保留来源；需要原话或语义判断时保留 raw evidence；输入格式更复杂时使用任务适配器。

长历史中遗漏依赖或预算中丢掉关键行也会影响回答。Demo 的 audit 信息展示候选记录及是否进入输出；交给 reader 的是 `compiled_memory`。短输入若能放进预算会原样保留，添加记录和来源标签则可能增加长度。论文的质量结果来自冻结 benchmark adapters，不能直接归给这个小 parser。

## 6. 本轮素材和检查

| 素材 | 本轮内容 | 完成条件 |
|---|---|---|
| 中英文 README | 用途、接入代码、配对结果、安装和适用范围 | 代码能离线准备上下文，链接和表头一致 |
| 发布稿 | 开发者短帖、研究帖、Show HN 草稿、常见问题 | 读者能说明模块放在 API 调用前，数字带比较条件 |
| 30 秒演示 | 更新、快照、来源、输出交接 | 实际录制，输入与 token 注释清晰 |
| 结果报告 | 冻结数字、所有长度、消融、资源单位 | 聚合校验通过，生成器与文档一致 |
| 本页 HTML | 四个导航区，便于作者集中查看 | 1440/390px 可读，无页面横向溢出 |

浏览器检查覆盖粘贴、上传、编译、复制和来源展开；修改输入应清除旧结果。核心编译不调用 reader。HF 网页的字体和 Space 元数据请求与编译行为分开说明。现有工程验证记录见 [validation](../docs/validation.md)，它们不代替用户首次体验。

## 7. 发布顺序和反馈

先请几位使用长对话、文档或 LLM API 的同事试用，记录他们是否找到接入代码、能否解释快照差别、能否完成自己的例子。邀请和录像由作者安排，现阶段没有这些用户反馈。

文案和安装准备好后，由作者决定公开时间、论文链接和维护安排。公开前确认 GitHub、Space 和展示素材的发布范围；公开后检查匿名访问，再发送一条以试用入口为主的帖子。Show HN 或其他社区按当时规则提交，研究版说明随后链接完整结果和复现命令。

反馈优先收集最小失败输入、问题、所选路线、预期与实际输出。重复出现的解析、检索或安装问题决定下一轮开发范围。平台展示/点击、GitHub 访问/clone、主动提交的案例分别记录；没有使用数据时，不估算安装量或传播效果。

## 证据与后续事项

本轮依据提交 PDF、当前冻结聚合、源代码和相关项目的官方仓库核对表述。[Mem0](https://github.com/mem0ai/mem0)、[LLMLingua](https://github.com/microsoft/LLMLingua)、[LightMem](https://github.com/zjunlp/LightMem) 用于比较项目呈现方式；[Show HN 规则](https://news.ycombinator.com/showhn.html)用于安排后续提交。

待完成事项：真实试用反馈、演示录像、公开论文链接和引用信息、作者发布授权、匿名访问检查及 GitHub social preview 后台配置。草稿和素材保存在仓库中；尚未发送推广内容。

# 论文 Reader 与编程 Agent 宿主

[English](readers_and_agents.md) · [论文范围](paper_scope.md) · [Windows Codex 实测](codex_retention_20261005_zh.md)

**Reader 是读取上下文并生成答案的模型。Harness 是模型外面的运行层**：它提供指令、管理会话历史、执行工具，并把结果交回模型。Codex 和 Claude Code 提供这样的运行层；模型决定下一步，宿主执行工具。参见官方 [Codex App Server 文档](https://learn.chatgpt.com/docs/app-server) 和 [Claude Code 工作原理](https://code.claude.com/docs/en/how-claude-code-works)。

## TOMC 的三种使用场景

| 场景 | 谁读取 TOMC 输出 | 对应证据 |
|---|---|---|
| 论文中的 API Reader 实验 | 通过各自 API 客户端调用的 GPT-5.1、Rednote preview、DeepSeek 4.1 Flash | 配对记忆比较、任务诊断和构建测量 |
| Windows Codex 回答测试 | Codex 中原有的 `gpt-6.1-sol` 模型 | 新会话内，完整历史与准备后证据的一次回答比较 |
| 助手原生工具调用 | Codex 或 Claude Code 中的模型，宿主先执行 TOMC MCP 调用 | 工具连接及返回证据的使用；完整任务需要另行评估 |

论文标题保持 *Task-Oriented Memory Compilation: Executable State Representations for Long-Context Language Models*。上传 arXiv 后再补链接。论文图中的 Reader 名称和 logo 标记的是当时评估的模型；Codex、Claude Code 是另外的接入环境，不替换这些 Reader 标签。

## 助手能否在做任务时使用 TOMC？

可以。助手向 `prepare_context` 提供历史、下一步任务和预算，TOMC 在 CPU 上准备文本，再通过 MCP 返回。模型可以依据记录和保留的原文回答问题或规划下一步。在自己的应用里，也可以在模型请求前调用 Python API，沿用[已有 API 示例](api_reference.md#prepare-context-before-your-api-call)。

[当前 Windows Codex 会话的工具检查](validation_data/windows_codex_foreground_20261005.json)确实返回了当前 `framework = FastAPI` 和更新前复制得到的 `backup_framework = Flask`，含两条 STATE 记录及来源原文。该例显式设置 64 的词法记忆预算，返回 45 个估算记忆 token。它验证了已安装工具的状态与复制例子，没有收集提供商用量，也没有测量完整代码任务。

在代码任务中，这类记录可以带入已确认的框架选择、复制的旧配置或项目约束。Demo 解析器需要支持的语法才能编译操作；普通叙述可能走相关原文选择。检查返回的证据，并在后续请求或新会话中用它替换完整历史。在现有长聊天里调用工具，不会删除宿主已有的消息。

## Codex 比较是否公平？

它是**同一宿主内的受控比较**。完整历史、40%、60% 和默认 80% 条件使用同一个模型、推理设置、安装配置、任务和回答指令。完整历史对照中，TOMC 和其他插件也保持安装；变化的是交给回答模型的证据，而不是是否安装插件。

准备在回答模型运行前，通过已安装的 MCP 工具完成。每次回答进入新临时会话，使用相同的禁工具指令，未观察到回答阶段的工具调用。提供商输入包括宿主指令、可用工具定义和缓存输入。四组均恢复 45/45 个当前值；40%、60%、80% 的平均配对回答输入分别减少 29.7%、19.5%、9.2%。[协议、答案和用量记录](codex_retention_20261005_zh.md)。

这些结果支持该批合成问题中的上下文替换。准备后的普通叙述历史只含 RAW 原文，没有编译操作记录。它们没有测出整个代码 Agent 工作流的 token 用量，也不是论文三 Reader、六基线实验的复现。Claude Code 的数据保留其独立模型和请求流程。

## 完整代码任务怎样比较？

一个适合的后续例子是框架迁移：保持公开 API 不变，并用固定验收测试检查结果。两组从同一个仓库快照出发，保持模型、共同工具权限、指令和测试用例一致，检查最终代码是否满足要求。

分别测两种设计：

- **证据替换**：在回答 Agent 运行前准备上下文，同一宿主内比较完整历史与准备结果。
- **原生工具工作流**：允许 Agent 在任务中调用 TOMC，与宿主平常的工作流比较。记录两组 TOMC 工具可用性的区别，并累计准备、召回、后续工具、自动压缩和子模型等所有回合的用量。

报告任务通过情况、总输入和输出、缓存计数、模型设置及初始工作区。缓存输入是输入总量的一部分；推理输出是输出总量的一部分，不能重复相加。一次回答的输入减少不能替代完整工作流的统计。这是后续实验方案，还不是本仓库已测得的结果。

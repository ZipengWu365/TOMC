# Windows Codex：上下文预算与实际输入 — 2026-10-05

[English report](codex_retention_20261005.md) · [实测数据](validation_data/windows_codex_retention_20261005.json) · [预算技巧](usage_tips_zh.md#choose-budget)

四种条件都答对了 45/45 个项目最新状态问题。相较完整历史，40%、60% 和默认 80% 历史预算的请求输入平均配对减少 29.7%、19.5% 和 9.2%。先通过已安装的 TOMC MCP 工具在 CPU 上准备上下文，再交给新的 Codex 聊天回答一次。

## 总体结果

每种条件包含九次回答回合、45 个被检查的值。输入均值四舍五入到整数 token；JSON 保留未舍入均值、每次回答及其 usage 记录。

| 发送的上下文 | 平均提供商输入 token | 平均配对输入减少 | 值检查 |
|---|---:|---:|---:|
| 完整历史 | 42,191 | 参照 | 45/45 |
| TOMC · 40% 历史预算 | 28,713 | 29.7% | 45/45 |
| TOMC · 60% 历史预算 | 33,344 | 19.5% | 45/45 |
| TOMC · 默认 80% 历史预算 | 38,035 | 9.2% | 45/45 |

对每份历史，减少比例为 `100 × (1 − prepared_input / full_input)`，再对九个比例等权取平均。这里不是先求两个条件的输入均值、再相除；后者会给长历史更大的权重。

## 按历史长度查看

每种长度有三份历史，每种条件检查 15 个值。长度标签是 `cl100k_base` 下的近似历史长度，不是完整请求输入，也不是 TOMC 的词法预算计数。

| 历史长度 | 发送的上下文 | 平均提供商输入 token | 平均配对输入减少 | 值检查 |
|---|---|---:|---:|---:|
| 约 10K | 完整历史 | 29,023 | 参照 | 15/15 |
| 约 10K | TOMC · 40% 预算 | 23,195 | 20.1% | 15/15 |
| 约 10K | TOMC · 60% 预算 | 25,160 | 13.3% | 15/15 |
| 约 10K | TOMC · 默认 80% | 27,134 | 6.5% | 15/15 |
| 约 20K | 完整历史 | 38,846 | 参照 | 15/15 |
| 约 20K | TOMC · 40% 预算 | 27,258 | 29.8% | 15/15 |
| 约 20K | TOMC · 60% 预算 | 31,220 | 19.6% | 15/15 |
| 约 20K | TOMC · 默认 80% | 35,173 | 9.5% | 15/15 |
| 约 40K | 完整历史 | 58,705 | 参照 | 15/15 |
| 约 40K | TOMC · 40% 预算 | 35,687 | 39.2% | 15/15 |
| 约 40K | TOMC · 60% 预算 | 43,651 | 25.6% | 15/15 |
| 约 40K | TOMC · 默认 80% | 51,797 | 11.8% | 15/15 |

## 测试设置

本次回答的 Reader 是 `gpt-6.1-sol`，Codex 提供外围指令、工具和会话管理。完整历史对照也保持 TOMC 和其他插件安装。因此比较的是同一宿主中的证据，而不是“安装插件”和“卸载插件”。[论文 Reader 与编程 Agent 宿主](readers_and_agents_zh.md)。

使用 Windows 桌面内置 Codex CLI 0.160.0，保留原有 `gpt-6.1-sol` 模型、OpenAI provider 和 `ultra` effort。preview.4 已安装在实际个人配置中，核对的三个准备代码文件（`easy.py`、`mcp_server.py`、`compiler.py`）与仓库 commit `ad89208` 一致。个人配置未改变，没有 feature、MCP 或工具 namespace 覆盖设置。测试程序给所有条件同一条 developer 指令：只根据提供的证据回答，不调用工具。

语料使用 seed 11、23、37，各自生成 670、1,340、2,700 条聊天消息。历史包含普通叙述的更新与干扰内容。五个问题分别查当前截止日期、页数限制、评估章节负责人、每周会议时间、最终展示地点。同一个 seed 的短历史嵌套在长历史中。因此，45 个值来自九份相关历史、三个 seed，不是 45 个独立项目。

对每份历史，测试程序在回答模型之外调用原生 MCP `prepare_context`。40% 和 60% 预算是历史词法估计长度乘以 0.40 或 0.60 后向下取整；80% 条件省略 `budget`，实际执行未改变的默认公式 `max(1024, ceil(history_estimate × 0.8))`。实际平均词法证据保留比例分别为 39.98%、59.96%、79.97%。

全部 27 份准备结果均选择 `tomc_raw`，包含原文块，没有 `STATE`、`REL` 或 `COUNT` 记录。这些普通叙述历史走的是原文选择回退；本次测试不能独立验证操作编译。

每份完整或准备后的证据分别交给全新的临时聊天。36 次回答回合全部完成，没有观察到工具调用或模型切换。没有保存或取回 notebook。让助手在聊天中准备或取回上下文会增加模型回合，这些单次回答的数字没有计入这类工作流。遥测无法排除隐藏的传输重试。

## Token 与答案如何核对

输入取 Codex 最终返回的 `inputTokens`，包含缓存输入、宿主指令及可用工具定义。缓存输入是总量的一部分，没有扣除，也没有减去估算的宿主开销。JSON 中的 `cl100k_base` 计数只描述所提供的文本，不声称它就是提供商 tokenizer。`outputTokens` 已包含 `reasoningOutputTokens`；两个字段都保留，不能再相加。本报告不据此计算货币费用或宣称加速。

答案与语料生成器的当前值核对，使用规范化字符串及识别出的页数上限同义表达。页数检查只核对数值，不区分“少于”与“不超过”。JSON 同时保留原始评分和核对结果。这些描述性结果只覆盖一个模型上的合成最新状态问题，不代表通用编程能力，也不保证小预算能保留所有事实。

## 怎么选预算

40% 产生了本次测试中最小的请求；60% 给证据留下更多空间。可以用自己的任务，将这两个选项与完整历史比较。默认值仍为 80%。按[Python 示例与 MCP 说明](usage_tips_zh.md#choose-budget)设置绝对预算，再检查保留的证据与回答。

[Claude Code 结果](validation.md#claude-code-windows-validation)使用 Claude Opus 5.5，且请求工作流不同。其默认设置约 20% 的输入减少不能替代本次 Codex 结果。

## 复现

可以先离线核验已发布记录。只需 Python 3.11 或更新版本，不需要账号、已安装插件、MCP host，也不请求模型：

```bash
python scripts/benchmarks/codex_retention_report.py --verify-published docs/validation_data/windows_codex_retention_20261005.json
```

它重新生成合成语料，核对历史哈希、预期值、保存的回答、usage 计数及汇总运算；不会重跑模型实验。

使用 Python 3.11 或更新版本，安装 `tiktoken`，并在待测 Codex 个人配置中安装 TOMC 插件。把 CLI 占位路径换成桌面内置可执行文件的位置。runner 使用该配置原有的模型、provider、effort，不修改这些设置。生成语料在本地离线完成；runner 执行 36 次模型回答以及 CPU 上的准备调用。

```bash
python -m pip install tiktoken
python scripts/benchmarks/codex_retention_cases.py --output outputs/codex_cases.json
python scripts/benchmarks/codex_retention_run.py --cli "C:/path/to/desktop-bundled/codex.exe" --cases outputs/codex_cases.json --output outputs/codex_retention --concurrency 2
```

在仓库根目录执行上述命令。向 runner 添加 `--resume`，可继续同一输出目录里已经完成的结果。报告程序的导出模式（`--results`、`--cases`、`--output`）针对 10 月 5 日这份记录的 host；换用其他设置时需要更新其来源常量。本次[实测数据](validation_data/windows_codex_retention_20261005.json)包含语料与结果哈希、逐例评分、预算、保留文本的 token 计数和 provider usage；以后重跑可能得到不同结果。

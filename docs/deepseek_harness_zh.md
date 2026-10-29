# 在 DeepSeek Harness 中使用 TOMC Memory

[English](deepseek_harness.md)

**非官方社区项目，由社区开发者独立开发和维护。** TOMC 通过 DSH 官方
`@deepseek-ai/dsh-mcp-client` 的本地 stdio 连接接入，工具名称为
`mcp__tomc__<工具名>`，无需修改 DSH 源码。

[实测记录与测试范围](deepseek_harness_validation_20261029.md)。

TOMC 用 CPU 准备任务记忆，不需要额外模型服务。聊天回答仍由你在 DSH 中选择的
模型生成。此接入用于明确保存的笔记和单独提供的外部历史，不接管 DSH 的原生聊天压缩，
也不自动拦截 API 请求。

## Windows 安装

准备 Git、Python 3.10+ 和 DSH 支持的 Node.js；本次验证使用 Node.js 24。
在 PowerShell 中执行：

```powershell
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[mcp]'
.\.venv\Scripts\python.exe scripts/setup_deepseek.py --output "$env:USERPROFILE/.tomc/deepseek/tomc.cordis.yml"
npx.cmd --yes @deepseek-ai/dsh@0.2.1-rc.5 web --patch "$env:USERPROFILE/.tomc/deepseek/tomc.cordis.yml"
```

打开 DSH 输出的本地地址，在 DSH 内单独配置模型。TOMC 本身无需 API Key。
macOS/Linux 命令见英文说明；平台测试范围以验证记录为准。

生成文件仅追加 TOMC MCP 配置，包含本机 Python 和数据库的绝对路径，不含密钥。
保留仓库和虚拟环境的目录位置；移动后使用新文件名重新生成。生成器拒绝覆盖已有文件。
每次启动保留 `--patch`，也可将其中单个 `insert` 操作合并进已有 DSH profile 的
`cordis.patch.yml`，不要覆盖原有配置，也不要重复注册同一服务。

可通过生成器的 `--store` 指定独立数据库。默认是 `~/.tomc/memory.sqlite3`
（`TOMC_MEMORY_PATH` 可覆盖）；要和其他助手共享笔记，需要明确配置同一个数据库文件。

## 实际验证

在会话 A 中输入：

> 调用 mcp__tomc__remember_memory，保存笔记 dsh-demo：Project Lark 使用端口
> 4317，公共 API 必须保持不变，分页测试尚未完成。请展示工具是否保存成功。

新建会话 B，不复制会话 A 的内容，然后输入：

> 调用 mcp__tomc__recall_memory 读取 dsh-demo。这个项目使用哪个端口、什么不能改、
> 还缺哪些测试？请根据工具返回回答，不要猜测。

最后让模型根据召回内容列出下一步清单。检查实际工具调用和结果，而不只是模型口头声称成功。
按 DSH 的正常权限提示允许相关操作。`mcp__tomc__get_status` 可检查运行设置；
`mcp__tomc__list_memories` 可查看笔记名。删除演示笔记时，明确指定只忘记 `dsh-demo`。

## 存储与限制

- 保存笔记需要明确调用，TOMC 不自动收集整段 DSH 聊天，也不能查看其他会话。
- 0.2.1 默认将成功准备／召回后的上下文和任务存入本地上下文库；可在 TOMC 控制中
  关闭记录，既有快照不会自动删除。先用 `get_status` 检查设置。
- TOMC 在本机处理数据；返回给聊天的工具内容会进入你选择的模型服务商的上下文。
- 词元数是记忆文本估算，不是完整 API 账单。短输入可能原样保留，工具调用也有开销。
  本次接入不证明所有任务都省钱、提速或提高回答质量。
- 下次启动去掉 `--patch` 即不再加载此接入；已保存的笔记和快照会保留。

若工具没有出现，检查启动日志和配置里的 Python 路径。本文件是 Cordis 追加配置，
不是其他客户端的 `mcpServers` JSON。

若网页能打开但接口报 403，检查浏览器是否改变了 Origin 的主机或端口，不要关闭 DSH
的安全检查。本机 Windows 验证遇到浏览器省略 Origin 端口，改为本地 `--port 80`
后恢复；仅在该端口空闲且系统允许时使用。正常环境可使用 DSH 默认端口。

[DSH 官方 MCP 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
· [官方社区分享规则](https://github.com/deepseek-ai/deepseek-harness/discussions/2004)

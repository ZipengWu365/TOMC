# TOMC Memory · 让猫猫帮你省 token

TOMC 在本地 CPU 上整理任务上下文，保存项目要求、决定和待办。连接同一记忆库的 Code Agent 可以接着做，任务笔记也可以导出后带到另一台电脑。

可选的桌面小猫展示节省统计、上下文库和四档动画。猫咪形态随本次处理的上下文长度变化；桌面组件单独安装。

## 安装

1. 安装 [UV](https://docs.astral.sh/uv/getting-started/installation/)，确保 `uvx` 在 PATH 中。
2. 先运行以下命令，下载固定版本源码、Python 及 MCP 依赖：

   ```sh
   uvx --from "tomc-memory[mcp] @ https://github.com/ZipengWu365/TOMC/archive/3951794d19c9c6d22920997434aa44c54b76abf9.zip" tomc --help
   ```

3. 按 WorkBuddy 连接器安装流程导入本目录。手动安装时，将 `mcp.json` 的 `mcpServers.tomc` 合并到 `~/.workbuddy/mcp.json`，保留已有服务。
4. 在新任务中启用 TOMC，试着说：**把这份项目要求保存到 TOMC 的发布计划笔记，下次接着做。**

默认笔记库为 `~/.tomc/memory.sqlite3`。在 `mcp.json` 的 server 配置中添加 `env.TOMC_MEMORY_PATH` 可选择其他本地文件。首次安装需联网下载；TOMC 自身不需要模型 API key，后续记忆操作在本地运行。召回内容进入 WorkBuddy 当前任务。

[桌面小猫安装](https://github.com/ZipengWu365/TOMC/blob/main/docs/desktop_companion.md) · [实验结果](https://github.com/ZipengWu365/TOMC#same-reader-baseline-memory-vs-tomc-memory) · [源码](https://github.com/ZipengWu365/TOMC)

## English

TOMC prepares task context locally on CPU and saves project requirements, decisions, and unfinished work. Agents connected to the same notebook database can continue the task; exported notes can travel to another computer.

The optional desktop cat shows context savings, saved contexts, and four animation forms. Its form follows the current context's input length. Install the desktop companion separately using the guide above.

Install UV, run the command above to prefetch the pinned source and dependencies, then import this connector. For manual setup, merge `mcpServers.tomc` from `mcp.json` into `~/.workbuddy/mcp.json`. Example: **Save these project requirements in a TOMC notebook named release-plan so we can continue later.**

Local notebooks default to `~/.tomc/memory.sqlite3`; `env.TOMC_MEMORY_PATH` selects a different file. TOMC requires no additional model API key. WorkBuddy uses its own model to answer with recalled context.

License: MIT. Author: Zipeng Wu. [Issue tracker](https://github.com/ZipengWu365/TOMC/issues).

# 在 WorkBuddy 中配置 TOMC

[English](workbuddy.md) · [助手接入指南](assistant_setup.md) · [验证记录](validation.md)

本文提供腾讯 WorkBuddy 的本地 MCP 手动配置。**WorkBuddy 图形界面安装及模型实际调用 TOMC 工具仍未验证**；此前 TOMC 后端检查保留各自范围。TOMC 尚未上架腾讯官方市场，也不代表获得腾讯背书。本次更新没有新增客户端实测。

## 使用锁定运行环境

安装 [UV](https://docs.astral.sh/uv/getting-started/installation/)，确保 `uv` 在 PATH 中，再克隆公开仓库：

```bash
git clone https://github.com/ZipengWu365/TOMC.git
```

主仓库的 `plugins/claude-code` 目录包含共用的 TOMC 源码、`pyproject.toml`、`uv.lock` 和 `src/server.py`。WorkBuddy 可把它作为本地 stdio 服务启动，不需要安装 Claude Code。首次启动时，UV 可能下载兼容的 Python 和锁定依赖。TOMC 本身不需要额外模型 API Key 或 GPU。

接入前，先用实际运行目录下载锁定依赖：

```bash
uv sync --locked --directory "/absolute/path/to/TOMC/plugins/claude-code"
```

复制 [WorkBuddy 配置模板](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.workbuddy.json)，替换**两处**绝对路径：运行目录及该目录下的 `src/server.py`。Windows JSON 路径可使用正斜杠，例如 `C:/Tools/TOMC/plugins/claude-code`。如果 UV 不在 PATH 中，将 `command` 改为实际可执行文件路径。保留仓库目录，移动后同步更新两处路径。

## 添加服务

打开侧边栏 **插件 → MCP 服务器 → 配置 MCP**，把 `mcpServers.tomc` 合并到 JSON，保留其他服务。[WorkBuddy 官方配置指南](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide)也提供以下文件位置：

| 范围 | 配置文件 |
|---|---|
| 用户级，多个项目共用 | `~/.workbuddy/mcp.json` |
| 当前项目 | `<项目目录>/.workbuddy/mcp.json` |

`~` 表示当前用户的主目录。保存后查看服务状态；官方指南用绿色表示连接成功，红色表示配置或启动异常。模板显式设置 `stdio`，该类型见[官方连接器参考](https://open.workbuddy.cn/docs/connector)。

备选方式是从当前 TOMC 源码安装 `.[mcp]`，再执行 `python -m tomc setup --client workbuddy`。命令打印当前 Python 环境的配置，不会修改 WorkBuddy 设置。可加 `--store /absolute/path/to/tomc-memory.sqlite3` 指定数据库。`workbuddy` 别名是当前源码新增入口；旧 ZIP/MCPB 预览包可能没有该选项，请更新源码或使用 UV 模板。`--link` 仍仅支持 Cursor。

## 工具、存储与反馈

`prepare_context` 处理明确提供的历史，不保存该历史。可选记忆本工具为 `remember_memory`、`recall_memory`、`list_memories` 和 `forget_memory`。仅保存用户明确授权的文本，删除时只处理指定记忆本。

默认记忆本是明文 SQLite 文件 `~/.tomc/memory.sqlite3`。使用 UV 模板时，可将以下字段合并到 `command`、`args` 同级，指定独立文件：

```json
{
  "env": {"TOMC_MEMORY_PATH": "/absolute/path/to/tomc-memory.sqlite3"}
}
```

使用同一文件的客户端可以共用显式保存的笔记。TOMC 不会收集其他聊天、删除宿主历史，也不提供云同步。返回内容进入 WorkBuddy 上下文，遵循其数据政策。

欢迎通过 [GitHub Issues](https://github.com/ZipengWu365/TOMC/issues)反馈配置情况，请提供 WorkBuddy 版本、操作系统、配置方式和报错。不要附凭据、私人历史或记忆本内容。

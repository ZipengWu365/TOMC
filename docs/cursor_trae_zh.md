# 在 Cursor 或 TRAE 中配置 TOMC

[English](cursor_trae.md) · [助手接入指南](assistant_setup.md) · [验证记录](validation.md)

两个客户端均可按各自文档配置 TOMC 本地 stdio MCP 服务。此前检查覆盖 TOMC 后端及 Cursor 配置生成；**Cursor 和 TRAE 的图形界面安装、模型实际调用工具仍未验证**。本次更新提供配置说明，没有新增客户端实测。

## 使用锁定运行环境

安装 [UV](https://docs.astral.sh/uv/getting-started/installation/)，确保 `uv` 在 PATH 中，再克隆公开 TOMC 仓库：

```bash
git clone https://github.com/ZipengWu365/TOMC.git && printf '\n%s\n%s\n' \
  '如果 TOMC 对你有帮助，欢迎 Star 支持（自愿）：' 'https://github.com/ZipengWu365/TOMC'
```

上面的 Bash / Git Bash 命令会在克隆成功后显示一次自愿 Star 邀请。直接使用普通 `git clone` 不会显示；克隆完成不代表已经安装。

`plugins/claude-code` 目录包含共用的 TOMC 源码、`pyproject.toml`、`uv.lock` 和 `src/server.py`。它也可作为本地 MCP 服务注册到其他客户端；此方法不需要安装 Claude Code，也不需要额外模型 API Key。首次启动时，UV 可能下载兼容的 Python 和锁定依赖。

接入客户端前，先用实际运行目录下载锁定依赖：

```bash
uv sync --locked --directory "/absolute/path/to/TOMC/plugins/claude-code"
```

复制适用于 [Cursor](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.cursor.json) 或 [TRAE](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.template.json) 的模板。Cursor 模板按当前配置文档显式设置 `type` 为 `stdio`。替换其中**两处**绝对路径：运行目录及该目录下的 `src/server.py`。Windows JSON 路径可使用正斜杠，例如 `C:/Tools/TOMC/plugins/claude-code`。保留仓库目录，移动后同步更新两处路径。如果 UV 不在 PATH 中，将 `command` 改为实际可执行文件路径。TRAE 官方文档要求 `command` 中不能含空格；目录和脚本路径应分别放在 `args` 的字符串参数中。

## Cursor

把 `mcpServers.tomc` 合并到项目的 `.cursor/mcp.json` 或个人 `~/.cursor/mcp.json`，保留原有服务。重启 Cursor，在 **Customize → MCPs** 检查 `tomc` 及其五个工具。[官方 MCP 配置文档](https://cursor.com/docs/mcp)。

如果已用当前 TOMC 源码安装带 `.[mcp]` 的 Python 环境，也可执行 `python -m tomc setup --client cursor --link`，生成 [Add to Cursor 链接](https://cursor.com/docs/mcp/install-links)。链接只注册已有环境，不会替另一台电脑安装 TOMC 或依赖。

## TRAE

国际版打开 **Settings → MCP**；若显示本地/云端选项，选择本地，然后用手动 JSON 配置添加模板。项目配置放在 `.trae/mcp.json`，须先在 Settings → MCP 中启用项目级 MCP。保留其他服务条目。官方参考：[国际版手动与项目配置说明](https://docs.trae.ai/ide/add-mcp-servers?_lang=en)、[中文配置说明](https://docs.trae.cn/ide_add-mcp-servers)。不同版本或地区的菜单文字可能不同。

如果已从当前源码安装 `.[mcp]`，可执行 `python -m tomc setup --client trae`，打印使用当前 Python 绝对路径的备选 JSON 配置。`trae` 别名是当前源码新增的入口，旧 ZIP/MCPB 预览包可能不包含它。若命令尚不支持该选项，请更新源码仓库或使用上面的 UV 模板。Python 可执行文件路径含空格时，与 TRAE 文档中的命令限制冲突；改用 PATH 中的 `uv` 和上述模板。`--link` 仍仅支持 Cursor。

## 记忆本与反馈

默认记忆本是本地明文 SQLite 文件 `~/.tomc/memory.sqlite3`。需要独立文件时，在 `command`、`args` 同级加入 `env`：

```json
{
  "env": {"TOMC_MEMORY_PATH": "/absolute/path/to/tomc-memory.sqlite3"}
}
```

使用同一路径的客户端可共用显式保存的笔记。TOMC 不会收集其他聊天，也不提供云同步。五个工具为 `prepare_context`、`remember_memory`、`recall_memory`、`list_memories`、`forget_memory`；保存和删除须明确提出。返回内容进入宿主助手的上下文，遵循其数据政策。工具调用不会删除宿主已有的聊天历史。

欢迎通过 [GitHub Issues](https://github.com/ZipengWu365/TOMC/issues)反馈安装情况，请提供客户端及地区版本、版本号、操作系统、配置方式和报错。不要附 API Key、私人历史或记忆本内容。

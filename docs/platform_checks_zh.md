# 各平台检查记录

以下带日期的安装和模型检查记录从主页移到这里。[完整验证记录](validation.md)

**这些检查对应哪个版本。** 本页所有检查用的都是 0.1.0 助手预览版（preview.2 到 preview.4，2026-10-02 至 2026-10-04），当时 TOMC 有五个工具。真实模型调用在 Codex（Windows 和 macOS）和 Claude Code（Windows，VS Code 扩展）里做过；Linux 检查没有调用模型。0.2.x 和 0.3.0 没有重新做完整的跨平台检查；0.3.0 只在 macOS 上跑过自动测试和一次真实的 MCP 服务启动。Cursor、TRAE、WorkBuddy 的工具调用，以及 Claude Desktop 的界面安装，都还没在真机上验证。

**Windows preview.4 实测 — 2026-10-04：**原始发布 ZIP 使用桌面内置 CLI 0.160.0，通过了前置检查及 Codex 个人配置中的完整原生安装。原有 `gpt-6.1-sol` 模型实际调用了准备、保存和取回工具；另一个新聊天没有收到原历史，也取回了正确值。未使用 feature 或 MCP 覆盖设置。五工具连接、host 重启和准确删除测试笔记均通过，安装保留并启用。默认记忆库在保存前和删除合成测试笔记后均为空；数据库元数据发生了变化。未实点图形界面安装流程。[当前验收记录](validation.md#windows-codex-preview4)。

之前的 preview.3 检查覆盖隔离 CLI 0.146.0 / 0.159.2 的安装和直接工具调用；preview.1 模型试用使用临时 MCP 设置。Claude Desktop 与 Cursor 仅有运行检查，其 GUI 验收仍待完成。

**2026-10-02 macOS 实测通过**：preview.2 在 **macOS 26.3 / arm64、Codex CLI 0.159.2** 上作为原生插件安装并启用；模型实际调用 `prepare_context`，正确回答了复制快照例子。中文笔记经进程重启后仍可取回，测试后删除；本地浏览器 Demo 也通过。这台 Mac 原先没有 UV，系统 Python 为 3.9.6，需要先准备兼容运行环境。Codex、Claude Desktop、Cursor 的 GUI 安装仍未验收。[macOS 安装、技巧与卸载](macos_usage.md#chinese-quickstart) · [完整中文安装指南](assistant_plugin_zh.md) · [验证记录](validation.md) · [Claude 校验文件](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.3/tomc-memory-0.1.0.mcpb.sha256) · [Codex 校验文件](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.3/tomc-memory-codex-0.1.0.zip.sha256)。

本轮 Linux 检查在 Ubuntu 24.04.5 上，使用 Codex CLI **0.159.0-alpha.12.1** 验证 preview.2 原生插件安装及 MCP 工具，并检查 `.mcpb` 的后端运行。全部使用临时配置和记忆库，没有调用模型；Claude/Cursor GUI 安装和模型自动使用工具不在这轮验证范围内。[Linux 验证与安装反馈](linux_validation.md)。

VS Code 扩展中的 Claude Code 2.1.287（模型为 Claude Opus 5.5）已注册 preview.2 运行环境，并在新会话中调用了 `prepare_context`、`remember_memory`、`recall_memory` 和 `forget_memory`；详见[验证记录](validation.md)。

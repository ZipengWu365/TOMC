# Platform checks

Dated installation and model checks moved from the homepage. [Full validation record](validation.md)

**Windows preview.4 — 2026-10-04:** the original release ZIP passed preflight and full native installation in the owner's personal Codex profile using the desktop-bundled CLI 0.160.0. The existing `gpt-6.1-sol` model called preparation, save and recall tools; a separate fresh chat recalled the correct values without receiving the history. No feature or MCP overrides were used. All five tools connected, host restart and exact test-notebook deletion passed, and the installation remains enabled. The default notebook database was empty before saving and after deleting the synthetic test notebook; its metadata changed. The GUI installation flow was not exercised. [Current acceptance record](validation.md#windows-codex-preview4).

Earlier preview.3 checks covered isolated CLI 0.146.0/0.159.2 installation and direct tool calls. Preview.1 model trials used temporary MCP settings. Claude Desktop and Cursor have runtime checks only; their GUI acceptance remains pending.

On **2026-10-02**, preview.2 installed and enabled as a native plugin on **macOS 26.3 / arm64 with Codex CLI 0.159.2**. The model called `prepare_context` and answered the snapshot example correctly; Chinese notes survived a process restart and were deleted after testing. The local browser demo also passed. This Mac initially lacked UV and had Python 3.9.6, so setup required a compatible runtime. Codex, Claude Desktop and Cursor GUI installation remain unvalidated. [macOS setup, usage tips and uninstall](macos_usage.md) · [Full installation guide](assistant_plugin.md) · [Dated validation](validation.md) · [Claude checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.3/tomc-memory-0.1.0.mcpb.sha256) · [Codex checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.3/tomc-memory-codex-0.1.0.zip.sha256).

Fresh preview.2 downloads also passed [Linux installation checks](linux_validation.md): the Codex native plugin installed and connected all five tools, and the Claude bundle passed MCP runtime checks. These Linux checks made no model calls.

Claude Code 2.1.287 in the VS Code extension, with Claude Opus 5.5, registered the preview.2 runtime; fresh sessions called `prepare_context`, `remember_memory`, `recall_memory` and `forget_memory`; see the [validation record](validation.md).

# Assistant workflow policy update — 2026-10-12

Plugin packaging **0.1.1** includes the host-managed active-chat policy. When native compaction is enabled or unknown, the assistant should leave that chat with the host. TOMC remains available for external task evidence and explicitly saved notebooks. This is assistant guidance, not a compaction-switch detector, automatic request hook or runtime prohibition. The compiler core remains 0.1.0.

| Current package | Download | SHA-256 |
|---|---|---|
| Codex native plugin 0.1.1 | [ZIP](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-codex-0.1.1.zip) | [Checksum](tomc-memory-codex-0.1.1.zip.sha256) |
| Claude MCP runtime 0.1.1 | [MCPB](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-0.1.1.mcpb) | [Checksum](tomc-memory-0.1.1.mcpb.sha256) |

Update the plugin and start a new assistant session to load the new instructions. Keep notebook databases separate from installation files. No new GUI or model acceptance result is asserted; historical evidence retains its stated versions. [Context ownership](../../docs/context_ownership.md) · [中文说明](../../docs/context_ownership_zh.md) · [Build receipt](context_policy_build_receipt_20261012.json).

The runtime also includes the opt-in API request-loop helper and output-equivalent lexical packing optimization. This helper requires a caller-controlled SDK entry point; MCP itself remains explicit tool use. [Request policy](../../docs/context_ownership.md).

Earlier 0.1.0 packages are preserved unchanged below.

# MIT-licensed assistant preview · 2026-10-10

These TOMC v0.1.0 packages were rebuilt after the copyright holder authorized the MIT License on 2026-10-10. They include the MIT license text and updated package documentation. The source remains a research preview; dated host/model validation is recorded in [validation](../../docs/validation.md).

| Package | Download | SHA-256 |
|---|---|---|
| Codex native plugin | [ZIP](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-codex-0.1.0.zip) | [Checksum](tomc-memory-codex-0.1.0.zip.sha256) |
| Claude MCP runtime | [MCPB](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-0.1.0.mcpb) | [Checksum](tomc-memory-0.1.0.mcpb.sha256) |

Install with the [English guide](../../docs/assistant_plugin.md) or [中文安装指南](../../docs/assistant_plugin_zh.md). The Codex package contains `plugins/tomc-memory/LICENSE`; the Claude package contains `LICENSE` at its root.

TOMC's original code and synthetic examples are free to use, including commercially, under MIT. Modification, redistribution and closed-source integration are allowed; copies or substantial portions of the software must retain the copyright and license notice. Research citation is encouraged. Third-party dependencies, model services and provider marks retain their own terms and ownership.

The [preview.5 release](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.5) distributes these same MIT-licensed packages.

To rebuild from the repository root:

```bash
python scripts/build_plugin.py --output outputs/plugins
python scripts/build_codex_plugin.py --output outputs/plugins
```

The included build receipts record each archive's file count, byte size and SHA-256. Rebuilding the same source produces the same bytes. A package rebuild does not add a new model evaluation or GUI installation result.

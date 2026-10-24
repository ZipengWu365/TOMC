# TOMC 0.2.1 — 2026-10-24

0.2.1 fits each MCP result into one tool output, can send only the changes on a repeat call, and lets notes and documents stop below the budget when the evidence is clear. Like 0.2.0, the packages are [release assets](https://github.com/ZipengWu365/TOMC/releases/tag/v0.2.1-preview.1).

| Current package | Download | Size | SHA-256 |
|---|---|---|---|
| Claude MCP runtime 0.2.1 | [MCPB](https://github.com/ZipengWu365/TOMC/releases/download/v0.2.1-preview.1/tomc-memory-0.2.1.mcpb) | 7.6 MB | `0b2807382011bee9fe6dd7fa36b9f35f9a830b980964cfb650eccc651409bbed` |
| Codex native plugin 0.2.1 | [ZIP](https://github.com/ZipengWu365/TOMC/releases/download/v0.2.1-preview.1/tomc-memory-codex-0.2.1.zip) | 7.6 MB | `1bab23d6978165c460bc6d30c8d9ecd02f0f57e2755ced6f3a5a6bbfbc68cf1f` |

# TOMC 0.2.0 — 2026-10-24

The 0.2.0 packages include the desktop cat images, so at about 7.6 MB they are published as [release assets](https://github.com/ZipengWu365/TOMC/releases/tag/v0.2.0-preview.1) rather than in this folder. They add the context library tools, the savings dashboard data and the analysis report; the desktop companion itself is installed from a checkout ([guide](../../docs/desktop_companion.md)).

| Package | Download | Size | SHA-256 |
|---|---|---|---|
| Claude MCP runtime 0.2.0 | [MCPB](https://github.com/ZipengWu365/TOMC/releases/download/v0.2.0-preview.1/tomc-memory-0.2.0.mcpb) | 7.6 MB | `b813f064ec02f3be408d551f8d3244926920d1b6f648908d0efa3402f401be09` |
| Codex native plugin 0.2.0 | [ZIP](https://github.com/ZipengWu365/TOMC/releases/download/v0.2.0-preview.1/tomc-memory-codex-0.2.0.zip) | 7.6 MB | `4666c15cdfc321aec2f5e358272ff0e761fbc5a570dd085977abd85068586aac` |

Packages below are earlier versions, kept unchanged.

# Codex installation support prompt — 2026-10-16

Codex packaging **0.1.2** adds an optional GitHub Star invitation after successful installation. It is shown once per successful installer run; `--no-support-message` hides it. Preflight, configure-only and failed installation paths do not show it. MCP tool output is unchanged. No new native-client or model acceptance is claimed. The 0.1.1 downloads remain available at their original paths.

# Assistant workflow policy update — 2026-10-12

Plugin packaging **0.1.1** includes the host-managed active-chat policy. When native compaction is enabled or unknown, the assistant should leave that chat with the host. TOMC remains available for external task evidence and explicitly saved notebooks. This is assistant guidance, not a compaction-switch detector, automatic request hook or runtime prohibition. The compiler core remains 0.1.0.

| Current package | Download | SHA-256 |
|---|---|---|
| Codex native plugin 0.1.2 | [ZIP](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-codex-0.1.2.zip) | [Checksum](tomc-memory-codex-0.1.2.zip.sha256) |
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

# MIT-licensed assistant preview · 2026-10-10

These TOMC v0.1.0 packages were rebuilt after the copyright holder authorized the MIT License on 2026-10-10. They include the MIT license text and updated package documentation. The source remains a research preview; dated host/model validation is recorded in [validation](../../docs/validation.md).

| Package | Download | SHA-256 |
|---|---|---|
| Codex native plugin | [ZIP](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-codex-0.1.0.zip) | [Checksum](tomc-memory-codex-0.1.0.zip.sha256) |
| Claude MCP runtime | [MCPB](https://github.com/ZipengWu365/TOMC/raw/refs/heads/main/plugins/downloads/tomc-memory-0.1.0.mcpb) | [Checksum](tomc-memory-0.1.0.mcpb.sha256) |

Install with the [English guide](../../docs/assistant_plugin.md) or [中文安装指南](../../docs/assistant_plugin_zh.md). The Codex package contains `plugins/tomc-memory/LICENSE`; the Claude package contains `LICENSE` at its root.

TOMC's original code and synthetic examples are free to use, including commercially, under MIT. Modification, redistribution and closed-source integration are allowed; copies or substantial portions of the software must retain the copyright and license notice. Research citation is encouraged. Third-party dependencies, model services and provider marks retain their own terms and ownership.

Earlier GitHub release assets retain their original embedded notices and are preserved as historical snapshots. Use these packages or the current source for the MIT-licensed distribution. The repository remains private until its owner separately authorizes publication.

To rebuild from the repository root:

```bash
python scripts/build_plugin.py --output outputs/plugins
python scripts/build_codex_plugin.py --output outputs/plugins
```

The included build receipts record each archive's file count, byte size and SHA-256. Rebuilding the same source produces the same bytes. A package rebuild does not add a new model evaluation or GUI installation result.

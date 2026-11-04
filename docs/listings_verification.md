# TOMC directory listings and verification

Checked on **2026-11-04**. The official MCP Registry and the eight third-party
directories below each have a dedicated TOMC entry. These records establish
discoverability in those directories. They do not measure TOMC adoption, search
engine indexing, installations or active users, and do not imply endorsement.

## Verified entries

| Directory | TOMC entry | What was verified |
| --- | --- | --- |
| Official MCP Registry | [Registry record](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.ZipengWu365%2Ftomc-memory/versions/latest) | Active `io.github.ZipengWu365/tomc-memory` entry; latest registry version v0.1.1, published 2026-10-15. |
| MCPRush | [TOMC Memory MCP](https://mcprush.com/zipengwu365/tomc-memory-mcp) | Dedicated v0.1.1 entry collected from the public index; marked unclaimed and not scanned. |
| MCP Harbor | [TOMC](https://www.mcpharbor.app/tools/zipengwu365-tomc/) | Dedicated entry identifying ZipengWu365 and the TOMC repository. |
| ProtocolProbe | [TOMC Memory record](https://protocolprobe.com/mcp/servers/io.github.ZipengWu365/tomc-memory) | Dated 2026-10-23 record for v0.1.1; scope described below. |
| SpaceRing Harness | [TOMC Memory](https://spacering.net/harness/zipengwu365/tomc-memory) | Registry-sourced v0.1.1 entry; marked unclaimed and not reviewed by a person. [Public record](https://spacering.net/api/harness/v1/items/zipengwu365/tomc-memory). |
| Odel | [TOMC Memory module](https://odel.app/modules/zipengwu365/tomc-memory) | Dedicated external MCP module record for v0.1.1, with an older README snapshot. |
| SkillsLLM | [TOMC skill and scan record](https://skillsllm.com/skill/tomc) | Dedicated entry and dated 2026-10-22 automated scan; scope described below. |
| AugmentClaude | [TOMC Memory](https://augmentclaude.com/s/tomc-memory-zipengwu365) | Dedicated skill entry identifying the author and TOMC repository. |
| mcpservers.org | [TOMC Memory directory entry](https://mcpservers.org/servers/github-com-zipengwu365-tomc-blob-67a170ae051e7b132765389f176f3999103375a6-docs-submissions-mcpmarketsenglish-md) | Live Memory-category entry sourced from a fixed-commit TOMC submission document; no public approval status was established. |

The v0.1.1 registry package and its five-tool inventory are older than the current
GitHub preview. Use the current [installation guide](assistant_plugin.md) for
installation; a directory snapshot does not establish current compatibility.

## Scope of the third-party checks

**ProtocolProbe:** its October 23 record reports 5/5 applicable public-record
checks met: active registry entry, accessible source repository, repository not
archived, recent code and a SECURITY.md file. Separately, its read-only runtime
record reports starting the published package and inspecting its inventory: five
tools, zero resources and zero prompts, without calling tools. These are dated
record and inventory results, not a certification of tool behavior or the safety
of the current release.

**SkillsLLM:** its October 22 automated record reports `PASSED`, no reported
issues, and npm-audit and prompt-injection checks run. It explicitly records
`pipAuditRan: false`. The result is not a Python dependency audit or a complete
security assessment of the current release.

## Promotional measurements

Directory-wide server, skill and creator totals are excluded from TOMC's News:
they describe the directory's catalog, not TOMC usage, and can change independently
of this project. Directory inclusion is also separate from Google or Bing indexing.

TikTok view and like totals are omitted because attributable, dated post-level
records were not available to substantiate the proposed aggregate. This does not
establish zero engagement. A future measurement should link the relevant posts,
define which posts are included, and state the snapshot date and whether counts
are lifetime totals or activity during a date range.

## Comparison figure

The [context engineering city figure](context_city.md) was checked against its
published source records: 3,600 planned paired judgments, 3,596 valid and four
invalid, covering 200 question IDs, ten sessions and three readers. The seven
plotted means match the source data. The 18/18 result counts reader-by-baseline
cells with a higher TOMC mean, rather than per-question wins or a significance
test. The 41.99% figure is a reduction in recorded reader input relative to LIGHT
under that protocol, not a billing reduction. The separate 31-entry directory is
unranked; the software's MIT license does not cover API or infrastructure charges.

## 中文说明

2026 年 11 月 4 日逐项核对：官方 MCP Registry 和上表 8 个第三方目录均有 TOMC
专属条目。部分目录自动导入、尚未人工审核，部分仍对应 v0.1.1。收录只说明目录中
存在条目，不代表平台背书、搜索引擎收录、安装量或活跃用户数。

ProtocolProbe 的 5/5 指当时的适用公开记录检查；另一项只读运行记录读取了五个工具的
清单，未调用工具。SkillsLLM 的扫描未执行
`pip-audit`。没有可核验的逐帖历史记录支持 TikTok 宣传合计，因此暂不展示数字，
也不将缺少记录解释为零播放。图表的均分、配对数量和 41.99% 输入减少已复算一致，
结论范围保持为原文所述的实验协议。

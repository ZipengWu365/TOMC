# Documented model context limits — 2026-10-12

These are public provider specifications, not live account tests or native-agent compaction triggers. 1M means one million tokens; 10M means ten million. No universal 1M or 10M default is assumed. Exact API/deployment IDs matter; older snapshots, previews and account plans can differ.

| Provider | Model ID / family | Documented window or input limit | Official source |
|---|---|---:|---|
| OpenAI | gpt-6.1-sol / gpt-6-astra / gpt-6-luna | 1,050,000 | [Comparison](https://developers.openai.com/api/docs/models/compare) |
| OpenAI | gpt-5.1 (deprecated) / gpt-4o | 400,000 / 128,000 | [5.1](https://developers.openai.com/api/docs/models/gpt-5.1), [4o](https://developers.openai.com/api/docs/models/gpt-4o) |
| Anthropic | claude-opus-5-5 / sonnet-5-5 / haiku-5-5 | 1M | [Model comparison](https://platform.claude.com/docs/en/models/opus-5-5/overview) |
| Google | gemini-3.8-flash / gemini-3.1-pro-preview | 1,048,576 input | [Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [Pro Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) |
| xAI | grok-4.7 | 500,000 | [Developer guide](https://docs.x.ai/developers/grok-4-7) |
| DeepSeek | deepseek-flash / deepseek-v4-pro | 1,048,576 | [Model metadata](https://api-docs.deepseek.com/api/list-models/) |
| Z.AI | glm-5.2 / glm-5.3 | 1M | [5.2](https://docs.z.ai/guides/llm/glm-5.2), [5.3](https://docs.z.ai/guides/llm/glm-5.3) |
| Kimi Platform | kimi-k3 | 1M | [Quickstart](https://platform.kimi.com/docs/guide/kimi-k3-quickstart) |
| Kimi Code | k3 | 262,144 or 1,048,576 by plan | [Code model settings](https://www.kimi.com/code/docs/en/kimi-code/models) |
| MiniMax | MiniMax-M3 / MiniMax-M2.7 | 1,000,000 / 204,800 | [API table](https://platform.minimax.io/docs/api-reference/text-anthropic-api) |
| Qwen | qwen3.8-max | 1,000,000 | [Model-specific table](https://help.aliyun.com/zh/model-studio/qwen3-8-max) |
| Doubao | seed-2-1-pro/lite-260915; earlier pro-260628 | 1024k; earlier 256k | [API model list](https://docs.volcengine.com/docs/ark/model-list?lang=zh) |
| Hunyuan TokenHub | hy3 / hy4-preview | 256k / 1M | [Model list](https://cloud.tencent.com/document/product/1823/130051) |
| Baidu Qianfan | ernie-5.1 / ernie-5.0 | 128k | [API model list](https://intl.cloud.baidu.com/en/doc/qianfan/s/7m95lyy43-intl-en) |

Gemini separates maximum input and output; most other rows describe a context window. The application must reserve instructions, tools and generation space according to the provider's semantics. Marketing K/M labels are retained in the evidence; the registry's lower decimal conversions are explicitly marked as conservative, not exact official integers. Kimi Code defaults to the smaller verified plan capacity unless a confirmed deployment override is supplied.

Google's reported [10M research demonstrations](https://blog.google/innovation-and-ai/products/long-context-window-ai-models/) are not a current universal API allowance. The model maximum also does not prove that a Code Agent has not already compacted: its configured window or trigger can be smaller.

[Machine-readable snapshot](https://github.com/ZipengWu365/TOMC/blob/main/src/tomc/data/model_contexts_20261012.json) · [Request policy / 中文](context_ownership_zh.md)

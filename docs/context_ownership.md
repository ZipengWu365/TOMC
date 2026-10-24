# API request optimization and native compaction

[中文](context_ownership_zh.md) · [Model limits](model_context_limits_20261012.md) · [API guide](api_reference.md)

Use **logical model API requests**, not user dialogue turns, as the clock. An agent can make several model requests while handling one user message. `AutomaticChatSession` provides opt-in preprocessing for a caller-controlled synchronous Chat Completions loop; installing an MCP plugin does not intercept those requests.

## Simple request policy

- Cache the documented model profile locally; look it up again only when the request's model ID changes. No repeated provider lookup or extra model judgment is made.
- Keep provider prompt caches warm. By default (`refresh_policy="stable"`) the compiled old-history memory is frozen: later requests reuse the identical text even when the task changes, and new messages stay raw after it, so consecutive requests share the same prefix. It is rebuilt only when the request would no longer fit, the source history is edited, or the explicit budget changes; set `stable_growth_tokens` to also rebuild after that much new history. Each rebuild is one full cache miss.
- `refresh_policy="cadence"` keeps the earlier behaviour (`refresh_every=2` or `1`). It rebuilds the memory almost every request in ordinary chats, because the task is the latest user message, and therefore defeats prefix caching: in [our measurement](prompt_cache_20261017.md) it cost several times more than sending the full history with caching. Use it only for providers without prompt caching.
- Back off once when a context-size hint crosses 50% or 90% of the effective window. For a 1M window these are approximately 500K and 900K. These are TOMC heuristics, not claims about a host's native trigger. Prefer caller-supplied or already available provider usage; the initial string-length fallback is coarse, especially for non-English or multimodal data.
- When a trusted integration reports native compaction in progress, pass through. After a completed event, skip one or two logical requests (default two), then resume. An ordinary eligible native summary may subsequently be optimized; it has no permanent special exclusion.

Model context capacity is not the same as the host's compaction threshold. Account, deployment and configured agent windows can be smaller. Unknown models have no assumed 1M/10M capacity; supply a confirmed `deployment_context_limit` or keep the request unchanged.

## Use your existing SDK and model

```python
from tomc import AutomaticChatSession

session = AutomaticChatSession(native_cooldown_requests=2)  # stable, cache-friendly prefix

# Reuse one session per conversation; pass the caller's original messages.
response = session.create(
    client,
    model="deepseek-flash",
    messages=messages,
    task="What should the agent do next?",
    max_tokens=8192,
    stream=True,
)
```

The same client, credentials, model, tools and request options are forwarded. The raw response or stream is returned unchanged, without extra model calls or consuming the stream. The wrapper changes only `messages`. Preserve the original history in your application; do not feed an earlier TOMC request view back as the original.

Old history gets the existing default memory budget (about 80% of its lexical estimate, at least 1,024), constrained by the model/deployment budget after protected contents and reservations. System/developer instructions, the latest user task, recent messages and pending tool protocol remain unchanged. Complete earlier tool groups are treated together. Unsupported/multimodal/opaque reasoning histories and nonshrinking output pass through. Lexical and string-length estimates are not provider billing counts or a guarantee that every request fits.

Specify the desired output limit in the normal SDK request. If it is omitted, `output_reserve` is a planning hint (8,192 by default), not a change to the provider's actual output limit; provider defaults can be larger, such as Kimi K3's documented 131,072. The wrapper does not silently rewrite output settings.

## Native events and client scope

`session.on_native_event("codex", event)` recognizes real app-server `contextCompaction` item start/completion notifications. `session.on_native_event("claude", event)` recognizes `PreCompact`/`PostCompact` hook payloads. A trusted outer integration must route the correct conversation's events. Supported/enabled flags and token-usage updates alone are not compaction events. There is no continuous log polling.

This release does not install those listeners, reconfigure Claude Code/Codex/WorkBuddy, or proxy their built-in models. MCP continues to provide explicit external-history preparation and optional notebooks. Its assistant policy leaves the active chat with the host; it is not the request interceptor described above.

The initial SDK wrapper supports synchronous, text Chat Completions requests. Anthropic Messages and OpenAI Responses require their own transport adapters; signed/opaque native compaction items must not be flattened into text. GPT-6.1 Sol tool calling specifically requires Responses according to [its model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

## CPU scope

Decision gating uses counters and cached metadata, with no separate LLM or neural service. The default lexical packing implementation now counts each row once instead of rescanning the growing packed prefix. In one local synthetic state/log fixture, 20K history tokens took 0.026 seconds and 100K took 0.293 seconds for compilation at an 80% memory budget. The earlier implementation took about 1.58 seconds at 20K and 38–47 seconds at 100K. Short randomized counter comparisons and the full 20K fixture preserved text, records and estimates. These are CPU/compiler timings, not real provider latency, billing or answer-quality measurements; they do not establish performance for every history, tokenizer or a 1M input.

[Claude compact hooks](https://code.claude.com/docs/en/hooks) · [Codex app-server](https://learn.chatgpt.com/docs/app-server)

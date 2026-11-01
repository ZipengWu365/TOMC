# Cost-aware gateway compaction

[中文](compaction_policy_zh.md) · [Context ownership](context_ownership.md) · [Prompt cache](prompt_cache_20261017.md)

The request gateway rewrites a request only when doing so is expected to cost less than sending it unchanged. This is the default `policy="dynamic"` for the Claude, Codex and OpenAI-compatible Chat Completions (`openai`) routes. `policy="legacy"` keeps the earlier behaviour: the gateway compiles whenever the size options allow.

## Why compilation can lose money

Providers bill a repeated request prefix at a cached rate. For Claude Sonnet 5.5, the catalog gives these rates per million tokens:

| Rate | Price |
|---|---:|
| Input | $2 |
| Cached read | $0.10 |
| 1-hour cache write | $4 |

So a cache write costs 40 times a cached read.

A rewrite changes the request from its first edited message onward. Everything after that point is written to the cache again. The history it removed would otherwise have been read at $0.10/M on every later request.

In a 50-task SWE-bench Verified run with Claude Code, the earlier in-turn setting lost money on every task where it fired:

- 29 rebuilds cost an extra $0.73.
- The 152 replays that followed saved $0.105 in total.

Each rebuild needed about 36 later requests to pay back, but a short task had about 5 left. Recompiling from the same anchor after every 6K tokens of growth made each rebuild larger than the last.

## Decision

Each candidate rewrite is weighed against the unchanged request. The calculation is in [`compaction_policy.decide`](https://github.com/ZipengWu365/TOMC/blob/main/src/tomc/compaction_policy.py):

```
immediate = cost(rewrite now) - cost(unchanged now)        # cache writes vs reads
future    = cached_rate * removed * (1 - risk) * expected_remaining_requests
refetch   = risk * removed * write_rate
compile when future - immediate - refetch > margin * (max(immediate, 0) + refetch)
```

The inputs are estimated as follows:

- **Rates:** taken from the bundled or synced price catalog for the request's model. The 1-hour write rate applies when the host marks a block `ttl: "1h"`. Unknown models fall back to conservative defaults.
- **Cache warmth:** the cache counts as warm when the session's previous request was within 90% of the cache lifetime and its large prompt was actually served from cache. A cold cache (first request, expired lifetime, provider without caching) bills the whole request anyway, so shrinking it is an immediate gain.
- **Expected remaining requests:** the median further length of this host's earlier sessions that reached the same length. Until there are 8 such sessions, the gateway uses half the requests made so far.
- **Risk:** the share of compiled-away tool calls that the agent later repeated, starting from a 1-in-10 prior. A file read counts as a repeat regardless of its line range.
- **Window pressure:** a request at 80% or more of the documented model window is compiled regardless. This is cheaper than a host's model-written summary.

## Rewrite shape

Both routes keep the rewritten prefix in the gateway's local store and replay it byte for byte across tool steps and user turns, so the provider cache keeps hitting.

**First compilation.** The first tool result is kept raw: a Claude `tool_result` message, or a Codex string `function_call_output`. For a chat without tools, the first user message is kept raw instead. Everything after it up to the recent tail is compiled, and the memory is appended to that kept message.

**Later compilations.** A later compilation covers only the messages after the frozen prefix. Its memory is appended to the frozen prefix's last carrier, and earlier memory stays unchanged. The cache therefore still hits everything up to that carrier.

**Host notes.** Per-step system notes from the host, such as working-directory updates or progress nudges, are compiled as labelled host data. A directive-only control (empty content with `output_config`) is kept. Any other system message ends the segment before it. Every remaining system message still precedes an assistant message.

**Codex.** Reasoning items are dropped together with the call group they precede. Calls, including parallel calls, are never separated from their outputs. Instructions, host context, settings and compaction state end the segment.

**Chat Completions (`openai` route).** Any OpenAI-compatible `/chat/completions` upstream. The client names its conversation with an `x-tomc-session-id` header, which is never forwarded; without it requests pass through. Assistant `tool_calls` stay with all of their `tool` results, and memory is appended to a tool result.

**What stays raw.** The latest user prompt and the recent tail are always sent unchanged.

## Configuration

These keys go in the gateway config (`compression`, or per route):

| Key | Default | Meaning |
|---|---|---|
| `policy` | `dynamic` | `dynamic` or `legacy` |
| `margin` | `0.5` | Required net saving relative to the cost at risk |
| `window_pressure` | `0.8` | Window fraction that forces compilation |
| `remaining_prior` | `0.5` | Remaining requests per request so far, before history exists |
| `turn_memory_ratio` | `0.35` | Memory budget as a share of the compiled segment |
| `recent_messages`, `min_history_tokens`, `memory_budget` | as before | Tail size, minimum segment, fixed budget |

`turn_trigger_tokens` and `turn_regrow_tokens` apply only to `legacy`.

Activity records hold the decision's numbers without content:

- `policy`: one of `profitable`, `cold_cache`, `window_pressure` or `unprofitable`;
- `policy_gain` and `policy_cost`, in input-price tokens;
- `policy_remaining`;
- `policy_warm`.

The gateway also writes each response's reported usage back to the session counters, which keeps the warmth and token-ratio estimates current.

## Evidence and limits

Replaying the decision on the recorded per-request sizes of the 50-task run is an offline estimate:

- 113 requests had at least 4K compilable tokens.
- The dynamic policy compiled none of them.

With 1-hour caching at Anthropic prices, warm compilation pays only in long sessions that will keep running. It also pays when the cache is cold, for example when a session resumes after the cache lifetime, and near the model window.

The remaining-request estimate is a heuristic. The 4-breakpoint, 20-block cache lookback is approximated by the kept-prefix estimate rather than modelled exactly. Quality effects of compiled history still need live measurement.
